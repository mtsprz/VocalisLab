"""VocalisLab Pro — OAuth 2.0 con Canva Connect API (PKCE S256).

Canva NO usa API keys estáticas: el Client ID + Client Secret solo sirven
para el flujo OAuth (autorización del usuario → access/refresh token).
Los tokens se guardan en Supabase (tabla canva_tokens) y el motor de
plantillas los usa para Autofill + Export a PDF.

Endpoints:
  GET /api/canva/auth/url       → URL de autorización (abrir en popup)
  GET /api/canva/auth/callback  → redirect_uri registrado en Canva Developers
  GET /api/canva/status         → {configurado, conectado}

Env:
  CANVA_CLIENT_ID, CANVA_CLIENT_SECRET,
  CANVA_REDIRECT_URI (default https://vocalislab.onrender.com/api/canva/auth/callback),
  CANVA_SCOPES (default: autofill + diseño/exportación),
  CANVA_TEMPLATE_ID (id del brand template con autofill, se usa en plantillas_engine).
"""
import os
import time
import base64
import hashlib
import secrets
import traceback
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, HTMLResponse

router = APIRouter()

CANVA_AUTHORIZE_URL = "https://www.canva.com/api/oauth/authorize"
CANVA_TOKEN_URL = "https://api.canva.com/rest/v1/oauth/token"

DEFAULT_SCOPES = (
    "autofill:read autofill:write "
    "design:content:read design:content:write design:meta:read"
)

# PKCE verifiers en memoria: {state: {"verifier": str, "ts": float}}
_PKCE_STORE: dict = {}

_supabase = None


def _db():
    global _supabase
    if _supabase is None:
        try:
            from supabase import create_client
            url = os.environ.get("SUPABASE_URL", "")
            key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))
            _supabase = create_client(url, key) if (url and key) else False
        except Exception as e:
            print(f"[canva_auth] Supabase no disponible: {str(e)[:120]}")
            _supabase = False
    return _supabase or None


def client_id() -> str:
    return os.environ.get("CANVA_CLIENT_ID", "").strip()


def client_secret() -> str:
    return os.environ.get("CANVA_CLIENT_SECRET", "").strip()


def redirect_uri() -> str:
    return os.environ.get(
        "CANVA_REDIRECT_URI",
        "https://vocalislab.onrender.com/api/canva/auth/callback",
    ).strip()


def scopes() -> str:
    return os.environ.get("CANVA_SCOPES", DEFAULT_SCOPES).strip() or DEFAULT_SCOPES


def template_id() -> str:
    return os.environ.get("CANVA_TEMPLATE_ID", "").strip()


def credenciales_presentes() -> bool:
    return bool(client_id() and client_secret())


def _basic_auth() -> str:
    raw = f"{client_id()}:{client_secret()}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def _pkce_pair() -> tuple:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


@router.get("/api/canva/auth/url")
async def canva_auth_url():
    """Devuelve la URL de autorización de Canva (abrir en popup/nueva pestaña)."""
    if not credenciales_presentes():
        raise HTTPException(
            status_code=400,
            detail="Faltan CANVA_CLIENT_ID y CANVA_CLIENT_SECRET en el servidor (Render → Environment).",
        )
    verifier, challenge = _pkce_pair()
    state = secrets.token_urlsafe(24)
    _PKCE_STORE[state] = {"verifier": verifier, "ts": time.time()}
    # Limpieza de estados viejos (>15 min)
    for k in [k for k, v in _PKCE_STORE.items() if time.time() - v["ts"] > 900]:
        _PKCE_STORE.pop(k, None)
    import urllib.parse
    params = urllib.parse.urlencode({
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "scope": scopes(),
        "redirect_uri": redirect_uri(),
        "response_type": "code",
        "client_id": client_id(),
        "state": state,
    })
    return JSONResponse(content={"ok": True, "url": f"{CANVA_AUTHORIZE_URL}?{params}"})


