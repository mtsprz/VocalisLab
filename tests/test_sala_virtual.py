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


class _Tabla:
    def __init__(self, filas):
        self.filas = filas

    def table(self, nombre):
        self.nombre = nombre
        return self

    def insert(self, fila):
        self.filas.append((self.nombre, fila))
        return self

    def execute(self):
        import types
        return types.SimpleNamespace(data=[self.filas[-1][1]] if self.filas else [])


def test_guardar_canto_no_suma_a_la_f0_conversacional(cliente, monkeypatch):
    import api_clinica
    import companion
    filas = []
    monkeypatch.setattr(api_clinica, "supabase", _Tabla(filas))
    llamadas = []

    async def pm(req):
        llamadas.append(await req.json())
        return {"session_id": "cs1"}
    monkeypatch.setattr(companion, "guardar_pitchmeter", pm)
    base = {"paciente_id": "p1", "resultados": {"mediana_hz": 220, "p5_hz": 210, "p95_hz": 230, "tmf_s": 14,
                                                "en_objetivo_pct": 81}, "objetivo": {"hz": 220, "nota": "La3", "tolerancia_cents": 50}}
    assert cliente.post("/api/sala-sesiones", json=dict(base, modo="canto")).status_code == 200
    assert llamadas == []  # el canto no va a la evolución de F0 del habla
    assert filas[-1][0] == "sala_sesiones" and filas[-1][1]["modo"] == "canto"
    assert filas[-1][1]["resultados"]["en_objetivo_pct"] == 81
    assert cliente.post("/api/sala-sesiones", json=dict(base, modo="habla")).status_code == 200
    assert llamadas[-1]["contexto"] == "sala_virtual" and filas[-1][1]["companion_session_id"] == "cs1"
    assert cliente.post("/api/sala-sesiones", json=dict(base, modo="otro")).status_code == 400


def test_salas_abiertas_incluye_las_del_bot(cliente):
    cliente.post("/api/salas", json={"nombre": "Laura Díaz", "modo": "tmf"})
    salas = cliente.get("/api/salas").json()["salas"]
    assert len(salas) == 1 and salas[0]["modo"] == "tmf" and salas[0]["enlace"].startswith("http")
