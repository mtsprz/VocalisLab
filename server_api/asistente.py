"""Asistente personal del Consultorio de Voz (Telegram).

Fase 2:
- Chat privado por Telegram: solo responde al chat vinculado del
  profesional. Entiende texto y notas de voz (Whisper de Groq; respaldo
  Gemini) y consulta la app con herramientas de lectura (agenda, pacientes,
  ficha resumida, práctica en casa, autoevaluaciones, pendientes).
- Acciones con confirmación: agendar, reprogramar, cancelar o marcar
  turnos, anotar en un turno, generar el enlace de autoevaluación y abrir
  una sala virtual. El modelo solo PROPONE; la acción se ejecuta cuando
  Matías toca «Confirmar» (o responde «sí»).
- Comandos rápidos sin modelo: /hoy, /manana, /semana, /pendientes,
  /repaso, /ayuda.
- Avisos proactivos: agenda de Fonoar importada y repaso del día de
  atención (07:30, lo dispara GitHub Actions).

Activación (desde la app, sin tocar variables salvo TELEGRAM_BOT_TOKEN):
POST /api/asistente/activar conecta el webhook de Telegram con este
servidor y devuelve un enlace t.me/<bot>?start=<código>; al tocarlo, el
chat queda vinculado (tabla asistente_config).

Privacidad: a Telegram y al modelo de lenguaje no se envían DNI, teléfono
ni email (los enlaces de WhatsApp van sin número). El audio de las notas de
voz se transcribe y no se guarda. Los mensajes automáticos usan el nombre del paciente y datos
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
MAX_PASOS = 6
MAX_AUDIO_BYTES = 20 * 1024 * 1024  # límite de descarga de la Bot API
_PENDIENTES: dict = {}         # chat_id → acción propuesta esperando confirmación
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
    base = "id, fecha_hora, duracion_min, tipo, estado, modalidad, motivo, notas, paciente_id, "
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
        turnos.append({"turno_id": t.get("id"), "cuando": cuando, "paciente": p.get("nombre_completo"),
                       "paciente_id": t.get("paciente_id"),
                       "centro": NOMBRE_CENTRO.get(p.get("centro") or "", p.get("centro") or ""),
                       "obra_social": p.get("obra_social") or "",
                       "tipo": TIPO_TURNO.get(t.get("tipo"), t.get("tipo")), "estado": t.get("estado"),
                       "motivo": t.get("motivo"), "modalidad": t.get("modalidad"),
                       "duracion_min": t.get("duracion_min"),
                       "notas": (t.get("notas") or "")[:200]})
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


def _frontend() -> str:
    return os.environ.get("FRONTEND_URL", "https://vocalis-lab.vercel.app").strip().rstrip("/")


def _fecha_txt(valor) -> str:
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).astimezone(ZONA).strftime("%d/%m %H:%M")
    except Exception:
        return str(valor or "")[:16]


def _nombre_paciente(pid: str) -> str:
    try:
        filas = _sb().table("pacientes").select("nombre_completo, nombre").eq("id", pid).execute().data or []
        return (filas[0].get("nombre_completo") or filas[0].get("nombre") or "") if filas else ""
    except Exception:
        return ""


def h_practica_paciente(paciente_id: str) -> dict:
    """Rutina de práctica en casa vigente, enlace y adherencia de 14 días."""
    from practica_guiada import adherencia
    sb = _sb()
    try:
        rutinas = (sb.table("practicas").select("*").eq("paciente_id", paciente_id)
                   .order("creada_at", desc=True).limit(3).execute().data or [])
        sesiones = (sb.table("practica_sesiones").select("id, creada_at, modo, ambiente, comentario")
                    .eq("paciente_id", paciente_id).order("creada_at", desc=True).limit(200).execute().data or [])
    except Exception as e:
        return {"error": f"La práctica guiada no está disponible ({str(e)[:100]})"}
    if not rutinas:
        return {"tiene_rutina": False}
    r = rutinas[0]
    veces = int(r.get("veces_por_dia") or 2)
    ad = adherencia(sesiones, veces, 14)
    ultima = sesiones[0].get("creada_at") if sesiones else None
    return {"tiene_rutina": True, "activa": bool(r.get("activa")), "creada": _fecha_txt(r.get("creada_at")),
            "vence": _fecha_txt(r.get("vence_at")), "veces_por_dia": veces,
            "ejercicios": [e.get("nombre") for e in (r.get("ejercicios") or []) if isinstance(e, dict)],
            "enlace": f"{_frontend()}/?practica={r.get('token', '')}",
            "adherencia_14_dias": {"hoy": ad["hoy"], "dias_cumplidos": ad["dias_cumplidos"],
                                   "dias_con_practica": ad["dias_con_practica"]},
            "ultima_practica": _fecha_txt(ultima) if ultima else None,
            "comentarios_recientes": [s["comentario"][:200] for s in sesiones[:10] if s.get("comentario")][:3]}


def h_autoevaluaciones(paciente_id: str = "") -> dict:
    """Autoevaluaciones (VHI-10, riesgo, autopercepción): pendientes y respondidas."""
    q = _sb().table("autoevaluaciones").select(
        "id, paciente_id, estado, instrumentos, creada_at, vence_at, completada_at, vhi10_score, "
        "riesgo_vocal_score, autopercepcion, comentario, pacientes(nombre_completo)")
    if paciente_id:
        q = q.eq("paciente_id", paciente_id)
    try:
        filas = q.order("creada_at", desc=True).limit(20).execute().data or []
    except Exception as e:
        return {"error": f"Autoevaluaciones no disponibles ({str(e)[:100]})"}
    out = []
    for f in filas:
        out.append({"paciente": (f.get("pacientes") or {}).get("nombre_completo"), "estado": f.get("estado"),
                    "enviada": _fecha_txt(f.get("creada_at")),
                    "respondida": _fecha_txt(f.get("completada_at")) if f.get("completada_at") else None,
                    "vhi10": f.get("vhi10_score"), "riesgo_vocal": f.get("riesgo_vocal_score"),
                    "autopercepcion": f.get("autopercepcion"), "comentario": (f.get("comentario") or "")[:200]})
    return {"cantidad": len(out), "autoevaluaciones": out}


def h_pendientes(dias: int = 7) -> dict:
    """Qué falta completar para los pacientes con turno en los próximos días."""
    hoy = _ahora().date()
    agenda = h_agenda(hoy.isoformat(), (hoy + timedelta(days=max(1, min(int(dias or 7), 21)))).isoformat())
    sb = _sb()
    vistos, faltas = set(), []
    for t in agenda["turnos"]:
        pid = t.get("paciente_id")
        if not pid or pid in vistos:
            continue
        vistos.add(pid)
        falta = []
        if not _uno("anamnesis", pid, "fecha", "id"):
            falta.append("anamnesis")
        if not _uno("evaluaciones_clinicas", pid, "fecha", "id"):
            falta.append("evaluación clínica")
        if not _uno("analisis_acusticos", pid, "fecha", "id"):
            falta.append("análisis acústico")
        try:
            pend = (sb.table("autoevaluaciones").select("id").eq("paciente_id", pid)
                    .eq("estado", "pendiente").limit(1).execute().data or [])
            if pend:
                falta.append("autoevaluación enviada sin responder")
        except Exception:
            pass
        if falta:
            faltas.append({"paciente": t.get("paciente"), "paciente_id": pid, "proximo_turno": t.get("cuando"),
                           "falta": falta})
    return {"dias": dias, "pacientes_con_turno": len(vistos), "con_pendientes": faltas}


HERRAMIENTAS = {
    "agenda": (h_agenda, "Turnos entre fechas (incluye turno_id). args: {desde: 'AAAA-MM-DD', hasta: 'AAAA-MM-DD'}"),
    "buscar_paciente": (h_buscar_paciente, "Busca pacientes por nombre. args: {texto}"),
    "resumen_paciente": (h_resumen_paciente,
                         "Ficha resumida de un paciente (usar el paciente_id de buscar_paciente o agenda). "
                         "args: {paciente_id}"),
    "practica_paciente": (h_practica_paciente,
                          "Rutina de práctica en casa: ejercicios, enlace, adherencia 14 días. args: {paciente_id}"),
    "autoevaluaciones": (h_autoevaluaciones,
                         "Autoevaluaciones enviadas/respondidas (VHI-10, riesgo, autopercepción). "
                         "args: {paciente_id?} (vacío = las últimas de todos)"),
    "pendientes": (h_pendientes, "Qué falta completar (anamnesis, evaluación, acústica, autoevaluación) de los "
                                 "pacientes con turno en los próximos días. args: {dias?: 7}"),
}


# ─── Acciones (cambian datos: siempre con confirmación) ────────────────
#
# Cada acción tiene `preparar(**args) -> {"resumen": str} | {"error": str}`
# (valida sin tocar nada) y `ejecutar(**args) -> {"texto": str, "botones"?}`.

def _llamar(corrutina):
    """Ejecuta una ruta async desde el hilo de BackgroundTasks."""
    import asyncio
    return asyncio.run(corrutina)


class _PedidoFalso:
    def __init__(self, cuerpo: dict, usuario: dict = None):
        self._cuerpo = cuerpo
        self.query_params = {}
        self.headers = {}

        class _Estado:
            pass
        self.state = _Estado()
        self.state.usuario = usuario or {"sub": "asistente-telegram"}

    async def json(self):
        return self._cuerpo


def _turno(turno_id: str) -> dict:
    filas = (_sb().table("turnos").select("id, fecha_hora, duracion_min, tipo, estado, notas, paciente_id, "
                                          "pacientes(nombre_completo)")
             .eq("id", turno_id).execute().data or [])
    return filas[0] if filas else {}


def _fecha_hora(fecha: str, hora: str) -> str:
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(fecha or "")):
        raise ValueError("fecha debe ser AAAA-MM-DD")
    m = re.match(r"^(\d{1,2})[:.h]?(\d{2})?$", str(hora or "").strip())
    if not m or int(m.group(1)) > 23 or int(m.group(2) or 0) > 59:
        raise ValueError("hora debe ser HH:MM")
    return f"{fecha}T{int(m.group(1)):02d}:{int(m.group(2) or 0):02d}:00-03:00"


def _superpuestos(fecha_hora: str, duracion: int, excluir: str = "") -> list:
    inicio = datetime.fromisoformat(fecha_hora)
    fin = inicio + timedelta(minutes=duracion)
    dia = inicio.date().isoformat()
    filas = (_sb().table("turnos").select("id, fecha_hora, duracion_min, estado, pacientes(nombre_completo)")
             .gte("fecha_hora", f"{dia}T00:00:00-03:00").lte("fecha_hora", f"{dia}T23:59:59-03:00")
             .execute().data or [])
    choques = []
    for t in filas:
        if t.get("id") == excluir or t.get("estado") == "cancelado":
            continue
        try:
            ti = datetime.fromisoformat(str(t["fecha_hora"]).replace("Z", "+00:00"))
        except Exception:
            continue
        tf = ti + timedelta(minutes=int(t.get("duracion_min") or 45))
        if ti < fin and inicio < tf:
            choques.append(f"{ti.astimezone(ZONA).strftime('%H:%M')} {(t.get('pacientes') or {}).get('nombre_completo')}")
    return choques


def p_agendar(paciente_id: str, fecha: str, hora: str, duracion_min: int = 45, tipo: str = "control",
              modalidad: str = "PRESENCIAL", motivo: str = "Consulta de Voz") -> dict:
    nombre = _nombre_paciente(paciente_id)
    if not nombre:
        return {"error": "Paciente inexistente: buscalo primero con buscar_paciente."}
    fh = _fecha_hora(fecha, hora)
    if tipo not in TIPO_TURNO:
        return {"error": f"tipo debe ser uno de {list(TIPO_TURNO)}"}
    choques = _superpuestos(fh, int(duracion_min or 45))
    aviso = f"\n⚠️ Se superpone con: {', '.join(choques)}" if choques else ""
    return {"resumen": f"Agendar a {nombre} el {_fecha_txt(fh)} ({int(duracion_min or 45)} min, "
                       f"{TIPO_TURNO[tipo]}, {str(modalidad).lower()}). Motivo: {motivo}.{aviso}"}


def e_agendar(paciente_id: str, fecha: str, hora: str, duracion_min: int = 45, tipo: str = "control",
              modalidad: str = "PRESENCIAL", motivo: str = "Consulta de Voz") -> dict:
    from api_clinica import crear_turno
    _llamar(crear_turno(paciente_id=paciente_id, fecha_hora=_fecha_hora(fecha, hora),
                        duracion_min=int(duracion_min or 45), tipo=tipo, modalidad=modalidad, motivo=motivo,
                        notas="Agendado desde el asistente de Telegram", user_id=_google_id() or None,
                        sincronizar_google=bool(_google_id())))
    extra = ("" if _google_id() else
             " Si lo querés en Google Calendar, sincronizalo desde la agenda de la app.")
    return {"texto": f"✅ Turno agendado: {_nombre_paciente(paciente_id)}, {_fecha_txt(_fecha_hora(fecha, hora))}.{extra}"}


def _google_id() -> str:
    """Cuenta de Google del profesional: si está, los cambios se reflejan en
    Google Calendar como cuando se hacen desde la app."""
    return os.environ.get("PROFESIONAL_GOOGLE_ID", "").strip()


def _actualizar_turno(turno_id: str, **cambios):
    from api_clinica import actualizar_turno
    campos = dict(estado=None, notas=None, modalidad=None, meet_link=None, motivo=None, fecha_hora=None,
                  duracion_min=None, tipo=None, user_id=_google_id() or None,
                  sincronizar_google=bool(_google_id()), zoom_meeting_id=None,
                  zoom_password=None, zoom_join_url=None)
    campos.update(cambios)
    return _llamar(actualizar_turno(turno_id, **campos))


def p_reprogramar(turno_id: str, fecha: str, hora: str) -> dict:
    t = _turno(turno_id)
    if not t:
        return {"error": "Turno inexistente: consultá la agenda para obtener el turno_id."}
    fh = _fecha_hora(fecha, hora)
    choques = _superpuestos(fh, int(t.get("duracion_min") or 45), excluir=turno_id)
    aviso = f"\n⚠️ Se superpone con: {', '.join(choques)}" if choques else ""
    return {"resumen": f"Pasar el turno de {(t.get('pacientes') or {}).get('nombre_completo')} del "
                       f"{_fecha_txt(t['fecha_hora'])} al {_fecha_txt(fh)}.{aviso}"}


def e_reprogramar(turno_id: str, fecha: str, hora: str) -> dict:
    _actualizar_turno(turno_id, fecha_hora=_fecha_hora(fecha, hora))
    return {"texto": f"✅ Turno reprogramado al {_fecha_txt(_fecha_hora(fecha, hora))}."}


ESTADOS = {"cancelado": "cancelar", "confirmado": "marcar como confirmado", "completado": "marcar como realizado",
           "programado": "volver a programado"}


def p_estado_turno(turno_id: str, estado: str) -> dict:
    t = _turno(turno_id)
    if not t:
        return {"error": "Turno inexistente: consultá la agenda para obtener el turno_id."}
    if estado not in ESTADOS:
        return {"error": f"estado debe ser uno de {list(ESTADOS)}"}
    return {"resumen": f"{ESTADOS[estado].capitalize()} el turno de "
                       f"{(t.get('pacientes') or {}).get('nombre_completo')} del {_fecha_txt(t['fecha_hora'])}."}


def e_estado_turno(turno_id: str, estado: str) -> dict:
    _actualizar_turno(turno_id, estado=estado)
    return {"texto": f"✅ Listo: turno {estado}."}


def p_anotar(turno_id: str, texto: str) -> dict:
    t = _turno(turno_id)
    if not t:
        return {"error": "Turno inexistente: consultá la agenda para obtener el turno_id."}
    if not str(texto or "").strip():
        return {"error": "Falta el texto de la nota."}
    return {"resumen": f"Anotar en el turno de {(t.get('pacientes') or {}).get('nombre_completo')} del "
                       f"{_fecha_txt(t['fecha_hora'])}:\n«{str(texto).strip()[:600]}»"}


def e_anotar(turno_id: str, texto: str) -> dict:
    t = _turno(turno_id)
    previo = (t.get("notas") or "").strip()
    sello = _ahora().strftime("%d/%m %H:%M")
    nuevas = (previo + "\n" if previo else "") + f"[{sello} · Telegram] {str(texto).strip()[:1500]}"
    _actualizar_turno(turno_id, notas=nuevas)
    return {"texto": "✅ Nota guardada en el turno."}


def p_autoevaluacion(paciente_id: str, instrumentos: list = None) -> dict:
    from autoevaluacion import INSTRUMENTOS
    nombre = _nombre_paciente(paciente_id)
    if not nombre:
        return {"error": "Paciente inexistente: buscalo primero con buscar_paciente."}
    elegidos = [i for i in (instrumentos or INSTRUMENTOS) if i in INSTRUMENTOS]
    if not elegidos:
        return {"error": f"instrumentos válidos: {list(INSTRUMENTOS)}"}
    return {"resumen": f"Generar el enlace de autoevaluación ({', '.join(elegidos)}) para {nombre}."}


def e_autoevaluacion(paciente_id: str, instrumentos: list = None) -> dict:
    from autoevaluacion import INSTRUMENTOS, crear
    from urllib.parse import quote
    elegidos = [i for i in (instrumentos or INSTRUMENTOS) if i in INSTRUMENTOS]
    r = _llamar(crear(_PedidoFalso({"paciente_id": paciente_id, "instrumentos": elegidos})))
    msj = (f"Hola {r.get('nombre') or ''}, te paso el cuestionario de voz para completar antes de la próxima "
           f"sesión (lleva unos minutos): {r['enlace']}")
    return {"texto": f"✅ Enlace de autoevaluación (vence en 14 días):\n{r['enlace']}",
            "botones": [[{"text": "Enviar por WhatsApp", "url": f"https://wa.me/?text={quote(msj)}"}]]}


def p_sala(paciente_id: str, modo: str = "habla") -> dict:
    from sala_virtual import MODOS
    nombre = _nombre_paciente(paciente_id)
    if not nombre:
        return {"error": "Paciente inexistente: buscalo primero con buscar_paciente."}
    if modo not in MODOS:
        return {"error": f"modo debe ser uno de {list(MODOS)}"}
    return {"resumen": f"Abrir una sala virtual en vivo ({MODOS[modo]}) para {nombre}."}


def e_sala(paciente_id: str, modo: str = "habla") -> dict:
    from sala_virtual import crear_sala
    from urllib.parse import quote
    r = _llamar(crear_sala(_PedidoFalso({"paciente_id": paciente_id, "modo": modo})))
    msj = f"Hola {r.get('nombre') or ''}, entrá a la sala de práctica en vivo desde acá: {r['enlace']}"
    return {"texto": f"✅ Sala abierta. Enlace para el paciente:\n{r['enlace']}\n"
                     "Vos la seguís desde la app (Sala virtual).",
            "botones": [[{"text": "Enviar por WhatsApp", "url": f"https://wa.me/?text={quote(msj)}"}],
                        [{"text": "Abrir la app", "url": _frontend()}]]}


ACCIONES = {
    "agendar_turno": (p_agendar, e_agendar,
                      "Agenda un turno. args: {paciente_id, fecha: 'AAAA-MM-DD', hora: 'HH:MM', duracion_min?: 45, "
                      f"tipo?: uno de {list(TIPO_TURNO)}, modalidad?: 'PRESENCIAL'|'VIRTUAL', motivo?}}"),
    "reprogramar_turno": (p_reprogramar, e_reprogramar,
                          "Cambia fecha/hora de un turno. args: {turno_id, fecha: 'AAAA-MM-DD', hora: 'HH:MM'}"),
    "estado_turno": (p_estado_turno, e_estado_turno,
                     f"Cancela o marca un turno. args: {{turno_id, estado: uno de {list(ESTADOS)}}}"),
    "anotar_turno": (p_anotar, e_anotar, "Agrega una nota clínica breve a un turno. args: {turno_id, texto}"),
    "enviar_autoevaluacion": (p_autoevaluacion, e_autoevaluacion,
                              "Genera el enlace de autoevaluación para el paciente. args: {paciente_id, "
                              "instrumentos?: lista de 'autopercepcion','vhi10','riesgo'}"),
    "abrir_sala": (p_sala, e_sala, "Abre una sala virtual en vivo para el paciente. args: {paciente_id, "
                                   "modo?: 'habla'|'nota'|'canto'|'tmf'}"),
}


# ─── Cerebro ───────────────────────────────────────────────────────────

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]


def _sistema() -> str:
    ahora = _ahora()
    lista = "\n".join(f"- {n}: {d}" for n, (_f, d) in HERRAMIENTAS.items())
    acciones = "\n".join(f"- {n}: {d}" for n, (_p, _e, d) in ACCIONES.items())
    calendario = ", ".join(f"{DIAS[(ahora + timedelta(days=i)).weekday()]} {(ahora + timedelta(days=i)).date().isoformat()}"
                           for i in range(0, 15))
    return (
        f"Sos el {NOMBRE}, el asistente personal de Matías Pérez, fonoaudiólogo especializado en voz "
        "(La Plata, Argentina). Trabajás como una secretaria clínica atenta: cercano y profesional, "
        "en español rioplatense, con respuestas claras y breves para leer en el celular (Telegram, "
        "texto plano, sin Markdown ni tablas; podés usar viñetas con «•»).\n"
        f"Ahora es {DIAS[ahora.weekday()]} {ahora.strftime('%d/%m/%Y %H:%M')} (hora de Argentina).\n"
        f"Próximos días: {calendario}.\n"
        "Centros: Fonoar La Plata (entrega su propio cuadernillo), DUE Brandsen y Atención virtual.\n"
        "Los mensajes que empiezan con «(nota de voz)» son transcripciones automáticas: pueden traer "
        "errores en nombres propios; si un nombre no aparece, buscá por partes o preguntá.\n\n"
        "Reglas:\n"
        "- Usá las herramientas para cualquier dato de la app; NUNCA inventes datos clínicos, fechas, "
        "nombres ni ids. Si un dato no está, decilo.\n"
        "- No diagnostiques: describí lo que muestran los datos (ej. «la F0 subió 2 semitonos») y, si "
        "corresponde, sugerí qué revisar.\n"
        "- Para cambiar datos usá una ACCIÓN: queda propuesta y Matías la confirma con un botón. Antes, "
        "conseguí los ids reales (buscar_paciente / agenda). Una acción por mensaje.\n"
        "- Lo que no está en la lista (borrar pacientes, editar fichas, cuadernillos, informes) se hace "
        "desde la app: decilo.\n"
        "- Si hay varios pacientes o turnos posibles, preguntá cuál.\n\n"
        f"Herramientas (lectura):\n{lista}\n\nAcciones (requieren confirmación):\n{acciones}\n\n"
        "Respondé SIEMPRE un único objeto JSON, sin texto fuera de él, con una de estas formas:\n"
        '{"accion": "herramienta", "nombre": "<herramienta o acción>", "args": {...}}\n'
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


def pensar(pregunta: str, historial: list = None, llm=None, propuestas: list = None) -> str:
    """Bucle del asistente: decide herramientas hasta poder responder.
    Las acciones no se ejecutan: se validan y se agregan a `propuestas`."""
    llm = llm or _llm_json
    mensajes = [{"role": "system", "content": _sistema()}]
    mensajes += list(historial or [])
    mensajes.append({"role": "user", "content": pregunta})
    for _ in range(MAX_PASOS):
        decision = llm(mensajes)
        accion = decision.get("accion")
        nombre = decision.get("nombre")
        if accion == "responder":
            return str(decision.get("texto") or "").strip() or "No tengo una respuesta para eso."
        if accion == "herramienta" and (nombre in HERRAMIENTAS or nombre in ACCIONES):
            args = decision.get("args") or {}
            if nombre in ACCIONES:
                if propuestas is None:
                    resultado = {"error": "Las acciones solo se pueden proponer desde el chat."}
                elif propuestas:
                    resultado = {"error": "Ya hay una acción propuesta en este mensaje; respondé."}
                else:
                    try:
                        resultado = ACCIONES[nombre][0](**args)
                    except Exception as e:
                        resultado = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
                    if "resumen" in resultado:
                        propuestas.append({"nombre": nombre, "args": args, "resumen": resultado["resumen"]})
                        resultado = {"propuesta": resultado["resumen"], "estado": (
                            "Preparada; se ejecuta cuando Matías toque Confirmar. Respondé con una frase breve "
                            "(el detalle y los botones se muestran aparte).")}
            else:
                try:
                    resultado = HERRAMIENTAS[nombre][0](**args)
                except Exception as e:
                    resultado = {"error": f"{type(e).__name__}: {str(e)[:200]}"}
            mensajes.append({"role": "assistant", "content": json.dumps(decision, ensure_ascii=False)})
            mensajes.append({"role": "user", "content": f"Resultado de {nombre}: {_resultado_texto(resultado)}"})
            continue
        mensajes.append({"role": "user", "content":
                         "Formato inválido. Respondé solo con el JSON pedido (herramienta o responder)."})
    if propuestas:
        return "Te dejo la acción lista para confirmar."
    return "Me trabé buscando esa información. ¿Me lo preguntás de otra forma?"


def conversar(chat_id: str, texto: str) -> dict:
    """Respuesta para el chat: {"texto", "propuesta"?}."""
    hist = _HISTORIAL.setdefault(chat_id, deque(maxlen=12))
    propuestas: list = []
    try:
        respuesta = pensar(texto, list(hist), propuestas=propuestas)
    except Exception as e:
        traceback.print_exc()
        respuesta = f"Ahora no puedo consultar el modelo ({str(e)[:120]}). Probá en un rato."
    hist.append({"role": "user", "content": texto})
    hist.append({"role": "assistant", "content": json.dumps({"accion": "responder", "texto": respuesta},
                                                           ensure_ascii=False)})
    out = {"texto": respuesta}
    if propuestas:
        out["propuesta"] = propuestas[0]
    return out


def proponer(chat_id: str, propuesta: dict, texto: str = "") -> None:
    """Guarda la acción y muestra el detalle con botones Confirmar/Cancelar."""
    pid = secrets.token_hex(3)
    _PENDIENTES[chat_id] = dict(propuesta, id=pid, vence=time.time() + 900)
    cuerpo = (texto.strip() + "\n\n" if texto.strip() else "") + f"📝 {propuesta['resumen']}"
    _tg("sendMessage", {"chat_id": chat_id, "text": cuerpo[:3900], "disable_web_page_preview": True,
                        "reply_markup": {"inline_keyboard": [[
                            {"text": "✅ Confirmar", "callback_data": f"ok:{pid}"},
                            {"text": "✖️ Cancelar", "callback_data": f"no:{pid}"}]]}})


def resolver_pendiente(chat_id: str, confirmar: bool, pid: str = "") -> dict:
    """Ejecuta o descarta la acción pendiente. Devuelve {"texto", "botones"?}."""
    pend = _PENDIENTES.get(chat_id)
    if not pend or (pid and pend["id"] != pid):
        return {"texto": "Esa acción ya no está pendiente."}
    _PENDIENTES.pop(chat_id, None)
    if pend["vence"] < time.time():
        return {"texto": "La propuesta venció (15 min). Pedímela de nuevo."}
    if not confirmar:
        return {"texto": "Cancelado, no cambié nada."}
    try:
        res = ACCIONES[pend["nombre"]][1](**pend["args"])
    except Exception as e:
        traceback.print_exc()
        detalle = getattr(e, "detail", None) or str(e)
        return {"texto": f"No se pudo: {str(detalle)[:300]}"}
    hist = _HISTORIAL.setdefault(chat_id, deque(maxlen=12))
    hist.append({"role": "user", "content": f"(confirmó: {pend['resumen'][:300]})"})
    hist.append({"role": "assistant", "content": json.dumps({"accion": "responder", "texto": res.get("texto", "")},
                                                           ensure_ascii=False)})
    return res


# ─── Notas de voz ──────────────────────────────────────────────────────

VOCABULARIO = ("Fonoaudiología, voz, turno, paciente, F0, VHI-10, GRBAS, RASATI, AVQI, CPPS, jitter, shimmer, "
               "TMF, índice s/z, Fonoar, DUE Brandsen, IOMA, cuadernillo, autoevaluación, anamnesis.")


def _descargar_archivo(file_id: str) -> tuple:
    info = _tg("getFile", {"file_id": file_id})
    if not info.get("ok"):
        raise RuntimeError(f"Telegram no entregó el audio: {info.get('description')}")
    ruta = info["result"]["file_path"]
    if int(info["result"].get("file_size") or 0) > MAX_AUDIO_BYTES:
        raise RuntimeError("el audio supera 20 MB")
    r = httpx.get(f"https://api.telegram.org/file/bot{_token_bot()}/{ruta}", timeout=60)
    r.raise_for_status()
    return r.content, ruta.rsplit("/", 1)[-1] or "nota.oga"


def _whisper_groq(audio: bytes, nombre: str) -> str:
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GROQ_API_KEY no configurada")
    if nombre.endswith(".oga"):
        nombre = nombre[:-4] + ".ogg"  # Groq no reconoce la extensión .oga de Telegram
    errores = []
    for modelo in ("whisper-large-v3-turbo", "whisper-large-v3"):
        try:
            r = httpx.post("https://api.groq.com/openai/v1/audio/transcriptions",
                           headers={"Authorization": f"Bearer {key}"},
                           data={"model": modelo, "language": "es", "temperature": "0",
                                 "prompt": VOCABULARIO, "response_format": "json"},
                           files={"file": (nombre, audio, "audio/ogg")}, timeout=90)
            r.raise_for_status()
            return (r.json().get("text") or "").strip()
        except Exception as e:
            errores.append(f"{modelo}: {str(e)[:100]}")
    raise RuntimeError(" | ".join(errores))


def _transcribir_gemini(audio: bytes, mime: str) -> str:
    import base64
    from llm_client import gemini_generate, gemini_texto
    data, _m = gemini_generate([
        {"text": "Transcribí literalmente esta nota de voz en español rioplatense. Devolvé solo el texto, "
                 f"sin comentarios. Vocabulario posible: {VOCABULARIO}"},
        {"inline_data": {"mime_type": mime or "audio/ogg", "data": base64.b64encode(audio).decode()}},
    ], {"temperature": 0}, timeout=90)
    return gemini_texto(data).strip()


def transcribir(file_id: str, mime: str = "audio/ogg") -> str:
    audio, nombre = _descargar_archivo(file_id)
    errores = []
    for fn in (lambda: _whisper_groq(audio, nombre), lambda: _transcribir_gemini(audio, mime)):
        try:
            texto = fn()
            if texto:
                return texto
        except Exception as e:
            errores.append(str(e)[:150])
    raise RuntimeError("; ".join(errores) or "transcripción vacía")


# ─── Comandos rápidos (sin modelo) ─────────────────────────────────────

AYUDA = (
    "Esto puedo hacer (escribime o mandame un audio):\n"
    "• Agenda: «¿qué tengo el jueves?», «¿cuándo viene Yesica?»\n"
    "• Pacientes: «¿cómo viene la F0 de Javier?», «¿practica en casa Laura?»\n"
    "• Autoevaluaciones: «¿quién respondió el VHI-10?»\n"
    "• Pendientes: «¿qué me falta completar esta semana?»\n"
    "• Acciones (con confirmación): agendar, reprogramar, cancelar o marcar turnos realizados, "
    "anotar en un turno, mandar la autoevaluación, abrir una sala virtual.\n\n"
    "Comandos: /hoy /manana /semana /pendientes /repaso /ayuda"
)

COMANDOS = [
    {"command": "hoy", "description": "Turnos de hoy"},
    {"command": "manana", "description": "Turnos de mañana"},
    {"command": "semana", "description": "Turnos de los próximos 7 días"},
    {"command": "pendientes", "description": "Qué falta completar de los próximos pacientes"},
    {"command": "repaso", "description": "Repaso clínico de los pacientes de hoy"},
    {"command": "ayuda", "description": "Qué puede hacer el asistente"},
]


def _texto_agenda(desde, hasta, titulo: str) -> str:
    ag = h_agenda(desde.isoformat(), hasta.isoformat())
    activos = [t for t in ag["turnos"] if t.get("estado") != "cancelado"]
    if not activos:
        return f"{titulo}: sin turnos."
    lineas = [f"{titulo} ({len(activos)} turno{'s' if len(activos) != 1 else ''}):"]
    dia_previo = ""
    for t in activos:
        dia, hora = t["cuando"][:-6], t["cuando"][-5:]
        if desde != hasta and dia != dia_previo:
            lineas.append(f"\n{dia}")
            dia_previo = dia
        extra = f" · {t['estado']}" if t.get("estado") not in (None, "programado") else ""
        lineas.append(f"• {hora} {t['paciente']} — {t['tipo']} ({t['centro'] or 'sin centro'}){extra}")
    return "\n".join(lineas)


def _texto_pendientes() -> str:
    p = h_pendientes(7)
    if not p["con_pendientes"]:
        return f"Próximos 7 días: {p['pacientes_con_turno']} pacientes con turno y nada pendiente. 👌"
    lineas = [f"Pendientes de los próximos 7 días ({len(p['con_pendientes'])} de {p['pacientes_con_turno']} pacientes):"]
    for x in p["con_pendientes"]:
        lineas.append(f"• {x['paciente']} ({x['proximo_turno']}): falta {', '.join(x['falta'])}")
    return "\n".join(lineas)


def comando(texto: str):
    """Respuesta de un comando rápido, o None si no es un comando conocido."""
    cmd = _norm(texto.split()[0].split("@")[0]) if texto.startswith("/") else ""
    hoy = _ahora().date()
    if cmd in ("/start", "/ayuda", "/help"):
        return AYUDA
    if cmd == "/hoy":
        return _texto_agenda(hoy, hoy, "Hoy")
    if cmd in ("/manana",):
        m = hoy + timedelta(days=1)
        return _texto_agenda(m, m, "Mañana")
    if cmd == "/semana":
        return _texto_agenda(hoy, hoy + timedelta(days=6), "Próximos 7 días")
    if cmd == "/pendientes":
        return _texto_pendientes()
    if cmd == "/repaso":
        return repaso_del_dia() or "Hoy no hay turnos para repasar."
    return None


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
    # Bots activados antes de la fase 2: publica el menú de comandos una vez.
    if info["bot_configurado"] and info["vinculado"] and config_leer("comandos_version") != 2:
        if _tg("setMyCommands", {"commands": COMANDOS}).get("ok"):
            config_guardar("comandos_version", 2)
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
    _tg("setMyCommands", {"commands": COMANDOS})
    config_guardar("comandos_version", 2)
    codigo = secrets.token_hex(4)
    config_guardar("codigo_vinculacion", {"codigo": codigo, "vence": int(time.time()) + 1800})
    return {"ok": True, "bot_usuario": usuario, "enlace": f"https://t.me/{usuario}?start={codigo}",
            "vinculado": bool(chat_vinculado())}


@router.post("/api/asistente/probar")
async def probar():
    r = enviar(f"Hola Matías, soy tu {NOMBRE}. Ya estoy conectado. Probá preguntarme «¿qué tengo mañana?», mandame un audio o usá /ayuda.")
    if not r.get("ok"):
        raise HTTPException(status_code=400, detail=r.get("description") or "No se pudo enviar")
    return {"ok": True}


SI = {"si", "sí", "dale", "confirmo", "confirmar", "ok", "okay", "listo", "hacelo", "de una", "perfecto"}
NO = {"no", "cancelar", "cancela", "cancelá", "dejalo", "mejor no", "nada"}


def _responder(chat_id: str, res: dict) -> None:
    """Manda {"texto", "botones"?, "propuesta"?} al chat."""
    if res.get("propuesta"):
        proponer(chat_id, res["propuesta"], res.get("texto", ""))
        return
    if res.get("botones"):
        _tg("sendMessage", {"chat_id": chat_id, "text": res["texto"][:3900], "disable_web_page_preview": True,
                            "reply_markup": {"inline_keyboard": res["botones"]}})
        return
    enviar(res.get("texto") or "…", chat_id)


def _procesar_callback(cb: dict) -> None:
    chat_id = str(((cb.get("message") or {}).get("chat") or {}).get("id") or "")
    datos = str(cb.get("data") or "")
    _tg("answerCallbackQuery", {"callback_query_id": cb.get("id")})
    if not chat_id or chat_id != chat_vinculado() or ":" not in datos:
        return
    tipo, pid = datos.split(":", 1)
    msg_id = (cb.get("message") or {}).get("message_id")
    if msg_id:  # saca los botones para que no se toque dos veces
        _tg("editMessageReplyMarkup", {"chat_id": chat_id, "message_id": msg_id,
                                       "reply_markup": {"inline_keyboard": []}})
    _responder(chat_id, resolver_pendiente(chat_id, tipo == "ok", pid))


def _procesar_update(update: dict) -> None:
    if update.get("callback_query"):
        _procesar_callback(update["callback_query"])
        return
    msg = update.get("message") or {}
    chat_id = str((msg.get("chat") or {}).get("id") or "")
    texto = (msg.get("text") or "").strip()
    if not chat_id:
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
                   "agenda de Fonoar, te mando el repaso del día a las 7:30 y podés preguntarme o pedirme "
                   "cosas por escrito o con un audio.\n\n" + AYUDA, chat_id)
        else:
            enviar("Ese enlace de vinculación venció. Generá uno nuevo desde la app (Inicio → Asistente).", chat_id)
        return
    if chat_id != chat_vinculado():
        return  # Solo atiende al chat del profesional.

    # Notas de voz, audios y videomensajes: se transcriben y siguen como texto.
    audio = msg.get("voice") or msg.get("audio") or msg.get("video_note")
    de_voz = False
    if audio and not texto:
        _tg("sendChatAction", {"chat_id": chat_id, "action": "typing"})
        try:
            texto = transcribir(audio["file_id"], audio.get("mime_type") or "audio/ogg")
        except Exception as e:
            traceback.print_exc()
            enviar(f"No pude entender el audio ({str(e)[:150]}). ¿Me lo escribís?", chat_id)
            return
        if not texto:
            enviar("El audio llegó vacío o no se entiende. ¿Lo repetís?", chat_id)
            return
        enviar(f"🎙️ «{texto[:900]}»", chat_id)
        de_voz = True
    if not texto:
        if msg.get("photo") or msg.get("document"):
            enviar("Por ahora no proceso fotos ni archivos: subilos desde la app (ficha del paciente → "
                   "Archivos). Texto y audios sí.", chat_id)
        return

    # Confirmación escrita o hablada de una acción pendiente.
    corto = _norm(texto).strip(" .!¡¿?")
    if chat_id in _PENDIENTES and (corto in {_norm(x) for x in SI} or corto in {_norm(x) for x in NO}):
        _responder(chat_id, resolver_pendiente(chat_id, corto in {_norm(x) for x in SI}))
        return

    rapido = comando(texto)
    if rapido is not None:
        enviar(rapido, chat_id)
        return
    _tg("sendChatAction", {"chat_id": chat_id, "action": "typing"})
    _responder(chat_id, conversar(chat_id, ("(nota de voz) " if de_voz else "") + texto))


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
