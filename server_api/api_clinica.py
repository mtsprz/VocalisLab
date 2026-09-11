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


def _get_supabase():
    """Devuelve el cliente Supabase compartido (o None si no está configurado)."""
    return supabase

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
        # Columna legacy del schema v1 (NOT NULL): se mantiene sincronizada
        "nombre": nombre_completo,
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
    demanda_vocal_horas: str = Form(None),
):
    data = {}
    if nombre_completo is not None:
        data["nombre_completo"] = nombre_completo
        data["nombre"] = nombre_completo  # columna legacy v1, mantener sincronizada
    if dni is not None: data["dni"] = dni
    if fecha_nacimiento is not None: data["fecha_nacimiento"] = fecha_nacimiento
    if sexo is not None: data["sexo"] = sexo
    if telefono is not None: data["telefono"] = telefono
    if email is not None: data["email"] = email
    if ocupacion is not None: data["ocupacion"] = ocupacion
    if derivador is not None: data["derivador"] = derivador
    if notas_iniciales is not None: data["notas_iniciales"] = notas_iniciales
    if demanda_vocal_horas is not None and str(demanda_vocal_horas).strip() != "":
        try:
            data["demanda_vocal_horas"] = int(float(demanda_vocal_horas))
        except Exception:
            pass
    result = _db_update("pacientes", paciente_id, data)
    return JSONResponse(content=result)


@router.delete("/api/pacientes/{paciente_id}")
async def eliminar_paciente(paciente_id: str):
    _db_update("pacientes", paciente_id, {"activo": False})
    return JSONResponse(content={"ok": True})


# ─── EVALUACIONES CLÍNICAS ──────────────────────────────────

def _to_int(v):
    try:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return int(float(v))
    except Exception:
        return None


def _to_float(v):
    try:
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return float(v)
    except Exception:
        return None


@router.post("/api/evaluaciones")
async def crear_evaluacion(
    paciente_id: str = Form(...),
    grbas: str = Form("{}"),
    rasati: str = Form("{}"),
    vhi10_score: str = Form(None),
    vhi10_detalle: str = Form("{}"),
    riesgo_vocal_score: str = Form(None),
    riesgo_vocal_detalle: str = Form("{}"),
    tme_o: str = Form(None),
    tme_s: str = Form(None),
    f0_conversacional_hz: str = Form(None),
    extension_vocal_min: str = Form(""),
    extension_vocal_max: str = Form(""),
    autopercepcion_vocal: str = Form(None),
    autopercepcion_momentos: str = Form("{}"),
    observaciones: str = Form(""),
):
    try:
        g = json.loads(grbas) if grbas.startswith("{") else {}
        r = json.loads(rasati) if rasati.startswith("{") else {}
    except Exception:
        g, r = {}, {}
    try:
        vhi_det = json.loads(vhi10_detalle) if vhi10_detalle.startswith("{") else {}
    except Exception:
        vhi_det = {}
    try:
        rv_det = json.loads(riesgo_vocal_detalle) if riesgo_vocal_detalle.startswith("{") else {}
    except Exception:
        rv_det = {}
    try:
        ap_mom = json.loads(autopercepcion_momentos) if autopercepcion_momentos.startswith("{") else {}
    except Exception:
        ap_mom = {}

    tme_o_f = _to_float(tme_o)
    tme_s_f = _to_float(tme_s)
    indice_so = None
    if tme_o_f and tme_s_f and tme_o_f > 0:
        indice_so = round(tme_s_f / tme_o_f, 2)

    data = {
        "paciente_id": paciente_id,
        "grbas": g,
        "rasati": r,
        "vhi10_score": _to_int(vhi10_score),
        "vhi10_detalle": vhi_det,
        "riesgo_vocal_score": _to_int(riesgo_vocal_score),
        "riesgo_vocal_detalle": rv_det,
        "tme_o": tme_o_f,
        "tme_s": tme_s_f,
        "indice_so": indice_so,
        "f0_conversacional_hz": _to_float(f0_conversacional_hz),
        "extension_vocal_min": extension_vocal_min,
        "extension_vocal_max": extension_vocal_max,
        "autopercepcion_vocal": _to_int(autopercepcion_vocal),
        "autopercepcion_momentos": ap_mom,
        "observaciones": observaciones,
    }
    result = _db_insert("evaluaciones_clinicas", data)
    return JSONResponse(content=result)


