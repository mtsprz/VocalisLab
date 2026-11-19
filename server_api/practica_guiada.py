"""Práctica guiada en casa (enlace por WhatsApp) y en vivo.

El profesional arma una rutina con ejercicios del cuadernillo que tienen
guía visual (sostenida, escalera, rampa/glissando o patrón propio). El
paciente abre https://vocalis-lab.vercel.app/?practica=<token>, da su
consentimiento y practica: una pelota sigue su voz. El tono se calcula en
su celular; a la app solo llegan NÚMEROS (porcentaje dentro del camino, F0,
estabilidad, ruido del ambiente). Nunca audio.

Rutas:
- GET  /api/practicas/sugerencias?paciente_id=  (sesión) ejercicios guiables + tono base
- POST /api/practicas                           (sesión) crea la rutina y el enlace
- GET  /api/practicas?paciente_id=              (sesión) rutinas y resultados
- PATCH /api/practicas/{id}                     (sesión) activar / desactivar
- GET  /api/practica/{token}                    (público) rutina para el paciente
- POST /api/practica/{token}/consentimiento     (público)
- POST /api/practica/{token}/sesion             (público) resultados (solo números)
"""
import math
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

MSG_MIGRACION = ("Falta correr la migración supabase/migracion_2026_11_practica.sql en "
                 "Supabase (SQL Editor).")
GUIAS = ("sostenida", "escalera", "rampa", "patron")
VERSION_CONSENTIMIENTO = "2026-11"

# Ejercicios del cuadernillo (exercise_bank.json) que se pueden guiar con la pelota.
GUIA_POR_EJERCICIO = {
    "tubo_agua": {"guia": "rampa", "amplitud": 7, "consigna": "Glissando con el tubo en el agua: subí y bajá suave, sin empujar."},
    "glissandos": {"guia": "rampa", "amplitud": 7, "consigna": "Sirena suave sobre /u/ o /m/: subí y bajá siguiendo la rampa."},
    "laxvox_agua": {"guia": "rampa", "amplitud": 5, "consigna": "Tubo en agua: burbujeo parejo mientras seguís la rampa."},
    "tubo_aire_libre": {"guia": "rampa", "amplitud": 5, "consigna": "Tubo en el aire: seguí la rampa con sonido continuo."},
    "popote_aire": {"guia": "escalera", "semitonos": [0, 2, 4, 5, 7, 5, 4, 2, 0], "consigna": "Escala de cinco notas, subiendo y bajando, cómoda."},
    "trino_labial": {"guia": "escalera", "semitonos": [0, 2, 4, 2, 0], "consigna": "Trino de labios /br/ siguiendo los escalones."},
    "trino_lingual": {"guia": "escalera", "semitonos": [0, 2, 4, 2, 0], "consigna": "Trino de lengua /rr/ siguiendo los escalones."},
    "oclusion_nasal": {"guia": "sostenida", "duracion_s": 6, "consigna": "/m/ sostenida en tu tono cómodo, abrí a vocal al final."},
    "vocales_cerradas": {"guia": "sostenida", "duracion_s": 6, "consigna": "/u/ o /i/ sostenida, pareja y sin esfuerzo."},
    "fricativas_sonoras": {"guia": "sostenida", "duracion_s": 6, "consigna": "/v/ o /z/ sostenida, sonido parejo."},
    "b_prolongada": {"guia": "sostenida", "duracion_s": 5, "consigna": "/b/ prolongada en tono cómodo."},
    "messa_di_voce": {"guia": "sostenida", "duracion_s": 8, "consigna": "Misma nota: empezá suave, crecé y volvé a suave."},
    "finger_kazoo": {"guia": "rampa", "amplitud": 5, "consigna": "Dedo en los labios: sirena suave siguiendo la rampa."},
}
TONO_BASE_DEFECTO = {"varon": 110.0, "mujer": 196.0, "otro": 150.0}


def _sb():
    from api_clinica import supabase
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    return supabase


def _ahora():
    return datetime.now(timezone.utc)


