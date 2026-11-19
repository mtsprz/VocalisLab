"""Voz guía: grabaciones del profesional para la práctica del paciente."""
import base64
import os
import sys

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import voz_guia as VG  # noqa: E402
from test_practica_guiada import _Base, _Q  # noqa: E402


class _QV(_Q):
    def upsert(self, d):
        self.op, self.d = "upsert", d
        return self

    def delete(self):
        self.op = "delete"
        return self

    def execute(self):
        filas = self.base.t.setdefault(self.tabla, [])
        if self.op == "upsert":
            filas[:] = [f for f in filas if f.get("clave") != self.d["clave"]] + [dict(self.d)]

            class R:
                data = [self.d]
            return R()
        if self.op == "delete":
            filas[:] = [f for f in filas if not all(f.get(k) == v for k, v in self.f.items())]

            class R:
                data = []
            return R()
        return super().execute()


class _BaseV(_Base):
    def table(self, t):
        return _QV(self, t)


@pytest.fixture
def cliente(monkeypatch):
    import api_clinica
    base = _BaseV()
    base.t["practicas"] = [{"id": "r1", "token": "tok", "paciente_id": "p1", "activa": True, "vence_at": "2099-01-01T00:00:00+00:00"}]
    monkeypatch.setattr(api_clinica, "supabase", base)
    app = FastAPI()
    app.include_router(VG.router)
    return TestClient(app), base


WAV = base64.b64encode(b"RIFF" + b"\x00" * 600).decode()


def test_grabar_escuchar_y_borrar(cliente):
    c, base = cliente
    assert c.put("/api/voz-guia/ahora_vos", json={"audio_b64": WAV, "mime": "audio/wav", "duracion_s": 0.8}).status_code == 200
    assert c.put("/api/voz-guia/ej:glissandos", json={"audio_b64": WAV, "mime": "audio/wav"}).status_code == 200
    lista = c.get("/api/voz-guia").json()
    assert next(f for f in lista["frases"] if f["clave"] == "ahora_vos")["grabada"]
    assert next(f for f in lista["ejercicios"] if f["clave"] == "ej:glissandos")["grabada"]
    r = c.get("/api/voz-guia/ahora_vos/audio")
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content.startswith(b"RIFF")
    # El paciente la escucha solo con un enlace válido.
    assert c.get("/api/practica/tok/voz/ahora_vos").status_code == 200
    assert c.get("/api/practica/otro/voz/ahora_vos").status_code == 404
    assert VG.claves_grabadas(base) == ["ahora_vos", "ej:glissandos"]
    assert c.delete("/api/voz-guia/ahora_vos").status_code == 200
    assert c.get("/api/voz-guia/ahora_vos/audio").status_code == 404


def test_rechaza_claves_y_audios_invalidos(cliente):
    c, _ = cliente
    assert c.put("/api/voz-guia/../../x", json={"audio_b64": WAV}).status_code in (400, 404)
    assert c.put("/api/voz-guia/Hola Mundo", json={"audio_b64": WAV}).status_code == 400
    assert c.put("/api/voz-guia/escucha", json={"audio_b64": "no-es-base64!!"}).status_code == 400
    assert c.put("/api/voz-guia/escucha", json={"audio_b64": WAV, "mime": "text/html"}).status_code == 400
    assert c.put("/api/voz-guia/escucha", json={"audio_b64": base64.b64encode(b"x").decode()}).status_code == 400
