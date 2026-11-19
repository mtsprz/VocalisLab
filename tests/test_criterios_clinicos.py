"""Exactitud clínica: los valores se informan tal cual y se leen bien."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import criterios_clinicos as CC  # noqa: E402


def _datos(**kw):
    d = {"paciente": {"sexo": "Masculino", "demanda_vocal_horas": 6, "ocupacion": "Docente"},
         "anamnesis": {}, "evaluaciones": [], "analisis_acusticos": [], "autoevaluaciones": [],
         "f0_conversacional": []}
    d.update(kw)
    return d


def _h(lect, parametro):
    return next(h for h in lect["hallazgos"] if h["parametro"] == parametro)


def test_autopercepcion_7_es_7_con_su_fuente():
    d = _datos(autoevaluaciones=[{"autopercepcion": 7, "completada_at": "2026-11-18T10:00:00"}],
               anamnesis={"autopercepcion_voz": 8, "fecha": "2025-03-01"})
    h = _h(CC.hallazgos(d), "Autopercepción de la voz")
    assert h["valor"] == 7 and h["lectura"].startswith("7/10")
    assert h["fuente"] == "respondida por el paciente (enlace)" and h["fecha"] == "2026-11-18"
    assert h["nivel"] == "normal"  # 7 = valoración conservada (10 = excelente)


def test_autopercepcion_baja_y_discrepancia_cercana():
    d = _datos(evaluaciones=[{"fecha": "2026-11-10", "autopercepcion_vocal": 8}],
               autoevaluaciones=[{"autopercepcion": 4, "completada_at": "2026-11-18"}])
    lect = CC.hallazgos(d)
    assert _h(lect, "Autopercepción de la voz")["nivel"] == "alterado"
    assert any("8/10" in a and "4/10" in a for a in lect["alertas"])


def test_vhi10_corte_11():
    for valor, nivel in ((11, "normal"), (12, "alterado"), (0, "normal")):
        lect = CC.hallazgos(_datos(evaluaciones=[{"fecha": "2026-11-10", "vhi10_score": valor}]))
        h = _h(lect, "VHI-10")
        assert h["valor"] == valor and h["nivel"] == nivel


def test_faltantes_no_se_leen_como_normales():
    lect = CC.hallazgos(_datos())
    params = {h["parametro"] for h in lect["hallazgos"]}
    assert "VHI-10" not in params and "Riesgo vocal" not in params and "GRBAS" not in params
    assert {"VHI-10", "ficha de riesgo vocal", "GRBAS", "análisis acústico", "autopercepción"} <= set(lect["faltan"])


def test_grbas_por_grado_no_por_porcentaje():
    lect = CC.hallazgos(_datos(evaluaciones=[{"fecha": "2026-11-10", "grbas": {"G": 2, "R": 1, "B": 2, "A": 0, "S": 1}}]))
    h = _h(lect, "GRBAS")
    assert h["valor"] == "G2 R1 B2 A0 S1" and h["nivel"] == "moderado"
    assert "soplosidad moderado (B2)" in h["lectura"]


def test_tmf_y_cociente_segun_sexo():
    ev = [{"fecha": "2026-11-10", "tme_o": 17, "tme_s": 25}]
    v = CC.hallazgos(_datos(evaluaciones=ev))
    assert _h(v, "TMF vocal sostenida")["nivel"] == "leve"  # varón < 20 s
    m = CC.hallazgos(_datos(evaluaciones=ev, paciente={"sexo": "Femenino"}))
    assert _h(m, "TMF vocal sostenida")["nivel"] == "normal"  # mujer ≥ 15 s
    assert _h(v, "Cociente /s/ ÷ vocal")["valor"] == "1.47" and _h(v, "Cociente /s/ ÷ vocal")["nivel"] == "alterado"


def test_riesgo_grupos_en_los_bordes():
    for total, nivel in ((69, "normal"), (70, "moderado"), (138, "moderado"), (139, "alterado")):
        h = _h(CC.hallazgos(_datos(evaluaciones=[{"fecha": "2026-11-10", "riesgo_vocal_score": total}])), "Riesgo vocal")
        assert h["nivel"] == nivel and h["valor"] == total


def test_acustica_cortes():
    ac = [{"fecha": "2026-11-10", "jitter_local_pct": 1.04, "shimmer_local_pct": 4.2, "hnr_db": 17.5, "cpps_db": 15, "avqi": 2.95}]
    lect = CC.hallazgos(_datos(analisis_acusticos=ac))
    assert _h(lect, "Jitter local")["nivel"] == "normal"  # 1,04 es el corte: > 1,04 alterado
    assert _h(lect, "Shimmer local")["nivel"] == "alterado"
    assert _h(lect, "HNR")["nivel"] == "alterado" and _h(lect, "CPPS")["nivel"] == "normal"
    assert _h(lect, "AVQI")["nivel"] == "alterado"


def test_patron_hipofuncional_requiere_dos_datos():
    ev = [{"fecha": "2026-11-10", "grbas": {"G": 1, "B": 2}, "tme_o": 12, "tme_s": 18}]
    pats = CC.hallazgos(_datos(evaluaciones=ev))["patrones"]
    assert any("cierre glótico" in p["patron"] for p in pats)
    ev1 = [{"fecha": "2026-11-10", "grbas": {"G": 1, "B": 2}}]
    assert not any("cierre glótico" in p["patron"] for p in CC.hallazgos(_datos(evaluaciones=ev1))["patrones"])


def test_texto_con_numero_inventado_se_quita():
    d = _datos(evaluaciones=[{"fecha": "2026-11-10", "vhi10_score": 18}],
               autoevaluaciones=[{"autopercepcion": 7, "completada_at": "2026-11-18"}])
    lect = CC.hallazgos(d)
    ok = CC.numeros_permitidos(lect, d)
    texto, quitadas = CC.verificar_texto(
        "Síntesis\nEl VHI-10 es 18/40. La autopercepción es 8/10. Usa la voz 6 h/día.", ok)
    assert "18/40" in texto and "6 h/día" in texto and "8/10" not in texto
    assert quitadas == ["La autopercepción es 8/10."]