def _err_tabla(e):
    if "practica" in str(e):
        raise HTTPException(status_code=503, detail=MSG_MIGRACION)
    raise e


def _sexo(p):
    s = str(p.get("sexo") or "").strip().lower()
    if s.startswith("f") or s.startswith("mu"):
        return "mujer"
    if s.startswith(("m", "v", "h")):
        return "varon"
    return "otro"


def tono_base(sb, pid: str, paciente: dict) -> dict:
    """Tono cómodo de partida: F0 conversacional medida (si hay) o un
    valor habitual por sexo. Siempre informa de dónde sale."""
    try:
        from ficha_integral import _f0_conversacional
        f0s = _f0_conversacional(sb, pid)
    except Exception:
        f0s = []
    if f0s:
        v = float(f0s[-1]["f0_mediana_hz"])
        if 60 <= v <= 500:
            return {"hz": round(v, 1), "origen": f"F0 conversacional medida ({f0s[-1]['fecha']})"}
    sx = _sexo(paciente)
    return {"hz": TONO_BASE_DEFECTO[sx], "origen": "valor habitual por sexo (sin F0 medida): ajustalo"}


def normalizar_ejercicio(e: dict, base_defecto: float) -> dict:
    """Valida y completa un ejercicio; rechaza valores fuera de rango."""
    guia = str(e.get("guia") or "")
    if guia not in GUIAS:
        raise HTTPException(status_code=400, detail=f"Tipo de guía inválido: {guia or 'vacío'}")
    try:
        base = float(e.get("base_hz") or base_defecto)
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Tono base inválido")
    if not 60 <= base <= 1000:
        raise HTTPException(status_code=400, detail="El tono base va de 60 a 1000 Hz.")
    out = {"bank_id": e.get("bank_id") or None, "nombre": str(e.get("nombre") or "Ejercicio")[:80],
           "guia": guia, "base_hz": round(base, 1),
           "consigna": str(e.get("consigna") or "")[:300],
           "repeticiones": max(1, min(20, int(e.get("repeticiones") or 3))),
           "tolerancia_cents": max(25, min(300, int(e.get("tolerancia_cents") or 100)))}
    if guia == "sostenida":
        out["duracion_s"] = max(2.0, min(30.0, float(e.get("duracion_s") or 6)))
    elif guia == "rampa":
        out["amplitud"] = max(1, min(24, int(e.get("amplitud") or 7)))
        out["duracion_s"] = max(2.0, min(20.0, float(e.get("duracion_s") or 6)))
    else:
        semis = [int(s) for s in (e.get("semitonos") or [])][:24]
        if len(semis) < 2 or any(abs(s) > 24 for s in semis):
            raise HTTPException(status_code=400, detail="La escalera necesita de 2 a 24 notas, dentro de ±24 semitonos.")
        out["semitonos"] = semis
        out["nota_s"] = max(0.5, min(5.0, float(e.get("nota_s") or 1.2)))
    tope = base * 2 ** (max(out.get("semitonos") or [out.get("amplitud", 0)]) / 12)
    if tope > 1200:
        raise HTTPException(status_code=400, detail="El ejercicio sube por encima de 1200 Hz: bajá el tono base.")
    return out


