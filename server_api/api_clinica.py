"""
VocalisLab Pro — API de Gestión Clínica
Endpoints para pacientes, evaluaciones, anamnesis, cuadernillos y turnos.
"""
import os
import sys
import json
import traceback
from datetime import datetime, timedelta
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import JSONResponse

sys.path.insert(0, os.path.dirname(__file__))

supabase = None
_supabase_error = None
try:
    from supabase import create_client
    SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
    SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))
    if SUPABASE_URL and SUPABASE_KEY:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    else:
        _supabase_error = "SUPABASE_URL o SUPABASE_KEY no configurados"
except Exception as e:
    _supabase_error = str(e)

router = APIRouter()

EXERCISE_BANK_PATH = os.path.join(os.path.dirname(__file__), "exercise_bank.json")

def _load_exercise_bank():
    try:
        with open(EXERCISE_BANK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sections": [], "presets": []}


def _db_insert(table: str, data: dict):
    if not supabase:
        return {"id": "local_" + str(hash(json.dumps(data, default=str)))[:12], **data}
    try:
        result = supabase.table(table).insert(data).execute()
        return result.data[0] if result.data else data
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error insertando en {table}: {str(e)}")


def _db_upsert(table: str, data: dict, on_conflict: str = "id"):
    if not supabase:
        return data
    try:
        result = supabase.table(table).upsert(data, on_conflict=on_conflict).execute()
        return result.data[0] if result.data else data
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error upsert en {table}: {str(e)}")


def _db_select(table: str, filters: dict = None, order: str = None, limit: int = 100):
    if not supabase:
        return []
    try:
        q = supabase.table(table).select("*")
        if filters:
            for k, v in filters.items():
                if v is not None:
                    q = q.eq(k, v)
        if order:
            q = q.order(order, desc=True)
        q = q.limit(limit)
        result = q.execute()
        return result.data or []
    except Exception as e:
        traceback.print_exc()
        print(f"[api_clinica] Error consultando {table}: {e}")
        return []


def _db_update(table: str, record_id: str, data: dict):
    if not supabase:
        return {**data, "id": record_id}
    try:
        result = supabase.table(table).update(data).eq("id", record_id).execute()
        return result.data[0] if result.data else {**data, "id": record_id}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error actualizando {table}: {str(e)}")


def _db_delete(table: str, record_id: str):
    if not supabase:
        return True
    try:
        supabase.table(table).delete().eq("id", record_id).execute()
        return True
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error eliminando de {table}: {str(e)}")


# ─── PACIENTES ──────────────────────────────────────────────

@router.post("/api/pacientes")
async def crear_paciente(
    nombre_completo: str = Form(...),
    dni: str = Form(...),
    fecha_nacimiento: str = Form(""),
    sexo: str = Form(""),
    telefono: str = Form(""),
    email: str = Form(""),
    ocupacion: str = Form(""),
    demanda_vocal_horas: int = Form(0),
    derivador: str = Form(""),
    notas_iniciales: str = Form(""),
):
    data = {
        "nombre_completo": nombre_completo,
        "dni": dni,
        "sexo": sexo,
        "telefono": telefono,
        "email": email,
        "ocupacion": ocupacion,
        "demanda_vocal_horas": demanda_vocal_horas,
        "derivador": derivador,
        "notas_iniciales": notas_iniciales,
    }
    if fecha_nacimiento:
        data["fecha_nacimiento"] = fecha_nacimiento
    result = _db_insert("pacientes", data)
    return JSONResponse(content=result)


@router.get("/api/pacientes")
async def listar_pacientes(
    buscar: str = Query("", description="Buscar por nombre o DNI"),
    activo: bool = Query(True),
    limit: int = Query(100),
):
    if not supabase:
        return JSONResponse(content=[])
    try:
        q = supabase.table("pacientes").select("*").eq("activo", activo).order("nombre_completo")
        if buscar:
            q = q.or_(f"nombre_completo.ilike.%{buscar}%,dni.ilike.%{buscar}%")
        q = q.limit(limit)
        result = q.execute()
        return JSONResponse(content=result.data or [])
    except Exception as e:
        traceback.print_exc()
        print(f"[api_clinica] Error en listar_pacientes: {e}")
        return JSONResponse(content=[])


@router.get("/api/pacientes/{paciente_id}")
async def obtener_paciente(paciente_id: str):
    if not supabase:
        raise HTTPException(status_code=404, detail="Paciente no encontrado (Supabase no configurado)")
    try:
        result = supabase.table("pacientes").select("*").eq("id", paciente_id).execute()
        if result.data:
            return JSONResponse(content=result.data[0])
    except Exception as e:
        traceback.print_exc()
    raise HTTPException(status_code=404, detail="Paciente no encontrado")


@router.put("/api/pacientes/{paciente_id}")
async def actualizar_paciente(
    paciente_id: str,
    nombre_completo: str = Form(None),
    dni: str = Form(None),
    fecha_nacimiento: str = Form(None),
    sexo: str = Form(None),
    telefono: str = Form(None),
    email: str = Form(None),
    ocupacion: str = Form(None),
    derivador: str = Form(None),
    notas_iniciales: str = Form(None),
):
    data = {}
    if nombre_completo is not None: data["nombre_completo"] = nombre_completo
    if dni is not None: data["dni"] = dni
    if fecha_nacimiento is not None: data["fecha_nacimiento"] = fecha_nacimiento
    if sexo is not None: data["sexo"] = sexo
    if telefono is not None: data["telefono"] = telefono
    if email is not None: data["email"] = email
    if ocupacion is not None: data["ocupacion"] = ocupacion
    if derivador is not None: data["derivador"] = derivador
    if notas_iniciales is not None: data["notas_iniciales"] = notas_iniciales
    result = _db_update("pacientes", paciente_id, data)
    return JSONResponse(content=result)


@router.delete("/api/pacientes/{paciente_id}")
async def eliminar_paciente(paciente_id: str):
    _db_update("pacientes", paciente_id, {"activo": False})
    return JSONResponse(content={"ok": True})


# ─── EVALUACIONES CLÍNICAS ──────────────────────────────────

@router.post("/api/evaluaciones")
async def crear_evaluacion(
    paciente_id: str = Form(...),
    grbas: str = Form("{}"),
    rasati: str = Form("{}"),
    vhi10_score: int = Form(None),
    vhi10_detalle: str = Form("{}"),
    riesgo_vocal_score: int = Form(None),
    riesgo_vocal_detalle: str = Form("{}"),
    tme_o: float = Form(None),
    tme_s: float = Form(None),
    f0_conversacional_hz: float = Form(None),
    extension_vocal_min: str = Form(""),
    extension_vocal_max: str = Form(""),
    autopercepcion_vocal: int = Form(None),
    autopercepcion_momentos: str = Form("{}"),
    observaciones: str = Form(""),
):
    try:
        g = json.loads(grbas) if grbas.startswith("{") else {}
        r = json.loads(rasati) if rasati.startswith("{") else {}
    except Exception:
        g, r = {}, {}

    indice_so = None
    if tme_o and tme_s and tme_o > 0:
        indice_so = round(tme_s / tme_o, 2)

    data = {
        "paciente_id": paciente_id,
        "grbas": g,
        "rasati": r,
        "vhi10_score": vhi10_score,
        "riesgo_vocal_score": riesgo_vocal_score,
        "tme_o": tme_o,
        "tme_s": tme_s,
        "indice_so": indice_so,
        "f0_conversacional_hz": f0_conversacional_hz,
        "extension_vocal_min": extension_vocal_min,
        "extension_vocal_max": extension_vocal_max,
        "autopercepcion_vocal": autopercepcion_vocal,
        "observaciones": observaciones,
    }
    result = _db_insert("evaluaciones_clinicas", data)
    return JSONResponse(content=result)


@router.get("/api/evaluaciones")
async def listar_evaluaciones(
    paciente_id: str = Query(None),
    limit: int = Query(50),
):
    filters = {}
    if paciente_id:
        filters["paciente_id"] = paciente_id
    data = _db_select("evaluaciones_clinicas", filters=filters, order="fecha", limit=limit)
    return JSONResponse(content=data)


@router.get("/api/evaluaciones/{evaluacion_id}")
async def obtener_evaluacion(evaluacion_id: str):
    if supabase:
        result = supabase.table("evaluaciones_clinicas").select("*").eq("id", evaluacion_id).execute()
        if result.data:
            return JSONResponse(content=result.data[0])
    raise HTTPException(status_code=404, detail="Evaluación no encontrada")


# ─── ANÁLISIS ACÚSTICOS ─────────────────────────────────────

@router.post("/api/analisis_acusticos")
async def guardar_analisis(
    paciente_id: str = Form(...),
    evaluacion_id: str = Form(""),
    metrics_json: str = Form("{}"),
    cross_check_json: str = Form("{}"),
    charts_json: str = Form("{}"),
    modo: str = Form("clinico"),
):
    try:
        metrics = json.loads(metrics_json) if metrics_json.startswith("{") else {}
        cross_check = json.loads(cross_check_json) if cross_check_json.startswith("{") else {}
        charts = json.loads(charts_json) if charts_json.startswith("{") else {}
    except Exception:
        metrics, cross_check, charts = {}, {}, {}

    data = {
        "paciente_id": paciente_id,
        "evaluacion_id": evaluacion_id if evaluacion_id else None,
        "f0_mean": metrics.get("f0_mean"),
        "f0_min": metrics.get("f0_min"),
        "f0_max": metrics.get("f0_max"),
        "f0_sd": metrics.get("f0_sd"),
        "f0_range": metrics.get("f0_range"),
        "jitter_local_pct": metrics.get("jitter_local_pct"),
        "jitter_rap_pct": metrics.get("jitter_rap_pct"),
        "jitter_ppq5_pct": metrics.get("jitter_ppq5_pct"),
        "shimmer_local_pct": metrics.get("shimmer_local_pct"),
        "shimmer_apq3_pct": metrics.get("shimmer_apq3_pct"),
        "shimmer_apq5_pct": metrics.get("shimmer_apq5_pct"),
        "hnr_db": metrics.get("hnr_db"),
        "cpps_db": metrics.get("cpps_db"),
        "nhr": metrics.get("nhr"),
        "nne_db": metrics.get("nne_db"),
        "avqi": metrics.get("avqi"),
        "f1_hz": metrics.get("f1_hz"),
        "f2_hz": metrics.get("f2_hz"),
        "f3_hz": metrics.get("f3_hz"),
        "f4_hz": metrics.get("f4_hz"),
        "intensity_mean_db": metrics.get("intensity_mean_db"),
        "spectral_tilt_slope": metrics.get("spectral_tilt_slope"),
        "cross_check": cross_check,
        "graficos_json": charts,
        "modo": modo,
    }
    result = _db_insert("analisis_acusticos", data)
    return JSONResponse(content=result)


@router.get("/api/analisis_acusticos")
async def listar_analisis(
    paciente_id: str = Query(None),
    limit: int = Query(50),
):
    filters = {}
    if paciente_id:
        filters["paciente_id"] = paciente_id
    data = _db_select("analisis_acusticos", filters=filters, order="fecha", limit=limit)
    return JSONResponse(content=data)


# ─── CUADERNILLOS TERAPÉUTICOS ──────────────────────────────

@router.get("/api/ejercicios")
async def obtener_banco_ejercicios():
    bank = _load_exercise_bank()
    return JSONResponse(content=bank)


@router.post("/api/cuadernillos")
async def crear_cuadernillo(
    paciente_id: str = Form(...),
    titulo: str = Form("Cuadernillo Terapéutico Vocal"),
    cantidad_sesiones: int = Form(8),
    ejercicios_ids: str = Form("[]"),
    preset: str = Form(""),
    notas: str = Form(""),
):
    bank = _load_exercise_bank()

    if preset:
        preset_data = next((p for p in bank.get("presets", []) if p["id"] == preset), None)
        if preset_data:
            ejercicios_ids = json.dumps(preset_data.get("exercise_ids", []))
            titulo = f"Cuadernillo — {preset_data['name']}"
            cantidad_sesiones = preset_data.get("sesiones_recomendadas", cantidad_sesiones)

    try:
        ex_ids = json.loads(ejercicios_ids) if isinstance(ejercicios_ids, str) else ejercicios_ids
    except Exception:
        ex_ids = []

    all_exercises = {}
    for section in bank.get("sections", []):
        for ex in section.get("exercises", []):
            all_exercises[ex["id"]] = ex

    selected = [all_exercises[eid] for eid in ex_ids if eid in all_exercises]

    contrato = {
        "frecuencia": "2 veces por semana",
        "duracion_sesion": "30 minutos",
        "pautas_ausencias": "Avisar con 24h de anticipación. Las sesiones canceladas se reprograman.",
    }

    data = {
        "paciente_id": paciente_id,
        "titulo": titulo,
        "cantidad_sesiones": cantidad_sesiones,
        "ejercicios_seleccionados": selected,
        "preset_usado": preset,
        "contrato_terapeutico": contrato,
        "notas_profesional": notas,
    }
    result = _db_insert("cuadernillos_paciente", data)
    result["ejercicios_detalles"] = selected
    return JSONResponse(content=result)


@router.get("/api/cuadernillos")
async def listar_cuadernillos(
    paciente_id: str = Query(None),
    limit: int = Query(50),
):
    filters = {}
    if paciente_id:
        filters["paciente_id"] = paciente_id
    data = _db_select("cuadernillos_paciente", filters=filters, order="fecha_creacion", limit=limit)
    return JSONResponse(content=data)


# ─── AGENDA / TURNOS ────────────────────────────────────────

@router.post("/api/turnos")
async def crear_turno(
    paciente_id: str = Form(...),
    fecha_hora: str = Form(...),
    duracion_min: int = Form(30),
    tipo: str = Form("control"),
    notas: str = Form(""),
):
    data = {
        "paciente_id": paciente_id,
        "fecha_hora": fecha_hora,
        "duracion_min": duracion_min,
        "tipo": tipo,
        "notas": notas,
    }
    result = _db_insert("turnos", data)
    return JSONResponse(content=result)


@router.get("/api/turnos")
async def listar_turnos(
    fecha_desde: str = Query(None),
    fecha_hasta: str = Query(None),
    estado: str = Query(None),
    limit: int = Query(100),
):
    if not supabase:
        return JSONResponse(content=[])
    try:
        q = supabase.table("turnos").select("*, pacientes(nombre_completo, dni, telefono)")
        if fecha_desde:
            q = q.gte("fecha_hora", fecha_desde)
        if fecha_hasta:
            q = q.lte("fecha_hora", fecha_hasta)
        if estado:
            q = q.eq("estado", estado)
        q = q.order("fecha_hora").limit(limit)
        result = q.execute()
        return JSONResponse(content=result.data or [])
    except Exception as e:
        traceback.print_exc()
        print(f"[api_clinica] Error en listar_turnos: {e}")
        return JSONResponse(content=[])


@router.put("/api/turnos/{turno_id}")
async def actualizar_turno(
    turno_id: str,
    estado: str = Form(None),
    notas: str = Form(None),
):
    data = {}
    if estado is not None: data["estado"] = estado
    if notas is not None: data["notas"] = notas
    result = _db_update("turnos", turno_id, data)
    return JSONResponse(content=result)


# ─── DASHBOARD / ESTADÍSTICAS ───────────────────────────────

@router.get("/api/dashboard")
async def dashboard():
    if not supabase:
        return JSONResponse(content={
            "total_pacientes": 0,
            "turnos_hoy": 0,
            "evaluaciones_mes": 0,
            "analisis_mes": 0,
        })

    try:
        hoy = datetime.now().strftime("%Y-%m-%d")
        mes_inicio = datetime.now().replace(day=1).strftime("%Y-%m-%d")

        pacientes = supabase.table("pacientes").select("id", count="exact").eq("activo", True).execute()
        turnos_hoy = supabase.table("turnos").select("id", count="exact").gte("fecha_hora", hoy).lt("fecha_hora", hoy + "T23:59:59").execute()
        evaluaciones = supabase.table("evaluaciones_clinicas").select("id", count="exact").gte("fecha", mes_inicio).execute()
        analisis = supabase.table("analisis_acusticos").select("id", count="exact").gte("fecha", mes_inicio).execute()

        return JSONResponse(content={
            "total_pacientes": pacientes.count or 0,
            "turnos_hoy": turnos_hoy.count or 0,
            "evaluaciones_mes": evaluaciones.count or 0,
            "analisis_mes": analisis.count or 0,
        })
    except Exception as e:
        traceback.print_exc()
        print(f"[api_clinica] Error en dashboard: {e}")
        return JSONResponse(content={
            "total_pacientes": 0, "turnos_hoy": 0,
            "evaluaciones_mes": 0, "analisis_mes": 0,
        })