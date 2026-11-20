"""Sala virtual: la voz del paciente o alumno en vivo durante Meet/Zoom.

Problema: en Meet/Zoom el audio llega procesado (cancelación de ruido,
compresión) y no hay forma de ver la voz del paciente. Solución:

1. El profesional crea una sala (POST /api/salas) y le pasa al paciente un
   enlace: https://vocalis-lab.vercel.app/?sala=<token> (sin cuenta).
2. En el equipo del paciente se mide la voz con su propio micrófono, sin
   filtros, y se envían por WebSocket las muestras (F0, intensidad) ~10 por
   segundo.
3. El profesional ve en vivo la curva, la nota y la intensidad; puede fijar
   una nota objetivo y enviarle consignas, que el paciente ve en su pantalla.

Las salas viven en memoria (4 horas); no se guarda audio. El profesional
puede guardar la medición en la historia del paciente al terminar
(reusa /api/companion/pitchmeter).

Rutas:
- POST /api/salas                         (sesión) crea la sala
- GET  /api/sala/{token}/info             (público) datos mínimos para el paciente
- WS   /ws/sala/{token}/paciente          (token de la sala)
- WS   /ws/sala/{token}/profesional?sesion=<token de sesión>
"""
import asyncio
import os
import secrets
import time
from collections import deque

from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect

router = APIRouter()

DURACION_S = 4 * 3600
MAX_SALAS = 50
MODOS = {"habla": "Habla (F0 conversacional)", "nota": "Nota sostenida / afinación",
         "canto": "Canto (rango amplio)", "tmf": "Tiempo máximo de fonación"}


class Sala:
    def __init__(self, token, paciente_id, nombre, profesional, modo):
        self.token, self.paciente_id, self.nombre = token, paciente_id, nombre
        self.profesional, self.modo = profesional, modo
        self.creada = time.time()
        self.vence = self.creada + DURACION_S
        self.objetivo = None          # {"hz": 220.0, "nota": "La3", "tolerancia_cents": 50}
        self.consigna = ""
        self.pacientes: set = set()
        self.profesionales: set = set()
        self.muestras = deque(maxlen=12000)  # ~20 min a 10/s, por si el profesional se reconecta

    def info_publica(self) -> dict:
        return {"ok": True, "nombre": self.nombre, "modo": self.modo, "modo_texto": MODOS.get(self.modo, ""),
                "objetivo": self.objetivo, "consigna": self.consigna, "vence": int(self.vence),
                "profesional": "Matías Pérez · Fonoaudiólogo"}


SALAS: dict = {}


def _limpiar():
    ahora = time.time()
    for t in [t for t, s in SALAS.items() if s.vence < ahora]:
        SALAS.pop(t, None)


def _sala(token: str) -> Sala:
    _limpiar()
    sala = SALAS.get(token)
    if not sala:
        raise HTTPException(status_code=404, detail="La sala no existe o venció. Pedile un enlace nuevo a tu fonoaudiólogo.")
    return sala


async def _enviar_a(conexiones: set, mensaje: dict):
    for ws in list(conexiones):
        try:
            await ws.send_json(mensaje)
        except Exception:
            conexiones.discard(ws)


@router.post("/api/salas")
async def crear_sala(request: Request):
    usuario = getattr(request.state, "usuario", None) or {}
    body = await request.json()
    modo = body.get("modo") if body.get("modo") in MODOS else "habla"
    pid = str(body.get("paciente_id") or "").strip() or None
    from nombres import nombre_para_saludo, saludo_de_paciente
    nombre = ""
    if pid:
        try:
            from api_clinica import supabase
            filas = supabase.table("pacientes").select("*").eq("id", pid).execute().data or []
            nombre = saludo_de_paciente(filas[0]) if filas else ""
        except Exception:
            nombre = ""
    if not nombre:
        nombre = nombre_para_saludo(str(body.get("nombre") or "").strip())
    _limpiar()
    if len(SALAS) >= MAX_SALAS:
        raise HTTPException(status_code=429, detail="Demasiadas salas abiertas; cerrá alguna.")
    token = secrets.token_urlsafe(16)
    sala = Sala(token, pid, nombre, str(usuario.get("sub") or ""), modo)
    SALAS[token] = sala
    frontend = os.environ.get("FRONTEND_URL", "https://vocalis-lab.vercel.app").rstrip("/")
    return {"ok": True, "token": token, "enlace": f"{frontend}/?sala={token}", "vence": int(sala.vence),
            "modo": modo, "paciente_id": pid, "nombre": sala.nombre}


