"""Autoevaluación del paciente por enlace (sin entrar a la app).

El profesional genera un enlace para un paciente; el paciente lo abre en su
celular (https://vocalis-lab.vercel.app/?autoeval=<token>), completa solo lo
de autovaloración y los puntajes quedan volcados en su ficha:

- Autopercepción de la voz (0–10) y un comentario libre.
- VHI-10 oficial: V1–V10, 0–4 cada uno (total 0–40).
- Cuestionario de Riesgo Vocal 2026: 69 ítems A1–A32, B1–B7, C1–C12,
  D1–D7, E1–E11, 0–3 cada uno (total 0–207).

En la app (Riesgo & Escalas) se ven las respuestas marcadas como
"completado por el paciente" y se cargan en el formulario para guardarlas
junto con lo que evalúa el profesional (GRBAS, RASATI, TME…).

Rutas:
- POST /api/autoevaluaciones                (sesión) crea el enlace
- GET  /api/autoevaluaciones?paciente_id=   (sesión) lista con resultados
- GET  /api/autoevaluacion/{token}          (público) datos mínimos para el formulario
- POST /api/autoevaluacion/{token}          (público) respuestas del paciente
"""
import os
import secrets
import traceback
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

VIGENCIA_DIAS = 14
INSTRUMENTOS = ("autopercepcion", "vhi10", "riesgo")
VHI10_ITEMS = [f"V{i}" for i in range(1, 11)]
RIESGO_ITEMS = ([f"A{i}" for i in range(1, 33)] + [f"B{i}" for i in range(1, 8)] +
                [f"C{i}" for i in range(1, 13)] + [f"D{i}" for i in range(1, 8)] +
                [f"E{i}" for i in range(1, 12)])
MSG_MIGRACION = ("Falta correr la migración supabase/migracion_2026_11_autoevaluacion.sql en "
                 "Supabase (SQL Editor).")


def _sb():
    from api_clinica import supabase
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    return supabase


def _ahora():
    return datetime.now(timezone.utc)


def grupo_riesgo(total: int) -> str:
    return ("Grupo 1 (Bajo Riesgo)" if total <= 69 else
            "Grupo 2 (Riesgo Moderado)" if total <= 138 else "Grupo 3 (Alto Riesgo)")


def _items(respuestas: dict, claves: list, maximo: int, nombre: str) -> dict:
    """Valida que estén todos los ítems y en rango."""
    datos = respuestas or {}
    faltan = [k for k in claves if k not in datos]
    if faltan:
        raise HTTPException(status_code=400, detail=f"Faltan respuestas de {nombre}: {', '.join(faltan[:5])}…")
    limpio = {}
    for k in claves:
        try:
            v = int(datos[k])
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail=f"Respuesta inválida en {nombre} ({k})")
        if not 0 <= v <= maximo:
            raise HTTPException(status_code=400, detail=f"Respuesta fuera de rango en {nombre} ({k})")
        limpio[k] = v
    return limpio


def puntuar(instrumentos: list, cuerpo: dict) -> dict:
    """Respuestas validadas y puntajes de los instrumentos pedidos."""
    out = {"respuestas": {}}
    if "vhi10" in instrumentos:
        v = _items(cuerpo.get("vhi10"), VHI10_ITEMS, 4, "VHI-10")
        out["respuestas"]["VHI10"] = v
        out["vhi10_score"] = sum(v.values())
    if "riesgo" in instrumentos:
        r = _items(cuerpo.get("riesgo"), RIESGO_ITEMS, 3, "Riesgo vocal")
        out["respuestas"]["RiesgoVocal"] = r
        out["riesgo_vocal_score"] = sum(r.values())
        out["riesgo_grupo"] = grupo_riesgo(out["riesgo_vocal_score"])
    if "autopercepcion" in instrumentos:
        try:
            ap = int(cuerpo.get("autopercepcion"))
        except (TypeError, ValueError):
            raise HTTPException(status_code=400, detail="Falta la autopercepción (0 a 10)")
        if not 0 <= ap <= 10:
            raise HTTPException(status_code=400, detail="La autopercepción va de 0 a 10")
        out["autopercepcion"] = ap
    out["comentario"] = str(cuerpo.get("comentario") or "")[:1000]
    return out


