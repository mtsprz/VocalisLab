"""VocalisLab — Vocalis Companion: sesiones offline + evolución de voz.

Prefijo: /api/companion. Estilo del repo (Form/JSONResponse, service_role,
tolerancia a columnas faltantes). Auth Companion = Bearer device_token
(hash SHA-256 en companion_devices). Endpoints web usan google_id como el
resto de la app. Contrato completo: docs/companion-api.md
"""
import hashlib
import json
import os
import re
import secrets
import shutil
import tempfile
import threading
import time
import traceback
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, Request
from fastapi.responses import JSONResponse, FileResponse

router = APIRouter()

supabase = None
try:
    from supabase import create_client
    _SB_URL = os.environ.get("SUPABASE_URL", "")
    _SB_KEY = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))
    if _SB_URL and _SB_KEY:
        supabase = create_client(_SB_URL, _SB_KEY)
except Exception:
    pass


def _sb():
    return supabase


# ─── Config ───
TASKS = ("vocal_sostenida_a", "conteo", "lectura", "conversacion_espontanea")
SPEAKERS = ("paciente", "fonoaudiologo")
BUCKET = "companion-audio-vault"
MAX_BYTES = 45 * 1024 * 1024
MIMES = {"audio/mp4": "m4a", "audio/x-m4a": "m4a", "audio/mpeg": "mp3",
         "audio/wav": "wav", "audio/x-wav": "wav", "audio/webm": "webm",
         "audio/ogg": "ogg", "audio/aac": "aac"}
CHUNK_TRANSCRIBE_BYTES = 20 * 1024 * 1024


def _env(n, d=""):
    return os.environ.get(n, d)


def _ai_provider():
    return _env("AI_PROVIDER", "gemini").strip().lower() or "gemini"


def _ai_model():
    return _env("AI_MODEL", "gemini-2.0-flash").strip() or "gemini-2.0-flash"


def _external_audio_ok():
    return _env("AI_EXTERNAL_AUDIO_ENABLED", "true").strip().lower() in ("1", "true", "yes")


def _profesional_env():
    return _env("PROFESIONAL_GOOGLE_ID", "").strip()


# ─── Auth ───
def _sha256(s: str) -> str:
    return hashlib.sha256((s or "").encode()).hexdigest()


def _device_from_bearer(request: Request) -> dict:
    auth = (request.headers.get("authorization") or "").strip()
    token = auth[7:] if auth.lower().startswith("bearer ") else ""
    if not token:
        raise HTTPException(status_code=401, detail="Falta Authorization: Bearer")
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    try:
        res = sb.table("companion_devices").select("*").eq("token_hash", _sha256(token)).execute()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Error de base: {e}")
    rows = res.data or []
    if not rows:
        raise HTTPException(status_code=401, detail="Token inválido")
    dev = rows[0]
    if dev.get("revoked"):
        raise HTTPException(status_code=401, detail="Dispositivo revocado")
    try:
        sb.table("companion_devices").update({"last_seen_at": _now_iso()}).eq("id", dev["id"]).execute()
    except Exception:
        pass
    return dev


def _require_profesional(user_id: str) -> str:
    uid = (user_id or "").strip()
    if not uid:
        raise HTTPException(status_code=401, detail="user_id requerido")
    only = _profesional_env()
    if only and uid != only:
        raise HTTPException(status_code=403, detail="Profesional no habilitado")
    return uid


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _pairing_code(n=6):
    alfabeto = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    return "".join(secrets.choice(alfabeto) for _ in range(n))


