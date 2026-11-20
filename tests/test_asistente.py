"""Asistente personal por Telegram (server_api/asistente.py), fases 1 y 2.

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
    llamadas_tg = []
    monkeypatch.setattr(A, "_tg", lambda metodo, datos, timeout=20: llamadas_tg.append((metodo, datos)) or {"ok": True})
    monkeypatch.setattr(A, "LLAMADAS_TG", llamadas_tg, raising=False)
    A._HISTORIAL.clear()
    A._PENDIENTES.clear()
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
    monkeypatch.setattr(A, "pensar", lambda texto, hist=None, llm=None, **kw: f"respuesta a: {texto}")
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


# ─── Fase 2: notas de voz, acciones con confirmación y comandos ─────────

def _h():
    return {"X-Telegram-Bot-Api-Secret-Token": A.secreto_webhook()}


def test_nota_de_voz_se_transcribe_y_responde(cliente, entorno, monkeypatch):
    config, enviados = entorno
    config["chat_id"] = "555"
    pedidos = []
    monkeypatch.setattr(A, "transcribir", lambda fid, mime="audio/ogg": pedidos.append(fid) or "qué tengo mañana")
    monkeypatch.setattr(A, "pensar", lambda texto, hist=None, llm=None, **kw: f"respuesta a: {texto}")
    upd = {"update_id": 10, "message": {"chat": {"id": 555}, "voice": {"file_id": "F1", "mime_type": "audio/ogg"}}}
    cliente.post("/api/asistente/telegram", json=upd, headers=_h())
    assert pedidos == ["F1"]
    assert enviados[-2][1] == "🎙️ «qué tengo mañana»"
    assert enviados[-1][1] == "respuesta a: (nota de voz) qué tengo mañana"


def test_nota_de_voz_fallida_avisa(cliente, entorno, monkeypatch):
    config, enviados = entorno
    config["chat_id"] = "555"

    def falla(fid, mime="audio/ogg"):
        raise RuntimeError("sin clave")
    monkeypatch.setattr(A, "transcribir", falla)
    upd = {"update_id": 11, "message": {"chat": {"id": 555}, "voice": {"file_id": "F1"}}}
    cliente.post("/api/asistente/telegram", json=upd, headers=_h())
    assert "No pude entender el audio" in enviados[-1][1]


def test_whisper_groq_renombra_oga(monkeypatch):
    monkeypatch.setenv("GROQ_API_KEY", "k")
    vistos = {}

    class Resp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"text": " hola "}

    def post(url, headers=None, data=None, files=None, timeout=None):
        vistos.update(url=url, nombre=files["file"][0], modelo=data["model"])
        return Resp()
    monkeypatch.setattr(A.httpx, "post", post)
    assert A._whisper_groq(b"x", "file_7.oga") == "hola"
    assert vistos["nombre"] == "file_7.ogg" and vistos["modelo"] == "whisper-large-v3-turbo"
    assert vistos["url"].endswith("/audio/transcriptions")


def _accion_falsa(monkeypatch, ejecutados):
    monkeypatch.setitem(A.ACCIONES, "agendar_turno", (
        lambda paciente_id, fecha, hora, **kw: {"resumen": f"Agendar a Yesica el {fecha} {hora}"},
        lambda paciente_id, fecha, hora, **kw: ejecutados.append((paciente_id, fecha, hora)) or {"texto": "✅ Agendado"},
        "x"))


def test_accion_se_propone_y_se_confirma_con_boton(cliente, entorno, monkeypatch):
    config, enviados = entorno
    config["chat_id"] = "555"
    ejecutados = []
    _accion_falsa(monkeypatch, ejecutados)
    pasos = iter([{"accion": "herramienta", "nombre": "agendar_turno",
                   "args": {"paciente_id": "p1", "fecha": "2026-11-26", "hora": "10:00"}},
                  {"accion": "responder", "texto": "Te lo dejo listo."}])
    monkeypatch.setattr(A, "_llm_json", lambda m: next(pasos))
    cliente.post("/api/asistente/telegram", json=_update("agendá a Yesica el jueves a las 10", uid=20), headers=_h())
    assert ejecutados == []  # nada se hace sin confirmar
    metodo, datos = A.LLAMADAS_TG[-1]
    assert metodo == "sendMessage" and "Agendar a Yesica el 2026-11-26 10:00" in datos["text"]
    boton_ok = datos["reply_markup"]["inline_keyboard"][0][0]["callback_data"]
    assert boton_ok.startswith("ok:")
    cb = {"update_id": 21, "callback_query": {"id": "c1", "data": boton_ok,
                                              "message": {"message_id": 9, "chat": {"id": 555}}}}
    cliente.post("/api/asistente/telegram", json=cb, headers=_h())
    assert ejecutados == [("p1", "2026-11-26", "10:00")]
    assert enviados[-1][1] == "✅ Agendado"
    # El mismo botón otra vez no repite la acción.
    cliente.post("/api/asistente/telegram", json=dict(cb, update_id=22), headers=_h())
    assert len(ejecutados) == 1


def test_accion_se_confirma_o_cancela_por_texto(cliente, entorno, monkeypatch):
    config, enviados = entorno
    config["chat_id"] = "555"
    ejecutados = []
    _accion_falsa(monkeypatch, ejecutados)
    prop = {"nombre": "agendar_turno", "args": {"paciente_id": "p1", "fecha": "2026-11-26", "hora": "10:00"},
            "resumen": "Agendar"}
    A.proponer("555", prop)
    cliente.post("/api/asistente/telegram", json=_update("No", uid=30), headers=_h())
    assert ejecutados == [] and "no cambié nada" in enviados[-1][1]
    A.proponer("555", prop)
    monkeypatch.setattr(A, "pensar", lambda texto, hist=None, llm=None, **kw: "¿Confirmo o no?")
    cliente.post("/api/asistente/telegram", json=_update("Sí, pero a las 11", uid=31), headers=_h())
    assert ejecutados == []  # no es un «sí» suelto: lo interpreta el modelo
    cliente.post("/api/asistente/telegram", json=_update("dale", uid=32), headers=_h())
    assert len(ejecutados) == 1


def test_accion_con_error_vuelve_al_modelo(monkeypatch):
    monkeypatch.setitem(A.ACCIONES, "agendar_turno", (lambda **kw: {"error": "Paciente inexistente"}, None, "x"))
    vistos = []
    pasos = iter([{"accion": "herramienta", "nombre": "agendar_turno", "args": {}},
                  {"accion": "responder", "texto": "No encontré al paciente."}])

    def llm(m):
        vistos.append(m[-1]["content"])
        return next(pasos)
    props = []
    assert A.pensar("agendá a X", llm=llm, propuestas=props) == "No encontré al paciente."
    assert props == [] and "Paciente inexistente" in vistos[-1]


def test_sin_chat_las_acciones_no_se_proponen():
    pasos = iter([{"accion": "herramienta", "nombre": "estado_turno", "args": {"turno_id": "t", "estado": "cancelado"}},
                  {"accion": "responder", "texto": "ok"}])
    vistos = []

    def llm(m):
        vistos.append(m[-1]["content"])
        return next(pasos)
    A.pensar("cancelá", llm=llm)  # el repaso automático no puede cambiar datos
    assert "solo se pueden proponer" in vistos[-1]


def test_comandos_rapidos(cliente, entorno, monkeypatch):
    config, enviados = entorno
    config["chat_id"] = "555"
    monkeypatch.setattr(A, "h_agenda", lambda d="", h="": {"turnos": [
        {"cuando": "Thu 26/11 09:30", "paciente": "Alvarez Yesica", "tipo": "tratamiento",
         "centro": "Fonoar La Plata", "estado": "programado"},
        {"cuando": "Thu 26/11 11:00", "paciente": "Pineyro Javier", "tipo": "control",
         "centro": "", "estado": "cancelado"}]})
    monkeypatch.setattr(A, "pensar", lambda *a, **k: pytest.fail("los comandos no usan el modelo"))
    cliente.post("/api/asistente/telegram", json=_update("/hoy", uid=40), headers=_h())
    assert enviados[-1][1] == "Hoy (1 turno):\n• 09:30 Alvarez Yesica — tratamiento (Fonoar La Plata)"
    cliente.post("/api/asistente/telegram", json=_update("/ayuda", uid=41), headers=_h())
    assert "/pendientes" in enviados[-1][1]


def test_fecha_hora_valida():
    assert A._fecha_hora("2026-11-26", "9") == "2026-11-26T09:00:00-03:00"
    assert A._fecha_hora("2026-11-26", "14:30") == "2026-11-26T14:30:00-03:00"
    with pytest.raises(ValueError):
        A._fecha_hora("26/11", "10:00")
    with pytest.raises(ValueError):
        A._fecha_hora("2026-11-26", "25:00")


def test_sistema_lista_acciones_y_calendario():
    s = A._sistema()
    assert "agendar_turno" in s and "Próximos días:" in s and "(nota de voz)" in s
