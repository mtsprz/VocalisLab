"""Login obligatorio del servidor (server_api/sesion_web.py).

Antes ninguna ruta pedía sesión: /api/pacientes devolvía nombre, DNI y
teléfono a cualquiera. Estos tests fijan el comportamiento nuevo.
"""
import os
import sys
import time

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient
from starlette.middleware.base import BaseHTTPMiddleware

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import sesion_web  # noqa: E402
from sesion_web import cuenta_autorizada, emitir_token, verificar_token  # noqa: E402

EMAIL = "profesional@ejemplo.com"


@pytest.fixture(autouse=True)
def _entorno(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "secreto-de-prueba")
    monkeypatch.setenv("EMAILS_PERMITIDOS", f"{EMAIL}, otra@ejemplo.com")
    monkeypatch.delenv("PROFESIONAL_GOOGLE_ID", raising=False)


def test_token_valido_y_datos():
    datos = verificar_token(emitir_token("123", EMAIL))
    assert datos["sub"] == "123" and datos["email"] == EMAIL


def test_token_alterado_o_con_otro_secreto_no_vale(monkeypatch):
    t = emitir_token("123", EMAIL)
    prefijo, cuerpo, firma = t.split(".")
    assert verificar_token(f"{prefijo}.{cuerpo}.{firma[:-2]}xx") is None
    assert verificar_token("cualquier-cosa") is None
    monkeypatch.setenv("SESSION_SECRET", "otro-secreto")
    assert verificar_token(t) is None


def test_token_vencido():
    viejo = emitir_token("123", EMAIL, ahora=time.time() - sesion_web.DURACION_SESION_S - 10)
    assert verificar_token(viejo) is None


def test_cerrado_por_defecto_sin_configuracion(monkeypatch):
    monkeypatch.delenv("EMAILS_PERMITIDOS")
    assert not sesion_web.acceso_configurado()
    assert not cuenta_autorizada("123", EMAIL)


def test_lista_de_cuentas_y_google_id(monkeypatch):
    assert cuenta_autorizada("1", "PROFESIONAL@ejemplo.com")
    assert not cuenta_autorizada("1", "intruso@ejemplo.com")
    monkeypatch.setenv("PROFESIONAL_GOOGLE_ID", "999")
    assert cuenta_autorizada("999", "cualquiera@ejemplo.com")


def test_quitar_una_cuenta_invalida_sus_sesiones(monkeypatch):
    t = emitir_token("123", "otra@ejemplo.com")
    assert verificar_token(t)
    monkeypatch.setenv("EMAILS_PERMITIDOS", EMAIL)
    assert verificar_token(t) is None


@pytest.fixture
def cliente(monkeypatch):
    # El token de dispositivo "dispositivo-ok" se simula como válido.
    monkeypatch.setattr(sesion_web, "_dispositivo_valido",
                        lambda req: sesion_web.token_bearer(req) == "dispositivo-ok")
    app = FastAPI()
    app.add_middleware(BaseHTTPMiddleware, dispatch=sesion_web.middleware_sesion)

    @app.get("/api/pacientes")
    def pacientes(request: Request):
        return {"usuario": getattr(request.state, "usuario", {}).get("email")}

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/companion/sessions")
    def sesiones():
        return {"ok": True}

    @app.post("/api/companion/pair")
    def pair():
        return {"ok": True}

    return TestClient(app)


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_sin_sesion_no_hay_datos(cliente):
    r = cliente.get("/api/pacientes")
    assert r.status_code == 401 and r.json()["codigo"] == "sesion_requerida"


def test_con_sesion_hay_datos(cliente):
    r = cliente.get("/api/pacientes", headers=_auth(emitir_token("1", EMAIL)))
    assert r.status_code == 200 and r.json()["usuario"] == EMAIL


def test_rutas_publicas_y_preflight(cliente):
    assert cliente.get("/api/health").status_code == 200
    assert cliente.post("/api/companion/pair").status_code == 200
    assert cliente.options("/api/pacientes").status_code != 401


def test_companion_con_token_de_dispositivo(cliente):
    assert cliente.get("/api/companion/sessions", headers=_auth("dispositivo-ok")).status_code == 200
    # Antes cualquier "Bearer" pasaba a las rutas que solo pedían user_id.
    assert cliente.get("/api/companion/sessions", headers=_auth("inventado")).status_code == 401
    # El token de dispositivo no sirve fuera de /api/companion.
    assert cliente.get("/api/pacientes", headers=_auth("dispositivo-ok")).status_code == 401
