"""Análisis acústico externo (server_api/externo_ocr.py).

Caso real: el PDF de un análisis acústico de otra profesional daba "Error en
OCR: La IA no devolvió un JSON válido" (el modelo de Groq se quedaba sin
espacio y no se le pedía JSON). Ahora Gemini lee el archivo completo y Groq
queda de respaldo con JSON estricto.
"""
import io
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import externo_ocr as EO  # noqa: E402
import llm_client  # noqa: E402

RESPUESTA = {"valores": {"f0_mean": "215,4 Hz", "jitter_local_pct": "0,42 %", "hnr_db": 21.3, "avqi": None},
             "origen_detectado": "Praat", "confianza": "alta", "observaciones": ""}


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "clave")
    app = FastAPI()
    app.include_router(EO.router)
    return TestClient(app)


def _pdf():
    return {"archivo": ("informe_castelli.pdf", io.BytesIO(b"%PDF-1.4 " + b"x" * 500), "application/pdf")}


def test_gemini_lee_el_pdf(cliente, monkeypatch):
    monkeypatch.setattr(EO, "_gemini_extract", lambda data, mime: (RESPUESTA, "gemini-3.6-flash"))
    d = cliente.post("/api/analisis-externo/ocr", files=_pdf()).json()
    assert d["ok"] and d["valores"]["f0_mean"] == 215.4 and d["valores"]["jitter_local_pct"] == 0.42
    assert d["modelo_ia"] == "gemini-3.6-flash"


def test_respaldo_groq_con_json_estricto(cliente, monkeypatch):
    def falla(data, mime):
        raise RuntimeError("cuota agotada")
    monkeypatch.setattr(EO, "_gemini_extract", falla)
    monkeypatch.setattr(EO, "_pdf_to_text", lambda data: "Informe acústico. F0 media 215,4 Hz. " * 10)
    pedidos = {}

    def groq(messages, **kw):
        pedidos.update(kw)
        return '```json\n{"valores": {"f0_mean": 215.4, "hnr_db": "21,3"},}\n```', "openai/gpt-oss-20b"
    monkeypatch.setattr(llm_client, "groq_chat", groq)
    d = cliente.post("/api/analisis-externo/ocr", files=_pdf()).json()
    assert d["ok"] and d["valores"]["hnr_db"] == 21.3
    assert pedidos["response_format"] == {"type": "json_object"} and pedidos["max_tokens"] >= 4000


def test_si_todo_falla_dice_por_que(cliente, monkeypatch):
    def falla(*a, **k):
        raise RuntimeError("sin servicio")
    monkeypatch.setattr(EO, "_gemini_extract", falla)
    monkeypatch.setattr(EO, "_pdf_to_text", lambda data: "")
    d = cliente.post("/api/analisis-externo/ocr", files=_pdf()).json()
    assert not d["ok"] and "Gemini" in d["error"] and "escaneado" in d["error"]
