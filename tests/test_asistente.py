"""Asistente personal por Telegram (server_api/asistente.py), fase 1.

Se simulan el modelo de lenguaje, la base y Telegram.
"""
import os
import sys
from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "server_api"))

import asistente as A  # noqa: E402


@pytest.fixture(autouse=True)
def entorno(monkeypatch):
    monkeypatch.setenv("SESSION_SECRET", "secreto-de-prueba")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "123:abc")
    monkeypatch.delenv("TELEGRAM_NOTIFY_CHAT_ID", raising=False)
    config = {}
    monkeypatch.setattr(A, "config_leer", lambda k, d=None: config.get(k, d))
    monkeypatch.setattr(A, "config_guardar", lambda k, v: config.__setitem__(k, v) or True)
    enviados = []
    monkeypatch.setattr(A, "enviar", lambda texto, chat_id="": enviados.append((chat_id or config.get("chat_id"), texto)) or {"ok": True})
    monkeypatch.setattr(A, "_tg", lambda metodo, datos, timeout=20: {"ok": True})
    A._HISTORIAL.clear()
    A._UPDATES_VISTOS.clear()
    return config, enviados


def test_piensa_con_herramientas(monkeypatch):
    llamados = []
    monkeypatch.setitem(A.HERRAMIENTAS, "buscar_paciente",
                        (lambda texto: llamados.append(texto) or {"pacientes": [{"paciente_id": "p1", "nombre": "Alvarez Yesica"}]}, "x"))
    pasos = iter([
        {"accion": "herramienta", "nombre": "buscar_paciente", "args": {"texto": "Yesica"}},
        {"accion": "responder", "texto": "Encontré a Alvarez Yesica."},
    ])
    vistos = []

    def llm(mensajes):
        vistos.append(mensajes[-1]["content"])
        return next(pasos)
    assert A.pensar("¿Está Yesica?", llm=llm) == "Encontré a Alvarez Yesica."
    assert llamados == ["Yesica"]
    assert "Alvarez Yesica" in vistos[-1]  # el resultado vuelve al modelo


def test_herramienta_inexistente_no_rompe():
    pasos = iter([{"accion": "herramienta", "nombre": "borrar_todo", "args": {}},
                  {"accion": "responder", "texto": "No puedo hacer eso."}])
    assert A.pensar("borrá todo", llm=lambda m: next(pasos)) == "No puedo hacer eso."


@pytest.fixture
def cliente():
    app = FastAPI()
    app.include_router(A.router)
    return TestClient(app)


def _update(texto, chat=555, uid=1):
    return {"update_id": uid, "message": {"chat": {"id": chat}, "text": texto}}


def test_webhook_rechaza_sin_secreto(cliente):
    assert cliente.post("/api/asistente/telegram", json=_update("hola")).status_code == 403


def test_vinculacion_y_chat(cliente, entorno, monkeypatch):
    config, enviados = entorno
    h = {"X-Telegram-Bot-Api-Secret-Token": A.secreto_webhook()}
    config["codigo_vinculacion"] = {"codigo": "a1b2c3d4", "vence": 9999999999}
    assert cliente.post("/api/asistente/telegram", json=_update("/start a1b2c3d4"), headers=h).status_code == 200
    assert config["chat_id"] == "555" and "vinculado" in enviados[-1][1]
    # Otro chat: se ignora.
    n = len(enviados)
    cliente.post("/api/asistente/telegram", json=_update("hola", chat=999, uid=2), headers=h)
    assert len(enviados) == n
    # El chat vinculado conversa.
    monkeypatch.setattr(A, "pensar", lambda texto, hist=None, llm=None: f"respuesta a: {texto}")
    cliente.post("/api/asistente/telegram", json=_update("¿qué tengo mañana?", uid=3), headers=h)
    assert enviados[-1] == ("555", "respuesta a: ¿qué tengo mañana?")
    # Telegram reintenta el mismo update: no se responde dos veces.
    n = len(enviados)
    cliente.post("/api/asistente/telegram", json=_update("¿qué tengo mañana?", uid=3), headers=h)
    assert len(enviados) == n


def test_codigo_vencido(cliente, entorno):
    config, enviados = entorno
    config["codigo_vinculacion"] = {"codigo": "a1b2c3d4", "vence": 1}
    cliente.post("/api/asistente/telegram", json=_update("/start a1b2c3d4"),
                 headers={"X-Telegram-Bot-Api-Secret-Token": A.secreto_webhook()})
    assert "chat_id" not in config and "venció" in enviados[-1][1]


def test_aviso_agenda_importada(entorno):
    config, enviados = entorno
    config["chat_id"] = "555"
    A.aviso_agenda_importada({"fecha": "2026-11-18", "turnos_nuevos": 2, "pacientes_nuevos": 1,
                              "detalle": [{"hora": "09:30", "paciente": "Alvarez Yesica", "tipo": "terapia",
                                           "obra_social": "IOMA", "accion_paciente": "existente"},
                                          {"hora": "14:30", "paciente": "Pineyro Javier", "tipo": "evaluacion",
                                           "obra_social": "", "accion_paciente": "nuevo"}]})
    texto = enviados[-1][1]
    assert "18/11" in texto and "09:30 Alvarez Yesica (tratamiento, IOMA)" in texto
    assert "Pineyro Javier (evaluación) · NUEVO" in texto


def test_repaso_una_vez_por_dia_y_en_horario(cliente, entorno, monkeypatch):
    config, enviados = entorno
    config["chat_id"] = "555"
    monkeypatch.setattr(A, "repaso_del_dia", lambda llm=None, fecha="": "Repaso de hoy: 2 turnos")
    monkeypatch.setattr(A, "_ahora", lambda: datetime(2026, 11, 18, 7, 30, tzinfo=A.ZONA))
    assert cliente.post("/api/asistente/repaso-dia").json()["motivo"] == "enviando"
    assert enviados[-1][1] == "Repaso de hoy: 2 turnos"
    assert cliente.post("/api/asistente/repaso-dia").json()["motivo"] == "ya enviado hoy"
    monkeypatch.setattr(A, "_ahora", lambda: datetime(2026, 11, 19, 22, 0, tzinfo=A.ZONA))
    assert cliente.post("/api/asistente/repaso-dia").json()["motivo"] == "fuera de horario"