@router.get("/api/practicas/sugerencias")
async def sugerencias(paciente_id: str):
    sb = _sb()
    p = (sb.table("pacientes").select("*").eq("id", paciente_id).execute().data or [{}])[0]
    if not p:
        raise HTTPException(status_code=404, detail="Paciente inexistente")
    base = tono_base(sb, paciente_id, p)
    from api_clinica import banco_ejercicios_completo
    banco = {e["id"]: e for s in banco_ejercicios_completo().get("sections", []) for e in s.get("exercises", []) if e.get("id")}
    plan_ids = []
    try:
        rec = (sb.table("recomendaciones_terapeuticas").select("*").eq("paciente_id", paciente_id)
               .order("creada_at", desc=True).limit(1).execute().data or [])
        if rec:
            plan_ids = [x.get("id") for x in (rec[0].get("recomendacion") or {}).get("ejercicios_recomendados") or []]
    except Exception:
        pass
    # Contraindicaciones del cuadernillo con el diagnóstico del paciente.
    diag = ""
    try:
        an = (sb.table("anamnesis").select("*").eq("paciente_id", paciente_id).order("fecha", desc=True)
              .limit(1).execute().data or [])
        diag = " ".join(str((an[0] if an else {}).get(k) or "") for k in ("diagnostico_orl", "motivo_consulta"))
    except Exception:
        pass
    from recomendar_motor import verificar_contraindicaciones
    seguros, excluidos = verificar_contraindicaciones([i for i in GUIA_POR_EJERCICIO if i in banco], diag)
    lista = []
    for bid in seguros:
        g = GUIA_POR_EJERCICIO[bid]
        lista.append(dict(g, bank_id=bid, nombre=banco[bid].get("name", bid), base_hz=base["hz"],
                          en_plan=bid in plan_ids))
    lista.sort(key=lambda x: (not x["en_plan"], x["nombre"]))
    return {"tono_base": base, "ejercicios": lista, "excluidos": excluidos}


