"""Autoevaluación del paciente por enlace (server_api/autoevaluacion.py)."""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import autoevaluacion as AE  # noqa: E402


class _Q:
    def __init__(self, base, tabla):
        self.base, self.tabla, self.f, self.op, self.d = base, tabla, {}, "select", None

    def select(self, *_):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_):
        return self

    def eq(self, k, v):
        self.f[k] = v
        return self

    def insert(self, d):
        self.op, self.d = "insert", d
        return self

    def update(self, d):
        self.op, self.d = "update", d
        return self

    def execute(self):
        class R:
            pass
        r, filas = R(), self.base.t.setdefault(self.tabla, [])
        sel = [x for x in filas if all(x.get(k) == v for k, v in self.f.items())]
        if self.op == "insert":
            fila = dict(self.d, id=f"{self.tabla}-{len(filas) + 1}")
            filas.append(fila)
            r.data = [fila]
        elif self.op == "update":
            for x in sel:
                x.update(self.d)
            r.data = sel
        else:
            r.data = [dict(x) for x in sel]
        return r


class _Base:
    def __init__(self):
        self.t = {"pacientes": [{"id": "p1", "nombre_completo": "Alvarez Yesica", "telefono": "221555"}]}

    def table(self, t):
        return _Q(self, t)


@pytest.fixture
def entorno(monkeypatch):
    base = _Base()
    monkeypatch.setattr(AE, "_sb", lambda: base)
    avisos = []
    monkeypatch.setattr(AE, "_avisar", lambda sb, pid, r: avisos.append(r))
    app = FastAPI()
    app.include_router(AE.router)
    return TestClient(app), base, avisos


def _respuestas(vhi=2, riesgo=1, auto=6):
    return {"autopercepcion": auto, "comentario": "Me canso al final del día",
            "vhi10": {k: vhi for k in AE.VHI10_ITEMS}, "riesgo": {k: riesgo for k in AE.RIESGO_ITEMS}}


def test_circuito_completo(entorno):
    c, base, avisos = entorno
    nuevo = c.post("/api/autoevaluaciones", json={"paciente_id": "p1"}).json()
    assert nuevo["enlace"].endswith(f"/?autoeval={nuevo['token']}") and nuevo["nombre"] == "Yesica"
    info = c.get(f"/api/autoevaluacion/{nuevo['token']}").json()
    assert info["estado"] == "pendiente" and info["nombre"] == "Yesica"
    assert "Alvarez" not in str(info) and "221555" not in str(info)  # sin datos de la ficha
    assert c.post(f"/api/autoevaluacion/{nuevo['token']}", json=_respuestas()).status_code == 200
    fila = base.t["autoevaluaciones"][0]
    assert (fila["vhi10_score"], fila["riesgo_vocal_score"], fila["autopercepcion"]) == (20, 69, 6)
    assert fila["estado"] == "completada" and fila["respuestas"]["VHI10"]["V1"] == 2
    assert avisos and avisos[0]["riesgo_grupo"] == "Grupo 1 (Bajo Riesgo)"
    # No se puede enviar dos veces.
    assert c.post(f"/api/autoevaluacion/{nuevo['token']}", json=_respuestas()).status_code == 409
    lista = c.get("/api/autoevaluaciones?paciente_id=p1").json()["autoevaluaciones"]
    assert lista[0]["vhi10_score"] == 20


def test_respuestas_incompletas_o_fuera_de_rango(entorno):
    c, _, _ = entorno
    token = c.post("/api/autoevaluaciones", json={"paciente_id": "p1"}).json()["token"]
    incompleta = _respuestas()
    del incompleta["riesgo"]["E11"]
    assert c.post(f"/api/autoevaluacion/{token}", json=incompleta).status_code == 400
    assert c.post(f"/api/autoevaluacion/{token}", json=_respuestas(vhi=5)).status_code == 400
    assert c.post(f"/api/autoevaluacion/{token}", json=_respuestas(auto=11)).status_code == 400


def test_solo_algunos_cuestionarios_y_vencimiento(entorno):
    c, base, _ = entorno
    token = c.post("/api/autoevaluaciones", json={"paciente_id": "p1", "instrumentos": ["vhi10"]}).json()["token"]
    assert c.post(f"/api/autoevaluacion/{token}", json={"vhi10": {k: 4 for k in AE.VHI10_ITEMS}}).status_code == 200
    assert base.t["autoevaluaciones"][0]["vhi10_score"] == 40
    token2 = c.post("/api/autoevaluaciones", json={"paciente_id": "p1"}).json()["token"]
    base.t["autoevaluaciones"][1]["vence_at"] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert c.get(f"/api/autoevaluacion/{token2}").json()["estado"] == "vencida"
    assert c.post(f"/api/autoevaluacion/{token2}", json=_respuestas()).status_code == 410
    assert c.get("/api/autoevaluacion/no-existe").status_code == 404
