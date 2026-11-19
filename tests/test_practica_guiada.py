"""Práctica guiada: rutina, enlace público, consentimiento y resultados."""
import os
import sys

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import practica_guiada as PG  # noqa: E402


class _Q:
    def __init__(self, base, tabla):
        self.base, self.tabla, self.f, self.op, self.d = base, tabla, {}, "select", None

    def select(self, *_):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_):
        return self

    def in_(self, *_):
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
        if self.op == "insert":
            fila = dict(self.d, id=f"{self.tabla}-{len(filas) + 1}", creada_at="2026-11-19T10:00:00")
            filas.insert(0, fila)
            r.data = [fila]
            return r
        sel = [x for x in filas if all(x.get(k) == v for k, v in self.f.items())]
        if self.op == "update":
            for x in sel:
                x.update(self.d)
        r.data = sel
        return r


class _Base:
    def __init__(self):
        self.t = {"pacientes": [{"id": "p1", "nombre_completo": "León Murillo", "sexo": "Masculino", "telefono": "221"}],
                  "anamnesis": [{"paciente_id": "p1", "fecha": "2026-11-01", "diagnostico_orl": "Nódulos bilaterales"}]}

    def table(self, t):
        return _Q(self, t)


@pytest.fixture
def cliente(monkeypatch):
    import api_clinica
    base = _Base()
    monkeypatch.setattr(api_clinica, "supabase", base)
    app = FastAPI()
    app.include_router(PG.router)
    return TestClient(app), base


EJ = [{"guia": "rampa", "nombre": "Sirena", "amplitud": 7, "base_hz": 110},
      {"guia": "escalera", "nombre": "Escala", "semitonos": [0, 2, 4, 2, 0]}]


def test_flujo_completo_sin_audio(cliente):
    c, base = cliente
    r = c.post("/api/practicas", json={"paciente_id": "p1", "ejercicios": EJ})
    assert r.status_code == 200, r.text
    token = r.json()["enlace"].split("practica=")[1]
    assert r.json()["nombre"] == "León"
    v = c.get(f"/api/practica/{token}").json()
    assert v["estado"] == "activa" and not v["consentimiento"] and v["ejercicios"][1]["base_hz"] == 110.0
    res = {"resultados": [{"ejercicio": 0, "dentro_pct": 82.5, "f0_mediana_hz": 131, "audio": "xxx"}]}
    assert c.post(f"/api/practica/{token}/sesion", json=res).status_code == 403  # sin consentimiento
    assert c.post(f"/api/practica/{token}/consentimiento", json={"acepta": False}).status_code == 400
    assert c.post(f"/api/practica/{token}/consentimiento", json={"acepta": True}).status_code == 200
    assert c.post(f"/api/practica/{token}/sesion", json=res).status_code == 200
    s = base.t["practica_sesiones"][0]
    assert s["resultados"][0]["dentro_pct"] == 82.5 and "audio" not in s["resultados"][0]
    lista = c.get("/api/practicas?paciente_id=p1").json()
    assert "token" not in lista["practicas"][0] and len(lista["sesiones"]) == 1


def test_valores_fuera_de_rango_no_se_guardan(cliente):
    c, base = cliente
    token = c.post("/api/practicas", json={"paciente_id": "p1", "ejercicios": EJ}).json()["enlace"].split("=")[1]
    c.post(f"/api/practica/{token}/consentimiento", json={"acepta": True})
    r = c.post(f"/api/practica/{token}/sesion", json={"resultados": [{"ejercicio": 0, "dentro_pct": 140, "f0_mediana_hz": 20}]})
    assert r.status_code == 200
    s = base.t["practica_sesiones"][0]["resultados"][0]
    assert s["dentro_pct"] is None and s["f0_mediana_hz"] is None
    assert c.post(f"/api/practica/{token}/sesion", json={"resultados": [{"ejercicio": 9}]}).status_code == 400


def test_rutina_pausada_no_recibe(cliente):
    c, base = cliente
    r = c.post("/api/practicas", json={"paciente_id": "p1", "ejercicios": EJ}).json()
    token = r["enlace"].split("=")[1]
    c.post(f"/api/practica/{token}/consentimiento", json={"acepta": True})
    c.patch(f"/api/practicas/{r['id']}", json={"activa": False})
    assert c.get(f"/api/practica/{token}").json()["estado"] == "pausada"
    assert c.post(f"/api/practica/{token}/sesion", json={"resultados": [{"ejercicio": 0}]}).status_code == 409


def test_validacion_de_ejercicios():
    with pytest.raises(HTTPException):
        PG.normalizar_ejercicio({"guia": "volar"}, 110)
    with pytest.raises(HTTPException):
        PG.normalizar_ejercicio({"guia": "escalera", "semitonos": [0]}, 110)
    with pytest.raises(HTTPException):
        PG.normalizar_ejercicio({"guia": "rampa", "amplitud": 24, "base_hz": 700}, 110)
    e = PG.normalizar_ejercicio({"guia": "sostenida", "repeticiones": 99}, 196)
    assert e["base_hz"] == 196 and e["repeticiones"] == 20 and e["duracion_s"] == 6


def test_sugerencias_respetan_contraindicaciones(cliente, monkeypatch):
    c, base = cliente
    import api_clinica
    banco = {"sections": [{"id": "sovte", "exercises": [
        {"id": "glissandos", "name": "Glissandos", "contraindications": []},
        {"id": "messa_di_voce", "name": "Messa di voce", "contraindications": ["nodulo"]}]}]}
    monkeypatch.setattr(api_clinica, "banco_ejercicios_completo", lambda: banco)
    import recomendar_motor
    monkeypatch.setattr(recomendar_motor, "_EXERCISE_INDEX", {
        "glissandos": {"name": "Glissandos", "contraindications": []},
        "messa_di_voce": {"name": "Messa di voce", "contraindications": ["nodulo"]}})
    d = c.get("/api/practicas/sugerencias?paciente_id=p1").json()
    assert [e["bank_id"] for e in d["ejercicios"]] == ["glissandos"]
    assert d["excluidos"][0]["id"] == "messa_di_voce"
    assert d["tono_base"]["hz"] == 110.0 and "ajustalo" in d["tono_base"]["origen"]
