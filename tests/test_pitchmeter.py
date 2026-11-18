"""PitchMeter guarda la F0 conversacional en la base del paciente.

Antes "Volcar a historia clínica" solo la dejaba en el navegador. Se guarda
como sesión + acústica (tarea conversacion_espontanea), igual que el
Companion, para que aparezca en la evolución de F0 y en los informes.
"""
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import companion  # noqa: E402


class _Tabla:
    def __init__(self, base, nombre):
        self.base, self.nombre, self._fila = base, nombre, None

    def select(self, *_a):
        return self

    def eq(self, _campo, valor):
        self._filtro = valor
        return self

    def insert(self, fila):
        self._fila = fila
        return self

    def execute(self):
        class R:
            pass
        r = R()
        if self._fila is not None:
            fila = dict(self._fila, id=f"{self.nombre}-1")
            self.base.insertados.setdefault(self.nombre, []).append(fila)
            r.data = [fila]
        else:  # select de pacientes
            r.data = [{"id": self._filtro}] if self._filtro == "pac-1" else []
        return r


class _Base:
    def __init__(self):
        self.insertados = {}

    def table(self, nombre):
        return _Tabla(self, nombre)


@pytest.fixture
def entorno(monkeypatch):
    base = _Base()
    monkeypatch.setattr(companion, "_sb", lambda: base)
    monkeypatch.delenv("PROFESIONAL_GOOGLE_ID", raising=False)
    app = FastAPI()

    @app.middleware("http")
    async def sesion(request, call_next):  # simula la sesión de la web
        request.state.usuario = {"sub": "prof-1"}
        return await call_next(request)

    app.include_router(companion.router)
    return TestClient(app), base


def _medicion(**extra):
    d = {"paciente_id": "pac-1", "contexto": "anamnesis", "duracion_s": 42,
         "f0": {"mean": 205.3, "median": 201.0, "p5": 170.0, "p95": 250.0,
                "min": 150.0, "max": 290.0, "sd_st": 2.1},
         "contorno": [200, 201.5, 199, 2000]}
    d.update(extra)
    return d


def test_guarda_sesion_y_acustica(entorno):
    cliente, base = entorno
    r = cliente.post("/api/companion/pitchmeter", json=_medicion())
    assert r.status_code == 200 and r.json()["f0_median_hz"] == 201.0
    ses = base.insertados["companion_sessions"][0]
    assert ses["patient_id"] == "pac-1" and ses["profesional_google_id"] == "prof-1"
    assert ses["status"] == "processed" and ses["device_info"]["contexto"] == "anamnesis"
    ac = base.insertados["session_acoustics"][0]
    assert ac["task_type"] == "conversacion_espontanea" and ac["f0_median_hz"] == 201.0
    assert ac["f0_contour"] == [200.0, 201.5, 199.0]  # 2000 Hz se descarta


def test_sin_paciente_o_sin_f0(entorno):
    cliente, _ = entorno
    assert cliente.post("/api/companion/pitchmeter", json=_medicion(paciente_id="")).status_code == 400
    assert cliente.post("/api/companion/pitchmeter", json=_medicion(f0={"median": None})).status_code == 400
    assert cliente.post("/api/companion/pitchmeter", json=_medicion(paciente_id="otro")).status_code == 404
