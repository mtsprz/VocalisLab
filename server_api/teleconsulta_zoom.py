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


async def _zoom_request(method: str, path: str, token: str, payload: dict = None):
    """Llamada a Zoom API con reintentos ante fallas transitorias (429/5xx/red)."""
    import asyncio
    last_err: Exception = RuntimeError("Sin respuesta de Zoom")
    for intento in range(3):
        try:
            async with httpx.AsyncClient(timeout=20) as client:
                r = await client.request(
                    method, f"{ZOOM_API_BASE}{path}",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                    json=payload,
                )
            if r.status_code in (200, 201, 204):
                return r
            if r.status_code in (429,) or 500 <= r.status_code < 600:
                last_err = RuntimeError(f"Zoom transitorio ({r.status_code}), reintento {intento + 1}/3")
                await asyncio.sleep(1.5 * (intento + 1))
                continue
            raise RuntimeError(f"Zoom API ({r.status_code}): {r.text[:300]}")
        except RuntimeError:
            raise
        except Exception as e:
            last_err = e
            await asyncio.sleep(1.5 * (intento + 1))
    raise last_err


def _require_user(user_id: str):
    """Valida que el profesional esté autenticado con Google (no expone nada)."""
    if not user_id:
        raise HTTPException(status_code=401, detail="Sesión requerida: iniciá sesión con Google")
    try:
        from api_clinica import _get_supabase
        sb = _get_supabase()
        if sb:
            res = sb.table("usuarios_google").select("google_id").eq("google_id", user_id).limit(1).execute()
            if res.data:
                return
    except HTTPException:
        raise
    except Exception:
        pass
    raise HTTPException(status_code=403, detail="Usuario no autorizado para este turno: volvé a iniciar sesión con Google")


def _persist_turno_zoom(turno_id: str, fields: dict):
    """Actualiza campos de sincronización del turno (tolerante a columnas faltantes)."""
    try:
        from api_clinica import _get_supabase, _missing_column
        from datetime import datetime, timezone
        sb = _get_supabase()
        if not sb or not turno_id:
            return
        fields = {**fields, "fecha_sincronizacion": datetime.now(timezone.utc).isoformat()}
        for _ in range(6):
            try:
                sb.table("turnos").update(fields).eq("id", turno_id).execute()
                return
            except Exception as e_upd:
                col = _missing_column(str(e_upd))
                if col and col in fields:
                    fields.pop(col, None)
                    continue
                raise
    except Exception as e:
        print(f"[zoom] No se pudo persistir sync en turno {turno_id}: {e}")


def _marcar_error_sync(turno_id: str, mensaje: str):
    try:
        from api_clinica import _get_supabase
        sb = _get_supabase()
        if sb and turno_id:
            sb.table("turnos").update({"ultima_error_sincronizacion": mensaje[:300]}).eq("id", turno_id).execute()
    except Exception:
        pass


