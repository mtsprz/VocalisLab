"""Vocalis Companion — vinculación con Google y lista de pacientes.

- GET /api/companion/google/start?return_to=...  → redirige al login de Google
  (solo openid/email/profile). Al volver, /api/auth/callback/google (mismo
  redirect_uri registrado) delega en `google_callback_companion`, que genera un
  código de un solo uso en companion_pairing_codes y redirige a la app
  (`return_to?code=...`). La app lo canjea con el POST /api/companion/pair
  existente → device_token. No se tocan los tokens de la web (usuarios_google).
- Solo se aceptan cuentas en COMPANION_GOOGLE_EMAILS (coma) o, si no está, la
  de PROFESIONAL_GOOGLE_ID. Sin ninguna de las dos: se rechaza a todos (los
  pacientes son de un solo consultorio).
- GET /api/companion/pacientes (Bearer device_token) → lista mínima para la
  caché offline (sin DNI, email, teléfono ni notas).
"""
import html
import re
import secrets
import time
import traceback
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

import google_auth as ga
from companion import _device_from_bearer, _env, _pairing_code, _profesional_env, _sb

router = APIRouter()

# state -> (return_to, vence_epoch). Una sola instancia en Render: alcanza.
_PENDIENTES: dict = {}
_TTL = 600
_RETURN_OK = re.compile(r"^(vocaliscompanion://auth|http://(localhost|127\.0\.0\.1):\d{2,5}(/[\w/-]*)?)$")


def _emails_habilitados() -> set:
    return {e.strip().lower() for e in _env("COMPANION_GOOGLE_EMAILS", "").split(",") if e.strip()}


def _volver(return_to: str, **params) -> HTMLResponse:
    """Redirección a la app (esquema propio o localhost) con enlace de respaldo."""
    url = f"{return_to}?{urlencode(params)}"
    u = html.escape(url, quote=True)
    return HTMLResponse(content=(
        f'<html><head><meta http-equiv="refresh" content="0;url={u}"></head>'
        f'<body style="font-family:sans-serif;font-size:20px;padding:24px">'
        f'<p>Volviendo a Vocalis Companion…</p><p><a href="{u}">Tocá acá si no vuelve sola</a></p>'
        f'<script>window.location.href={url!r};</script></body></html>'))


@router.get("/api/companion/google/start")
async def google_start(return_to: str = "vocaliscompanion://auth"):
    if not _RETURN_OK.match(return_to):
        raise HTTPException(status_code=400, detail="return_to no permitido")
    if not ga.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID no configurado")
    ahora = time.time()
    for k in [k for k, (_, v) in _PENDIENTES.items() if v < ahora]:
        _PENDIENTES.pop(k, None)
    state = "companion:" + secrets.token_urlsafe(24)
    _PENDIENTES[state] = (return_to, ahora + _TTL)
    q = urlencode({
        "client_id": ga.GOOGLE_CLIENT_ID,
        "redirect_uri": ga.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "prompt": "select_account",
        "state": state,
    })
    return RedirectResponse(url=f"{ga.GOOGLE_AUTH_URL}?{q}", status_code=302)


async def google_callback_companion(code: str, state: str) -> HTMLResponse:
    pend = _PENDIENTES.pop(state, None)
    if not pend or pend[1] < time.time():
        return HTMLResponse(content="<p>El inicio de sesión venció. Volvé a la app y tocá "
                                    "'Entrar con Google' otra vez.</p>", status_code=400)
    return_to = pend[0]
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            tr = await client.post(ga.GOOGLE_TOKEN_URL, data={
                "code": code, "client_id": ga.GOOGLE_CLIENT_ID,
                "client_secret": ga.GOOGLE_CLIENT_SECRET,
                "redirect_uri": ga.GOOGLE_REDIRECT_URI, "grant_type": "authorization_code"})
            if tr.status_code != 200:
                return _volver(return_to, error="google_token")
            ur = await client.get(ga.GOOGLE_USERINFO_URL, headers={
                "Authorization": f"Bearer {tr.json().get('access_token', '')}"})
        info = ur.json() if ur.status_code == 200 else {}
        gid = str(info.get("id", "")).strip()
        email = str(info.get("email", "")).strip().lower()
        if not gid or not email or info.get("verified_email") is False:
            return _volver(return_to, error="cuenta_invalida")
        emails = _emails_habilitados()
        unico = _profesional_env()
        if emails:
            permitido = email in emails
        elif unico:
            permitido = gid == unico
        else:
            permitido = False
        if not permitido:
            return _volver(return_to, error="no_habilitado", email=email)
        sb = _sb()
        if not sb:
            return _volver(return_to, error="sin_base")
        _registrar_cuenta(sb, gid, email, str(info.get("name", "") or ""))
        codigo = _codigo_google()
        exp = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        sb.table("companion_pairing_codes").insert({
            "code": codigo, "profesional_google_id": gid, "expires_at": exp}).execute()
        return _volver(return_to, code=codigo)
    except Exception as e:
        traceback.print_exc()
        # Sin secretos: tipo + mensaje corto (ej. error de RLS de Supabase).
        return _volver(return_to, error="servidor", detalle=f"{type(e).__name__}: {str(e)[:160]}")