def _fila_token(sb, token: str) -> dict:
    try:
        filas = sb.table("autoevaluaciones").select("*").eq("token", token).execute().data or []
    except Exception as e:
        if "autoevaluaciones" in str(e):
            raise HTTPException(status_code=503, detail=MSG_MIGRACION)
        raise
    if not filas:
        raise HTTPException(status_code=404, detail="El enlace no existe. Pedile uno nuevo a tu fonoaudiólogo.")
    return filas[0]


def _vencido(fila: dict) -> bool:
    try:
        return datetime.fromisoformat(str(fila["vence_at"]).replace("Z", "+00:00")) < _ahora()
    except Exception:
        return False


def _paciente(sb, pid: str) -> dict:
    """Fila del paciente (con origen y tipo de atención si existen)."""
    filas = sb.table("pacientes").select("*").eq("id", pid).execute().data or []
    return filas[0] if filas else {}


def _saludo(fila_auto: dict, paciente: dict) -> str:
    """Nombre con el que se saluda: el que eligió el profesional al crear el
    enlace (guardado en respuestas.saludo) o el nombre de pila deducido."""
    from nombres import saludo_de_paciente
    return str((fila_auto.get("respuestas") or {}).get("saludo") or "").strip() or saludo_de_paciente(paciente)


@router.post("/api/autoevaluaciones")
async def crear(request: Request):
    body = await request.json()
    pid = str(body.get("paciente_id") or "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="Elegí un paciente.")
    instrumentos = [i for i in (body.get("instrumentos") or INSTRUMENTOS) if i in INSTRUMENTOS]
    if not instrumentos:
        raise HTTPException(status_code=400, detail="Elegí al menos un cuestionario.")
    sb = _sb()
    pac = _paciente(sb, pid)
    if not pac:
        raise HTTPException(status_code=404, detail="Paciente inexistente")
    from nombres import saludo_de_paciente
    saludo = str(body.get("saludo") or "").strip()[:60] or saludo_de_paciente(pac)
    token = secrets.token_urlsafe(18)
    # El saludo elegido viaja en respuestas.saludo (se conserva al responder).
    fila = {"token": token, "paciente_id": pid, "estado": "pendiente", "instrumentos": instrumentos,
            "respuestas": {"saludo": saludo},
            "vence_at": (_ahora() + timedelta(days=VIGENCIA_DIAS)).isoformat()}
    try:
        guardada = (sb.table("autoevaluaciones").insert(fila).execute().data or [fila])[0]
    except Exception as e:
        if "autoevaluaciones" in str(e):
            raise HTTPException(status_code=503, detail=MSG_MIGRACION)
        raise
    frontend = os.environ.get("FRONTEND_URL", "https://vocalis-lab.vercel.app").rstrip("/")
    return {"ok": True, "id": guardada.get("id"), "token": token, "enlace": f"{frontend}/?autoeval={token}",
            "vence_at": fila["vence_at"], "instrumentos": instrumentos,
            "nombre": saludo, "telefono": pac.get("telefono") or ""}


@router.patch("/api/autoevaluaciones/{autoeval_id}")
async def cambiar_saludo(autoeval_id: str, request: Request):
    """Corrige el nombre con el que se saluda al paciente (enlace pendiente)."""
    body = await request.json()
    saludo = str(body.get("saludo") or "").strip()[:60]
    if not saludo:
        raise HTTPException(status_code=400, detail="Escribí el nombre para saludar.")
    sb = _sb()
    filas = sb.table("autoevaluaciones").select("*").eq("id", autoeval_id).execute().data or []
    if not filas:
        raise HTTPException(status_code=404, detail="Autoevaluación inexistente")
    if filas[0].get("estado") == "completada":
        raise HTTPException(status_code=409, detail="Ya fue completada.")
    respuestas = dict(filas[0].get("respuestas") or {}, saludo=saludo)
    sb.table("autoevaluaciones").update({"respuestas": respuestas}).eq("id", autoeval_id).execute()
    return {"ok": True, "saludo": saludo}


@router.get("/api/autoevaluaciones")
async def listar(paciente_id: str):
    sb = _sb()
    try:
        filas = (sb.table("autoevaluaciones").select("*").eq("paciente_id", paciente_id)
                 .order("creada_at", desc=True).limit(20).execute().data or [])
    except Exception as e:
        if "autoevaluaciones" in str(e):
            return {"autoevaluaciones": [], "aviso": MSG_MIGRACION}
        raise
    for f in filas:
        f.pop("token", None) if f.get("estado") == "completada" else None
    return {"autoevaluaciones": filas}


@router.get("/api/autoevaluacion/{token}")
async def ver(token: str):
    sb = _sb()
    fila = _fila_token(sb, token)
    try:
        nombre = _saludo(fila, _paciente(sb, fila["paciente_id"]))
    except Exception:
        nombre = ""
    return {"ok": True, "nombre": nombre, "instrumentos": fila.get("instrumentos") or list(INSTRUMENTOS),
            "estado": "vencida" if fila.get("estado") == "pendiente" and _vencido(fila) else fila.get("estado"),
            "profesional": "Matías Pérez · Fonoaudiólogo"}


@router.post("/api/autoevaluacion/{token}")
async def responder(token: str, request: Request):
    sb = _sb()
    fila = _fila_token(sb, token)
    if fila.get("estado") == "completada":
        raise HTTPException(status_code=409, detail="Este cuestionario ya fue enviado. ¡Gracias!")
    if _vencido(fila):
        raise HTTPException(status_code=410, detail="El enlace venció. Pedile uno nuevo a tu fonoaudiólogo.")
    cuerpo = await request.json()
    resultado = puntuar(fila.get("instrumentos") or list(INSTRUMENTOS), cuerpo)
    respuestas = dict(resultado["respuestas"])
    if (fila.get("respuestas") or {}).get("saludo"):
        respuestas["saludo"] = fila["respuestas"]["saludo"]
    cambios = {"estado": "completada", "completada_at": _ahora().isoformat(),
               "respuestas": respuestas, "comentario": resultado["comentario"],
               "vhi10_score": resultado.get("vhi10_score"),
               "riesgo_vocal_score": resultado.get("riesgo_vocal_score"),
               "autopercepcion": resultado.get("autopercepcion")}
    sb.table("autoevaluaciones").update(cambios).eq("id", fila["id"]).execute()
    _avisar(sb, fila["paciente_id"], resultado)
    return {"ok": True}


def _avisar(sb, paciente_id: str, r: dict) -> None:
    """El asistente de Telegram avisa que el paciente completó la autoevaluación."""
    try:
        from asistente import avisar
        p = sb.table("pacientes").select("nombre_completo").eq("id", paciente_id).execute().data or []
        nombre = (p[0].get("nombre_completo") if p else "") or "Un paciente"
        partes = []
        if r.get("autopercepcion") is not None:
            partes.append(f"autopercepción {r['autopercepcion']}/10")
        if r.get("vhi10_score") is not None:
            partes.append(f"VHI-10 {r['vhi10_score']}/40")
        if r.get("riesgo_vocal_score") is not None:
            partes.append(f"riesgo vocal {r['riesgo_vocal_score']}/207 ({r['riesgo_grupo']})")
        texto = f"{nombre} completó su autoevaluación: {', '.join(partes)}."
        if r.get("comentario"):
            texto += f"\nComentario: «{r['comentario'][:300]}»"
        texto += "\nYa está en Riesgo & Escalas para revisarla."
        avisar(texto)
    except Exception:
        traceback.print_exc()