def _s2s_creds():
    return (
        os.environ.get("ZOOM_ACCOUNT_ID", "").strip(),
        os.environ.get("ZOOM_CLIENT_ID", "").strip(),
        os.environ.get("ZOOM_CLIENT_SECRET", "").strip(),
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
    sdk_key = os.environ.get("ZOOM_SDK_KEY", "").strip()
    sdk_secret = os.environ.get("ZOOM_SDK_SECRET", "").strip()
    advertencias = []
    if sdk_key and client_id and sdk_key == client_id:
        advertencias.append(
            "ZOOM_SDK_KEY es idéntico al Client ID Server-to-Server: la firma del Meeting SDK "
            "será rechazada (error 3712). Creá una app 'Meeting SDK' en el Marketplace y usá su SDK Key/SDK Secret."
        )
    if sdk_secret and client_secret and sdk_secret == client_secret:
        advertencias.append(
            "ZOOM_SDK_SECRET es idéntico al Client Secret Server-to-Server: la firma será inválida (error 3712)."
        )
    return JSONResponse(content={
        "s2s_configured": bool(account_id and client_id and client_secret),
        "sdk_configured": bool(sdk_key and sdk_secret),
        "advertencias": advertencias,
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
    sdk_key = os.environ.get("ZOOM_SDK_KEY", "").strip()
    sdk_secret = os.environ.get("ZOOM_SDK_SECRET", "").strip()
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


# ═══════════════════════════════════════════════════════════════
# Endpoints de especificación (flujo agenda ↔ Google ↔ Zoom)
# ═══════════════════════════════════════════════════════════════

@router.post("/api/teleconsulta/zoom/create")
async def zoom_create(request: Request):
    """Crea (o reutiliza si ya existe: idempotente ante doble clic) la reunión
    Zoom asociada a un turno. Body: {turno_id, user_id}."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    turno_id = body.get("turno_id", "")
    user_id = body.get("user_id", "")
    _require_user(user_id)
    if not turno_id:
        raise HTTPException(status_code=400, detail="turno_id requerido")

    from api_clinica import _get_supabase
    sb = _get_supabase()
    turno, paciente_nombre = {}, "Paciente"
    if sb:
        try:
            tr = sb.table("turnos").select("*").eq("id", turno_id).limit(1).execute()
            turno = (tr.data or [{}])[0]
            if turno.get("paciente_id"):
                pr = sb.table("pacientes").select("nombre_completo").eq("id", turno["paciente_id"]).limit(1).execute()
                if pr.data:
                    paciente_nombre = pr.data[0].get("nombre_completo", "Paciente")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"No se pudo leer el turno: {str(e)[:200]}")

    # Idempotencia: si ya hay reunión, devolverla sin crear otra
    if turno.get("zoom_meeting_id"):
        return JSONResponse(content={
            "ok": True,
            "reutilizada": True,
            "zoom_meeting_id": turno.get("zoom_meeting_id"),
            "zoom_password": turno.get("zoom_password", ""),
            "zoom_join_url": turno.get("zoom_join_url", ""),
            "zoom_status": turno.get("zoom_status", "programada"),
        })

    fecha_hora = turno.get("fecha_hora", "") or body.get("fecha_hora", "")
    duracion_min = int(turno.get("duracion_min") or body.get("duracion_min") or 45)
    motivo = turno.get("motivo") or body.get("motivo", "Teleconsulta fonoaudiológica")

    try:
        token = await _s2s_token()
    except Exception as e:
        _marcar_error_sync(turno_id, str(e))
        raise HTTPException(status_code=503, detail=f"Zoom no disponible: {e}")

    try:
        from datetime import datetime as dt
        parsed = dt.fromisoformat(str(fecha_hora).replace("Z", "+00:00"))
        start_time = parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
    except Exception:
        start_time = None

    payload = {
        "topic": f"Teleconsulta Vocal: {paciente_nombre} — VocalisLab Pro",
        "type": 2,
        "duration": duracion_min,
        "timezone": "America/Argentina/Buenos_Aires",
        "agenda": f"{motivo}\nPaciente: {paciente_nombre}",
        "settings": {
            "host_video": True, "participant_video": True,
            "join_before_host": False, "waiting_room": True,
            "audio": "both", "auto_recording": "none",
            "meeting_authentication": False,
        },
    }
    if start_time:
        payload["start_time"] = start_time

    try:
        r = await _zoom_request("POST", "/users/me/meetings", token, payload)
        m = r.json()
    except Exception as e:
        _marcar_error_sync(turno_id, str(e))
        raise HTTPException(status_code=502, detail=f"No se pudo crear la reunión: {str(e)[:300]}")

    sala = {
        "ok": True,
        "reutilizada": False,
        "zoom_meeting_id": str(m.get("id", "")),
        "zoom_password": m.get("password", ""),
        "zoom_join_url": m.get("join_url", ""),
        "zoom_start_url": m.get("start_url", ""),
        "zoom_status": "programada",
    }
    _persist_turno_zoom(turno_id, {
        "zoom_meeting_id": sala["zoom_meeting_id"],
        "zoom_password": sala["zoom_password"],
        "zoom_join_url": sala["zoom_join_url"],
        "zoom_start_url": sala.get("zoom_start_url", ""),
        "zoom_status": "programada",
        "teleconsulta_provider": "zoom",
        "ultima_error_sincronizacion": None,
    })
    return JSONResponse(content=sala)


@router.post("/api/teleconsulta/zoom/signature")
async def zoom_signature_spec(request: Request):
    """Alias de especificación (valida usuario antes de firmar)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    _require_user(body.get("user_id", ""))
    return await zoom_signature(request)


@router.patch("/api/teleconsulta/zoom/{meeting_id}")
async def zoom_update(meeting_id: str, request: Request):
    """Reprograma la reunión (fecha/hora/duración) y sincroniza el turno."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    _require_user(body.get("user_id", ""))
    turno_id = body.get("turno_id", "")

    patch: dict = {}
    if body.get("fecha_hora"):
        try:
            from datetime import datetime as dt
            parsed = dt.fromisoformat(str(body["fecha_hora"]).replace("Z", "+00:00"))
            patch["start_time"] = parsed.strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:
            pass
    if body.get("duracion_min"):
        try:
            patch["duration"] = int(body["duracion_min"])
        except Exception:
            pass
    if not patch:
        raise HTTPException(status_code=400, detail="Nada para actualizar (fecha_hora / duracion_min)")

    try:
        token = await _s2s_token()
        await _zoom_request("PATCH", f"/meetings/{meeting_id}", token, patch)
    except Exception as e:
        if turno_id:
            _marcar_error_sync(turno_id, str(e))
        raise HTTPException(status_code=502, detail=f"No se pudo reprogramar en Zoom: {str(e)[:300]}")

    if turno_id:
        sync_fields: dict = {"zoom_status": "reprogramada"}
        if body.get("fecha_hora"):
            sync_fields["fecha_hora"] = body["fecha_hora"]
        if body.get("duracion_min"):
            try:
                sync_fields["duracion_min"] = int(body["duracion_min"])
            except Exception:
                pass
        _persist_turno_zoom(turno_id, sync_fields)
    return JSONResponse(content={"ok": True, "zoom_meeting_id": meeting_id})


@router.delete("/api/teleconsulta/zoom/{meeting_id}")
async def zoom_delete(meeting_id: str, request: Request):
    """Cancela la reunión en Zoom y marca el turno. Acepta body o query params."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    qp = dict(request.query_params)
    user_id = body.get("user_id", "") or qp.get("user_id", "")
    turno_id = body.get("turno_id", "") or qp.get("turno_id", "")
    _require_user(user_id)

    if not turno_id:
        try:
            from api_clinica import _get_supabase
            sb = _get_supabase()
            if sb:
                tr = sb.table("turnos").select("id").eq("zoom_meeting_id", meeting_id).limit(1).execute()
                if tr.data:
                    turno_id = tr.data[0]["id"]
        except Exception:
            pass

    try:
        token = await _s2s_token()
        try:
            await _zoom_request("DELETE", f"/meetings/{meeting_id}", token)
        except Exception as e:
            if "404" not in str(e):
                raise
    except Exception as e:
        if turno_id:
            _marcar_error_sync(turno_id, str(e))
        raise HTTPException(status_code=502, detail=f"No se pudo cancelar en Zoom: {str(e)[:300]}")

    if turno_id:
        _persist_turno_zoom(turno_id, {"zoom_status": "cancelada"})
    return JSONResponse(content={"ok": True, "zoom_meeting_id": meeting_id})


@router.get("/api/teleconsulta/{turno_id}")
async def teleconsulta_estado(turno_id: str, role: str = "host"):
    """Agregado turno + Zoom + conteo de sesiones. start_url solo para host."""
    try:
        from api_clinica import _get_supabase
        sb = _get_supabase()
        if not sb:
            raise HTTPException(status_code=500, detail="Base de datos no configurada")
        tr = sb.table("turnos").select("*").eq("id", turno_id).limit(1).execute()
        turno = (tr.data or [None])[0]
        if not turno:
            raise HTTPException(status_code=404, detail="Turno no encontrado")
        paciente = {}
        if turno.get("paciente_id"):
            pr = sb.table("pacientes").select("id, nombre_completo, dni, telefono, email").eq("id", turno["paciente_id"]).limit(1).execute()
            paciente = (pr.data or [{}])[0]
        try:
            sesiones = sb.table("sesiones_teleconsulta").select("id", count="exact").eq("turno_id", turno_id).execute()
            sesiones_count = sesiones.count or 0
        except Exception as e_ses:
            print(f"[zoom] sesiones_teleconsulta no disponible: {e_ses}")
            sesiones_count = 0
        out = {
            "ok": True,
            "turno": turno,
            "paciente": paciente,
            "sesiones_count": sesiones_count,
        }
        if role != "host":
            out["turno"] = {**turno, "zoom_start_url": None}
        return JSONResponse(content=out)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error obteniendo teleconsulta: {str(e)[:300]}")


def _sesion_abierta(sb, turno_id: str):
    try:
        r = sb.table("sesiones_teleconsulta").select("*").eq("turno_id", turno_id)\
            .is_("fecha_fin", "null").order("fecha_inicio", desc=True).limit(1).execute()
        return (r.data or [None])[0]
    except Exception:
        return None


@router.post("/api/teleconsulta/{turno_id}/notes")
async def teleconsulta_notes(turno_id: str, request: Request):
    """Guarda notas/ejercicios/duración/incidencias en la sesión abierta (o crea una)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    _require_user(body.get("user_id", ""))
    try:
        from api_clinica import _get_supabase
        sb = _get_supabase()
        if not sb:
            raise HTTPException(status_code=500, detail="Base de datos no configurada")
        tr = sb.table("turnos").select("id, paciente_id").eq("id", turno_id).limit(1).execute()
        turno = (tr.data or [None])[0]
        if not turno:
            raise HTTPException(status_code=404, detail="Turno no encontrado")

        ses = _sesion_abierta(sb, turno_id)
        payload = {}
        if body.get("notas") is not None:
            payload["notas"] = body["notas"]
        if body.get("ejercicios") is not None:
            payload["ejercicios_realizados"] = body["ejercicios"]
        if body.get("duracion_min") is not None:
            try:
                payload["duracion_min"] = int(body["duracion_min"])
            except Exception:
                pass
        if body.get("incidencias") is not None:
            payload["incidencias_tecnicas"] = body["incidencias"]
        if ses:
            sb.table("sesiones_teleconsulta").update(payload).eq("id", ses["id"]).execute()
            return JSONResponse(content={"ok": True, "sesion_id": ses["id"]})
        payload["turno_id"] = turno_id
        payload["paciente_id"] = turno.get("paciente_id")
        ins = sb.table("sesiones_teleconsulta").insert(payload).execute()
        return JSONResponse(content={"ok": True, "sesion_id": (ins.data or [{}])[0].get("id")})
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error guardando notas: {str(e)[:300]}")


@router.post("/api/teleconsulta/{turno_id}/end")
async def teleconsulta_end(turno_id: str, request: Request):
    """Finaliza la sesión: cierra sesión abierta, guarda resumen y completa el turno."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    _require_user(body.get("user_id", ""))
    try:
        from api_clinica import _get_supabase
        from datetime import datetime, timezone
        sb = _get_supabase()
        if not sb:
            raise HTTPException(status_code=500, detail="Base de datos no configurada")
        tr = sb.table("turnos").select("id, paciente_id").eq("id", turno_id).limit(1).execute()
        turno = (tr.data or [None])[0]
        if not turno:
            raise HTTPException(status_code=404, detail="Turno no encontrado")

        ahora = datetime.now(timezone.utc).isoformat()
        ses = _sesion_abierta(sb, turno_id)
        base = {}
        if body.get("notas") is not None:
            base["notas"] = body["notas"]
        if body.get("ejercicios") is not None:
            base["ejercicios_realizados"] = body["ejercicios"]
        if body.get("duracion_min") is not None:
            try:
                base["duracion_min"] = int(body["duracion_min"])
            except Exception:
                pass
        if body.get("incidencias") is not None:
            base["incidencias_tecnicas"] = body["incidencias"]
        if body.get("resumen") is not None:
            base["resumen_final"] = body["resumen"]
        base["fecha_fin"] = ahora
        if ses:
            sb.table("sesiones_teleconsulta").update(base).eq("id", ses["id"]).execute()
            sesion_id = ses["id"]
        else:
            base["turno_id"] = turno_id
            base["paciente_id"] = turno.get("paciente_id")
            ins = sb.table("sesiones_teleconsulta").insert(base).execute()
            sesion_id = (ins.data or [{}])[0].get("id")
        sb.table("turnos").update({"estado": "completado"}).eq("id", turno_id).execute()
        return JSONResponse(content={"ok": True, "sesion_id": sesion_id})
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error finalizando sesión: {str(e)[:300]}")
