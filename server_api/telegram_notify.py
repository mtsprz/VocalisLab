"""VocalisLab — Notificaciones salientes por Telegram (bot).

Solo saliente por defecto. El inbound vive en companion.py detrás de
TELEGRAM_INBOUND_ENABLED=false. Nunca se envían nombre completo ni datos clínicos:
solo iniciales + fecha + enlace a la ficha.
"""
import os
import traceback


def _cfg():
    return {
        "token": os.environ.get("TELEGRAM_BOT_TOKEN", "").strip(),
        "chat_id": os.environ.get("TELEGRAM_NOTIFY_CHAT_ID", "").strip(),
        "frontend": os.environ.get("FRONTEND_URL", "https://vocalis-lab.vercel.app").strip().rstrip("/"),
    }


def telegram_enabled() -> bool:
    c = _cfg()
    return bool(c["token"] and c["chat_id"])


def iniciales_paciente(nombre_completo: str, sexo_ref: str = "") -> str:
    """'María Teresa Gonzalez' -> 'MG (f)'. Partículas ignoradas."""
    parts = [p for p in (nombre_completo or "").split()
             if p.lower() not in ("de", "del", "la", "las", "el", "los", "y", "e")]
    if not parts:
        return "??"
    ini = (parts[0][0] + (parts[-1][0] if len(parts) > 1 else "")).upper()
    s = (sexo_ref or "").strip().lower()
    marca = " (m)" if s.startswith("masc") else (" (f)" if s.startswith("fem") else "")
    return f"{ini}{marca}"


def ficha_url(patient_id: str) -> str:
    return f"{_cfg()['frontend']}/?paciente={patient_id}"


def enviar_mensaje(texto: str) -> dict:
    c = _cfg()
    if not telegram_enabled():
        return {"ok": False, "error": "Telegram no configurado (TELEGRAM_BOT_TOKEN/TELEGRAM_NOTIFY_CHAT_ID)"}
    try:
        import httpx
        r = httpx.post(
            f"https://api.telegram.org/bot{c['token']}/sendMessage",
            json={"chat_id": c["chat_id"], "text": texto,
                  "disable_web_page_preview": True},
            timeout=20,
        )
        if r.status_code != 200:
            return {"ok": False, "error": f"Telegram API {r.status_code}: {r.text[:200]}"}
        return {"ok": True}
    except Exception as e:
        traceback.print_exc()
        return {"ok": False, "error": str(e)[:200]}


def notificar_sesion_procesada(nombre_completo: str, sexo_ref: str,
                               fecha_txt: str, patient_id: str) -> dict:
    ini = iniciales_paciente(nombre_completo, sexo_ref)
    return enviar_mensaje(
        f"Sesión procesada — {ini} · {fecha_txt}\nVer ficha: {ficha_url(patient_id)}")
