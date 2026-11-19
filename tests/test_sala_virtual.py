"""Sala virtual (server_api/sala_virtual.py): voz del paciente en vivo."""
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import sala_virtual as SV  # noqa: E402
import sesion_web  # noqa: E402


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "secreto-de-prueba")
    monkeypatch.setenv("EMAILS_PERMITIDOS", "prof@ejemplo.com")
    SV.SALAS.clear()
    app = FastAPI()

    @app.middleware("http")
    async def sesion(request, call_next):  # simula la sesión de la web
        request.state.usuario = {"sub": "prof-1"}
        return await call_next(request)

    app.include_router(SV.router)
    return TestClient(app)


def test_sala_en_vivo(cliente):
    r = cliente.post("/api/salas", json={"nombre": "Yesica Alvarez", "modo": "canto"}).json()
    token = r["token"]
    assert r["enlace"].endswith(f"/?sala={token}") and r["nombre"] == "Yesica"
    info = cliente.get(f"/api/sala/{token}/info").json()
    assert info["nombre"] == "Yesica" and info["modo"] == "canto"
    assert "Alvarez" not in str(info)  # al paciente no se le muestra el apellido

    sesion = sesion_web.emitir_token("prof-1", "prof@ejemplo.com")
    with cliente.websocket_connect(f"/ws/sala/{token}/profesional?sesion={sesion}") as prof:
        assert prof.receive_json()["paciente_conectado"] is False
        with cliente.websocket_connect(f"/ws/sala/{token}/paciente") as pac:
            assert pac.receive_json()["tipo"] == "config"
            assert prof.receive_json() == {"tipo": "estado", "paciente_conectado": True}
            pac.send_json({"tipo": "muestras", "datos": [{"t": 1, "f0": 220.0, "db": -20}]})
            assert prof.receive_json() == {"tipo": "muestras", "datos": [{"t": 1, "f0": 220.0, "db": -20}]}
            objetivo = {"hz": 220.0, "nota": "La2", "tolerancia_cents": 50}
            prof.send_json({"tipo": "objetivo", "objetivo": objetivo})
            assert pac.receive_json() == {"tipo": "objetivo", "objetivo": objetivo}
            prof.send_json({"tipo": "consigna", "texto": "Sostené una /u/"})
            assert pac.receive_json() == {"tipo": "consigna", "texto": "Sostené una /u/"}
        assert prof.receive_json() == {"tipo": "estado", "paciente_conectado": False}


def test_sesion_invalida_y_sala_inexistente(cliente):
    token = cliente.post("/api/salas", json={}).json()["token"]
    with cliente.websocket_connect(f"/ws/sala/{token}/profesional?sesion=falsa") as prof:
        assert prof.receive_json()["tipo"] == "error"
    with cliente.websocket_connect("/ws/sala/no-existe/paciente") as pac:
        assert pac.receive_json()["tipo"] == "error"
    assert cliente.get("/api/sala/no-existe/info").status_code == 404


def test_cerrar_sala(cliente):
    token = cliente.post("/api/salas", json={}).json()["token"]
    sesion = sesion_web.emitir_token("prof-1", "prof@ejemplo.com")
    with cliente.websocket_connect(f"/ws/sala/{token}/paciente") as pac:
        pac.receive_json()
        with cliente.websocket_connect(f"/ws/sala/{token}/profesional?sesion={sesion}") as prof:
            prof.receive_json()
            prof.send_json({"tipo": "cerrar"})
            assert pac.receive_json() == {"tipo": "cerrada"}
    assert token not in SV.SALAS