# ─── ANAMNESIS (una ficha vigente por paciente: actualiza la última o crea) ──

def _parse_json_field(v, default):
    try:
        if isinstance(v, (dict, list)):
            return v
        if isinstance(v, str) and v.strip().startswith(("{", "[")):
            return json.loads(v)
    except Exception:
        pass
    return default


@router.post("/api/anamnesis")
async def guardar_anamnesis(
    paciente_id: str = Form(...),
    motivo_consulta: str = Form(""),
    diagnostico_orl: str = Form(""),
    metodo_exploracion: str = Form(""),
    sintomas: str = Form("{}"),
    factores_riesgo: str = Form("{}"),
    resumen_clinico: str = Form(""),
    transcripcion_audio: str = Form(""),
    demanda_vocal_horas: str = Form(""),
):
    data = {
        "paciente_id": paciente_id,
        "motivo_consulta": motivo_consulta,
        "diagnostico_orl": diagnostico_orl,
        "metodo_exploracion": metodo_exploracion,
        "sintomas": _parse_json_field(sintomas, {}),
        "factores_riesgo": _parse_json_field(factores_riesgo, {}),
        "resumen_clinico": resumen_clinico,
        "transcripcion_audio": transcripcion_audio,
    }
    if not supabase:
        return JSONResponse(content={"id": "local", **data})
    # Upsert manual: actualizar la ficha más reciente del paciente, o insertar
    try:
        existing = supabase.table("anamnesis").select("id").eq("paciente_id", paciente_id)\
            .order("fecha", desc=True).limit(1).execute()
        if existing.data:
            rid = existing.data[0]["id"]
            # Reintento tolerante: si alguna columna no existe en la DB, quitarla y reintentar
            for _ in range(4):
                try:
                    upd = supabase.table("anamnesis").update(data).eq("id", rid).execute()
                    return JSONResponse(content=(upd.data[0] if upd.data else {"id": rid, **data}))
                except Exception as e:
                    col = _missing_column(str(e))
                    if col and col in data:
                        data.pop(col, None)
                        continue
                    raise
        for _ in range(4):
            try:
                return JSONResponse(content=_db_insert("anamnesis", data))
            except Exception as e:
                col = _missing_column(str(e))
                if col and col in data:
                    data.pop(col, None)
                    continue
                raise
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error guardando anamnesis: {str(e)[:300]}")


def _missing_column(err_msg: str):
    """Extrae la columna faltante de un error PGRST204, o None."""
    import re
    m = re.search(r"Could not find the '([^']+)' column", err_msg)
    return m.group(1) if m else None


@router.get("/api/anamnesis")
async def obtener_anamnesis(paciente_id: str = Query(...)):
    if not supabase:
        return JSONResponse(content={})
    try:
        result = supabase.table("anamnesis").select("*").eq("paciente_id", paciente_id)\
            .order("fecha", desc=True).limit(1).execute()
        if result.data:
            return JSONResponse(content=result.data[0])
    except Exception as e:
        traceback.print_exc()
        print(f"[api_clinica] Error en obtener_anamnesis: {e}")
    return JSONResponse(content={})


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
    duracion_min: int = Form(45),
    tipo: str = Form("control"),
    modalidad: str = Form("PRESENCIAL"),
    motivo: str = Form("Consulta de Voz"),
    notas: str = Form(""),
    user_id: Optional[str] = Form(None),
    sincronizar_google: bool = Form(False),
):
    meet_link = None
    google_event_id = None

    # Si se solicita sincronización con Google Calendar y se proporciona user_id
    if sincronizar_google and user_id:
        try:
            # Obtener datos del paciente
            paciente_nombre = "Paciente"
            paciente_email = ""
            if supabase:
                p_res = supabase.table("pacientes").select("nombre_completo, email").eq("id", paciente_id).execute()
                if p_res.data:
                    paciente_nombre = p_res.data[0].get("nombre_completo", "Paciente")
                    paciente_email = p_res.data[0].get("email", "")

            # Calcular fecha fin
            start_dt = datetime.fromisoformat(fecha_hora.replace("Z", "+00:00"))
            end_dt = start_dt + timedelta(minutes=duracion_min)

            from google_calendar import create_calendar_event
            g_resp = await create_calendar_event(
                user_id=user_id,
                summary=f"Atención Vocal: {paciente_nombre}",
                description=f"Consulta Fonoaudiológica — Consultorio de Voz.\nModalidad: {modalidad}\nMotivo: {motivo}\n{notas}".strip(),
                start_datetime=start_dt.isoformat(),
                end_datetime=end_dt.isoformat(),
                attendee_email=paciente_email,
                modalidad=modalidad,
                motivo=motivo,
            )
            g_data = json.loads(g_resp.body.decode()) if hasattr(g_resp, "body") else {}
            if g_data.get("ok"):
                google_event_id = g_data.get("google_event_id")
                meet_link = g_data.get("meet_link")
        except Exception as e:
            print(f"[api_clinica] No se pudo sincronizar turno con Google: {e}")

    data = {
        "paciente_id": paciente_id,
        "fecha_hora": fecha_hora,
        "duracion_min": duracion_min,
        "tipo": tipo,
        "modalidad": modalidad.upper(),
        "motivo": motivo,
        "notas": notas,
        "meet_link": meet_link,
        "google_event_id": google_event_id,
        "estado": "programado",
    }
    result = _db_insert("turnos", data)
    return JSONResponse(content=result)


