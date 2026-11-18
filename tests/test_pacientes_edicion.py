"""Edición de pacientes (server_api/api_clinica.py).

Caso real: un paciente que llegó por la agenda de Fonoar (sin fecha de
nacimiento ni DNI) parecía no poder editarse. La causa era de pantalla (el
formulario se abría fuera de la vista y los errores no se mostraban); acá
se verifica que el servidor acepte la edición con campos vacíos y que un
DNI repetido dé un mensaje claro.
"""
import os
import sys

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import api_clinica as AC  # noqa: E402


@pytest.fixture
def cliente(monkeypatch):
    enviados = {}

    def falso_update(tabla, rid, data):
        if data.get("fecha_nacimiento") == "":
            raise HTTPException(status_code=500, detail='invalid input syntax for type date: ""')
        if data.get("dni") == "11111111":
            raise HTTPException(status_code=500, detail='duplicate key value violates unique constraint "pacientes_dni_key"')
        enviados.update(data)
        return {"id": rid, **data}

    monkeypatch.setattr(AC, "_db_update", falso_update)
    monkeypatch.setattr(AC, "supabase", None)
    app = FastAPI()
    app.include_router(AC.router)
    return TestClient(app), enviados


def _form(**extra):
    base = {"nombre_completo": "Pineyro Javier", "dni": "", "fecha_nacimiento": "", "sexo": "Masculino",
            "telefono": "2215551234", "email": "", "ocupacion": "", "derivador": "", "notas_iniciales": ""}
    base.update(extra)
    return base


def test_editar_paciente_sin_fecha_de_nacimiento(cliente):
    c, enviados = cliente
    r = c.put("/api/pacientes/p1", data=_form())
    assert r.status_code == 200, r.text
    # La fecha vacía nunca llega como "" (FastAPI la descarta o se guarda NULL).
    assert enviados.get("fecha_nacimiento") is None and not enviados.get("dni")
    assert enviados["telefono"] == "2215551234"


def test_dni_duplicado_da_mensaje_claro(cliente):
    c, _ = cliente
    r = c.put("/api/pacientes/p1", data=_form(dni="11111111"))
    assert r.status_code == 409
    assert "Ya hay otro paciente con ese DNI" in r.json()["detail"]
