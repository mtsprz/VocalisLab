"""Ficha integral: datos juntos, imágenes de los PDF y análisis de estudios."""
import os
import sys

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import archivos_drive as AD  # noqa: E402
import ficha_integral as FI  # noqa: E402
from test_recomendaciones import _Base  # noqa: E402


def _base():
    b = _Base()
    b.t.update({
        "anamnesis": [{"paciente_id": "p1", "fecha": "2026-11-01", "diagnostico_orl": "Nódulos bilaterales"}],
        "informes_orl": [{"id": "i1", "paciente_id": "p1", "fecha": "2023-05-02", "texto_extraido": "largo…",
                          "diagnostico_principal": "Nódulos"}],
        "autoevaluaciones": [{"id": "a1", "paciente_id": "p1", "estado": "completada", "token": "secreto"},
                             {"id": "a2", "paciente_id": "p1", "estado": "pendiente", "token": "x"}],
        "turnos": [{"paciente_id": "p1", "fecha_hora": "2023-04-01T10:00:00", "estado": "completado"},
                   {"paciente_id": "p1", "fecha_hora": "2026-11-20T10:00:00", "estado": "pendiente"}],
        "archivos_paciente": [
            {"id": "f1", "paciente_id": "p1", "fecha": "2026-03-01", "tipo": "video", "drive_file_id": "D2", "titulo": "Estrobo 2026"},
            {"id": "f0", "paciente_id": "p1", "fecha": "2023-05-02", "tipo": "foto", "drive_file_id": "D1", "titulo": "Laringo 2023"},
        ],
    })
    return b


def _cliente(monkeypatch, base):
    import api_clinica
    monkeypatch.setattr(api_clinica, "supabase", base)
    app = FastAPI()
    app.include_router(FI.router)
    return TestClient(app)


def test_ficha_junta_todo_sin_datos_sensibles(monkeypatch):
    d = _cliente(monkeypatch, _base()).get("/api/ficha/p1").json()
    assert d["paciente"]["nombre_completo"] == "León Murillo"
    assert d["anamnesis"]["diagnostico_orl"] == "Nódulos bilaterales"
    assert "texto_extraido" not in d["informes_orl"][0]
    assert [a["id"] for a in d["autoevaluaciones"]] == ["a1"] and "token" not in d["autoevaluaciones"][0]
    assert d["turnos"] == {"total": 2, "realizados": 1, "primero": "2023-04-01"}
    assert d["f0_conversacional"][0]["f0_mediana_hz"] == 118.5
    assert len(d["archivos"]) == 2


def test_ficha_inexistente(monkeypatch):
    assert _cliente(monkeypatch, _base()).get("/api/ficha/nadie").status_code == 404


def test_analisis_compara_en_orden_cronologico(monkeypatch):
    import google_auth
    import llm_client

    async def token(_uid):
        return "tok"

    async def bajar(_tok, fid):
        return f"bytes-{fid}".encode(), "image/jpeg", fid

    enviado = {}

    def generar(partes, *_a, **_k):
        enviado["partes"] = partes
        return {"x": 1}, "gemini-test"

    monkeypatch.setattr(google_auth, "_get_valid_token", token)
    monkeypatch.setattr(FI, "_descargar_drive", bajar)
    monkeypatch.setattr(llm_client, "gemini_generate", generar)
    monkeypatch.setattr(llm_client, "gemini_texto", lambda _r: "Evolución favorable. Análisis orientativo.")
    r = _cliente(monkeypatch, _base()).post("/api/ficha/p1/analisis-imagenes", json={"archivo_ids": ["f1", "f0"]})
    assert r.status_code == 200, r.text
    j = r.json()
    assert [e["id"] for e in j["estudios"]] == ["f0", "f1"]  # 2023 antes que 2026
    textos = [p["text"] for p in enviado["partes"] if "text" in p]
    assert "Compará ambos estudios" in textos[0] and "Nódulos bilaterales" in textos[0]
    assert sum(1 for p in enviado["partes"] if "inline_data" in p) == 2


def test_analisis_rechaza_archivo_de_otro_paciente(monkeypatch):
    c = _cliente(monkeypatch, _base())
    assert c.post("/api/ficha/p2/analisis-imagenes", json={"archivo_ids": ["f1"]}).status_code == 404
    assert c.post("/api/ficha/p1/analisis-imagenes", json={"archivo_ids": []}).status_code == 400


def test_extrae_imagenes_del_pdf_sin_iconos(tmp_path):
    import fitz
    grande = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 320, 240), False)
    grande.clear_with(200)
    chica = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 40, 40), False)
    chica.clear_with(50)
    doc = fitz.open()
    pag = doc.new_page()
    pag.insert_image(fitz.Rect(20, 20, 340, 260), pixmap=grande)
    pag.insert_image(fitz.Rect(20, 300, 60, 340), pixmap=chica)  # logo/ícono: se descarta
    ruta = tmp_path / "informe.pdf"
    doc.save(str(ruta))
    imgs = AD.extraer_imagenes_pdf(str(ruta))
    assert len(imgs) == 1 and imgs[0][2:] == (320, 240)