@router.get("/api/turnos")
async def listar_turnos(
    fecha_desde: str = Query(None),
    fecha_hasta: str = Query(None),
    estado: str = Query(None),
    modalidad: str = Query(None),
    paciente_id: str = Query(None),
    limit: int = Query(200),
):
    if not supabase:
        return JSONResponse(content=[])
    try:
        # Intento con join relacional
        q = supabase.table("turnos").select("*, pacientes(nombre_completo, dni, telefono, email)")
        if fecha_desde:
            q = q.gte("fecha_hora", fecha_desde)
        if fecha_hasta:
            q = q.lte("fecha_hora", fecha_hasta)
        if estado:
            q = q.eq("estado", estado)
        if modalidad:
            q = q.eq("modalidad", modalidad.upper())
        if paciente_id:
            q = q.eq("paciente_id", paciente_id)
        q = q.order("fecha_hora").limit(limit)
        result = q.execute()
        return JSONResponse(content=result.data or [])
    except Exception as e:
        print(f"[api_clinica] Error con join relacional en listar_turnos: {e}. Probando consulta simple...")
        try:
            # Fallback seguro sin join relacional en caso de que la FK no esté en Supabase
            q2 = supabase.table("turnos").select("*")
            if fecha_desde: q2 = q2.gte("fecha_hora", fecha_desde)
            if fecha_hasta: q2 = q2.lte("fecha_hora", fecha_hasta)
            if estado: q2 = q2.eq("estado", estado)
            if modalidad: q2 = q2.eq("modalidad", modalidad.upper())
            if paciente_id: q2 = q2.eq("paciente_id", paciente_id)
            q2 = q2.order("fecha_hora").limit(limit)
            turnos_data = q2.execute().data or []

            # Mapear pacientes manualmente
            p_ids = list({t.get("paciente_id") for t in turnos_data if t.get("paciente_id")})
            if p_ids:
                p_map = {}
                p_rows = supabase.table("pacientes").select("id, nombre_completo, dni, telefono, email").in_("id", p_ids).execute().data or []
                for p in p_rows:
                    p_map[p["id"]] = p
                for t in turnos_data:
                    t["pacientes"] = p_map.get(t.get("paciente_id"))
            return JSONResponse(content=turnos_data)
        except Exception as e2:
            print(f"[api_clinica] Error en fallback listar_turnos: {e2}")
            return JSONResponse(content=[])


