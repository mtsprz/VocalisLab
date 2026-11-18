"""Planilla de alumnos de canto (server_api/planilla_canto.py)."""
import os
import sys
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

from planilla_canto import clases_proximas, importar_planilla, parsear_planilla  # noqa: E402

FILAS = [
    ["DÍA", "HORA", "ALUMNOS", "EDAD", "DNI", "CELULAR", "EMAIL", "NOVIEMBRE", "DICIEMBRE"],
    ["MIÉRCOLES", "15 HS", "Lara Rozenfeld", "18", "48430880", "2216331302", "",
     "$20.000 por TRF el 4/11 / 60.000 por TRF el 11/11", ""],
    ["18/11 a las 6 hs y 25/11 a las 10 am", "16 HS", "Juan Ignacio Soracco", "14", "52698207",
     "1141902615", "mama@ejemplo.com", ".80.000 por TRF el 10/11", "Tiene 1 clase a favor"],
    ["MIÉRCOLES", "17 HS", "", "", "", "", "", "", ""],
    [],
    ["Liquidacion Matias Perez- NOVIEMBRE", "", "", ""],
    ["ACTIVIDAD", "ALUMNOS", "PAGO", "DOCENTE 60%"],
    ["Canto individual", "Lara Rozenfeld", "$80,000", "$48,000"],
    ["", "", "$160,000", "$96,000"],
]
HOY = date(2026, 11, 18)


def test_horarios_reemplazos_y_pagos():
    d = parsear_planilla(FILAS, hoy=HOY)
    lara, juan = d["alumnos"]
    assert (lara["dia_semana"], lara["hora"]) == (2, (15, 0))
    assert juan["hora"] == (16, 0)
    assert juan["pagos"] == {"Noviembre": ".80.000 por TRF el 10/11", "Diciembre": "Tiene 1 clase a favor"}
    clases = [(f.isoformat(), h) for f, h in clases_proximas(juan, HOY)]
    assert clases[:3] == [("2026-11-18", (18, 0)), ("2026-11-25", (10, 0)), ("2026-12-02", (16, 0))]
    assert len(d["alumnos"]) == 2  # el horario libre de las 17 h no es un alumno
    assert d["liquidacion"]["mes"] == "Noviembre" and d["liquidacion"]["items"][-1]["docente"] == "$96,000"


class _Q:
    def __init__(self, base, tabla):
        self.base, self.tabla, self.f, self.rangos, self.op, self.d = base, tabla, {}, [], "select", None

    def select(self, *_):
        return self

    def limit(self, *_):
        return self

    def eq(self, k, v):
        self.f[k] = v
        return self

    def gte(self, k, v):
        self.rangos.append((k, ">=", v))
        return self

    def lte(self, k, v):
        self.rangos.append((k, "<=", v))
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
        sel = [x for x in filas if all(x.get(k) == v for k, v in self.f.items())
               and all((str(x.get(k)) >= v) if op == ">=" else (str(x.get(k)) <= v) for k, op, v in self.rangos)]
        if self.op == "insert":
            fila = dict(self.d, id=f"{self.tabla}-{len(filas) + 1}")
            filas.append(fila)
            r.data = [fila]
        elif self.op == "update":
            for x in sel:
                x.update(self.d)
            r.data = sel
        else:
            r.data = sel
        return r


class _Base:
    def __init__(self, pacientes=None, turnos=None):
        self.t = {"pacientes": list(pacientes or []), "turnos": list(turnos or [])}

    def table(self, t):
        return _Q(self, t)


def test_importa_sin_duplicar_y_respeta_la_agenda_de_fonoar():
    # Juan ya existe (vino por la agenda de Fonoar) con un turno el 18/11 a las 10.
    base = _Base(pacientes=[{"id": "p-juan", "nombre_completo": "Juan Soracco", "dni": None,
                             "telefono": "", "centro": "fonoar_la_plata"}],
                 turnos=[{"id": "t1", "paciente_id": "p-juan", "fecha_hora": "2026-11-18T10:00:00-03:00"}])
    r = importar_planilla(parsear_planilla(FILAS, hoy=HOY), sb=base, hoy=HOY)
    assert (r["alumnos_nuevos"], r["alumnos_actualizados"]) == (1, 1)
    juan = base.t["pacientes"][0]
    assert juan["tipo_atencion"] == "canto" and juan["telefono"] == "1141902615" and juan["dni"] == "52698207"
    assert juan["datos_canto"]["pagos"]["Diciembre"] == "Tiene 1 clase a favor"
    fechas_juan = sorted(t["fecha_hora"] for t in base.t["turnos"] if t["paciente_id"] == "p-juan")
    assert fechas_juan[0] == "2026-11-18T10:00:00-03:00"  # no se agrega otra clase el 18/11
    assert "2026-11-25T10:00:00-03:00" in fechas_juan and "2026-12-02T16:00:00-03:00" in fechas_juan
    lara = next(p for p in base.t["pacientes"] if p["nombre_completo"] == "Lara Rozenfeld")
    assert lara["centro"] == "fonoar_la_plata" and lara["tipo_atencion"] == "canto"
    # Correr de nuevo (el script corre cada día): nada nuevo.
    r2 = importar_planilla(parsear_planilla(FILAS, hoy=HOY), sb=base, hoy=HOY)
    assert (r2["alumnos_nuevos"], r2["clases_nuevas"]) == (0, 0)
