"""Plan clínico del cuadernillo (server_api/plan_cuadernillo.py) y firma.

- Cada área a trabajar sale con al menos 3 variantes (si el banco las tiene),
  elegidas según el perfil del paciente.
- Nunca se agrega un ejercicio contraindicado para el perfil.
- Lo que eligió el profesional no se quita.
- La firma es "Fonoaudiólogo" (sin "Lic.") y ningún texto impreso dice "IA".
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

from firma_profesional import limpiar_nombre, limpiar_titulo, sin_mencion_ia  # noqa: E402
from plan_cuadernillo import armar_plan, perfil_clinico  # noqa: E402

NODULOS_DOCENTE = {
    "paciente": {"sexo": "Femenino", "ocupacion": "Docente", "demanda_vocal_horas": 6},
    "anamnesis": {"diagnostico_orl": "Nódulos vocales bilaterales",
                  "motivo_consulta": "Ronquera y cansancio vocal",
                  "sintomas": {"fatiga_vocal": True, "dolor_cuello": False}},
    "escalas": {"grbas": {"G": 2, "R": 2, "B": 1, "A": 0, "S": 2},
                "tme_o": 11, "tme_s": 12, "vhi10_score": 18},
    "acustica": {"hnr_db": 16.5},
    "riesgoVocal": {"puntaje_total": 85},
}
PARALISIS = {
    "paciente": {"sexo": "Masculino"},
    "anamnesis": {"diagnostico_orl": "Parálisis cordal izquierda, hiatus fonatorio"},
    "escalas": {"grbas": {"G": 2, "B": 3, "A": 2}, "tme_o": 7, "tme_s": 12},
}


def _areas(plan):
    return {a["id"]: a for a in plan["areas"]}


def test_perfil_lee_datos_del_paciente():
    p = perfil_clinico(NODULOS_DOCENTE)
    for cond in ("nodulo", "hiperfuncion", "fonastenia", "docentes", "debilidad"):
        assert p.tiene(cond), cond
    assert any("GRBAS" in ev for ev in p.evidencia["hiperfuncion"])
    assert not p.tiene("paralisis")


def test_minimo_tres_por_area_cuando_el_banco_alcanza():
    plan = armar_plan(["le_huche", "tubo_agua", "calentamiento"], NODULOS_DOCENTE)
    for a in plan["areas"]:
        if not a["faltan"]:
            assert a["cantidad"] >= 3, a["id"]
        else:
            assert a["aviso"], a["id"]  # si falta, se avisa (nunca se rellena mal)
    assert len(plan["ejercicios_ids"]) == len(set(plan["ejercicios_ids"]))


def test_no_quita_lo_elegido_por_el_profesional():
    elegidos = ["le_huche", "tubo_agua", "calentamiento"]
    plan = armar_plan(elegidos, NODULOS_DOCENTE)
    assert set(elegidos) <= set(plan["ejercicios_ids"])


def test_contraindicados_nunca_se_agregan_con_nodulos():
    plan = armar_plan([], NODULOS_DOCENTE)
    for prohibido in ("empuje_glotico", "lsvt_fuerte", "pushing_terapeutico",
                      "deglucion_sonorizada", "messa_di_voce"):
        assert prohibido not in plan["ejercicios_ids"], prohibido
    assert {x["id"] for x in plan["excluidos"]} >= {"empuje_glotico", "lsvt_fuerte"}


def test_profesional_elige_contraindicado_queda_con_alerta():
    plan = armar_plan(["empuje_glotico"], NODULOS_DOCENTE)
    assert "empuje_glotico" in plan["ejercicios_ids"]
    assert [a["id"] for a in plan["alertas"]] == ["empuje_glotico"]


def test_paralisis_trabaja_cierre_y_no_relajacion_laringea():
    plan = armar_plan([], PARALISIS)
    lar = _areas(plan)["laringeo"]["ejercicios"]
    ids = {e["id"] for e in lar}
    assert "b_prolongada" in ids
    assert not ids & {"masaje_laringeo", "masaje_aronson", "traccion_laringea"}
    assert _areas(plan)["respiratorio"]["prioritaria"]


def test_orden_terapeutico_por_area():
    plan = armar_plan([], NODULOS_DOCENTE)
    orden = [a["id"] for a in plan["areas"]]
    assert orden.index("corporal") < orden.index("respiratorio") < orden.index("sovte") \
        < orden.index("resonancia") < orden.index("higiene")


def test_reflujo_solo_si_hay_reflujo():
    assert "pautas_rlf" not in armar_plan([], NODULOS_DOCENTE)["ejercicios_ids"]
    con_rlf = dict(NODULOS_DOCENTE, anamnesis={"diagnostico_orl": "Laringitis por reflujo (RLF)"})
    assert "pautas_rlf" in armar_plan([], con_rlf)["ejercicios_ids"]


def test_firma_sin_licenciado():
    # El valor viejo guardado venía sin tildes: se imprime con tildes.
    assert limpiar_nombre("Lic. Matias Perez") == "Matías Pérez"
    assert limpiar_nombre("Licenciado Matías Pérez") == "Matías Pérez"
    assert limpiar_nombre("Lic. Ana Gómez") == "Ana Gómez"
    assert limpiar_nombre("") == "Matías Pérez"
    assert limpiar_titulo("Lic. en Fonoaudiología") == "Fonoaudiólogo"
    assert limpiar_titulo("Fonoaudiólogo") == "Fonoaudiólogo"


def test_textos_impresos_sin_ia():
    assert sin_mencion_ia("Cuadernillo — Prescripción IA Fonoaudiológica") == \
        "Cuadernillo — Prescripción Fonoaudiológica"
    t = sin_mencion_ia("Disfonía funcional.\n\nInterpretación generada por IA — Requiere correlación.")
    assert "IA" not in t and t.startswith("Disfonía funcional.")
    assert sin_mencion_ia("AVQI e IAVQI normales") == "AVQI e IAVQI normales"
