"""Cliente Gemini central (server_api/llm_client.py).

Google apaga modelos (gemini-2.0-flash el 1/6/2026). Estos tests simulan la
API para verificar que se saltean los modelos apagados aunque estén
configurados y que, si uno falla, se prueba el siguiente.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import llm_client  # noqa: E402
from llm_client import gemini_generate, gemini_models, gemini_texto  # noqa: E402


class _Resp:
    def __init__(self, status, data=None, text=""):
        self.status_code, self._data, self.text = status, data or {}, text

    def json(self):
        return self._data


def _ok(texto):
    return _Resp(200, {"candidates": [{"content": {"parts": [{"text": texto}]}}]})


@pytest.fixture(autouse=True)
def _entorno(monkeypatch):
    for v in ("GEMINI_MODEL", "AI_MODEL", "GEMINI_IMAGE_MODEL"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("GEMINI_API_KEY", "clave-de-prueba")


def test_saltea_modelos_apagados_aunque_esten_configurados(monkeypatch):
    monkeypatch.setenv("AI_MODEL", "gemini-2.0-flash")
    monkeypatch.setenv("GEMINI_MODEL", "gemini-1.5-flash")
    modelos = gemini_models()
    assert not any(m.startswith(("gemini-2.0", "gemini-1.5")) for m in modelos)
    assert modelos[0] == "gemini-3.6-flash"


def test_respeta_modelo_configurado_vigente(monkeypatch):
    monkeypatch.setenv("GEMINI_MODEL", "gemini-3.8-flash")
    assert gemini_models()[0] == "gemini-3.8-flash"
    assert "gemini-3.6-flash" in gemini_models()  # el respaldo sigue


def test_modelos_de_imagen_vigentes():
    modelos = gemini_models("imagen")
    assert "gemini-2.0-flash-preview-image-generation" not in modelos
    assert modelos[0] == "gemini-nano-banana-2.1"


def test_si_un_modelo_falla_prueba_el_siguiente(monkeypatch):
    import httpx
    pedidos = []

    def falso_post(url, params=None, json=None, timeout=None):
        pedidos.append(url)
        return _Resp(404, text="model not found") if len(pedidos) == 1 else _ok('{"a": 1}')

    monkeypatch.setattr(httpx, "post", falso_post)
    data, modelo = gemini_generate([{"text": "hola"}])
    assert gemini_texto(data) == '{"a": 1}'
    assert modelo == llm_client.GEMINI_TEXT_MODELS[1]
    assert "gemini-3.6-flash" in pedidos[0]


def test_sin_ningun_modelo_disponible_da_error_claro(monkeypatch):
    import httpx
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _Resp(503, text="caído"))
    with pytest.raises(RuntimeError, match="Ningún modelo Gemini respondió"):
        gemini_generate([{"text": "hola"}])


def test_sin_clave(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY")
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        gemini_generate([{"text": "hola"}])
