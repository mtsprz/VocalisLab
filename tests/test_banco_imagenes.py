"""Banco de imágenes v2 (galerías): el mapa DB devuelve listas ordenadas con
epígrafes en UNA sola query, y nunca lanza (sin Supabase -> {} y el PDF usa
el dibujo vectorial)."""
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

    def order(self, *a):
        return self

    def execute(self):
        class R:
            pass
        r = R()
        r.data = sorted(
            [x for x in self._rows if x.get("exercise_id") in self._ids],
            key=lambda x: x.get("orden", 0),
        )
        return r


class _FakeSB:
    def __init__(self, rows):
        self._rows = rows

    def table(self, name):
        assert name == "ejercicio_imagenes"
        return _FakeTable(self._rows)


def test_mapa_db_galeria_ordenada_con_epigrafes(monkeypatch, tmp_path):
    rows = [
        {"exercise_id": "tubo_agua", "image_url": "http://x/2.png",
         "storage_path": "tubo_agua-1.png", "orden": 1, "epigrafe": "Paso 2"},
        {"exercise_id": "tubo_agua", "image_url": "http://x/1.png",
         "storage_path": "tubo_agua-0.png", "orden": 0, "epigrafe": "Paso 1"},
    ]
    monkeypatch.setattr(it, "_supabase", lambda: _FakeSB(rows))
    monkeypatch.setattr(it, "_cache_path", lambda prompt, prov: str(tmp_path / f"{prov}.png"))
    monkeypatch.setattr(it, "_es_imagen_valida", lambda p: False)
    monkeypatch.setattr(it, "_descargar", lambda url, dest, timeout=60: True)
    out = it.mapa_imagenes_db(["tubo_agua", "sin_imagen"])
    gal = out["tubo_agua"]
    assert [g["epigrafe"] for g in gal] == ["Paso 1", "Paso 2"]
    assert all(g["path"] == str(tmp_path / "db.png") for g in gal)
    assert "sin_imagen" not in out


def test_mapa_db_sin_supabase_devuelve_vacio(monkeypatch):
    monkeypatch.setattr(it, "_supabase", lambda: None)
    assert it.mapa_imagenes_db(["tubo_agua"]) == {}
    assert it.mapa_imagenes_db([]) == {}


def test_mapa_db_nunca_lanza(monkeypatch):
    def _boom():
        raise RuntimeError("db caída")
    monkeypatch.setattr(it, "_supabase", _boom)
    assert it.mapa_imagenes_db(["tubo_agua"]) == {}


def test_buscar_compat_devuelve_primera(monkeypatch, tmp_path):
    rows = [
        {"exercise_id": "tubo_agua", "image_url": "http://x/1.png",
         "storage_path": "a.png", "orden": 0, "epigrafe": ""},
    ]
    monkeypatch.setattr(it, "_supabase", lambda: _FakeSB(rows))
    monkeypatch.setattr(it, "_cache_path", lambda prompt, prov: str(tmp_path / f"{prov}.png"))
    monkeypatch.setattr(it, "_es_imagen_valida", lambda p: True)
    assert it.buscar_imagen_guardada("tubo_agua") == str(tmp_path / "db.png")
    assert it.buscar_imagen_guardada("inexistente") is None