@router.put("/api/turnos/{turno_id}")
async def actualizar_turno(
    turno_id: str,
    estado: str = Form(None),
    notas: str = Form(None),
    modalidad: str = Form(None),
    meet_link: str = Form(None),
    motivo: str = Form(None),
    fecha_hora: str = Form(None),
    duracion_min: int = Form(None),
    tipo: str = Form(None),
    user_id: str = Form(None),
    sincronizar_google: bool = Form(False),
    zoom_meeting_id: str = Form(None),
    zoom_password: str = Form(None),
    zoom_join_url: str = Form(None),
):
    data = {}
    if estado is not None: data["estado"] = estado
    if notas is not None: data["notas"] = notas
    if modalidad is not None: data["modalidad"] = modalidad.upper()
    if meet_link is not None: data["meet_link"] = meet_link
    if motivo is not None: data["motivo"] = motivo
    if fecha_hora is not None: data["fecha_hora"] = fecha_hora
    if duracion_min is not None: data["duracion_min"] = duracion_min
    if tipo is not None: data["tipo"] = tipo
    if zoom_meeting_id is not None: data["zoom_meeting_id"] = zoom_meeting_id
    if zoom_password is not None: data["zoom_password"] = zoom_password
    if zoom_join_url is not None: data["zoom_join_url"] = zoom_join_url

    # Sincronizar cambios con Google Calendar (patch o creación con Meet)
    if sincronizar_google and user_id and supabase:
        try:
            cur = supabase.table("turnos").select("*").eq("id", turno_id).execute()
            row = (cur.data or [{}])[0]
            merged = {**row, **data}
            google_event_id = merged.get("google_event_id")
            mod = (merged.get("modalidad") or "PRESENCIAL").upper()
            fh = merged.get("fecha_hora", "")
            try:
                s_dt = datetime.fromisoformat(str(fh).replace("Z", "+00:00"))
                e_dt = s_dt + timedelta(minutes=int(merged.get("duracion_min") or 45))
            except Exception:
                s_dt = e_dt = None
            p_nombre, p_email = "Paciente", ""
            if merged.get("paciente_id"):
                pr = supabase.table("pacientes").select("nombre_completo, email")\
                    .eq("id", merged["paciente_id"]).execute()
                if pr.data:
                    p_nombre = pr.data[0].get("nombre_completo", "Paciente")
                    p_email = pr.data[0].get("email", "")
            summary = f"Atención Vocal: {p_nombre}"
            desc = (f"Consulta Fonoaudiológica — Consultorio de Voz.\n"
                    f"Modalidad: {mod}\nMotivo: {merged.get('motivo', '')}\n"
                    f"{merged.get('notas', '')}").strip()
            from google_calendar import update_calendar_event, create_calendar_event
            if google_event_id and s_dt:
                g_resp = await update_calendar_event(
                    event_id=google_event_id, user_id=user_id,
                    summary=summary, description=desc,
                    start_datetime=s_dt.isoformat(), end_datetime=e_dt.isoformat(),
                )
                g_data = json.loads(g_resp.body.decode()) if hasattr(g_resp, "body") else {}
                if not g_data.get("ok"):
                    print(f"[api_clinica] Patch Google falló, se recrea evento: {g_data}")
                    google_event_id = None
            if not google_event_id and s_dt:
                g_resp = await create_calendar_event(
                    user_id=user_id, summary=summary, description=desc,
                    start_datetime=s_dt.isoformat(), end_datetime=e_dt.isoformat(),
                    attendee_email=p_email, modalidad=mod,
                    motivo=merged.get("motivo", ""),
                )
                g_data = json.loads(g_resp.body.decode()) if hasattr(g_resp, "body") else {}
                if g_data.get("ok"):
                    data["google_event_id"] = g_data.get("google_event_id")
                    if g_data.get("meet_link"):
                        data["meet_link"] = g_data.get("meet_link")
        except Exception as e:
            print(f"[api_clinica] No se pudo sincronizar edición con Google: {e}")

    # Sincronizar Zoom: reprogramación (PATCH) o cancelación (DELETE)
    if user_id and supabase:
        try:
            cur2 = supabase.table("turnos").select("id, zoom_meeting_id, fecha_hora, duracion_min").eq("id", turno_id).execute()
            zrow = (cur2.data or [{}])[0]
            zmid = zrow.get("zoom_meeting_id")
            if zmid:
                # Llamada interna a los endpoints Zoom (misma app)
                from teleconsulta_zoom import zoom_update as _zupd, zoom_delete as _zdel

                class _FakeReq:
                    def __init__(self, payload):
                        self._payload = payload
                        self.query_params = {}
                    async def json(self):
                        return self._payload

                if data.get("estado") == "cancelado":
                    try:
                        await _zdel(zmid, _FakeReq({"user_id": user_id, "turno_id": turno_id}))
                    except Exception as e_z:
                        print(f"[api_clinica] Cancelación Zoom tolerada: {e_z}")
                elif ("fecha_hora" in data or "duracion_min" in data):
                    try:
                        await _zupd(zmid, _FakeReq({
                            "user_id": user_id, "turno_id": turno_id,
                            "fecha_hora": data.get("fecha_hora", zrow.get("fecha_hora")),
                            "duracion_min": data.get("duracion_min", zrow.get("duracion_min")),
                        }))
                    except Exception as e_z:
                        print(f"[api_clinica] Reprogramación Zoom tolerada: {e_z}")
        except Exception as e:
            print(f"[api_clinica] Sync Zoom omitido: {e}")

    # Update tolerante: si las columnas zoom_* aún no existen en Supabase, quitarlas y reintentar
    for _ in range(4):
        try:
            result = _db_update("turnos", turno_id, data)
            return JSONResponse(content=result)
        except Exception as e_upd:
            col = _missing_column(str(e_upd))
            if col and col in data:
                data.pop(col, None)
                continue
            raise