@router.get("/api/sala/{token}/info")
async def info_sala(token: str):
    return _sala(token).info_publica()


@router.websocket("/ws/sala/{token}/paciente")
async def ws_paciente(ws: WebSocket, token: str):
    _limpiar()
    sala = SALAS.get(token)
    await ws.accept()
    if not sala:
        await ws.send_json({"tipo": "error", "texto": "La sala no existe o venció."})
        await ws.close(code=4404)
        return
    sala.pacientes.add(ws)
    await ws.send_json({"tipo": "config", **sala.info_publica()})
    await _enviar_a(sala.profesionales, {"tipo": "estado", "paciente_conectado": True})
    try:
        while True:
            msg = await ws.receive_json()
            if msg.get("tipo") == "muestras":
                datos = [m for m in (msg.get("datos") or [])[:50] if isinstance(m, dict)]
                sala.muestras.extend(datos)
                await _enviar_a(sala.profesionales, {"tipo": "muestras", "datos": datos})
            elif msg.get("tipo") == "ping":
                await ws.send_json({"tipo": "pong"})
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        sala.pacientes.discard(ws)
        await _enviar_a(sala.profesionales, {"tipo": "estado", "paciente_conectado": bool(sala.pacientes)})


@router.websocket("/ws/sala/{token}/profesional")
async def ws_profesional(ws: WebSocket, token: str):
    from sesion_web import verificar_token
    await ws.accept()
    if not verificar_token(ws.query_params.get("sesion", "")):
        await ws.send_json({"tipo": "error", "texto": "Sesión inválida: volvé a iniciar sesión."})
        await ws.close(code=4401)
        return
    _limpiar()
    sala = SALAS.get(token)
    if not sala:
        await ws.send_json({"tipo": "error", "texto": "La sala no existe o venció."})
        await ws.close(code=4404)
        return
    sala.profesionales.add(ws)
    await ws.send_json({"tipo": "estado", "paciente_conectado": bool(sala.pacientes),
                        "objetivo": sala.objetivo, "modo": sala.modo,
                        "historial": list(sala.muestras)[-600:]})
    try:
        while True:
            msg = await ws.receive_json()
            tipo = msg.get("tipo")
            if tipo == "objetivo":
                sala.objetivo = msg.get("objetivo") or None
                await _enviar_a(sala.pacientes, {"tipo": "objetivo", "objetivo": sala.objetivo})
            elif tipo == "consigna":
                sala.consigna = str(msg.get("texto") or "")[:300]
                await _enviar_a(sala.pacientes, {"tipo": "consigna", "texto": sala.consigna})
            elif tipo == "modo" and msg.get("modo") in MODOS:
                sala.modo = msg["modo"]
                await _enviar_a(sala.pacientes, {"tipo": "modo", "modo": sala.modo,
                                                 "modo_texto": MODOS[sala.modo]})
            elif tipo == "cerrar":
                await _enviar_a(sala.pacientes, {"tipo": "cerrada"})
                SALAS.pop(token, None)
                break
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        sala.profesionales.discard(ws)


# ─── Salas abiertas y sesiones guardadas ───────────────────────────────

MSG_MIGRACION = ("Falta crear la tabla de la sala virtual: corré supabase/migracion_2026_11_sala.sql en "
                 "Supabase (SQL Editor → pegar → Run).")


@router.get("/api/salas")
async def salas_abiertas():
    """Salas abiertas (también las creadas desde Telegram), para retomarlas."""
    _limpiar()
    frontend = os.environ.get("FRONTEND_URL", "https://vocalis-lab.vercel.app").rstrip("/")
    return {"salas": [{"token": s.token, "enlace": f"{frontend}/?sala={s.token}", "nombre": s.nombre,
                       "paciente_id": s.paciente_id, "modo": s.modo, "creada": int(s.creada),
                       "vence": int(s.vence), "paciente_conectado": bool(s.pacientes)}
                      for s in sorted(SALAS.values(), key=lambda x: -x.creada)]}


