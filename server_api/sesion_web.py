"""Sesión de la web: token firmado y control de acceso a /api/*.

Antes ninguna ruta pedía autenticación: cualquiera que conociera la URL del
servidor podía leer los datos de los pacientes. Ahora:

- Al iniciar sesión con Google, si la cuenta está AUTORIZADA (variable
  EMAILS_PERMITIDOS o PROFESIONAL_GOOGLE_ID), el servidor emite un token de
  sesión firmado (HMAC-SHA256, 30 días). La web lo manda en cada pedido
  (Authorization: Bearer ...).
- El middleware exige ese token en todo /api/*, salvo las rutas públicas por
  diseño (estado del servidor, inicio de sesión, vinculación del Companion,
  webhook de Telegram con su propio secreto).
- La app Companion sigue entrando con su token de dispositivo, que se valida
  contra la base (antes cualquier "Bearer" pasaba a las rutas que solo
  pedían user_id).

Sin EMAILS_PERMITIDOS ni PROFESIONAL_GOOGLE_ID configurados, NO se emite
sesión a nadie (cerrado por defecto: son datos de salud).
"""
import base64
import hashlib
import hmac
import json
import os
import secrets
import time

DURACION_SESION_S = 30 * 24 * 3600

# Rutas que no requieren sesión de la web.
RUTAS_PUBLICAS = {
    "/api/health",
    "/api/keepalive",
    "/api/auth/google/url",
    "/api/auth/callback/google",
    "/api/companion/health",
    "/api/companion/health/capacidades",
    "/api/companion/pair",          # el teléfono aún no tiene token
    "/api/companion/google/start",  # login del teléfono en el navegador
    "/api/telegram/webhook",        # valida su propio secreto
    "/api/agenda/importar-fonoar/script",  # script de Gmail: valida su clave
    "/api/asistente/telegram",      # webhook de Telegram: valida su secreto
    "/api/canto/importar-planilla/script",  # script de Gmail/Drive: valida su clave
    "/api/asistente/repaso-dia",    # GitHub Actions 07:30: una vez por día
}
# Prefijo donde además se acepta el token de dispositivo del Companion.
PREFIJO_COMPANION = "/api/companion/"

_SECRETO_EFIMERO = secrets.token_bytes(32)


def _secreto() -> bytes:
    """SESSION_SECRET si está; si no, derivado de la clave de servicio de
    Supabase (estable entre reinicios, no hace falta configurar nada). Sin
    ninguna de las dos, uno al azar por proceso (las sesiones se pierden al
    reiniciar)."""
    s = os.environ.get("SESSION_SECRET", "").strip()
    if s:
        return s.encode()
    # Primera clave estable disponible. GOOGLE_CLIENT_SECRET está siempre que
    # el login con Google funciona; sin una clave estable, si el servidor
    # corre varios procesos cada uno firmaría distinto y rechazaría las
    # sesiones emitidas por otro ("Tu sesión venció" justo al entrar).
    for var in ("SUPABASE_SERVICE_KEY", "GOOGLE_CLIENT_SECRET", "SUPABASE_ANON_KEY"):
        base = os.environ.get(var, "").strip()
        if base:
            return hashlib.sha256(b"vocalislab-sesion-web:" + base.encode()).digest()
    return _SECRETO_EFIMERO


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _firma(cuerpo: str) -> str:
    return _b64(hmac.new(_secreto(), cuerpo.encode(), hashlib.sha256).digest())


def emails_permitidos() -> set:
    return {e.strip().lower() for e in os.environ.get("EMAILS_PERMITIDOS", "").split(",")
            if e.strip()}


def acceso_configurado() -> bool:
    return bool(emails_permitidos() or os.environ.get("PROFESIONAL_GOOGLE_ID", "").strip())


def cuenta_autorizada(google_id: str, email: str) -> bool:
    """Cerrado por defecto: solo las cuentas listadas."""
    gid = os.environ.get("PROFESIONAL_GOOGLE_ID", "").strip()
    if gid and str(google_id or "").strip() == gid:
        return True
    return str(email or "").strip().lower() in emails_permitidos()


def emitir_token(google_id: str, email: str, ahora: float = None) -> str:
    ahora = time.time() if ahora is None else ahora
    datos = {"sub": str(google_id), "email": str(email or ""),
             "iat": int(ahora), "exp": int(ahora) + DURACION_SESION_S}
    cuerpo = _b64(json.dumps(datos, separators=(",", ":")).encode())
    return f"vls1.{cuerpo}.{_firma(cuerpo)}"


def verificar_token(token: str, ahora: float = None):
    """Datos de la sesión si el token es válido, vigente y de una cuenta que
    sigue autorizada; si no, None."""
    try:
        prefijo, cuerpo, firma = str(token or "").split(".")
        if prefijo != "vls1" or not hmac.compare_digest(firma, _firma(cuerpo)):
            return None
        datos = json.loads(_unb64(cuerpo))
    except Exception:
        return None
    if int(datos.get("exp", 0)) < (time.time() if ahora is None else ahora):
        return None
    # Si se quita una cuenta de la lista, sus sesiones dejan de valer.
    if not cuenta_autorizada(datos.get("sub"), datos.get("email")):
        return None
    return datos


def token_bearer(request) -> str:
    auth = (request.headers.get("authorization") or "").strip()
    return auth[7:].strip() if auth.lower().startswith("bearer ") else ""


def _dispositivo_valido(request) -> bool:
    """Token de dispositivo del Companion, validado contra la base."""
    try:
        from companion import _device_from_bearer
        _device_from_bearer(request)
        return True
    except Exception:
        return False


async def middleware_sesion(request, call_next):
    """Exige sesión en /api/* (salvo rutas públicas y preflight CORS)."""
    from fastapi.responses import JSONResponse
    from starlette.concurrency import run_in_threadpool

    ruta = request.url.path.rstrip("/") or "/"
    if (request.method == "OPTIONS" or not ruta.startswith("/api/")
            or ruta in RUTAS_PUBLICAS
            # Página del paciente en la sala virtual (valida su propio token).
            or (ruta.startswith("/api/sala/") and ruta.endswith("/info"))
            # Formulario de autoevaluación del paciente (valida su propio token).
            or ruta.startswith("/api/autoevaluacion/")):
        return await call_next(request)
    token = token_bearer(request)
    usuario = verificar_token(token) if token else None
    if usuario:
        request.state.usuario = usuario
        return await call_next(request)
    if token and ruta.startswith(PREFIJO_COMPANION) \
            and await run_in_threadpool(_dispositivo_valido, request):
        return await call_next(request)
    return JSONResponse(status_code=401, content={
        "detail": "Iniciá sesión para usar la plataforma.",
        "codigo": "sesion_requerida",
    })
