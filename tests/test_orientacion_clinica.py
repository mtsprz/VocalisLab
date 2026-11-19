"""Orientación clínica: situación quirúrgica, texto sin cortes y guardado."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import criterios_clinicos as CC  # noqa: E402
import llm_client  # noqa: E402
import orientacion_clinica as OC  # noqa: E402


def test_situacion_quirurgica_por_registros():
    post = CC.situacion_quirurgica({"anamnesis": {"antecedentes_salud": "Paciente operada de pólipo en marzo 2026 (microcirugía realizada)."}})
    assert post["etapa"] == "postquirurgica" and "operada" in post["evidencia"][0]["texto"]
    pre = CC.situacion_quirurgica({"informes_orl": [{"fecha_informe": "2026-10-01", "diagnostico_principal": "Pólipo cordal izquierdo",
                                                    "datos_estructurados": {"recomendaciones": "Se indica microcirugía laríngea."}}]})
    assert pre["etapa"] == "prequirurgica"
    lesion = CC.situacion_quirurgica({"anamnesis": {"diagnostico_orl": "Edema de Reinke bilateral"}})
    assert lesion["etapa"] == "a_definir"
    nodulos = CC.situacion_quirurgica({"anamnesis": {"diagnostico_orl": "Nódulos bilaterales, sin indicación quirúrgica"}})
    assert nodulos["etapa"] == "no_quirurgica"  # la negación no cuenta como prequirúrgica
    assert CC.situacion_quirurgica({})["etapa"] == "sin_datos"
    assert CC.situacion_quirurgica({}, manual="postquirurgica")["origen"] == "indicada por el profesional"


def test_valores_a_revisar_no_borra_texto():
    permitidos = {"18", "7", "6"}
    texto = "VHI-10 18/40. Autopercepción 8/10 y 7/10. Usa la voz 6 h/día. Hacer 3 series de 10 repeticiones."
    assert OC.valores_a_revisar(texto, permitidos) == ["8/10"]


class _R:
    def __init__(self, texto, motivo):
        self.status_code = 200
        self._d = {"candidates": [{"content": {"parts": [{"text": texto}]}, "finishReason": motivo}]}
        self.text = ""

    def json(self):
        return self._d


def test_texto_largo_continua_si_se_corta(monkeypatch):
    import httpx
    llamadas = []
    respuestas = [_R("1. Síntesis del cuadro\nLa paciente presen", "MAX_TOKENS"), _R("ta disfonía.\nFin.", "STOP")]

    def post(url, **kw):
        llamadas.append(kw["json"]["contents"])
        return respuestas[len(llamadas) - 1]
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.setattr(httpx, "post", post)
    texto, modelo, completo = llm_client.gemini_texto_completo("prompt")
    assert texto == "1. Síntesis del cuadro\nLa paciente presenta disfonía.\nFin." and completo
    assert len(llamadas) == 2 and llamadas[1][-1]["parts"][0]["text"].startswith("Seguí exactamente")


def test_generar_cruza_todo_y_guarda(monkeypatch):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    import api_clinica
    import ficha_integral
    from test_practica_guiada import _Base
    base = _Base()
    base.t["evaluaciones_clinicas"] = [{"paciente_id": "p1", "fecha": "2026-11-10", "vhi10_score": 18, "grbas": {"G": 2, "B": 2}}]
    base.t["anamnesis"][0]["diagnostico_orl"] = "Pólipo cordal; se indica microcirugía"
    monkeypatch.setattr(api_clinica, "supabase", base)
    monkeypatch.setattr(api_clinica, "banco_ejercicios_completo", lambda: {"sections": [{"exercises": [{"name": "Glissandos"}]}]})
    visto = {}

    def fake(prompt, **kw):
        visto["prompt"] = prompt
        return "1. Síntesis del cuadro\nVHI-10 18/40, autopercepción 9/10.\nOrientación de apoyo al criterio profesional.", "gemini-test", True
    monkeypatch.setattr(llm_client, "gemini_texto_completo", fake)
    app = FastAPI()
    app.include_router(ficha_integral.router)
    app.include_router(OC.router)
    c = TestClient(app)
    r = c.post("/api/ficha/p1/orientacion", json={}).json()
    assert r["situacion"]["etapa"] == "prequirurgica" and "PREQUIRÚRGICA" in visto["prompt"]
    assert "Glissandos" in visto["prompt"] and '"vhi10_score": 18' in visto["prompt"]
    assert r["valores_a_revisar"] == ["9/10"] and r["texto"].endswith("profesional.")
    assert base.t["orientaciones_clinicas"][0]["texto"] == r["texto"]
    assert c.put(f"/api/orientaciones/{r['id']}", json={"texto": "Editado por mí"}).status_code == 200
    assert base.t["orientaciones_clinicas"][0]["editado"] is True
    assert c.get("/api/ficha/p1/orientaciones").json()["orientaciones"][0]["texto"] == "Editado por mí"
