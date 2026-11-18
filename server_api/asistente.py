"""Asistente personal del Consultorio de Voz (Telegram).

Fase 1:
- Chat privado por Telegram: solo responde al chat vinculado del
  profesional. Entiende preguntas en lenguaje natural y consulta la app con
  herramientas de solo lectura (agenda, pacientes, resumen clínico y
  evolución de F0). No cambia datos.
- Avisos proactivos: agenda de Fonoar importada y repaso del día de
  atención (07:30, lo dispara GitHub Actions).

Activación (desde la app, sin tocar variables salvo TELEGRAM_BOT_TOKEN):
POST /api/asistente/activar conecta el webhook de Telegram con este
servidor y devuelve un enlace t.me/<bot>?start=<código>; al tocarlo, el
chat queda vinculado (tabla asistente_config).

Privacidad: a Telegram y al modelo de lenguaje no se envían DNI, teléfono
ni email. Los mensajes automáticos usan el nombre del paciente y datos
clínicos resumidos.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import time
import traceback
import unicodedata
from collections import deque
from datetime import datetime, timedelta, timezone

import httpx
from fastapi import APIRouter, BackgroundTasks, HTTPException, Request

router = APIRouter()

ZONA = timezone(timedelta(hours=-3))  # Argentina (sin horario de verano)
NOMBRE = "Asistente del Consultorio de Voz"
MAX_PASOS = 5
_HISTORIAL: dict = {}          # chat_id → deque de mensajes (memoria corta)
_UPDATES_VISTOS: deque = deque(maxlen=200)
_CACHE_CONFIG: dict = {}

TIPO_TURNO = {"terapia": "tratamiento", "evaluacion": "evaluación", "control": "control",
              "primera_vez": "primera vez", "seguimiento": "seguimiento"}
NOMBRE_CENTRO = {"fonoar_la_plata": "Fonoar La Plata", "due_brandsen": "DUE Brandsen",
                 "virtual": "Atención virtual"}


# ─── Configuración persistente (tabla asistente_config) ────────────────

def _sb():
    from api_clinica import supabase
    return supabase


def config_leer(clave: str, defecto=None):
    if clave in _CACHE_CONFIG:
        return _CACHE_CONFIG[clave]
    try:
        filas = _sb().table("asistente_config").select("valor").eq("clave", clave).execute().data or []
        valor = filas[0]["valor"] if filas else defecto
    except Exception:
        valor = defecto
    if valor is not None:
        _CACHE_CONFIG[clave] = valor
    return valor


def config_guardar(clave: str, valor) -> bool:
    _CACHE_CONFIG[clave] = valor
    try:
        _sb().table("asistente_config").upsert({"clave": clave, "valor": valor},
                                               on_conflict="clave").execute()
        return True
    except Exception as e:
        print(f"[asistente] no se pudo guardar {clave}: {str(e)[:120]}")
        return False


def chat_vinculado() -> str:
    return str(config_leer("chat_id") or os.environ.get("TELEGRAM_NOTIFY_CHAT_ID", "") or "").strip()


# ─── Telegram ──────────────────────────────────────────────────────────

def _token_bot() -> str:
    return os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()


def secreto_webhook() -> str:
    from sesion_web import _secreto
    return hmac.new(_secreto(), b"asistente-telegram", hashlib.sha256).hexdigest()[:48]


def _tg(metodo: str, datos: dict, timeout: float = 20) -> dict:
    token = _token_bot()
    if not token:
        return {"ok": False, "description": "Falta TELEGRAM_BOT_TOKEN"}
    try:
        r = httpx.post(f"https://api.telegram.org/bot{token}/{metodo}", json=datos, timeout=timeout)
        return r.json()
    except Exception as e:
        return {"ok": False, "description": str(e)[:200]}


def enviar(texto: str, chat_id: str = "") -> dict:
    """Manda un mensaje (en partes de 3800 caracteres si es largo)."""
    chat_id = chat_id or chat_vinculado()
    if not chat_id:
        return {"ok": False, "description": "Asistente sin chat vinculado"}
    res = {"ok": False}
    for i in range(0, max(len(texto), 1), 3800):
        res = _tg("sendMessage", {"chat_id": chat_id, "text": texto[i:i + 3800],
                                  "disable_web_page_preview": True})
    return res


def avisar(texto: str) -> None:
    """Aviso proactivo: nunca rompe el flujo que lo llama."""
    try:
        if chat_vinculado() and _token_bot():
            enviar(texto)
    except Exception:
        traceback.print_exc()


# ─── Herramientas (solo lectura) ───────────────────────────────────────

def _norm(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower())
                   if unicodedata.category(c) != "Mn")


def _ahora() -> datetime:
    return datetime.now(ZONA)


def _consulta_tolerante(armar, campos_completos: str, campos_basicos: str):
    """Consulta con centro/obra social; si la base aún no tiene esas
    columnas (migración de centros sin correr), repite sin ellas."""
    try:
        return armar(campos_completos).execute().data or []
    except Exception as e:
        if "centro" in str(e) or "obra_social" in str(e):
            return armar(campos_basicos).execute().data or []
        raise


def h_agenda(desde: str = "", hasta: str = "") -> dict:
    """Turnos entre dos fechas (AAAA-MM-DD, inclusive)."""
    hoy = _ahora().date()
    d = desde or hoy.isoformat()
    h = hasta or d
    base = "fecha_hora, tipo, estado, modalidad, motivo, paciente_id, "
    filas = _consulta_tolerante(
        lambda campos: (_sb().table("turnos").select(campos)
                        .gte("fecha_hora", f"{d}T00:00:00-03:00").lte("fecha_hora", f"{h}T23:59:59-03:00")
                        .order("fecha_hora")),
        base + "pacientes(nombre_completo, centro, obra_social)", base + "pacientes(nombre_completo)")
    turnos = []
    for t in filas:
        p = t.get("pacientes") or {}
        try:
            fh = datetime.fromisoformat(str(t["fecha_hora"]).replace("Z", "+00:00")).astimezone(ZONA)
            cuando = fh.strftime("%a %d/%m %H:%M")
        except Exception:
            cuando = str(t.get("fecha_hora"))
        turnos.append({"cuando": cuando, "paciente": p.get("nombre_completo"),
                       "paciente_id": t.get("paciente_id"),
                       "centro": NOMBRE_CENTRO.get(p.get("centro") or "", p.get("centro") or ""),
                       "obra_social": p.get("obra_social") or "",
                       "tipo": TIPO_TURNO.get(t.get("tipo"), t.get("tipo")), "estado": t.get("estado"),
                       "motivo": t.get("motivo"), "modalidad": t.get("modalidad")})
    return {"desde": d, "hasta": h, "cantidad": len(turnos), "turnos": turnos}


def h_buscar_paciente(texto: str) -> dict:
    """Pacientes cuyo nombre contiene las palabras buscadas."""
    palabras = [w for w in re.split(r"\s+", _norm(texto)) if len(w) > 1]
    filas = _consulta_tolerante(
        lambda campos: _sb().table("pacientes").select(campos).limit(5000),
        "id, nombre_completo, nombre, centro, obra_social, ocupacion", "id, nombre_completo, nombre, ocupacion")
    hallados = []
    for p in filas:
        nombre = _norm(p.get("nombre_completo") or p.get("nombre") or "")
        if palabras and all(w in nombre for w in palabras):
            hallados.append({"paciente_id": p["id"], "nombre": p.get("nombre_completo") or p.get("nombre"),
                             "centro": NOMBRE_CENTRO.get(p.get("centro") or "", p.get("centro") or ""),
                             "obra_social": p.get("obra_social") or "", "ocupacion": p.get("ocupacion") or ""})
    return {"cantidad": len(hallados), "pacientes": hallados[:10]}


def _uno(tabla: str, pid: str, orden: str, campos: str = "*"):
    try:
        filas = (_sb().table(tabla).select(campos).eq("paciente_id", pid)
                 .order(orden, desc=True).limit(1).execute().data or [])
        return filas[0] if filas else None
    except Exception:
        return None


def h_resumen_paciente(paciente_id: str) -> dict:
    """Ficha resumida: datos, anamnesis, evaluación, acústica, F0, turnos y archivos."""
    sb = _sb()
    filas = sb.table("pacientes").select("*").eq("id", paciente_id).execute().data or []
    if not filas:
        return {"error": "Paciente inexistente"}
    p = filas[0]
    out = {
        "paciente": {"nombre": p.get("nombre_completo") or p.get("nombre"),
                     "sexo": p.get("sexo") or p.get("genero"), "fecha_nacimiento": p.get("fecha_nacimiento"),
                     "ocupacion": p.get("ocupacion"), "demanda_vocal_horas": p.get("demanda_vocal_horas"),
                     "centro": NOMBRE_CENTRO.get(p.get("centro") or "", p.get("centro") or ""),
                     "obra_social": p.get("obra_social"), "derivador": p.get("derivador"),
                     "notas_iniciales": (p.get("notas_iniciales") or "")[:300]},
    }
    a = _uno("anamnesis", paciente_id, "fecha")
    out["anamnesis"] = {"fecha": a.get("fecha"), "motivo": a.get("motivo_consulta"),
                        "diagnostico_orl": a.get("diagnostico_orl"),
                        "resumen": (a.get("resumen_clinico") or "")[:600]} if a else None
    e = _uno("evaluaciones_clinicas", paciente_id, "fecha")
    out["ultima_evaluacion"] = {k: e.get(k) for k in (
        "fecha", "grbas", "rasati", "vhi10_score", "tme_o", "tme_s", "indice_so",
        "riesgo_vocal_score", "autopercepcion_vocal")} if e else None
    ac = _uno("analisis_acusticos", paciente_id, "fecha")
    out["ultimo_analisis_acustico"] = {k: ac.get(k) for k in (
        "fecha", "f0_mean_hz", "f0_mean", "jitter_local_pct", "shimmer_local_pct", "hnr_db",
        "cpps_db", "avqi") if k in ac} if ac else None
    # Evolución de F0 conversacional (Companion, PitchMeter, audios importados).
    try:
        ses = (sb.table("companion_sessions").select("id, recorded_at").eq("patient_id", paciente_id)
               .order("recorded_at", desc=True).limit(12).execute().data or [])
        ids = [s["id"] for s in ses]
        f0 = {}
        if ids:
            for r in (sb.table("session_acoustics").select("session_id, task_type, f0_median_hz")
                      .in_("session_id", ids).execute().data or []):
                if r.get("task_type") == "conversacion_espontanea" and r.get("f0_median_hz"):
                    f0[r["session_id"]] = r["f0_median_hz"]
        out["f0_conversacional"] = [{"fecha": str(s.get("recorded_at") or "")[:10], "mediana_hz": f0[s["id"]]}
                                    for s in reversed(ses) if s["id"] in f0]
    except Exception:
        out["f0_conversacional"] = []
    try:
        ts = (sb.table("turnos").select("fecha_hora, tipo, estado").eq("paciente_id", paciente_id)
              .order("fecha_hora", desc=True).limit(20).execute().data or [])
        ahora = _ahora().isoformat()
        out["turnos"] = {"pasados": len([t for t in ts if str(t["fecha_hora"]) < ahora]),
                         "proximos": [str(t["fecha_hora"])[:16] for t in ts if str(t["fecha_hora"]) >= ahora][:3]}
    except Exception:
        out["turnos"] = None
    try:
        arch = (sb.table("archivos_paciente").select("tipo, titulo, fecha").eq("paciente_id", paciente_id)
                .order("fecha", desc=True).limit(10).execute().data or [])
        out["archivos"] = arch
    except Exception:
        out["archivos"] = None
    c = _uno("cuadernillos_paciente", paciente_id, "fecha_creacion", "fecha_creacion, titulo")
    out["ultimo_cuadernillo"] = c
    return out


HERRAMIENTAS = {
    "agenda": (h_agenda, "Turnos entre fechas. args: {desde: 'AAAA-MM-DD', hasta: 'AAAA-MM-DD'}"),
    "buscar_paciente": (h_buscar_paciente, "Busca pacientes por nombre. args: {texto}"),
    "resumen_paciente": (h_resumen_paciente,
                         "Ficha resumida de un paciente (usar el paciente_id de buscar_paciente o agenda). "
                         "args: {paciente_id}"),
}


# ─── Cerebro ───────────────────────────────────────────────────────────

def _sistema() -> str:
    ahora = _ahora()
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    lista = "\n".join(f"- {n}: {d}" for n, (_f, d) in HERRAMIENTAS.items())
    return (
        f"Sos el {NOMBRE}, el asistente personal de Matías Pérez, fonoaudiólogo especializado en voz "
        "(La Plata, Argentina). Trabajás como una secretaria clínica atenta: cercano y profesional, "
        "en español rioplatense, con respuestas claras y breves para leer en el celular (Telegram, "
        "texto plano, sin Markdown ni tablas; podés usar viñetas con «•»).\n"
        f"Ahora es {dias[ahora.weekday()]} {ahora.strftime('%d/%m/%Y %H:%M')} (hora de Argentina).\n"
        "Centros: Fonoar La Plata (entrega su propio cuadernillo), DUE Brandsen y Atención virtual.\n\n"
        "Reglas:\n"
        "- Usá las herramientas para cualquier dato de la app; NUNCA inventes datos clínicos, fechas ni "
        "nombres. Si un dato no está, decilo.\n"
        "- No diagnostiques: describí lo que muestran los datos (ej. «la F0 subió 2 semitonos») y, si "
        "corresponde, sugerí qué revisar.\n"
        "- Por ahora solo podés consultar: si te piden agendar, anotar o modificar algo, explicá que esa "
        "función llega en la próxima etapa y que por ahora se hace desde la app.\n"
        "- Si hay varios pacientes parecidos, preguntá cuál.\n\n"
        f"Herramientas:\n{lista}\n\n"
        "Respondé SIEMPRE un único objeto JSON, sin texto fuera de él, con una de estas formas:\n"
        '{"accion": "herramienta", "nombre": "<herramienta>", "args": {...}}\n'
        '{"accion": "responder", "texto": "<mensaje para Matías>"}'
    )


def _llm_json(mensajes: list) -> dict:
    """JSON del primer proveedor que responda (Groq, luego Gemini)."""
    errores = []
    try:
        from llm_client import groq_chat
        txt, _m = groq_chat(mensajes, temperature=0.2, max_tokens=1800,
                            response_format={"type": "json_object"}, timeout=45)
        return json.loads(re.search(r"\{.*\}", txt, re.DOTALL).group(0))
    except Exception as e:
        errores.append(f"groq: {str(e)[:120]}")
    try:
        from llm_client import gemini_generate, gemini_texto
        texto = "\n\n".join(f"[{m['role']}]\n{m['content']}" for m in mensajes)
        data, _m = gemini_generate([{"text": texto}], {"temperature": 0.2,
                                                        "responseMimeType": "application/json"}, timeout=60)
        return json.loads(re.search(r"\{.*\}", gemini_texto(data), re.DOTALL).group(0))
    except Exception as e:
        errores.append(f"gemini: {str(e)[:120]}")
    raise RuntimeError("Sin modelo disponible: " + " | ".join(errores))


def _resultado_texto(datos) -> str:
    texto = json.dumps(datos, ensure_ascii=False, default=str)
    return texto if len(texto) <= 7000 else texto[:7000] + "…(recortado)"


def pensar(pregunta: str, historial: list = None, llm=None) -> str:
    """Bucle del asistente: decide herramientas hasta poder responder."""
    llm = llm or _llm_json
    mensajes = [{"role": "system", "content": _sistema()}]
    mensajes += list(historial or [])
    mensajes.append({"role": "user", "content": pregunta})
    for _ in range(MAX_PASOS):
        decision = llm(mensajes)
        accion = decision.get("accion")
        if accion == "responder":
            return str(decision.get("texto") or "").strip() or "No tengo una respuesta para eso."
        if accion == "herramienta" and decision.get("nombre") in HERRAMIENTAS:
            nombre = decision["nombre"]
            fn = HERRAMIENTAS[nombre][0]
            try:
                resultado = fn(**(decision.get("args") or {}))
            except Exception as e:
                resultado = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
            mensajes.append({"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)})
            mensajes.append({"role": "user", "content": f"Resultado de {nombre}: {_resultado_texto(resultado)}"})
            continue
        mensajes.append({"role": "user", "content":
                         "Formato inválido. Respondé solo con el JSON pedido (herramienta o responder)."})
    return "Me trabé buscando esa información. ¿Me lo preguntás de otra forma?"


def conversar(chat_id: str, texto: str) -> str:
    hist = _HISTORIAL.setdefault(chat_id, deque(maxlen=12))
    try:
        respuesta = pensar(texto, list(hist))
    except Exception as e:
        traceback.print_exc()
        respuesta = f"Ahora no puedo consultar el modelo ({str(e)[:120]}). Probá en un rato."
    hist.append({"role": "user", "content": texto})
    hist.append({"role": "assistant", "content": json.dumps({"accion": "responder", "texto": respuesta},
                                                           ensure_ascii=False)})
    return respuesta


# ─── Avisos proactivos ─────────────────────────────────────────────────

def aviso_agenda_importada(resultado: dict) -> None:
    """Después de importar la agenda de Fonoar."""
    if resultado.get("simulacion") or not resultado.get("turnos_nuevos"):
        return
    try:
        fecha = datetime.fromisoformat(resultado["fecha"]).strftime("%d/%m")
    except Exception:
        fecha = resultado.get("fecha", "")
    lineas = [f"Llegó la agenda de Fonoar del {fecha}: {len(resultado.get('detalle') or [])} turnos."]
    for d in resultado.get("detalle") or []:
        extra = " · NUEVO" if d.get("accion_paciente") == "nuevo" else ""
        tipo = TIPO_TURNO.get(d.get("tipo"), d.get("tipo"))
        os_txt = f", {d['obra_social']}" if d.get("obra_social") else ""
        lineas.append(f"• {d['hora']} {d['paciente']} ({tipo}{os_txt}){extra}")
    nuevos = resultado.get("pacientes_nuevos") or 0
    if nuevos:
        lineas.append(f"Cargué {nuevos} paciente{'s' if nuevos > 1 else ''} nuevo{'s' if nuevos > 1 else ''} en la app.")
    lineas.append("A las 7:30 de ese día te mando el repaso de cada paciente.")
    avisar("\n".join(lineas))


def repaso_del_dia(llm=None, fecha: str = "") -> str:
    """Texto del repaso de los pacientes del día ("" si no hay turnos)."""
    dia = fecha or _ahora().date().isoformat()
    agenda = h_agenda(dia, dia)
    if not agenda["turnos"]:
        return ""
    fichas = []
    for t in agenda["turnos"]:
        ficha = h_resumen_paciente(t["paciente_id"]) if t.get("paciente_id") else {}
        fichas.append({"turno": t, "ficha": ficha})
    pedido = (
        "Armá el repaso de la jornada de hoy para Matías, un bloque por paciente en orden de hora: "
        "hora, nombre, centro y tipo de turno; en qué punto del tratamiento está (turnos previos, última "
        "evaluación); evolución de la F0 conversacional si hay datos (en Hz y, si podés, en semitonos); y "
        "qué conviene revisar o completar (ej. falta anamnesis, falta informe ORL, VHI-10 pendiente). "
        "Breve y concreto. Cerrá con una línea de resumen. Datos:\n" + _resultado_texto(fichas)
    )
    try:
        texto = pensar(pedido, llm=llm)
    except Exception:
        texto = ""
    if not texto or texto.startswith("Me trabé"):
        lineas = [f"Repaso de hoy ({len(agenda['turnos'])} turnos):"]
        for t in agenda["turnos"]:
            lineas.append(f"• {t['cuando'][-5:]} {t['paciente']} — {t['tipo']} ({t['centro'] or 'sin centro'})")
        texto = "\n".join(lineas)
    return texto


# ─── Rutas ─────────────────────────────────────────────────────────────

def _url_publica(request: Request) -> str:
    host = request.headers.get("x-forwarded-host") or request.url.hostname
    return f"https://{host}"


@router.get("/api/asistente/estado")
async def estado():
    info = {"bot_configurado": bool(_token_bot()), "vinculado": bool(chat_vinculado()),
            "bot_usuario": config_leer("bot_usuario") or ""}
    if info["bot_configurado"] and not info["bot_usuario"]:
        me = _tg("getMe", {})
        if me.get("ok"):
            info["bot_usuario"] = me["result"].get("username", "")
            config_guardar("bot_usuario", info["bot_usuario"])
    return info


@router.post("/api/asistente/activar")
async def activar(request: Request):
    """Conecta Telegram con este servidor y devuelve el enlace para vincular el chat."""
    if not _token_bot():
        raise HTTPException(status_code=400, detail=(
            "Falta TELEGRAM_BOT_TOKEN en Render. Creá el bot con @BotFather en Telegram (/newbot), "
            "copiá el token y cargalo en Render → Environment."))
    me = _tg("getMe", {})
    if not me.get("ok"):
        raise HTTPException(status_code=400, detail=f"Telegram rechazó el token: {me.get('description')}")
    usuario = me["result"].get("username", "")
    config_guardar("bot_usuario", usuario)
    wh = _tg("setWebhook", {"url": f"{_url_publica(request)}/api/asistente/telegram",
                            "secret_token": secreto_webhook(),
                            "allowed_updates": ["message", "callback_query"],
                            "drop_pending_updates": True})
    if not wh.get("ok"):
        raise HTTPException(status_code=502, detail=f"No se pudo conectar Telegram: {wh.get('description')}")
    codigo = secrets.token_hex(4)
    config_guardar("codigo_vinculacion", {"codigo": codigo, "vence": int(time.time()) + 1800})
    return {"ok": True, "bot_usuario": usuario, "enlace": f"https://t.me/{usuario}?start={codigo}",
            "vinculado": bool(chat_vinculado())}


@router.post("/api/asistente/probar")
async def probar():
    r = enviar(f"Hola Matías, soy tu {NOMBRE}. Ya estoy conectado. Probá preguntarme «¿qué tengo mañana?».")
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("description") or "No se pudo enviar")
    return {"ok": True}


def _procesar_update(update: dict) -> None:
    msg = update.get("message") or {}
    chat_id = str((msg.get("chat") or {}).get("id") or "")
    texto = (msg.get("text") or "").strip()
    if not chat_id or not texto:
        return
    # Vinculación: /start <código> desde el enlace de la app.
    m = re.match(r"^/start\s+([0-9a-f]{8})$", texto)
    if m:
        pend = config_leer("codigo_vinculacion") or {}
        _CACHE_CONFIG.pop("codigo_vinculacion", None)
        if pend.get("codigo") == m.group(1) and int(pend.get("vence", 0)) > time.time():
            config_guardar("chat_id", chat_id)
            config_guardar("codigo_vinculacion", {})
            enviar(f"¡Listo! Quedé vinculado a este chat. Soy tu {NOMBRE}: te aviso cuando llegue la "
                   "agenda de Fonoar, te mando el repaso del día a las 7:30 y podés preguntarme lo que "
                   "necesites de la agenda y de tus pacientes.", chat_id)
        else:
            enviar("Ese enlace de vinculación venció. Generá uno nuevo desde la app (Inicio → Asistente).", chat_id)
        return
    if chat_id != chat_vinculado():
        return  # Solo atiende al chat del profesional.
    _tg("sendChatAction", {"chat_id": chat_id, "action": "typing"})
    enviar(conversar(chat_id, texto), chat_id)


@router.post("/api/asistente/telegram")
async def webhook(request: Request, tareas: BackgroundTasks):
    """Webhook de Telegram. Responde enseguida y procesa en segundo plano
    (si tarda, Telegram reintenta y el mensaje se duplicaría)."""
    if not hmac.compare_digest(request.headers.get("x-telegram-bot-api-secret-token", ""), secreto_webhook()):
        raise HTTPException(status_code=403, detail="Secreto inválido")
    update = await request.json()
    uid = update.get("update_id")
    if uid in _UPDATES_VISTOS:
        return {"ok": True}
    _UPDATES_VISTOS.append(uid)
    tareas.add_task(_procesar_update, update)
    return {"ok": True}


@router.post("/api/asistente/repaso-dia")
async def repaso_dia(tareas: BackgroundTasks):
    """Lo dispara GitHub Actions a las 07:30. Una vez por día; solo de 6 a 12 h."""
    ahora = _ahora()
    hoy = ahora.date().isoformat()
    if not (6 <= ahora.hour < 12):
        return {"ok": False, "motivo": "fuera de horario"}
    if not chat_vinculado():
        return {"ok": False, "motivo": "asistente sin chat vinculado"}
    _CACHE_CONFIG.pop("ultimo_repaso", None)
    if config_leer("ultimo_repaso") == hoy:
        return {"ok": True, "motivo": "ya enviado hoy"}
    config_guardar("ultimo_repaso", hoy)

    def _enviar():
        texto = repaso_del_dia()
        if texto:
            enviar(texto)
    tareas.add_task(_enviar)
    return {"ok": True, "motivo": "enviando"}
