"""Motor terapéutico: datos reales desde la base y planes guardados."""
import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import recomendaciones as RC  # noqa: E402


class _Q:
    def __init__(self, base, tabla):
        self.base, self.tabla, self.f, self.op, self.d, self.inn = base, tabla, {}, "select", None, None

    def select(self, *_):
        return self

    def order(self, *_a, **_k):
        return self

    def limit(self, *_):
        return self

    def eq(self, k, v):
        self.f[k] = v
        return self

    def in_(self, k, vals):
        self.inn = (k, vals)
        return self

    def insert(self, d):
        self.op, self.d = "insert", d
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
        if self.inn:
            sel = [x for x in sel if x.get(self.inn[0]) in self.inn[1]]
        r.data = sel
        return r


class _Base:
    def __init__(self):
        self.t = {
            "pacientes": [{"id": "p1", "nombre_completo": "León Murillo", "sexo": "Masculino",
                           "fecha_nacimiento": "1990-05-10", "ocupacion": "Docente", "demanda_vocal_horas": 6}],
            "evaluaciones_clinicas": [{"paciente_id": "p1", "fecha": "2026-11-10", "grbas": {"G": 2, "S": 2},
                                       "vhi10_score": 18, "tme_o": 11, "riesgo_vocal_score": 85}],
            "analisis_acusticos": [],
            "companion_sessions": [{"id": "s1", "patient_id": "p1", "recorded_at": "2026-11-12"}],
            "session_acoustics": [{"session_id": "s1", "task_type": "conversacion_espontanea", "f0_median_hz": 118.5}],
        }

    def table(self, t):
        return _Q(self, t)


def test_completa_desde_la_base_sin_pisar_ni_inventar():
    paciente, escalas, riesgo, acustica = {"ocupacion": "Profesor de canto"}, {"vhi10_score": 22}, {}, {}
    usados = RC.hidratar_desde_db(_Base(), "p1", paciente, escalas, riesgo, acustica)
    assert paciente["ocupacion"] == "Profesor de canto"  # lo de la pantalla manda
    assert paciente["edad"] >= 36 and paciente["sexo"] == "Masculino"
    assert escalas["vhi10_score"] == 22 and escalas["grbas"] == {"G": 2, "S": 2} and escalas["tme_o"] == 11
    assert riesgo["puntaje_total"] == 85
    assert acustica == {"f0_conversacional_hz": 118.5}  # sin análisis acústico: no se inventa
    assert "análisis acústico" not in usados["faltan"] or acustica.get("f0_mean") is None
    assert usados["evaluacion"] == "2026-11-10"


def test_guardar_y_listar_planes(monkeypatch):
    import api_clinica
    base = _Base()
    monkeypatch.setattr(api_clinica, "supabase", base)
    app = FastAPI()
    app.include_router(RC.router)
    c = TestClient(app)
    plan = {"diagnostico_funcional_fonoaudiologico": "DMT", "ejercicios_recomendados": [{"id": "le_huche"}]}
    assert c.post("/api/recomendaciones", json={"paciente_id": "p1", "recomendacion": plan}).status_code == 200
    lista = c.get("/api/recomendaciones?paciente_id=p1").json()["recomendaciones"]
    assert lista[0]["recomendacion"] == plan
    assert c.post("/api/recomendaciones", json={"paciente_id": "p1"}).status_code == 400
