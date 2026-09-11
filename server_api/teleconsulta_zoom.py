"""VocalisLab Pro — Teleconsulta Zoom con audio profesional.

Flujo:
1. POST /api/teleconsulta/crear-sala → OAuth Server-to-Server → crea la
   reunión (waiting room, audio both) → devuelve join_url + credenciales y las
   guarda en el turno de Supabase.
2. POST /api/teleconsulta/zoom-signature → firma JWT para el Meeting SDK web
   (terapeuta role=1, paciente role=0).
3. GET /api/teleconsulta/config → indica si Zoom está configurado.

Env vars requeridas:
  ZOOM_ACCOUNT_ID, ZOOM_CLIENT_ID, ZOOM_CLIENT_SECRET (Server-to-Server OAuth)
  ZOOM_SDK_KEY, ZOOM_SDK_SECRET (firma Meeting SDK web)
"""
import os
import time
import hmac
import hashlib
import base64
import json
import traceback
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import httpx

router = APIRouter()

ZOOM_TOKEN_URL = "https://zoom.us/oauth/token"
ZOOM_API_BASE = "https://api.zoom.us/v2"

_token_cache = {"token": "", "exp": 0}


def _s2s_creds():
    return (
        os.environ.get("ZOOM_ACCOUNT_ID", ""),
        os.environ.get("ZOOM_CLIENT_ID", ""),
        os.environ.get("ZOOM_CLIENT_SECRET", ""),
    )


async def _s2s_token() -> str:
    account_id, client_id, client_secret = _s2s_creds()
    if not (account_id and client_id and client_secret):
        raise RuntimeError("Zoom no configurado: faltan ZOOM_ACCOUNT_ID / ZOOM_CLIENT_ID / ZOOM_CLIENT_SECRET")
    if _token_cache["token"] and time.time() < _token_cache["exp"] - 60:
        return _token_cache["token"]
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(
            ZOOM_TOKEN_URL,
            params={"grant_type": "account_credentials", "account_id": account_id},
            auth=(client_id, client_secret),
        )
    if r.status_code != 200:
        raise RuntimeError(f"Zoom OAuth falló ({r.status_code}): {r.text[:200]}")
    data = r.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["exp"] = time.time() + int(data.get("expires_in", 3600))
    return _token_cache["token"]


@router.get("/api/teleconsulta/config")
async def zoom_config():
    account_id, client_id, client_secret = _s2s_creds()
    sdk_key = os.environ.get("ZOOM_SDK_KEY", "")
    sdk_secret = os.environ.get("ZOOM_SDK_SECRET", "")
    return JSONResponse(content={
        "s2s_configured": bool(account_id and client_id and client_secret),
        "sdk_configured": bool(sdk_key and sdk_secret),
    })


@router.post("/api/teleconsulta/crear-sala")
async def crear_sala(request: Request):
    """Crea una reunión de teleconsulta y la asocia al turno."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    paciente_nombre = body.get("paciente_nombre", "Paciente")
    fecha_hora = body.get("fecha_hora", "")
    duracion_min = int(body.get("duracion_min") or 45)
    turno_id = body.get("turno_id", "")
    motivo = body.get("motivo", "Teleconsulta fonoaudiológica")

    try:
        token = await _s2s_token()
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))

    # start_time ISO con Z; Zoom acepta "YYYY-MM-DDTHH:MM:SSZ"
    start_time = fecha_hora
    try:
        from datetime import datetime as dt
        parsed = dt.fromisoformat(str(fecha_hora).replace("Z", "+00:00"))
        start_time = parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        pass

    payload = {
        "topic": f"Teleconsulta Vocal: {paciente_nombre} — VocalisLab Pro",
        "type": 2,
        "start_time": start_time or None,
        "duration": duracion_min,
        "timezone": "America/Argentina/Buenos_Aires",
        "agenda": f"{motivo}\nPaciente: {paciente_nombre}",
        "settings": {
            "host_video": True,
            "participant_video": True,
            "join_before_host": False,
            "waiting_room": True,
            "audio": "both",
            "auto_recording": "none",
            "meeting_authentication": False,
        },
    }
    if not start_time:
        payload.pop("start_time", None)

    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.post(
                f"{ZOOM_API_BASE}/users/me/meetings",
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json=payload,
            )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error contactando Zoom: {e}")
    if r.status_code not in (200, 201):
        raise HTTPException(status_code=502, detail=f"Zoom API ({r.status_code}): {r.text[:300]}")

    m = r.json()
    sala = {
        "ok": True,
        "zoom_meeting_id": str(m.get("id", "")),
        "zoom_password": m.get("password", ""),
        "zoom_join_url": m.get("join_url", ""),
        "zoom_start_url": m.get("start_url", ""),
    }

    # Persistir en el turno (tolerante si las columnas aún no existen en Supabase)
    if turno_id:
        try:
            from api_clinica import _get_supabase, _missing_column
            sb = _get_supabase()
            if sb:
                zdata = {
                    "zoom_meeting_id": sala["zoom_meeting_id"],
                    "zoom_password": sala["zoom_password"],
                    "zoom_join_url": sala["zoom_join_url"],
                }
                for _ in range(4):
                    try:
                        sb.table("turnos").update(zdata).eq("id", turno_id).execute()
                        break
                    except Exception as e_upd:
                        col = _missing_column(str(e_upd))
                        if col and col in zdata:
                            zdata.pop(col, None)
                            continue
                        print(f"[zoom] No se pudo persistir sala en turno: {e_upd}")
                        break
        except Exception as e:
            print(f"[zoom] Persistencia omitida: {e}")

    return JSONResponse(content=sala)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


@router.post("/api/teleconsulta/zoom-signature")
async def zoom_signature(request: Request):
    """Firma JWT para unir al Meeting SDK web (role 1 = terapeuta, 0 = paciente)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    meeting_number = str(body.get("meeting_number", "")).strip()
    role = int(body.get("role", 0))
    sdk_key = os.environ.get("ZOOM_SDK_KEY", "")
    sdk_secret = os.environ.get("ZOOM_SDK_SECRET", "")
    if not (sdk_key and sdk_secret):
        raise HTTPException(status_code=503, detail="Zoom SDK no configurado: faltan ZOOM_SDK_KEY / ZOOM_SDK_SECRET")
    if not meeting_number:
        raise HTTPException(status_code=400, detail="meeting_number requerido")

    iat = int(time.time()) - 30
    exp = iat + 60 * 60 * 2
    header = _b64url(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64url(json.dumps({
        "sdkKey": sdk_key, "mn": meeting_number, "role": role,
        "iat": iat, "exp": exp, "appKey": sdk_key, "tokenExp": exp,
    }).encode())
    signature = _b64url(hmac.new(sdk_secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256).digest())
    return JSONResponse(content={
        "ok": True,
        "signature": f"{header}.{payload}.{signature}",
        "sdkKey": sdk_key,
    })