def _registrar_cuenta(sb, gid: str, email: str, nombre: str) -> None:
    """Deja constancia gid→email en usuarios_google si la cuenta no existe
    (login solo desde la app). Nunca pisa una fila de la web (tokens)."""
    try:
        r = sb.table("usuarios_google").select("google_id").eq("google_id", gid).execute()
        if not (r.data or []):
            sb.table("usuarios_google").insert(
                {"google_id": gid, "email": email, "name": nombre}).execute()
    except Exception:
        traceback.print_exc()


def _codigo_google() -> str:
    """Código de vinculación emitido SOLO tras un login de Google autorizado.
    Formato propio (G + 15 caracteres) que /pairing-code (6) no puede generar."""
    return "G" + _pairing_code(15)


def _es_codigo_google(code: str) -> bool:
    return len(code or "") == 16 and code.startswith("G")


def _cuenta_autorizada(sb, gid: str, device_id: str = "") -> bool:
    """El dispositivo se vinculó con un código de Google (lista blanca
    verificada en el login), o su cuenta es PROFESIONAL_GOOGLE_ID, o figura en
    usuarios_google con un email de COMPANION_GOOGLE_EMAILS. Evita que un
    dispositivo vinculado con un user_id inventado (POST /pairing-code) lea
    pacientes."""
    unico = _profesional_env()
    if unico and gid == unico:
        return True
    if device_id:
        try:
            r = sb.table("companion_pairing_codes").select("code")                .eq("used_by_device_id", device_id).execute()
            if any(_es_codigo_google(str(x.get("code", ""))) for x in (r.data or [])):
                return True
        except Exception:
            traceback.print_exc()
    emails = _emails_habilitados()
    if not emails or not gid:
        return False
    try:
        r = sb.table("usuarios_google").select("email").eq("google_id", gid).execute()
    except Exception:
        return False
    return any(str(x.get("email", "")).strip().lower() in emails for x in (r.data or []))


def _abreviar(nombre: str) -> str:
    p = [x for x in (nombre or "").split(" ") if x]
    if not p:
        return "—"
    return p[0] if len(p) == 1 else f"{p[0]} {p[-1][0]}."


@router.get("/api/companion/pacientes")
async def pacientes_companion(request: Request, q: str = "", limit: int = 200):
    dev = _device_from_bearer(request)
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    if not _cuenta_autorizada(sb, str(dev.get("profesional_google_id", "")), str(dev.get("id", "") or "")):
        raise HTTPException(status_code=403, detail="Cuenta no habilitada para la lista de pacientes")
    limit = max(1, min(int(limit or 200), 1000))
    try:
        r = sb.table("pacientes").select("*").limit(limit).execute()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error de base: {e}")
    qq = (q or "").strip().lower()
    out = []
    for p in r.data or []:
        nombre = p.get("nombre_completo") or p.get("nombre") or ""
        if qq and qq not in nombre.lower():
            continue
        out.append({
            "id": p.get("id"),
            "nombre_abreviado": _abreviar(nombre),
            "sexo_referencia": p.get("sexo_referencia") or p.get("sexo") or p.get("genero") or "",
            "fecha_nacimiento": p.get("fecha_nacimiento") or "",
            "updated_at": p.get("updated_at") or "",
            "activo": p.get("activo", True) is not False,
        })
    out.sort(key=lambda x: x["nombre_abreviado"].lower())
    return JSONResponse(content={"ok": True, "pacientes": out})