# ─── Métricas: validación pura (testeable) ───
def _semitones_stats(frames: list, ref_hz: float):
    """(sd_st, mean, median) desde serie por trama; 0/None = sordo (se ignoran)."""
    import math
    vals = [float(f) for f in (frames or []) if f and float(f) > 0]
    if not vals or not ref_hz or ref_hz <= 0:
        return None, None, None
    sts = [12 * math.log2(v / ref_hz) for v in vals]
    n = len(sts)
    mean = sum(sts) / n
    srt = sorted(sts)
    median = srt[n // 2] if n % 2 else (srt[n // 2 - 1] + srt[n // 2]) / 2
    sd = (sum((x - mean) ** 2 for x in sts) / n) ** 0.5
    fmean = sum(vals) / n
    fsrt = sorted(vals)
    fmedian = fsrt[n // 2] if n % 2 else (fsrt[n // 2 - 1] + fsrt[n // 2]) / 2
    return sd, fmean, fmedian


def _pct(vals: list, p: float):
    if not vals:
        return None
    s = sorted(vals)
    k = max(0, min(len(s) - 1, int(round((p / 100) * (len(s) - 1)))))
    return s[k]


def _validar_acustica_row(a: dict) -> tuple:
    """(validada: bool, notas: list). Recalcula desde histograma+contorno y
    compara con lo informado. Nunca sobrescribe: solo marca."""
    notas = []
    try:
        hist = a.get("f0_histogram") or {}
        cont = a.get("f0_contour") or []
        ref = float(hist.get("ref_hz") or 0)
        bins = hist.get("bins") or {}
        # Expandir histograma a serie sintética (centro de cada bin)
        serie = []
        for k, c in bins.items():
            try:
                st, n = float(k), int(c)
            except Exception:
                continue
            if ref > 0 and n > 0:
                import math
                serie.extend([ref * (2 ** (st / 12))] * min(n, 5000))
        # Sumar contorno (tramas sonoras)
        serie.extend([float(f) for f in cont if f and float(f) > 0][:20000])
        if not serie or ref <= 0:
            return True, ["sin histograma/contorno: no validable, se acepta"]
        sd_st, fmean, fmedian = _semitones_stats(serie, ref)
        tol = lambda rep, rec, t: (rep is None or rec is None or
                                   (abs(rep - rec) <= abs(rec) * t if rec else rep == rec))
        ok = True
        if not tol(a.get("f0_mean_hz"), fmean, 0.03):
            ok = False
            notas.append("media inconsistente con histograma/contorno")
        if not tol(a.get("f0_median_hz"), fmedian, 0.03):
            ok = False
            notas.append("mediana inconsistente con histograma/contorno")
        for campo, pv in (("f0_p5_hz", 5), ("f0_p95_hz", 95)):
            rep = a.get(campo)
            if rep is not None:
                import math as _m
                rec = _pct(serie, pv)
                # tolerancia: ±1 semitono
                if rec and not (rec / (2 ** (1 / 12)) <= rep <= rec * (2 ** (1 / 12))):
                    ok = False
                    notas.append(f"{campo} fuera de ±1 semitono")
        rep_sd = a.get("f0_sd_semitones")
        if rep_sd is not None and sd_st is not None and sd_st > 0:
            if abs(rep_sd - sd_st) > sd_st * 0.10 + 0.05:
                ok = False
                notas.append("SD en semitonos inconsistente (>10%)")
        return ok, notas
    except Exception as e:
        return True, [f"validación omitida: {e}"]


def _backoff(attempts: int) -> datetime:
    mins = [1, 5, 15, 60, 240][min(max(attempts - 1, 0), 4)]
    return datetime.now(timezone.utc) + timedelta(minutes=mins)


# ─── Referencia aplicable ───
def _edad(fecha_nac: str):
    try:
        if not fecha_nac:
            return None
        d = datetime.fromisoformat(str(fecha_nac)[:10])
        hoy = datetime.now(timezone.utc).date()
        return hoy.year - d.year - ((hoy.month, hoy.day) < (d.month, d.day))
    except Exception:
        return None


def _elegir_referencia(paciente: dict, rangos: list) -> dict:
    """Override del paciente > rango por sexo/edad. Sin rango: gris."""
    try:
        omin = paciente.get("f0_ref_min_hz")
        omax = paciente.get("f0_ref_max_hz")
        if omin and omax:
            return {"sexo": paciente.get("sexo_referencia") or paciente.get("sexo") or "—",
                    "edad": _edad(paciente.get("fecha_nacimiento")), "min_hz": omin,
                    "max_hz": omax, "origen": "override del paciente"}
    except Exception:
        pass
    sexo = ((paciente.get("sexo_referencia") or paciente.get("sexo")) or "").strip().lower()
    edad = _edad(paciente.get("fecha_nacimiento"))
    cand = None
    if edad is not None and 4 <= edad <= 10:
        cand = next((r for r in rangos if r.get("sexo_referencia") == "ninex"), None)
    elif sexo.startswith("masc"):
        cand = next((r for r in rangos if r.get("sexo_referencia") == "masculino"), None)
    elif sexo.startswith("fem"):
        cand = next((r for r in rangos if r.get("sexo_referencia") == "femenino"), None)
    else:
        cand = next((r for r in rangos if r.get("sexo_referencia") == "masculino"), None)
    if not cand:
        return {"sexo": sexo or "—", "edad": edad, "min_hz": None,
                "max_hz": None, "origen": "sin referencia"}
    return {"sexo": cand["sexo_referencia"], "edad": edad,
            "min_hz": cand.get("f0_min_hz"), "max_hz": cand.get("f0_max_hz"),
            "origen": cand.get("fuente") or "tabla"}


# ═══ ENDPOINTS ═══
@router.get("/api/companion/health")
async def companion_health():
    sb = _sb()
    q = {"queued": 0, "processing": 0}
    if sb:
        try:
            r = sb.table("processing_jobs").select("status").in_("status", ["queued", "processing"]).execute()
            for row in (r.data or []):
                if row.get("status") in q:
                    q[row["status"]] += 1
        except Exception:
            pass
    return JSONResponse(content={"ok": True, "queue": q})


@router.post("/api/companion/pairing-code")
async def crear_pairing_code(user_id: str = ""):
    _require_profesional(user_id)
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    code = _pairing_code()
    exp = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    try:
        sb.table("companion_pairing_codes").insert({
            "code": code, "profesional_google_id": user_id.strip(),
            "expires_at": exp}).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo generar: {e}")
    return JSONResponse(content={"ok": True, "code": code, "expires_at": exp})


@router.post("/api/companion/pair")
async def pair_device(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    code = str(body.get("code", "")).strip().upper()
    name = str(body.get("device_name", "")).strip()[:80]
    if not code:
        raise HTTPException(status_code=400, detail="code requerido")
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    try:
        r = sb.table("companion_pairing_codes").select("*").eq("code", code).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error de base: {e}")
    rows = r.data or []
    if not rows:
        raise HTTPException(status_code=401, detail="Código inválido")
    pc = rows[0]
    if pc.get("used"):
        raise HTTPException(status_code=401, detail="Código ya usado")
    try:
        exp = datetime.fromisoformat(str(pc.get("expires_at", "")).replace("Z", "+00:00"))
        if exp < datetime.now(timezone.utc):
            raise HTTPException(status_code=401, detail="Código vencido")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Código inválido")
    token = secrets.token_urlsafe(32)
    try:
        d = sb.table("companion_devices").insert({
            "profesional_google_id": pc["profesional_google_id"],
            "device_name": name or "Companion",
            "token_hash": _sha256(token)}).execute()
        dev_id = (d.data or [{}])[0].get("id")
        sb.table("companion_pairing_codes").update(
            {"used": True, "used_at": _now_iso(), "used_by_device_id": dev_id})\
            .eq("id", pc["id"]).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo emparejar: {e}")
    return JSONResponse(content={"ok": True, "device_token": token,
                                 "device_id": dev_id,
                                 "aviso": "Guardalo ahora: no se vuelve a mostrar"})


@router.get("/api/companion/devices")
async def listar_devices(user_id: str = ""):
    uid = _require_profesional(user_id)
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    r = sb.table("companion_devices").select(
        "id, profesional_google_id, device_name, created_at, last_seen_at, revoked, revoked_at")\
        .eq("profesional_google_id", uid).order("created_at", desc=True).execute()
    return JSONResponse(content={"ok": True, "devices": r.data or []})


@router.delete("/api/companion/devices/{device_id}")
async def revocar_device(device_id: str, user_id: str = ""):
    uid = _require_profesional(user_id)
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    sb.table("companion_devices").update({"revoked": True, "revoked_at": _now_iso()})\
        .eq("id", device_id).eq("profesional_google_id", uid).execute()
    return JSONResponse(content={"ok": True, "device_id": device_id, "revoked": True})


def _mime_ext(mime: str) -> str:
    return MIMES.get((mime or "").strip().lower().split(";")[0], "")


def _cuota_ok(sb, size_bytes: int) -> tuple:
    try:
        quota = int(_env("STORAGE_QUOTA_BYTES", "1000000000"))
    except Exception:
        quota = 1000000000
    usado = 0
    try:
        r = sb.table("companion_sessions").select("audio_size_bytes").execute()
        usado += sum(int(x.get("audio_size_bytes") or 0) for x in (r.data or []))
        c = sb.table("session_clips").select("size_bytes").execute()
        usado += sum(int(x.get("size_bytes") or 0) for x in (c.data or []))
    except Exception:
        pass
    return (usado + int(size_bytes or 0) <= quota), usado, quota


@router.post("/api/companion/uploads")
async def firmar_upload(request: Request):
    dev = _device_from_bearer(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    dsid = str(body.get("device_session_id", "")).strip()
    kind = str(body.get("kind", "session_audio")).strip()
    task = str(body.get("task_type", "") or "").strip()
    mime = str(body.get("mime", "")).strip()
    try:
        size = int(body.get("size_bytes") or 0)
    except Exception:
        size = 0
    part = body.get("part_index")
    total = body.get("part_total")
    if not dsid:
        raise HTTPException(status_code=400, detail="device_session_id requerido")
    if kind not in ("session_audio", "clip"):
        raise HTTPException(status_code=400, detail="kind inválido")
    if kind == "clip" and task not in TASKS:
        raise HTTPException(status_code=400, detail="task_type requerido para clip")
    ext = _mime_ext(mime)
    if not ext:
        raise HTTPException(status_code=400, detail=f"mime no soportado: {mime}")
    if size <= 0 or size > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Tamaño inválido (máx 45 MB por archivo)")
    sb = _sb()
    ok_quota, usado, quota = _cuota_ok(sb, size)
    if not ok_quota:
        raise HTTPException(status_code=507, detail=f"Cuota excedida ({usado}/{quota} bytes)")
    if kind == "session_audio":
        base = f"{dsid}.{ext}"
    else:
        base = f"{dsid}/clips/{task}.{ext}"
    path = base
    if total and int(total or 0) > 1:
        try:
            pi = int(part or 0)
        except Exception:
            raise HTTPException(status_code=400, detail="part_index inválido")
        path = f"{base}.part{pi}"
    full = f"vault/{path}"
    try:
        signed = sb.storage.from_(BUCKET).create_signed_upload_url(full)
        url = signed.get("signedURL") or signed.get("signedUrl") or signed.get("signed_url") or ""
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo firmar: {e}")
    return JSONResponse(content={"ok": True, "upload_url": url, "path": full,
                                 "expires_in": 3600})


def _storage_exists(sb, path: str) -> bool:
    try:
        parent = path.rsplit("/", 1)[0] if "/" in path else ""
        items = sb.storage.from_(BUCKET).list(parent) or []
        base = path.rsplit("/", 1)[-1]
        return any((it.get("name") == base) for it in items if isinstance(it, dict))
    except Exception:
        return False


def _encolar_job(sb, session_id: str):
    try:
        sb.table("processing_jobs").upsert(
            {"session_id": session_id, "status": "queued",
             "next_retry_at": _now_iso(), "last_error": ""},
            on_conflict="session_id").execute()
    except Exception as e:
        print(f"[companion] no se pudo encolar {session_id}: {e}")


@router.post("/api/companion/uploads/confirm")
async def confirmar_upload(request: Request):
    dev = _device_from_bearer(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    dsid = str(body.get("device_session_id", "")).strip()
    kind = str(body.get("kind", "session_audio")).strip()
    task = str(body.get("task_type", "") or "").strip()
    reprocesar = bool(body.get("reprocesar", False))
    if not dsid:
        raise HTTPException(status_code=400, detail="device_session_id requerido")
    sb = _sb()
    r = sb.table("companion_sessions").select("*").eq("device_session_id", dsid).execute()
    rows = r.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Sesión inexistente: creala primero con POST /sessions")
    ses = rows[0]
    if ses.get("profesional_google_id") != dev.get("profesional_google_id"):
        raise HTTPException(status_code=403, detail="Sesión de otro profesional")
    total = body.get("part_total")
    if total and int(total or 0) > 1:
        _unir_partes(sb, ses, kind, task, int(total))
    else:
        if kind == "session_audio":
            path = ses.get("audio_storage_path", "")
            if not path or not _storage_exists(sb, path):
                raise HTTPException(status_code=422, detail="Audio incompleto: el archivo no está en Storage")
            try:
                size = int(body.get("size_bytes") or ses.get("audio_size_bytes") or 0)
                sb.table("companion_sessions").update(
                    {"audio_size_bytes": size, "status": "uploaded", "error_detail": ""})\
                    .eq("id", ses["id"]).execute()
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"No se pudo confirmar: {e}")
        else:
            c = sb.table("session_clips").select("*").eq("session_id", ses["id"])\
                .eq("task_type", task).execute()
            crows = c.data or []
            if not crows or not _storage_exists(sb, crows[0].get("storage_path", "")):
                raise HTTPException(status_code=422, detail="Clip incompleto en Storage")
    if ses.get("status") == "processed" and not reprocesar:
        raise HTTPException(status_code=409, detail="Sesión ya procesada (usá reprocesar:true)")
    sb.table("companion_sessions").update({"status": "uploaded", "error_detail": ""})\
        .eq("id", ses["id"]).execute()
    _encolar_job(sb, ses["id"])
    return JSONResponse(content={"ok": True, "session_id": ses["id"], "status": "uploaded"})


def _unir_partes(sb, ses: dict, kind: str, task: str, total: int):
    """Concatena partes numeradas (rangos de bytes en orden) vía /tmp y resube."""
    if kind == "session_audio":
        base = ses.get("audio_storage_path", "")
    else:
        c = sb.table("session_clips").select("*").eq("session_id", ses["id"])\
            .eq("task_type", task).execute()
        crows = c.data or []
        if not crows:
            raise HTTPException(status_code=422, detail="Clip inexistente para unir partes")
        base = crows[0].get("storage_path", "")
    if not base:
        raise HTTPException(status_code=422, detail="Sin path base para unir")
    tmp = tempfile.NamedTemporaryFile(delete=False)
    try:
        with open(tmp.name, "wb") as out:
            for i in range(total):
                part = f"{base}.part{i}"
                try:
                    data = sb.storage.from_(BUCKET).download(part)
                except Exception:
                    raise HTTPException(status_code=422,
                                        detail=f"Parte incompleta: falta {part} ({i + 1}/{total})")
                out.write(data if isinstance(data, (bytes, bytearray)) else bytes(data))
        with open(tmp.name, "rb") as f:
            sb.storage.from_(BUCKET).upload(base, f.read(), {"upsert": "true"})
        for i in range(total):
            try:
                sb.storage.from_(BUCKET).remove([f"{base}.part{i}"])
            except Exception:
                pass
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def _validar_segmentos(segs: list, dur: float):
    if not isinstance(segs, list) or not segs:
        raise HTTPException(status_code=400, detail="segments requerido (no vacío)")
    for i, s in enumerate(segs):
        if not isinstance(s, dict):
            raise HTTPException(status_code=400, detail=f"segments[{i}] inválido")
        if s.get("task_type") not in TASKS:
            raise HTTPException(status_code=400, detail=f"segments[{i}].task_type inválido")
        if s.get("speaker") not in SPEAKERS:
            raise HTTPException(status_code=400, detail=f"segments[{i}].speaker inválido")
        try:
            a, b = float(s.get("start_sec")), float(s.get("end_sec"))
        except Exception:
            raise HTTPException(status_code=400, detail=f"segments[{i}] tiempos inválidos")
        if not (b > a >= 0):
            raise HTTPException(status_code=400, detail=f"segments[{i}] rango inválido")
        if dur and a > dur:
            raise HTTPException(status_code=422, detail=f"segments[{i}] fuera de la duración")


@router.post("/api/companion/sessions")
async def crear_sesion(request: Request):
    dev = _device_from_bearer(request)
    try:
        body = await request.json()
    except Exception:
        body = {}
    dsid = str(body.get("device_session_id", "")).strip()
    patient_id = str(body.get("patient_id", "")).strip()
    if not dsid or not patient_id:
        raise HTTPException(status_code=400, detail="device_session_id y patient_id requeridos")
    sb = _sb()
    try:
        p = sb.table("pacientes").select("id").eq("id", patient_id).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error de base: {e}")
    if not (p.data or []):
        raise HTTPException(status_code=404, detail="Paciente inexistente")
    try:
        dur = float(body.get("audio_duration_sec") or 0)
    except Exception:
        dur = 0
    segs = body.get("segments", []) or []
    _validar_segmentos(segs, dur)
    acs = body.get("acoustics", []) or []
    if not isinstance(acs, list):
        raise HTTPException(status_code=400, detail="acoustics inválido")
    avisos = []
    filas_ac = []
    for i, a in enumerate(acs):
        if not isinstance(a, dict) or a.get("task_type") not in TASKS:
            raise HTTPException(status_code=422, detail=f"acoustics[{i}].task_type inválido")
        if a.get("task_type") != "vocal_sostenida_a":
            for k in ("jitter_pct", "shimmer_pct", "hnr_db", "mpt_sec"):
                if a.get(k) is not None:
                    avisos.append(f"acoustics[{i}].{k} ignorado (solo vocal sostenida)")
                    a[k] = None
        ok, notas = _validar_acustica_row(a)
        if not ok:
            avisos.append(f"acoustics[{i}] no validada: {'; '.join(notas)}")
        filas_ac.append({
            "task_type": a["task_type"],
            "f0_mean_hz": a.get("f0_mean_hz"), "f0_median_hz": a.get("f0_median_hz"),
            "f0_sd_hz": a.get("f0_sd_hz"), "f0_sd_semitones": a.get("f0_sd_semitones"),
            "f0_p5_hz": a.get("f0_p5_hz"), "f0_p95_hz": a.get("f0_p95_hz"),
            "f0_min_hz": a.get("f0_min_hz"), "f0_max_hz": a.get("f0_max_hz"),
            "voiced_fraction": a.get("voiced_fraction"),
            "intensity_mean_db": a.get("intensity_mean_db"),
            "intensity_sd_db": a.get("intensity_sd_db"),
            "mpt_sec": a.get("mpt_sec"), "jitter_pct": a.get("jitter_pct"),
            "shimmer_pct": a.get("shimmer_pct"), "hnr_db": a.get("hnr_db"),
            "f0_histogram": a.get("f0_histogram") or {},
            "f0_contour": a.get("f0_contour") or [],
            "dsp_version": str(a.get("dsp_version", "") or "")[:60],
            "validada": ok,
        })
    info = body.get("device_info", {}) or {}
    if not isinstance(info, dict):
        raise HTTPException(status_code=400, detail="device_info inválido")
    fila = {
        "patient_id": patient_id,
        "profesional_google_id": dev["profesional_google_id"],
        "device_id": dev["id"],
        "device_session_id": dsid,
        "recorded_at": body.get("recorded_at"),
        "audio_duration_sec": dur or None,
        "audio_codec": str(body.get("audio_codec", "") or "")[:20],
        "audio_bitrate_kbps": body.get("audio_bitrate_kbps"),
        "dsp_version": str(body.get("dsp_version", "") or "")[:60],
        "device_info": info,
        "consent_recorded": bool(body.get("consent_recorded", False)),
    }
    try:
        r = sb.table("companion_sessions").upsert(fila, on_conflict="device_session_id").execute()
        ses = (r.data or [{}])[0]
        sid = ses.get("id")
        if not sid:
            q = sb.table("companion_sessions").select("id").eq("device_session_id", dsid).execute()
            sid = (q.data or [{}])[0].get("id")
        sb.table("session_segments").delete().eq("session_id", sid).execute()
        for s in segs:
            sb.table("session_segments").insert({
                "session_id": sid, "task_type": s["task_type"], "speaker": s["speaker"],
                "start_sec": float(s["start_sec"]), "end_sec": float(s["end_sec"])}).execute()
        for a in filas_ac:
            sb.table("session_acoustics").upsert(
                dict(a, session_id=sid), on_conflict="session_id,task_type").execute()
        for c in (body.get("clips", []) or []):
            if isinstance(c, dict) and c.get("task_type") in TASKS:
                sb.table("session_clips").insert({
                    "session_id": sid, "task_type": c["task_type"],
                    "storage_path": f"vault/{dsid}/clips/{c['task_type']}.wav",
                    "duration_sec": c.get("duration_sec")}).execute()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo guardar: {e}")
    return JSONResponse(content={"ok": True, "session_id": sid, "status": "uploaded",
                                 "avisos": avisos})


def _sesion_de_profesional(sb, session_id: str, prof: str) -> dict:
    try:
        r = sb.table("companion_sessions").select("*").eq("id", session_id).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error de base: {e}")
    rows = r.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Sesión inexistente")
    if rows[0].get("profesional_google_id") != prof:
        raise HTTPException(status_code=403, detail="Sesión de otro profesional")
    return rows[0]


@router.get("/api/companion/sessions")
async def listar_sesiones(request: Request, patient_id: str = ""):
    dev = _device_from_bearer(request)
    if not patient_id:
        raise HTTPException(status_code=400, detail="patient_id requerido")
    sb = _sb()
    r = sb.table("companion_sessions").select(
        "id, device_session_id, recorded_at, synced_at, audio_duration_sec, audio_codec,"
        "audio_bitrate_kbps, status, dsp_version, consent_recorded, error_detail, created_at")\
        .eq("patient_id", patient_id)\
        .eq("profesional_google_id", dev["profesional_google_id"])\
        .order("recorded_at", desc=True).execute()
    return JSONResponse(content={"ok": True, "sessions": r.data or []})


@router.get("/api/companion/sessions/{session_id}")
async def detalle_sesion(request: Request, session_id: str):
    dev = _device_from_bearer(request)
    sb = _sb()
    ses = _sesion_de_profesional(sb, session_id, dev["profesional_google_id"])
    segs = sb.table("session_segments").select("*").eq("session_id", session_id)\
        .order("start_sec").execute()
    acs = sb.table("session_acoustics").select("*").eq("session_id", session_id).execute()
    trs = sb.table("session_transcripts").select("*").eq("session_id", session_id)\
        .order("start_sec").execute()
    dr = sb.table("anamnesis_drafts").select("*").eq("session_id", session_id).execute()
    jb = sb.table("processing_jobs").select("status, attempts, next_retry_at, last_error")\
        .eq("session_id", session_id).execute()
    clips = sb.table("session_clips").select("id, task_type, storage_path, size_bytes, duration_sec")\
        .eq("session_id", session_id).execute()
    return JSONResponse(content={"ok": True, "sesion": ses,
                                 "segmentos": (segs.data or []),
                                 "acustica": (acs.data or []),
                                 "transcripciones": (trs.data or []),
                                 "borrador": ((dr.data or [None])[0]),
                                 "job": ((jb.data or [None])[0]),
                                 "clips": (clips.data or [])})


@router.get("/api/companion/sessions/{session_id}/audio-url")
async def audio_url(request: Request, session_id: str, clip: str = ""):
    dev = _device_from_bearer(request)
    sb = _sb()
    ses = _sesion_de_profesional(sb, session_id, dev["profesional_google_id"])
    if clip:
        c = sb.table("session_clips").select("*").eq("id", clip)\
            .eq("session_id", session_id).execute()
        if not (c.data or []):
            raise HTTPException(status_code=404, detail="Clip inexistente")
        path = c.data[0].get("storage_path", "")
        que = f"clip:{clip}"
    else:
        path = ses.get("audio_storage_path", "")
        que = "audio principal"
    if not path:
        raise HTTPException(status_code=404, detail="Audio no disponible (purgado o sin subir)")
    try:
        signed = sb.storage.from_(BUCKET).create_signed_url(path, 900)
        url = signed.get("signedURL") or signed.get("signedUrl") or signed.get("signed_url") or ""
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo firmar: {e}")
    try:
        sb.table("audio_access_log").insert({
            "session_id": session_id,
            "actor": dev.get("device_name") or dev.get("id", ""),
            "accion": f"url_firmada:{que}"}).execute()
    except Exception:
        pass
    return JSONResponse(content={"ok": True, "url": url, "expires_in": 900})


def _rangos(sb) -> list:
    try:
        r = sb.table("reference_ranges").select("*").execute()
        return r.data or []
    except Exception:
        return []


@router.get("/api/companion/referencias")
async def referencias(request: Request, sexo: str = "", edad: str = ""):
    _device_from_bearer(request)
    sb = _sb()
    return JSONResponse(content={"ok": True, "rangos": _rangos(sb)})


@router.get("/api/companion/progreso")
async def progreso(request: Request, patient_id: str = ""):
    dev = _device_from_bearer(request)
    if not patient_id:
        raise HTTPException(status_code=400, detail="patient_id requerido")
    sb = _sb()
    try:
        p = sb.table("pacientes").select("id").eq("id", patient_id).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error de base: {e}")
    if not (p.data or []):
        raise HTTPException(status_code=404, detail="Paciente inexistente")
    try:
        r = sb.table("voice_progress").select("*").eq("patient_id", patient_id)\
            .order("task_type").order("session_number").execute()
        serie = r.data or []
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo leer progreso: {e}")
    own = [s for s in serie]
    if serie:
        try:
            ids = {s.get("session_id") for s in serie if s.get("session_id")}
            chk = sb.table("companion_sessions").select("id")\
                .in_("id", list(ids))\
                .eq("profesional_google_id", dev["profesional_google_id"]).execute()
            ok_ids = {x.get("id") for x in (chk.data or [])}
            own = [s for s in serie if s.get("session_id") in ok_ids]
        except Exception:
            own = []
    return JSONResponse(content={"ok": True, "serie": own})


@router.get("/api/companion/almacenamiento")
async def almacenamiento(user_id: str = ""):
    _require_profesional(user_id)
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    usado, n = 0, 0
    try:
        r = sb.table("companion_sessions").select("audio_size_bytes").execute()
        for x in (r.data or []):
            if x.get("audio_size_bytes"):
                usado += int(x["audio_size_bytes"])
                n += 1
        c = sb.table("session_clips").select("size_bytes").execute()
        usado += sum(int(x.get("size_bytes") or 0) for x in (c.data or []))
    except Exception:
        pass
    try:
        quota = int(_env("STORAGE_QUOTA_BYTES", "1000000000"))
    except Exception:
        quota = 1000000000
    return JSONResponse(content={"ok": True, "used_bytes": usado,
                                 "quota_bytes": quota, "sessions_count": n})


@router.post("/api/companion/mantenimiento/purgar")
async def purgar(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    uid = _require_profesional(str(body.get("user_id", "")))
    if body.get("confirmar") is not True:
        raise HTTPException(status_code=400, detail="Falta confirmar:true")
    ids = body.get("session_ids", []) or []
    if not isinstance(ids, list) or not ids:
        raise HTTPException(status_code=400, detail="session_ids requerido")
    sb = _sb()
    borrados, errores = [], []
    for sid in ids:
        try:
            ses = _sesion_de_profesional(sb, str(sid), uid)
            paths = []
            if ses.get("audio_storage_path"):
                paths.append(ses["audio_storage_path"])
            clips = sb.table("session_clips").select("storage_path")\
                .eq("session_id", ses["id"]).execute()
            paths.extend([c.get("storage_path", "") for c in (clips.data or []) if c.get("storage_path")])
            for pth in set(paths):
                try:
                    sb.storage.from_(BUCKET).remove([pth])
                except Exception:
                    pass
            sb.table("companion_sessions").update(
                {"audio_storage_path": None, "audio_size_bytes": None})\
                .eq("id", ses["id"]).execute()
            sb.table("audio_access_log").insert({
                "session_id": ses["id"], "actor": uid, "accion": "purga_archivos"}).execute()
            borrados.append(ses["id"])
        except HTTPException as e:
            errores.append({"id": sid, "error": e.detail})
        except Exception as e:
            errores.append({"id": sid, "error": str(e)[:150]})
    return JSONResponse(content={"ok": True, "purgadas": borrados, "errores": errores})


# ─── Borradores de anamnesis ───
def _missing_column(msg: str):
    import re as _re
    m = _re.search(r"Could not find the '([^']+)' column", str(msg or ""))
    return m.group(1) if m else ""


@router.get("/api/companion/anamnesis-drafts/{session_id}")
async def leer_borrador(session_id: str, user_id: str = ""):
    uid = _require_profesional(user_id)
    sb = _sb()
    ses = _sesion_de_profesional(sb, session_id, uid)
    r = sb.table("anamnesis_drafts").select("*").eq("session_id", ses["id"]).execute()
    rows = r.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Sin borrador para esta sesión")
    return JSONResponse(content={"ok": True, "borrador": rows[0]})


@router.put("/api/companion/anamnesis-drafts/{session_id}")
async def editar_borrador(session_id: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    uid = _require_profesional(str(body.get("user_id", "")))
    sb = _sb()
    ses = _sesion_de_profesional(sb, session_id, uid)
    campos = {}
    for k in ("motivo_consulta", "sintomatologia_vocal", "habitos_vocales",
              "observaciones_clinicas", "plan_sugerido"):
        if k in body:
            campos[k] = str(body.get(k) or "")
    if not campos:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    campos["updated_at"] = _now_iso()
    try:
        r = sb.table("anamnesis_drafts").update(campos).eq("session_id", ses["id"]).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo guardar: {e}")
    if not (r.data or []):
        raise HTTPException(status_code=404, detail="Sin borrador para esta sesión")
    return JSONResponse(content={"ok": True, "borrador": r.data[0]})


@router.post("/api/companion/anamnesis-drafts/{session_id}/descartar")
async def descartar_borrador(session_id: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    uid = _require_profesional(str(body.get("user_id", "")))
    sb = _sb()
    ses = _sesion_de_profesional(sb, session_id, uid)
    sb.table("anamnesis_drafts").update({"status": "discarded", "updated_at": _now_iso()})\
        .eq("session_id", ses["id"]).execute()
    return JSONResponse(content={"ok": True, "status": "discarded"})


@router.post("/api/companion/anamnesis-drafts/{session_id}/aprobar")
async def aprobar_borrador(session_id: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    uid = _require_profesional(str(body.get("user_id", "")))
    sb = _sb()
    ses = _sesion_de_profesional(sb, session_id, uid)
    r = sb.table("anamnesis_drafts").select("*").eq("session_id", ses["id"]).execute()
    rows = r.data or []
    if not rows:
        raise HTTPException(status_code=404, detail="Sin borrador para esta sesión")
    dr = rows[0]
    if dr.get("status") == "approved":
        raise HTTPException(status_code=409, detail="Borrador ya aprobado")
    try:
        fecha_ses = (ses.get("recorded_at") or ses.get("created_at") or "")[:10]
    except Exception:
        fecha_ses = ""
    bloque = (f"\n\n[Sesión {fecha_ses}] Motivo: {dr.get('motivo_consulta', '')} · "
              f"Síntomas: {dr.get('sintomatologia_vocal', '')} · "
              f"Hábitos: {dr.get('habitos_vocales', '')} · "
              f"Observaciones: {dr.get('observaciones_clinicas', '')} · "
              f"Plan sugerido: {dr.get('plan_sugerido', '')}").strip()
    try:
        cur = sb.table("anamnesis").select("*").eq("paciente_id", ses["patient_id"])\
            .order("fecha", desc=True).limit(1).execute()
        vigente = (cur.data or [None])[0]
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo leer anamnesis: {e}")
    try:
        if vigente:
            upd = {"resumen_clinico": ((vigente.get("resumen_clinico") or "") + bloque).strip()}
            if not (vigente.get("motivo_consulta") or "").strip() and dr.get("motivo_consulta"):
                upd["motivo_consulta"] = dr["motivo_consulta"]
            for _ in range(4):
                try:
                    sb.table("anamnesis").update(upd).eq("id", vigente["id"]).execute()
                    break
                except Exception as e_upd:
                    col = _missing_column(str(e_upd))
                    if col and col in upd:
                        upd.pop(col, None)
                        continue
                    raise
            anam_id = vigente["id"]
        else:
            ins = {"paciente_id": ses["patient_id"],
                   "motivo_consulta": dr.get("motivo_consulta", ""),
                   "resumen_clinico": bloque}
            for _ in range(4):
                try:
                    rr = sb.table("anamnesis").insert(ins).execute()
                    anam_id = (rr.data or [{}])[0].get("id")
                    break
                except Exception as e_ins:
                    col = _missing_column(str(e_ins))
                    if col and col in ins:
                        ins.pop(col, None)
                        continue
                    raise
        sb.table("anamnesis_drafts").update(
            {"status": "approved", "approved_at": _now_iso(), "updated_at": _now_iso()})\
            .eq("session_id", ses["id"]).execute()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"No se pudo volcar: {e}")
    return JSONResponse(content={"ok": True, "status": "approved", "anamnesis_id": anam_id})


# ─── Informes PDF ───
def _datos_sesion_pdf(sb, ses: dict) -> dict:
    acs = sb.table("session_acoustics").select("*").eq("session_id", ses["id"]).execute()
    pac = sb.table("pacientes").select(
        "id, nombre_completo, sexo, sexo_referencia, fecha_nacimiento")\
        .eq("id", ses["patient_id"]).execute()
    p = (pac.data or [{}])[0]
    ref = _elegir_referencia(p, _rangos(sb))
    mets = []
    for a in (acs.data or []):
        mets.append({k: a.get(k) for k in (
            "task_type", "f0_median_hz", "f0_sd_semitones", "intensity_mean_db",
            "jitter_pct", "shimmer_pct", "hnr_db", "mpt_sec")})
    try:
        fecha = (ses.get("recorded_at") or "")[:10]
    except Exception:
        fecha = ""
    return {"paciente": p.get("nombre_completo", "—"), "fecha": fecha or "—",
            "duracion_sec": ses.get("audio_duration_sec") or "—",
            "codec": ses.get("audio_codec") or "—",
            "bitrate_kbps": ses.get("audio_bitrate_kbps") or "—",
            "dsp_version": ses.get("dsp_version") or "—",
            "referencia": {"sexo": ref.get("sexo"), "edad": ref.get("edad"),
                           "min_hz": ref.get("min_hz"), "max_hz": ref.get("max_hz")},
            "metricas": mets}


@router.post("/api/companion/informes/sesion")
async def informe_sesion(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    uid = _require_profesional(str(body.get("user_id", "")))
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    ses = _sesion_de_profesional(sb, str(body.get("session_id", "")), uid)
    firma = body.get("firma", {}) or {}
    try:
        from reportes_sesion import generar_pdf_sesion
        path = generar_pdf_sesion(_datos_sesion_pdf(sb, ses), firma)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"No se pudo generar: {e}")
    return FileResponse(path, media_type="application/pdf",
                        filename=f"Informe_sesion_{ses['id'][:8]}.pdf")


@router.post("/api/companion/informes/evolucion")
async def informe_evolucion(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    uid = _require_profesional(str(body.get("user_id", "")))
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    pid = str(body.get("patient_id", "")).strip()
    if not pid:
        raise HTTPException(status_code=400, detail="patient_id requerido")
    try:
        pac = sb.table("pacientes").select(
            "id, nombre_completo, sexo, sexo_referencia, fecha_nacimiento")\
            .eq("id", pid).execute()
        if not (pac.data or []):
            raise HTTPException(status_code=404, detail="Paciente inexistente")
        p = pac.data[0]
        r = sb.table("voice_progress").select("*").eq("patient_id", pid)\
            .order("task_type").order("session_number").execute()
        serie = []
        for s in (r.data or []):
            try:
                f = (s.get("recorded_at") or "")[:10]
            except Exception:
                f = ""
            serie.append({"n": s.get("session_number"), "fecha": f,
                          "f0_median_hz": s.get("f0_median_hz"),
                          "f0_sd_semitones": s.get("f0_sd_semitones"),
                          "intensity_mean_db": s.get("intensity_mean_db"),
                          "jitter_pct": s.get("jitter_pct"),
                          "shimmer_pct": s.get("shimmer_pct"),
                          "hnr_db": s.get("hnr_db"), "mpt_sec": s.get("mpt_sec")})
        ref = _elegir_referencia(p, _rangos(sb))
        from reportes_sesion import generar_pdf_evolucion
        path = generar_pdf_evolucion(
            {"paciente": p.get("nombre_completo", "—"), "serie": serie,
             "referencia": {"sexo": ref.get("sexo"), "edad": ref.get("edad"),
                            "min_hz": ref.get("min_hz"), "max_hz": ref.get("max_hz")}},
            body.get("firma", {}) or {})
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"No se pudo generar: {e}")
    return FileResponse(path, media_type="application/pdf",
                        filename=f"Evolucion_voz_{pid[:8]}.pdf")


# ─── Sesiones web (grabador de emergencia PWA): multipart directo ───
@router.post("/api/companion/sesiones-web")
async def crear_sesion_web(
    user_id: str = Form(""),
    paciente_id: str = Form(...),
    recorded_at: str = Form(""),
    audio_duration_sec: float = Form(0),
    consent_recorded: bool = Form(False),
    audio: UploadFile = File(...),
):
    uid = _require_profesional(user_id)
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    try:
        data = await audio.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo audio: {e}")
    if not data or len(data) < 1000:
        raise HTTPException(status_code=400, detail="Audio vacío")
    if len(data) > MAX_BYTES:
        raise HTTPException(status_code=413, detail="Audio mayor a 45 MB")
    mime = (audio.content_type or "audio/webm").split(";")[0].strip().lower()
    ext = _mime_ext(mime) or "webm"
    try:
        p = sb.table("pacientes").select("id").eq("id", paciente_id).execute()
        if not (p.data or []):
            raise HTTPException(status_code=404, detail="Paciente inexistente")
        dsid = f"web-{secrets.token_hex(6)}"
        path = f"vault/{dsid}.{ext}"
        sb.storage.from_(BUCKET).upload(
            path, data, {"content-type": mime, "upsert": "true"})
        r = sb.table("companion_sessions").insert({
            "patient_id": paciente_id, "profesional_google_id": uid,
            "device_id": None, "device_session_id": dsid,
            "recorded_at": recorded_at or None,
            "audio_storage_path": path, "audio_mime": mime,
            "audio_size_bytes": len(data), "audio_duration_sec": audio_duration_sec or None,
            "audio_codec": "web", "dsp_version": "web-emergency/1.0",
            "device_info": {"origen": "grabador-emergencia-web"},
            "consent_recorded": bool(consent_recorded),
            "status": "uploaded"}).execute()
        sid = (r.data or [{}])[0].get("id")
        _encolar_job(sb, sid)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"No se pudo guardar: {e}")
    return JSONResponse(content={"ok": True, "session_id": sid,
                                 "device_session_id": dsid, "status": "uploaded"})


# ─── Telegram inbound (apagado salvo TELEGRAM_INBOUND_ENABLED=true) ───
@router.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    if _env("TELEGRAM_INBOUND_ENABLED", "false").strip().lower() not in ("1", "true", "yes"):
        raise HTTPException(status_code=403, detail="Inbound desactivado")
    secret = _env("TELEGRAM_WEBHOOK_SECRET", "")
    got = request.query_params.get("secret", "")
    if not secret or got != secret:
        raise HTTPException(status_code=403, detail="Secret inválido")
    try:
        update = await request.json()
    except Exception:
        return JSONResponse(content={"ok": True})
    msg = (update or {}).get("message") or {}
    media = msg.get("voice") or msg.get("audio")
    if not media or int(media.get("file_size") or 0) > 20 * 1024 * 1024:
        return JSONResponse(content={"ok": True, "skipped": True})
    prof = _profesional_env()
    if not prof:
        return JSONResponse(content={"ok": False, "error": "PROFESIONAL_GOOGLE_ID no configurado"})
    sb = _sb()
    if not sb:
        return JSONResponse(content={"ok": False, "error": "Supabase no configurado"})
    try:
        import httpx
        token = _env("TELEGRAM_BOT_TOKEN", "")
        g = httpx.get(f"https://api.telegram.org/bot{token}/getFile",
                      params={"file_id": media["file_id"]}, timeout=30).json()
        fpath = ((g.get("result") or {}).get("file_path")) or ""
        if not fpath:
            return JSONResponse(content={"ok": False, "error": "getFile vacío"})
        dl = httpx.get(f"https://api.telegram.org/file/bot{token}/{fpath}", timeout=120).content
        caption = str(msg.get("caption", "") or "")
        m = re.search(r"dni\s*:?\s*([0-9.\-]{6,12})", caption, re.IGNORECASE)
        if not m:
            _tg_send(msg.get("chat", {}).get("id"),
                     "Recibido. Para asignarlo a un paciente, reenviá el audio con DNI:<número> en el texto.")
            return JSONResponse(content={"ok": True, "skipped": "sin DNI"})
        dni = m.group(1).replace(".", "").replace("-", "")
        pr = sb.table("pacientes").select("id").eq("dni", dni).execute()
        if not (pr.data or []):
            _tg_send(msg.get("chat", {}).get("id"), "DNI no encontrado en pacientes.")
            return JSONResponse(content={"ok": False, "error": "DNI inexistente"})
        pid = pr.data[0]["id"]
        dsid = f"tg-{media.get('file_unique_id', secrets.token_hex(4))}"
        path = f"vault/{dsid}.ogg"
        sb.storage.from_(BUCKET).upload(path, dl, {"content-type": "audio/ogg", "upsert": "true"})
        r = sb.table("companion_sessions").insert({
            "patient_id": pid, "profesional_google_id": prof, "device_id": None,
            "device_session_id": dsid, "audio_storage_path": path,
            "audio_mime": "audio/ogg", "audio_size_bytes": len(dl),
            "audio_codec": "opus-telegram", "dsp_version": "telegram-inbound/1.0",
            "device_info": {"origen": "telegram", "chat_id": msg.get("chat", {}).get("id")},
            "consent_recorded": False, "status": "uploaded"}).execute()
        sid = (r.data or [{}])[0].get("id")
        _encolar_job(sb, sid)
        _tg_send(msg.get("chat", {}).get("id"),
                 "Audio recibido y encolado. Registrá el consentimiento en la ficha para procesarlo.")
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"ok": False, "error": str(e)[:200]})
    return JSONResponse(content={"ok": True})


def _tg_send(chat_id, texto: str):
    try:
        if not chat_id:
            return
        import httpx
        token = _env("TELEGRAM_BOT_TOKEN", "")
        httpx.post(f"https://api.telegram.org/bot{token}/sendMessage",
                   json={"chat_id": chat_id, "text": texto}, timeout=20)
    except Exception:
        pass


# ═══ WORKER (hilo in-process, un job a la vez) ═══
_worker_started = False


def _boot_recovery():
    """Reencola jobs 'processing' con lease vencido (>10 min)."""
    sb = _sb()
    if not sb:
        return 0
    try:
        limite = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        r = sb.table("processing_jobs").select("id, lease_at").eq("status", "processing").execute()
        n = 0
        for j in (r.data or []):
            lease = str(j.get("lease_at") or "")
            if not lease or lease < limite:
                sb.table("processing_jobs").update(
                    {"status": "queued", "next_retry_at": _now_iso(),
                     "last_error": "recuperado tras reinicio"})\
                    .eq("id", j["id"]).execute()
                n += 1
        try:
            s = sb.table("companion_sessions").select("id").eq("status", "processing").execute()
            for row in (s.data or []):
                jb = sb.table("processing_jobs").select("status").eq("session_id", row["id"]).execute()
                if not (jb.data or []) or (jb.data[0].get("status") not in ("queued", "processing")):
                    sb.table("companion_sessions").update(
                        {"status": "uploaded", "error_detail": "recuperada tras reinicio"})\
                        .eq("id", row["id"]).execute()
        except Exception:
            pass
        return n
    except Exception as e:
        print(f"[companion] boot recovery falló: {e}")
        return 0


def _claim_next_job():
    sb = _sb()
    if not sb:
        return None
    try:
        ahora = _now_iso()
        r = sb.table("processing_jobs").select("*").eq("status", "queued")\
            .lte("next_retry_at", ahora).order("created_at").limit(1).execute()
        rows = r.data or []
        if not rows:
            return None
        job = rows[0]
        u = sb.table("processing_jobs").update(
            {"status": "processing", "lease_at": ahora,
             "attempts": int(job.get("attempts") or 0) + 1,
             "updated_at": ahora})\
            .eq("id", job["id"]).eq("status", "queued").execute()
        if not (u.data or []):
            return None
        job.update(u.data[0])
        return job
    except Exception as e:
        print(f"[companion] claim falló: {e}")
        return None


def _job_done(sb, job: dict, ok: bool, error: str = ""):
    try:
        if ok:
            sb.table("processing_jobs").update(
                {"status": "done", "last_error": "", "updated_at": _now_iso()})\
                .eq("id", job["id"]).execute()
        else:
            att = int(job.get("attempts") or 1)
            if att >= 5:
                sb.table("processing_jobs").update(
                    {"status": "error", "last_error": error[:500], "updated_at": _now_iso()})\
                    .eq("id", job["id"]).execute()
            else:
                sb.table("processing_jobs").update(
                    {"status": "queued", "next_retry_at": _backoff(att).isoformat(),
                     "last_error": error[:500], "updated_at": _now_iso()})\
                    .eq("id", job["id"]).execute()
    except Exception as e:
        print(f"[companion] job_done falló: {e}")


def _chunk_plan(tmp_path: str, size_bytes: int, segments: list) -> list:
    """Plan de trozos <20MB: por ventanas de tarea; si no hay segmentos, archivo único
    (o error si excede y no hay ffmpeg). Devuelve [(path, offset_sec)]."""
    import shutil as _sh
    if size_bytes <= CHUNK_TRANSCRIBE_BYTES:
        return [(tmp_path, 0.0)]
    if not _sh.which("ffmpeg") or not segments:
        raise RuntimeError("Audio >20MB sin ffmpeg ni segmentos para trocear")
    # Agrupar segmentos contiguos por tarea hasta ~18MB (regla: bytes ∝ duración)
    per_sec = size_bytes / max(_dur_total(segments), 1)
    budget = 18 * 1024 * 1024
    wins, cur, acc = [], [], 0.0
    for s in sorted(segments, key=lambda x: float(x.get("start_sec", 0))):
        d = float(s.get("end_sec", 0)) - float(s.get("start_sec", 0))
        if acc + d * per_sec > budget and cur:
            wins.append(cur)
            cur, acc = [], 0.0
        cur.append(s)
        acc += d * per_sec
    if cur:
        wins.append(cur)
    import subprocess
    chunks = []
    for i, w in enumerate(wins):
        a = float(w[0].get("start_sec", 0))
        b = float(w[-1].get("end_sec", a))
        dst = f"{tmp_path}.chunk{i}.m4a"
        subprocess.run(["ffmpeg", "-y", "-ss", str(max(a - 1, 0)), "-t", str(b - a + 1),
                        "-i", tmp_path, "-acodec", "copy", dst],
                       capture_output=True, timeout=300, check=False)
        chunks.append((dst, max(a - 1, 0)))
    return chunks or [(tmp_path, 0.0)]


def _dur_total(segments: list) -> float:
    try:
        return max(float(s.get("end_sec", 0)) for s in segments)
    except Exception:
        return 0.0


def _transcribir_trozos(chunks: list) -> list:
    """[{start, end, text}] con offsets absolutos. Reintento por trozo (3×)."""
    from anamnesis_engine import transcribir_audio_groq
    out = []
    for path, off in chunks:
        last = None
        for intento in range(3):
            try:
                with open(path, "rb") as f:
                    raw = f.read()
                r = transcribir_audio_groq(raw, "chunk.m4a")
                segs = r.get("segmentos") or r.get("segments") or []
                if segs:
                    for s in segs:
                        out.append({"start": float(s.get("start", 0)) + off,
                                    "end": float(s.get("end", 0)) + off,
                                    "text": s.get("text", "")})
                elif r.get("transcripcion"):
                    out.append({"start": off, "end": off + float(r.get("duracion_s") or 0),
                                "text": r["transcripcion"]})
                last = None
                break
            except Exception as e:
                last = e
                time.sleep(2 * (intento + 1))
        if last is not None:
            raise RuntimeError(f"Transcripción falló en trozo {path}: {last}")
    return out


def _diarizar(trans_segs: list, task_segs: list) -> list:
    """Asigna speaker por solape con ventanas de tarea. Devuelve transcripts."""
    out = []
    for t in trans_segs:
        a, b = float(t.get("start", 0)), float(t.get("end", 0))
        best, best_ov = "paciente", 0.0
        for s in (task_segs or []):
            try:
                sa, sb_ = float(s.get("start_sec", 0)), float(s.get("end_sec", 0))
            except Exception:
                continue
            ov = max(0.0, min(b, sb_) - max(a, sa))
            if ov > best_ov:
                best_ov, best = ov, s.get("speaker", "paciente")
        if (t.get("text") or "").strip():
            out.append({"speaker": best, "start_sec": a, "end_sec": b,
                        "text": t["text"].strip(), "source": "ai"})
    return out


def _ia_borrador(contexto: dict) -> dict:
    """Borrador con proveedor intercambiable. Sin audio externo si el switch lo apaga."""
    base = {"motivo_consulta": "", "sintomatologia_vocal": "", "habitos_vocales": "",
            "observaciones_clinicas": "", "plan_sugerido": ""}
    prompt = ("Sos fonoaudiólogo clínico. Con estos datos de sesión (métricas acústicas, "
              "segmentos por tarea y transcripción), devolvé EXCLUSIVAMENTE JSON con: "
              "motivo_consulta, sintomatologia_vocal, habitos_vocales, observaciones_clinicas, "
              "plan_sugerido. Sin diagnósticos definitivos.\nDATOS:\n" +
              json.dumps(contexto, ensure_ascii=False)[:6000])
    txt = ""
    try:
        if _ai_provider() == "groq":
            from llm_client import groq_chat
            txt = groq_chat([{"role": "user", "content": prompt}],
                            temperature=0.2, max_tokens=1500,
                            model=_ai_model()) or ""
            if isinstance(txt, dict):
                txt = json.dumps(txt, ensure_ascii=False)
        else:
            import httpx
            key = _env("GEMINI_API_KEY", "")
            if not key:
                raise RuntimeError("GEMINI_API_KEY ausente")
            r = httpx.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{_ai_model()}:generateContent?key={key}",
                json={"contents": [{"parts": [{"text": prompt + "\nDevolvé solo JSON válido."}]}]},
                timeout=120)
            cands = (r.json().get("candidates") or [])
            parts = ((cands[0].get("content") or {}).get("parts") or []) if cands else []
            txt = "".join(p.get("text", "") for p in parts)
        m = re.search(r"\{.*\}", txt, re.DOTALL)
        data = json.loads(m.group(0)) if m else {}
        for k in base:
            if isinstance(data.get(k), str):
                base[k] = data[k][:2000]
        return base
    except Exception as e:
        print(f"[companion] borrador IA falló: {e}")
        base["observaciones_clinicas"] = ("Borrador automático no disponible; "
                                          "completar manual. " + (txt[:500] if txt else ""))
        return base


def _process_job(job: dict):
    sb = _sb()
    sid = job.get("session_id")
    tmp_files = []
    try:
        r = sb.table("companion_sessions").select("*").eq("id", sid).execute()
        if not (r.data or []):
            _job_done(sb, job, False, "Sesión inexistente")
            return
        ses = r.data[0]
        sb.table("companion_sessions").update(
            {"status": "processing", "error_detail": ""}).eq("id", sid).execute()
        if not ses.get("consent_recorded"):
            msg = "consent_recorded=false: registre el consentimiento y reprocese"
            sb.table("companion_sessions").update(
                {"status": "error", "error_detail": msg}).eq("id", sid).execute()
            _job_done(sb, job, True)
            return
        if not ses.get("audio_storage_path"):
            raise RuntimeError("Sesión sin audio confirmado")
        # 1. Descargar audio
        try:
            raw = sb.storage.from_(BUCKET).download(ses["audio_storage_path"])
        except Exception as e:
            raise RuntimeError(f"No se pudo descargar audio: {e}")
        tmp = tempfile.NamedTemporaryFile(suffix=".m4a", delete=False)
        tmp.write(raw if isinstance(raw, (bytes, bytearray)) else bytes(raw))
        tmp.close()
        tmp_files.append(tmp.name)
        segs = sb.table("session_segments").select("*").eq("session_id", sid)\
            .order("start_sec").execute()
        task_segs = segs.data or []
        # 2. Trocear + transcribir
        chunks = _chunk_plan(tmp.name, len(raw), task_segs)
        tmp_files.extend([p for p, _ in chunks if p != tmp.name])
        trans = _transcribir_trozos(chunks)
        # 3. Diarizar por ventanas y guardar (idempotente)
        trs = _diarizar(trans, task_segs)
        sb.table("session_transcripts").delete().eq("session_id", sid).execute()
        for t in trs:
            sb.table("session_transcripts").insert(dict(t, session_id=sid)).execute()
        # 4. Borrador de anamnesis
        acs = sb.table("session_acoustics").select("*").eq("session_id", sid).execute()
        if _external_audio_ok():
            ctx_audio = "audio enviado al proveedor (switch activo)"
        else:
            ctx_audio = "audio NO enviado (AI_EXTERNAL_AUDIO_ENABLED=false)"
        borrador = _ia_borrador({
            "metricas": acs.data or [], "segmentos": task_segs,
            "transcripcion": " ".join(t["text"] for t in trs)[:4000],
            "audio": ctx_audio, "duracion_sec": ses.get("audio_duration_sec")})
        try:
            sb.table("anamnesis_drafts").upsert(
                dict(borrador, session_id=sid, status="draft",
                     updated_at=_now_iso()),
                on_conflict="session_id").execute()
        except Exception as e:
            print(f"[companion] draft falló: {e}")
        # 5. Cerrar + notificar
        sb.table("companion_sessions").update(
            {"status": "processed", "error_detail": ""}).eq("id", sid).execute()
        _job_done(sb, job, True)
        try:
            from telegram_notify import notificar_sesion_procesada
            p = sb.table("pacientes").select("nombre_completo, sexo, sexo_referencia")\
                .eq("id", ses["patient_id"]).execute()
            if p.data:
                nm = p.data[0].get("nombre_completo", "")
                sx = p.data[0].get("sexo_referencia") or p.data[0].get("sexo") or ""
                try:
                    fch = (ses.get("recorded_at") or "")[:10]
                except Exception:
                    fch = ""
                notificar_sesion_procesada(nm, sx, fch, ses["patient_id"])
        except Exception as e:
            print(f"[companion] telegram falló: {e}")
    except Exception as e:
        traceback.print_exc()
        try:
            sb.table("companion_sessions").update(
                {"status": "error", "error_detail": str(e)[:500]}).eq("id", sid).execute()
        except Exception:
            pass
        _job_done(sb, job, False, str(e)[:300])
    finally:
        for pth in tmp_files:
            try:
                os.unlink(pth)
            except Exception:
                pass


def _worker_loop():
    print("[companion] worker iniciado")
    _boot_recovery()
    sb = _sb()
    while True:
        try:
            job = _claim_next_job()
            if job:
                # heartbeat durante el proceso
                def _beat(jid=job["id"]):
                    while True:
                        time.sleep(60)
                        try:
                            s = _sb()
                            st = s.table("processing_jobs").select("status")\
                                .eq("id", jid).execute()
                            if not (st.data or []) or st.data[0].get("status") != "processing":
                                return
                            s.table("processing_jobs").update({"lease_at": _now_iso()})\
                                .eq("id", jid).execute()
                        except Exception:
                            return
                bt = threading.Thread(target=_beat, daemon=True)
                bt.start()
                _process_job(job)
            else:
                time.sleep(10)
        except Exception as e:
            print(f"[companion] worker error: {e}")
            time.sleep(10)


def start_companion_worker():
    global _worker_started
    if _worker_started:
        return False
    if _env("COMPANION_WORKER_ENABLED", "true").strip().lower() not in ("1", "true", "yes"):
        print("[companion] worker desactivado por env")
        return False
    try:
        t = threading.Thread(target=_worker_loop, daemon=True, name="companion-worker")
        t.start()
        _worker_started = True
        return True
    except Exception as e:
        print(f"[companion] no se pudo iniciar worker: {e}")
        return False