def _exchange_token(payload: dict) -> dict:
    import httpx
    import urllib.parse
    r = httpx.post(
        CANVA_TOKEN_URL,
        headers={
            "Authorization": _basic_auth(),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        content=urllib.parse.urlencode(payload),
        timeout=30.0,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Canva OAuth {r.status_code}: {r.text[:300]}")
    return r.json()


@router.get("/api/canva/auth/callback")
async def canva_auth_callback(code: str = "", state: str = "", error: str = ""):
    """redirect_uri: intercambia el code por tokens y los guarda."""
    if error:
        return HTMLResponse(
            content=f"<h3>Canva: autorización denegada ({error})</h3>",
            status_code=400,
        )
    if not code or not state or state not in _PKCE_STORE:
        return HTMLResponse(
            content="<h3>Canva: código o estado inválido/expirado. Reintentá desde la app.</h3>",
            status_code=400,
        )
    verifier = _PKCE_STORE.pop(state)["verifier"]
    try:
        tokens = _exchange_token({
            "grant_type": "authorization_code",
            "code": code,
            "code_verifier": verifier,
            "redirect_uri": redirect_uri(),
        })
    except Exception as e:
        traceback.print_exc()
        return HTMLResponse(content=f"<h3>Canva: error obteniendo tokens: {e}</h3>", status_code=502)
    _guardar_tokens(tokens)
    return HTMLResponse(content=(
        "<h3>✅ Canva conectado correctamente</h3>"
        "<p>Ya podés cerrar esta ventana y volver a VocalisLab → Cuadernillo → motor Canva.</p>"
        "<script>setTimeout(function(){window.close()}, 4000);</script>"
    ))


def _guardar_tokens(tokens: dict):
    import datetime
    sb = _db()
    expires_in = int(tokens.get("expires_in") or 0)
    row = {
        "id": "default",
        "access_token": tokens.get("access_token", ""),
        "refresh_token": tokens.get("refresh_token", ""),
        "scope": tokens.get("scope", ""),
        "token_type": tokens.get("token_type", "Bearer"),
        "expires_at": (
            datetime.datetime.utcnow() + datetime.timedelta(seconds=max(expires_in - 60, 0))
        ).isoformat() if expires_in else None,
        "updated_at": datetime.datetime.utcnow().isoformat(),
    }
    if not sb:
        print("[canva_auth] Sin Supabase: tokens solo en memoria (no persistente)")
        _MEM_TOKENS.update(row)
        return
    try:
        sb.table("canva_tokens").upsert(row, on_conflict="id").execute()
    except Exception as e:
        traceback.print_exc()
        print(f"[canva_auth] No se pudo guardar en canva_tokens (¿corriste el SQL?): {e}")
        _MEM_TOKENS.update(row)


_MEM_TOKENS: dict = {}


def _leer_tokens() -> dict:
    sb = _db()
    if sb:
        try:
            res = sb.table("canva_tokens").select("*").eq("id", "default").limit(1).execute()
            if res.data:
                return res.data[0]
        except Exception as e:
            print(f"[canva_auth] Leyendo canva_tokens: {e}")
    return dict(_MEM_TOKENS)


def get_valid_access_token() -> str:
    """Access token vigente (refresca si venció). Lanza RuntimeError si no hay conexión."""
    toks = _leer_tokens()
    if not toks.get("access_token"):
        raise RuntimeError("Canva no conectado: completá la autorización OAuth primero.")
    exp = toks.get("expires_at") or ""
    vencido = True
    if exp:
        try:
            import datetime
            dt = datetime.datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
            now = datetime.datetime.now(dt.tzinfo) if dt.tzinfo else datetime.datetime.utcnow()
            vencido = (dt - now).total_seconds() < 120
        except Exception:
            vencido = True
    if not vencido:
        return toks["access_token"]
    if not toks.get("refresh_token"):
        raise RuntimeError("Token de Canva vencido y sin refresh_token: reautorizá.")
    try:
        nuevos = _exchange_token({
            "grant_type": "refresh_token",
            "refresh_token": toks["refresh_token"],
        })
    except Exception as e:
        raise RuntimeError(f"No se pudo refrescar el token de Canva: {e}")
    if not nuevos.get("refresh_token"):
        nuevos["refresh_token"] = toks.get("refresh_token", "")
    _guardar_tokens(nuevos)
    return nuevos.get("access_token", "")


@router.get("/api/canva/status")
async def canva_status():
    toks = _leer_tokens()
    return JSONResponse(content={
        "ok": True,
        "configurado": credenciales_presentes() and bool(template_id()),
        "conectado": bool(toks.get("access_token")),
        "tiene_template": bool(template_id()),
        "redirect_uri": redirect_uri(),
    })