@router.post("/api/practicas")
async def crear(request: Request):
    body = await request.json()
    pid = str(body.get("paciente_id") or "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="Elegí un paciente.")
    sb = _sb()
    p = (sb.table("pacientes").select("*").eq("id", pid).execute().data or [{}])[0]
    if not p:
        raise HTTPException(status_code=404, detail="Paciente inexistente")
    ejercicios = body.get("ejercicios") or []
    if not 1 <= len(ejercicios) <= 8:
        raise HTTPException(status_code=400, detail="La rutina lleva de 1 a 8 ejercicios.")
    base = tono_base(sb, pid, p)["hz"]
    ejercicios = [normalizar_ejercicio(e, base) for e in ejercicios]
    from nombres import saludo_de_paciente
    saludo = str(body.get("saludo") or "").strip()[:60] or saludo_de_paciente(p)
    dias = max(1, min(90, int(body.get("vence_dias") or 30)))
    token = secrets.token_urlsafe(18)
    fila = {"token": token, "paciente_id": pid, "activa": True, "saludo": saludo,
            "ejercicios": ejercicios, "indicaciones": str(body.get("indicaciones") or "")[:500],
            "vence_at": (_ahora() + timedelta(days=dias)).isoformat()}
    try:
        guardada = (sb.table("practicas").insert(fila).execute().data or [fila])[0]
    except Exception as e:
        _err_tabla(e)
    frontend = os.environ.get("FRONTEND_URL", "https://vocalis-lab.vercel.app").rstrip("/")
    return {"ok": True, "id": guardada.get("id"), "enlace": f"{frontend}/?practica={token}",
            "vence_at": fila["vence_at"], "nombre": saludo, "telefono": p.get("telefono") or ""}


@router.get("/api/practicas")
async def listar(paciente_id: str):
    sb = _sb()
    try:
        rutinas = (sb.table("practicas").select("*").eq("paciente_id", paciente_id)
                   .order("creada_at", desc=True).limit(20).execute().data or [])
        sesiones = (sb.table("practica_sesiones").select("*").eq("paciente_id", paciente_id)
                    .order("creada_at", desc=True).limit(200).execute().data or [])
    except Exception as e:
        if "practica" in str(e):
            return {"practicas": [], "sesiones": [], "aviso": MSG_MIGRACION}
        raise
    frontend = os.environ.get("FRONTEND_URL", "https://vocalis-lab.vercel.app").rstrip("/")
    for r in rutinas:
        r["enlace"] = f"{frontend}/?practica={r.pop('token', '')}"
    return {"practicas": rutinas, "sesiones": sesiones}


@router.patch("/api/practicas/{practica_id}")
async def cambiar(practica_id: str, request: Request):
    body = await request.json()
    sb = _sb()
    sb.table("practicas").update({"activa": bool(body.get("activa"))}).eq("id", practica_id).execute()
    return {"ok": True}


# ------------------------------------------------------------------ público
def _rutina(sb, token: str) -> dict:
    try:
        filas = sb.table("practicas").select("*").eq("token", token).execute().data or []
    except Exception as e:
        _err_tabla(e)
    if not filas:
        raise HTTPException(status_code=404, detail="El enlace no existe. Pedile uno nuevo a tu fonoaudiólogo.")
    return filas[0]


def _disponible(r: dict) -> str:
    if not r.get("activa"):
        return "pausada"
    try:
        if datetime.fromisoformat(str(r["vence_at"]).replace("Z", "+00:00")) < _ahora():
            return "vencida"
    except Exception:
        pass
    return "activa"


@router.get("/api/practica/{token}")
async def ver(token: str):
    sb = _sb()
    r = _rutina(sb, token)
    return {"ok": True, "nombre": r.get("saludo") or "", "estado": _disponible(r),
            "ejercicios": r.get("ejercicios") or [], "indicaciones": r.get("indicaciones") or "",
            "consentimiento": bool(r.get("consentimiento_at")),
            "version_consentimiento": VERSION_CONSENTIMIENTO,
            "profesional": "Matías Pérez · Fonoaudiólogo"}


@router.post("/api/practica/{token}/consentimiento")
async def consentir(token: str, request: Request):
    body = await request.json()
    if body.get("acepta") is not True:
        raise HTTPException(status_code=400, detail="Para usar la práctica hace falta aceptar.")
    sb = _sb()
    r = _rutina(sb, token)
    sb.table("practicas").update({
        "consentimiento_at": _ahora().isoformat(),
        "consentimiento": {"version": VERSION_CONSENTIMIENTO, "medir_voz": True, "audio": False,
                           "agente": str(request.headers.get("user-agent") or "")[:200]},
    }).eq("id", r["id"]).execute()
    return {"ok": True}


def _num(v, lo, hi):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or not lo <= f <= hi:
        return None
    return round(f, 2)


def limpiar_resultado(x: dict, n_ejercicios: int) -> dict:
    i = int(x.get("ejercicio") if x.get("ejercicio") is not None else -1)
    if not 0 <= i < n_ejercicios:
        raise HTTPException(status_code=400, detail="Ejercicio inexistente en la rutina.")
    return {"ejercicio": i,
            "repeticiones": int(_num(x.get("repeticiones"), 0, 50) or 0),
            "dentro_pct": _num(x.get("dentro_pct"), 0, 100),
            "voz_pct": _num(x.get("voz_pct"), 0, 100),
            "f0_mediana_hz": _num(x.get("f0_mediana_hz"), 50, 1500),
            "f0_min_hz": _num(x.get("f0_min_hz"), 50, 1500),
            "f0_max_hz": _num(x.get("f0_max_hz"), 50, 1500),
            "desvio_cents": _num(x.get("desvio_cents"), 0, 2400),
            "duracion_s": _num(x.get("duracion_s"), 0, 3600)}


@router.post("/api/practica/{token}/sesion")
async def guardar_sesion(token: str, request: Request):
    body = await request.json()
    sb = _sb()
    r = _rutina(sb, token)
    estado = _disponible(r)
    if estado != "activa":
        raise HTTPException(status_code=409, detail=f"La práctica está {estado}.")
    if not r.get("consentimiento_at"):
        raise HTTPException(status_code=403, detail="Falta aceptar el consentimiento.")
    n = len(r.get("ejercicios") or [])
    resultados = [limpiar_resultado(x, n) for x in (body.get("resultados") or [])][:50]
    if not resultados:
        raise HTTPException(status_code=400, detail="No hay resultados para guardar.")
    amb = body.get("ambiente") or {}
    fila = {"practica_id": r["id"], "paciente_id": r["paciente_id"], "resultados": resultados,
            "ambiente": {"ruido_dbfs": _num(amb.get("ruido_dbfs"), -120, 0),
                         "silencioso": bool(amb.get("silencioso"))},
            "modo": "vivo" if body.get("modo") == "vivo" else "casa",
            "comentario": str(body.get("comentario") or "")[:500]}
    sb.table("practica_sesiones").insert(fila).execute()
    return {"ok": True}