def _n(v, lo, hi):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return round(f, 2) if lo <= f <= hi else None


def resultados_sala(r: dict) -> dict:
    """Valida los resultados que manda la pantalla de la sala."""
    return {"mediana_hz": _n(r.get("mediana_hz"), 50, 1500), "p5_hz": _n(r.get("p5_hz"), 50, 1500),
            "p95_hz": _n(r.get("p95_hz"), 50, 1500), "min_hz": _n(r.get("min_hz"), 50, 1500),
            "max_hz": _n(r.get("max_hz"), 50, 1500), "sd_st": _n(r.get("sd_st"), 0, 48),
            "en_objetivo_pct": _n(r.get("en_objetivo_pct"), 0, 100), "tmf_s": _n(r.get("tmf_s"), 0, 120),
            "n": int(_n(r.get("n"), 0, 10 ** 6) or 0)}


@router.post("/api/sala-sesiones")
async def guardar_sesion_sala(request: Request):
    """Guarda la medición de la sala con su modo. Solo el modo «habla» suma a
    la F0 conversacional (Companion); nota, canto y TMF quedan aparte."""
    body = await request.json()
    pid = str(body.get("paciente_id") or "").strip()
    modo = body.get("modo") if body.get("modo") in MODOS else None
    if not pid:
        raise HTTPException(status_code=400, detail="La sala no tiene paciente: elegilo antes de guardar.")
    if not modo:
        raise HTTPException(status_code=400, detail="Modo de sala inválido.")
    res = resultados_sala(body.get("resultados") or {})
    if res["mediana_hz"] is None and res["tmf_s"] is None:
        raise HTTPException(status_code=400, detail="No hay voz medida para guardar.")
    from api_clinica import supabase as sb
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    contorno = [v for v in (_n(x, 50, 1500) for x in (body.get("contorno") or [])[:600]) if v is not None]
    obj = body.get("objetivo") if isinstance(body.get("objetivo"), dict) else None
    fila = {"paciente_id": pid, "modo": modo, "duracion_s": _n(body.get("duracion_s"), 0, 4 * 3600),
            "objetivo": {"hz": _n(obj.get("hz"), 50, 1500), "nota": str(obj.get("nota") or "")[:8],
                         "tolerancia_cents": _n(obj.get("tolerancia_cents"), 0, 1200)} if obj else None,
            "consigna": str(body.get("consigna") or "")[:300], "resultados": res, "contorno": contorno,
            "notas": str(body.get("notas") or "")[:1000]}
    sid = None
    if modo == "habla" and res["mediana_hz"]:
        from companion import guardar_pitchmeter

        class _P:
            headers, query_params = request.headers, request.query_params
            state = request.state

            async def json(self_inner):
                return {"paciente_id": pid, "contexto": "sala_virtual", "duracion_s": fila["duracion_s"],
                        "f0": {"median": res["mediana_hz"], "p5": res["p5_hz"], "p95": res["p95_hz"],
                               "min": res["min_hz"], "max": res["max_hz"], "sd_st": res["sd_st"],
                               "mean": body.get("media_hz")}, "contorno": contorno}
        sid = (await guardar_pitchmeter(_P())).get("session_id")
        fila["companion_session_id"] = sid
    try:
        guardada = (sb.table("sala_sesiones").insert(fila).execute().data or [fila])[0]
    except Exception as e:
        if "sala_sesiones" in str(e):
            if sid:  # la F0 del habla igual quedó guardada
                return {"ok": True, "aviso": MSG_MIGRACION + " La F0 del habla SÍ se guardó."}
            raise HTTPException(status_code=503, detail=MSG_MIGRACION)
        raise
    return {"ok": True, "sesion": guardada}


@router.get("/api/sala-sesiones")
async def listar_sesiones_sala(paciente_id: str):
    from api_clinica import supabase as sb
    try:
        filas = (sb.table("sala_sesiones").select("id, creada_at, modo, duracion_s, objetivo, consigna, resultados, notas")
                 .eq("paciente_id", paciente_id).order("creada_at", desc=True).limit(50).execute().data or [])
    except Exception as e:
        if "sala_sesiones" in str(e):
            return {"sesiones": [], "aviso": MSG_MIGRACION}
        raise
    return {"sesiones": filas}
