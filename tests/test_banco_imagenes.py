"""Banco de imágenes: el mapa DB (una sola query) resuelve asignaciones y
nunca lanza (sin Supabase -> {} y el PDF usa el dibujo vectorial)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import imagen_terapeutica as it


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows

    def select(self, *a):
        return self

    def in_(self, col, ids):
        self._ids = set(ids)
        return self

    def execute(self):
        class R:
            pass
        r = R()
        r.data = [x for x in self._rows if x.get("exercise_id") in self._ids]
        return r


class _FakeSB:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        assert name == "ejercicio_imagenes"
        return _FakeTable(self._rows)


def test_mapa_db_resuelve_y_descarga(monkeypatch, tmp_path):
    rows = [
        {"exercise_id": "tubo_agua", "image_url": "http://x/tubo.png", "storage_path": "tubo_agua.png"},
        {"exercise_id": "otro", "image_url": "http://x/otro.png", "storage_path": "otro.png"},
    ]
    monkeypatch.setattr(it, "_supabase", lambda: _FakeSB(rows))
    monkeypatch.setattr(it, "_cache_path", lambda prompt, prov: str(tmp_path / f"{prov}.png"))
    monkeypatch.setattr(it, "_es_imagen_valida", lambda p: False)
    monkeypatch.setattr(it, "_descargar", lambda url, dest, timeout=60: True)
    out = it.mapa_imagenes_db(["tubo_agua", "sin_imagen"])
    assert out == {"tubo_agua": str(tmp_path / "db.png")}


def test_mapa_db_sin_supabase_devuelve_vacio(monkeypatch):
    monkeypatch.setattr(it, "_supabase", lambda: None)
    assert it.mapa_imagenes_db(["tubo_agua"]) == {}
    assert it.mapa_imagenes_db([]) == {}


def test_mapa_db_nunca_lanza(monkeypatch):
    def _boom():
        raise RuntimeError("db caída")
    monkeypatch.setattr(it, "_supabase", _boom)
    assert it.mapa_imagenes_db(["tubo_agua"]) == {}
