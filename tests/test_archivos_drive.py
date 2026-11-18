"""Archivos de la ficha en Google Drive (server_api/archivos_drive.py).

Se simula la API de Drive con httpx.MockTransport: carpeta por paciente
(se crea una vez y se reusa), subida reanudable por trozos y mensajes
claros cuando falta el permiso o la API.
"""
import asyncio
import json
import os
import sys

import httpx
import pytest
from fastapi import HTTPException

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import archivos_drive as AD  # noqa: E402


class DriveFalso:
    def __init__(self, error=None):
        self.carpetas, self.trozos, self.subidas, self.error = [], [], [], error

    def __call__(self, req: httpx.Request) -> httpx.Response:
        if self.error:
            return httpx.Response(403, text=self.error)
        url = str(req.url)
        if req.method == "GET" and "/drive/v3/files" in url:
            q = req.url.params.get("q", "")
            hallados = [c for c in self.carpetas
                        if any(f"value='{v}'" in q for v in c["appProperties"].values())]
            return httpx.Response(200, json={"files": hallados[:1]})
        if req.method == "POST" and url.startswith(AD.DRIVE + "/files"):
            meta = json.loads(req.content)
            c = {"id": f"carp-{len(self.carpetas)}", "name": meta["name"],
                 "webViewLink": f"https://drive/c{len(self.carpetas)}",
                 "appProperties": meta.get("appProperties", {})}
            self.carpetas.append(c)
            return httpx.Response(200, json=c)
        if req.method == "POST" and url.startswith(AD.DRIVE_UPLOAD):
            self.subidas.append(json.loads(req.content))
            return httpx.Response(200, headers={"location": "https://upload/sesion-1"})
        if req.method == "PUT" and url == "https://upload/sesion-1":
            self.trozos.append(req.headers["content-range"])
            total = int(req.headers["content-range"].split("/")[1])
            fin = int(req.headers["content-range"].split(" ")[1].split("-")[1].split("/")[0])
            if fin + 1 < total:
                return httpx.Response(308)
            return httpx.Response(200, json={"id": "arch-1", "webViewLink": "https://drive/a1"})
        return httpx.Response(404)


def _correr(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


PACIENTE = {"id": "1234abcd-0000", "nombre_completo": "Alvarez Yesica"}


def test_carpeta_por_paciente_se_crea_una_vez():
    drive = DriveFalso()

    async def dos_veces():
        async with httpx.AsyncClient(transport=httpx.MockTransport(drive)) as c:
            a = await AD.carpeta_paciente(c, "tok", PACIENTE)
            b = await AD.carpeta_paciente(c, "tok", PACIENTE)
            return a, b
    a, b = _correr(dos_veces())
    assert a["id"] == b["id"]
    assert [c["name"] for c in drive.carpetas] == ["VocalisLab - Pacientes", "Alvarez Yesica (1234abcd)"]


def test_subida_por_trozos(tmp_path, monkeypatch):
    monkeypatch.setattr(AD, "TROZO", 256 * 1024)
    ruta = tmp_path / "video.mp4"
    ruta.write_bytes(b"x" * (256 * 1024 * 2 + 1000))
    drive = DriveFalso()

    async def subir():
        async with httpx.AsyncClient(transport=httpx.MockTransport(drive)) as c:
            return await AD.subir_a_drive(c, "tok", str(ruta), "v.mp4", "video/mp4", "carp-1", {})
    r = _correr(subir())
    assert r["id"] == "arch-1"
    total = ruta.stat().st_size
    assert drive.trozos == [f"bytes 0-262143/{total}", f"bytes 262144-524287/{total}",
                            f"bytes 524288-{total - 1}/{total}"]
    assert drive.subidas[0]["parents"] == ["carp-1"]


@pytest.mark.parametrize("error,esperado", [
    ('{"error": {"status": "PERMISSION_DENIED", "details": "ACCESS_TOKEN_SCOPE_INSUFFICIENT"}}', AD.MSG_PERMISO),
    ('{"error": {"message": "Google Drive API has not been used in project", "status": "SERVICE_DISABLED"}}', AD.MSG_API),
])
def test_errores_de_drive_con_mensaje_claro(error, esperado):
    drive = DriveFalso(error=error)

    async def intentar():
        async with httpx.AsyncClient(transport=httpx.MockTransport(drive)) as c:
            await AD.carpeta_paciente(c, "tok", PACIENTE)
    with pytest.raises(HTTPException) as e:
        _correr(intentar())
    assert e.value.detail == esperado
