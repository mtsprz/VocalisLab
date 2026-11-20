"""Motor terapéutico: datos reales del paciente y recomendaciones guardadas.

Problemas que resuelve:
- La pantalla arrancaba con un paciente de demostración inventado y, si al
  paciente real le faltaba un dato (p. ej. la acústica), se mandaba el de la
  demo a la IA. Ahora el servidor completa lo que falta desde la base y
  devuelve qué datos usó y cuáles no había.
- La recomendación no se guardaba en ningún lado (al volver atrás se
  perdía). Ahora se guarda con su fecha y se puede volver a ver.

Rutas (con sesión):
- POST /api/recomendaciones                 guarda una recomendación
- GET  /api/recomendaciones?paciente_id=    historial (la más nueva primero)
"""
from datetime import date, datetime

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

MSG_MIGRACION = ("Falta correr la migración supabase/migracion_2026_11_recomendaciones.sql en "
                 "Supabase (SQL Editor).")
CAMPOS_ACUSTICA = ("f0_mean", "f0_min", "f0_max", "f0_sd", "jitter_local_pct", "shimmer_local_pct",
                   "hnr_db", "cpps_db", "nhr", "avqi")


def _vacio(v) -> bool:
    return v in (None, "", {}, []) or (isinstance(v, (int, float)) and v == 0)


def _ultima(sb, tabla: str, pid: str, orden: str = "fecha"):
    try:
        filas = (sb.table(tabla).select("*").eq("paciente_id", pid)
                 .order(orden, desc=True).limit(1).execute().data or [])
        return filas[0] if filas else None
    except Exception:
        return None


def _edad(fecha_nac) -> int | None:
    try:
        n = date.fromisoformat(str(fecha_nac)[:10])
    except Exception:
        return None
    hoy = __import__("fechas").hoy_ar()
    return hoy.year - n.year - ((hoy.month, hoy.day) < (n.month, n.day))


def hidratar_desde_db(sb, pid: str, paciente: dict, escalas: dict, riesgo: dict, acustica: dict) -> dict:
    """Completa (sin pisar lo que ya trae la pantalla) con la ficha, la última
    evaluación y el último análisis acústico. Devuelve el detalle de qué hay."""
    usados = {}
    p = (sb.table("pacientes").select("*").eq("id", pid).execute().data or [None])[0]
    if p:
        for clave, valor in (("nombre_completo", p.get("nombre_completo") or p.get("nombre")),
                             ("sexo", p.get("sexo") or p.get("genero")),
                             ("ocupacion", p.get("ocupacion")),
                             ("demanda_vocal_horas", p.get("demanda_vocal_horas")),
                             ("edad", _edad(p.get("fecha_nacimiento")) or p.get("edad")),
                             ("centro", p.get("centro")), ("tipo_atencion", p.get("tipo_atencion"))):
            if _vacio(paciente.get(clave)) and not _vacio(valor):
                paciente[clave] = valor
    usados["ficha"] = bool(p)

    ev = _ultima(sb, "evaluaciones_clinicas", pid)
    if ev:
        for clave in ("grbas", "rasati", "vhi10_score", "tme_o", "tme_s", "indice_so"):
            if _vacio(escalas.get(clave)) and not _vacio(ev.get(clave)):
                escalas[clave] = ev[clave]
        if _vacio(riesgo.get("puntaje_total")) and not _vacio(ev.get("riesgo_vocal_score")):
            riesgo["puntaje_total"] = ev["riesgo_vocal_score"]
            det = ev.get("riesgo_vocal_detalle") or {}
            if isinstance(det, dict) and det.get("factores_prioritarios"):
                riesgo.setdefault("factores_prioritarios", det["factores_prioritarios"])
    usados["evaluacion"] = (__import__("fechas").dia_ar(ev.get("fecha")) if ev else None)

    ac = _ultima(sb, "analisis_acusticos", pid)
    if ac:
        for clave in CAMPOS_ACUSTICA:
            if _vacio(acustica.get(clave)) and not _vacio(ac.get(clave)):
                acustica[clave] = ac[clave]
    usados["acustica"] = (__import__("fechas").dia_ar(ac.get("fecha")) if ac else None)

    # F0 conversacional más reciente (Companion, PitchMeter, sala virtual).
    try:
        ses = (sb.table("companion_sessions").select("id, recorded_at").eq("patient_id", pid)
               .order("recorded_at", desc=True).limit(5).execute().data or [])
        if ses:
            ids = [s["id"] for s in ses]
            ac2 = (sb.table("session_acoustics").select("session_id, f0_median_hz, task_type")
                   .in_("session_id", ids).execute().data or [])
            f0 = next((a["f0_median_hz"] for s in ses for a in ac2
                       if a["session_id"] == s["id"] and a.get("task_type") == "conversacion_espontanea"
                       and a.get("f0_median_hz")), None)
            if f0:
                acustica.setdefault("f0_conversacional_hz", f0)
                usados["f0_conversacional"] = f0
    except Exception:
        pass
    usados["faltan"] = [nombre for nombre, ok in (
        ("evaluación (escalas/riesgo)", usados["evaluacion"]),
        ("análisis acústico", usados["acustica"] or acustica.get("f0_mean")),
    ) if not ok]
    return usados


@router.post("/api/recomendaciones")
async def guardar(request: Request):
    from api_clinica import supabase as sb
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    body = await request.json()
    pid = str(body.get("paciente_id") or "").strip()
    rec = body.get("recomendacion")
    if not pid or not isinstance(rec, dict):
        raise HTTPException(status_code=400, detail="Falta el paciente o la recomendación.")
    fila = {"paciente_id": pid, "recomendacion": rec, "contexto": body.get("contexto") or {},
            "notas": str(body.get("notas") or "")[:2000]}
    try:
        guardada = (sb.table("recomendaciones_terapeuticas").insert(fila).execute().data or [fila])[0]
    except Exception as e:
        if "recomendaciones_terapeuticas" in str(e):
            raise HTTPException(status_code=503, detail=MSG_MIGRACION)
        raise
    return {"ok": True, "recomendacion": guardada}


@router.get("/api/recomendaciones")
async def listar(paciente_id: str):
    from api_clinica import supabase as sb
    if not sb:
        return {"recomendaciones": []}
    try:
        filas = (sb.table("recomendaciones_terapeuticas").select("*").eq("paciente_id", paciente_id)
                 .order("creada_at", desc=True).limit(20).execute().data or [])
    except Exception as e:
        if "recomendaciones_terapeuticas" in str(e):
            return {"recomendaciones": [], "aviso": MSG_MIGRACION}
        raise
    return {"recomendaciones": filas}