@router.delete("/api/turnos/{turno_id}")
async def eliminar_turno(turno_id: str):
    res = _db_delete("turnos", turno_id)
    return JSONResponse(content={"ok": res})


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


# ─── DIAGNÓSTICO (sin secretos) ─────────────────────────────
def _supabase_key_role() -> str:
    """Devuelve el rol ('anon' o 'service_role') de la key configurada, sin exponerla."""
    try:
        import base64
        import json as _json
        key = os.environ.get("SUPABASE_SERVICE_KEY", "") or os.environ.get("SUPABASE_ANON_KEY", "")
        parts = key.split(".")
        if len(parts) != 3:
            return "desconocido"
        payload = parts[1] + "=" * (-len(parts[1]) % 4)
        return _json.loads(base64.urlsafe_b64decode(payload).decode()).get("role", "desconocido")
    except Exception:
        return "desconocido"


@router.get("/api/debug/status")
async def debug_status():
    """Indica si Supabase está configurado y qué tablas existen. No expone secretos."""
    info: dict = {
        "supabase_configured": bool(supabase),
        "supabase_key_role": _supabase_key_role(),
        "supabase_error": _supabase_error,
        "tables": {},
    }
    if not supabase:
        return JSONResponse(content=info)
    for tbl in ["pacientes", "turnos", "anamnesis", "evaluaciones_clinicas",
                "analisis_acusticos", "cuadernillos_paciente", "usuarios_google",
                "sesiones_teleconsulta"]:
        try:
            r = supabase.table(tbl).select("id", count="exact").limit(1).execute()
            info["tables"][tbl] = {"exists": True, "count": r.count}
        except Exception as e:
            info["tables"][tbl] = {"exists": False, "error": str(e)[:200]}
    # Prueba de escritura autolimpiante por tabla: inserta y borra una fila
    # centinela. Detecta RLS/constraints que bloquean writes aunque los reads pasen.
    probe_tests = {
        "pacientes": ({"nombre_completo": "DEBUG_PROBE", "dni": "DEBUG_PROBE_TMP"}, {"dni": "DEBUG_PROBE_TMP"}),
        "evaluaciones_clinicas": ({"observaciones": "DEBUG_PROBE"}, {"observaciones": "DEBUG_PROBE"}),
        "anamnesis": ({"motivo_consulta": "DEBUG_PROBE"}, {"motivo_consulta": "DEBUG_PROBE"}),
        "analisis_acusticos": ({"modo": "DEBUG_PROBE"}, {"modo": "DEBUG_PROBE"}),
        "turnos": ({"fecha_hora": "2030-01-01T00:00:00", "motivo": "DEBUG_PROBE"}, {"motivo": "DEBUG_PROBE"}),
        "usuarios_google": ({"google_id": "DEBUG_PROBE", "email": "debug@probe.local"}, {"google_id": "DEBUG_PROBE"}),
        "sesiones_teleconsulta": ({"notas": "DEBUG_PROBE"}, {"notas": "DEBUG_PROBE"}),
    }
    probe: dict = {}
    for tbl, (payload, delfilter) in probe_tests.items():
        res: dict = {"insert_ok": False, "delete_ok": False}
        try:
            ins = supabase.table(tbl).insert(payload).execute()
            res["insert_ok"] = bool(ins.data)
            try:
                q = supabase.table(tbl).delete()
                for k, v in delfilter.items():
                    q = q.eq(k, v)
                q.execute()
                res["delete_ok"] = True
            except Exception as e_del:
                res["delete_error"] = str(e_del)[:200]
        except Exception as e_ins:
            res["insert_error"] = str(e_ins)[:300]
        probe[tbl] = res
    info["write_probe"] = probe
    return JSONResponse(content=info)