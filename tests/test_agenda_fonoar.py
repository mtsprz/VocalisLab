"""Importación de la agenda de Fonoar (server_api/agenda_fonoar.py).

Formato real del mail: asunto "Fonoar: Turnos del 18/11/2026 Mat: 7276",
tabla Hora | Paciente | O.Social | Telefono, filas de sección ("Estudios") y
códigos en el campo Paciente (TTO, EVAL, prefijo CLASE DE CANTO).
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

from agenda_fonoar import importar_agenda, interpretar_paciente, parsear_agenda  # noqa: E402

HTML = """<p>Turnos del 18/11/2026 Mat: 7276</p><table>
<tr><th>Hora</th><th>Paciente</th><th>O.Social</th><th>Telefono</th></tr>
<tr><td>Estudios</td></tr>
<tr><td>09:30</td><td>ALVAREZ YESICA TTO</td><td>IOMA</td><td></td><td></td></tr>
<tr><td>10:00</td><td>CLASE DE CANTO JUAN SORACCO</td><td></td><td></td></tr>
<tr><td>14:30</td><td>PINEYRO JAVIER EVAL</td><td>PARTICU</td><td>221 555-1234</td></tr>
</table>"""
TEXTO_PEGADO = ("Turnos del 18/11/2026 Mat: 7276\nHora\tPaciente\tO.Social\tTelefono\n"
                "Estudios\n09:30\tALVAREZ YESICA TTO\tIOMA\t\n"
                "10:00\tCLASE DE CANTO JUAN SORACCO\t\t\n14:30\tPINEYRO JAVIER EVAL\tPARTICU\t")


def test_codigos_del_campo_paciente():
    assert interpretar_paciente("ALVAREZ YESICA TTO")[ "tipo"] == "terapia"
    assert interpretar_paciente("PINEYRO JAVIER EVAL")["tipo"] == "evaluacion"
    c = interpretar_paciente("CLASE DE CANTO JUAN SORACCO")
    assert c["nombre"] == "Juan Soracco" and c["motivo"] == "Clase de canto"


def test_html_y_texto_pegado_dan_lo_mismo():
    a, b = parsear_agenda(HTML), parsear_agenda(TEXTO_PEGADO)
    assert a["fecha"] == b["fecha"] == "2026-11-18"
    clave = lambda r: [(t["hora"], t["nombre"], t["tipo"], t["obra_social"]) for t in r["turnos"]]
    assert clave(a) == clave(b) == [
        ("09:30", "Alvarez Yesica", "terapia", "IOMA"),
        ("10:00", "Juan Soracco", "control", ""),
        ("14:30", "Pineyro Javier", "evaluacion", "Particular"),
    ]
    assert a["turnos"][0]["seccion"] == "Estudios"


class _Q:
    def __init__(self, base, tabla):
        self.base, self.tabla, self.filtros, self.op, self.datos = base, tabla, {}, "select", None

    def select(self, *_):
        return self

    def limit(self, *_):
        return self

    def eq(self, k, v):
        self.filtros[k] = v
        return self

    def insert(self, d):
        self.op, self.datos = "insert", d
        return self

    def update(self, d):
        self.op, self.datos = "update", d
        return self

    def execute(self):
        class R:
            pass
        r, filas = R(), self.base.tablas.setdefault(self.tabla, [])
        if self.op == "insert":
            fila = dict(self.datos, id=f"{self.tabla}-{len(filas) + 1}")
            filas.append(fila)
            r.data = [fila]
        elif self.op == "update":
            for f in filas:
                if all(f.get(k) == v for k, v in self.filtros.items()):
                    f.update(self.datos)
            r.data = []
        else:
            r.data = [f for f in filas if all(f.get(k) == v for k, v in self.filtros.items())]
        return r


class _Base:
    def __init__(self, pacientes=None):
        self.tablas = {"pacientes": list(pacientes or []), "turnos": []}

    def table(self, t):
        return _Q(self, t)


def test_importa_sin_duplicar_y_reconoce_existentes():
    base = _Base([{"id": "p-viejo", "nombre_completo": "Yesica Alvarez", "telefono": ""}])
    agenda = parsear_agenda(HTML)
    r = importar_agenda(agenda, sb=base)
    assert (r["pacientes_nuevos"], r["turnos_nuevos"]) == (2, 3)
    yesica = base.tablas["pacientes"][0]
    assert yesica["centro"] == "fonoar_la_plata" and yesica["obra_social"] == "IOMA"
    nuevos = [p for p in base.tablas["pacientes"] if p["id"] != "p-viejo"]
    assert {p["nombre_completo"] for p in nuevos} == {"Juan Soracco", "Pineyro Javier"}
    assert all(p["centro"] == "fonoar_la_plata" and p["dni"] is None for p in nuevos)
    t = base.tablas["turnos"][0]
    assert t["fecha_hora"] == "2026-11-18T09:30:00-03:00" and t["tipo"] == "terapia"
    # Segunda importación del mismo mail: nada nuevo.
    r2 = importar_agenda(parsear_agenda(HTML), sb=base)
    assert (r2["pacientes_nuevos"], r2["turnos_nuevos"], r2["turnos_existentes"]) == (0, 0, 3)


def test_simulacion_no_escribe():
    base = _Base()
    r = importar_agenda(parsear_agenda(HTML), simular=True, sb=base)
    assert r["turnos_nuevos"] == 3 and base.tablas["turnos"] == [] and base.tablas["pacientes"] == []
