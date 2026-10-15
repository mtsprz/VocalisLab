"""Vocalis Companion — atribución de hablantes con IA (por contenido).

El teléfono separa paciente / fonoaudiólogo por altura tonal (perfil "Mi
voz") y manda esos tramos como `segments`. Al procesar, la transcripción se
alinea con esos tramos (`companion._diarizar`). Este módulo agrega un segundo
paso: un LLM (el mismo proveedor que el borrador de anamnesis) revisa cada
frase con su etiqueta tentativa y la corrige si el contenido lo indica
(consignas/preguntas → fonoaudiólogo; respuestas/síntomas → paciente).

Se engancha envolviendo `companion._diarizar` al importarse (index.py), sin
modificar companion.py. Apagable con COMPANION_DIARIZACION_IA=false. Ante
cualquier falla del LLM se conserva la atribución del teléfono.
"""
import json
import re
import traceback

import companion as comp

_MAX_LINEAS = 400
_original = comp._diarizar


def _llm(prompt: str) -> str:
    if comp._ai_provider() == "groq":
        from llm_client import groq_chat
        txt = groq_chat([{"role": "user", "content": prompt}],
                        temperature=0.0, max_tokens=4000, model=comp._ai_model()) or ""
        return txt if isinstance(txt, str) else json.dumps(txt, ensure_ascii=False)
    import httpx
    key = comp._env("GEMINI_API_KEY", "")
    if not key:
        raise RuntimeError("GEMINI_API_KEY ausente")
    r = httpx.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{comp._ai_model()}:generateContent?key={key}",
        json={"contents": [{"parts": [{"text": prompt}]}],
              "generationConfig": {"temperature": 0, "responseMimeType": "application/json"}},
        timeout=120)
    cands = r.json().get("candidates") or []
    parts = ((cands[0].get("content") or {}).get("parts") or []) if cands else []
    return "".join(p.get("text", "") for p in parts)


def corregir_hablantes(base: list) -> list:
    """Devuelve `base` con `speaker` corregido por contenido (in place)."""
    lineas = base[:_MAX_LINEAS]
    texto = "\n".join(
        f"{i}|{s.get('speaker', 'paciente')}|{(s.get('text') or '').replace(chr(10), ' ')[:300]}"
        for i, s in enumerate(lineas))
    prompt = (
        "Transcripción de una sesión de fonoaudiología (terapia de voz) entre un "
        "FONOAUDIOLOGO y un PACIENTE. Cada línea es: índice|hablante tentativo|texto. "
        "El hablante tentativo viene de un análisis acústico y suele acertar; "
        "corregilo SOLO cuando el contenido lo deja claro: el fonoaudiólogo da "
        "consignas, explica ejercicios, pregunta y evalúa; el paciente responde, "
        "cuenta síntomas, hábitos y su historia, y realiza los ejercicios.\n"
        "Respondé SOLO JSON: {\"hablantes\": [\"paciente\"|\"fonoaudiologo\", ...]} "
        f"con exactamente {len(lineas)} elementos, en el mismo orden.\n\n" + texto)
    txt = _llm(prompt)
    m = re.search(r"\{.*\}", txt or "", re.DOTALL)
    data = json.loads(m.group(0)) if m else {}
    hablantes = data.get("hablantes") or []
    if len(hablantes) != len(lineas):
        raise ValueError(f"IA devolvió {len(hablantes)} etiquetas para {len(lineas)} líneas")
    for s, h in zip(lineas, hablantes):
        h = str(h).strip().lower()
        if h in ("paciente", "fonoaudiologo") and h != s.get("speaker"):
            s["speaker"] = h   # source sigue "ai": la tabla solo admite ai/manual
    return base


def diarizar_ia(trans_segs: list, task_segs: list) -> list:
    base = _original(trans_segs, task_segs)
    if comp._env("COMPANION_DIARIZACION_IA", "true").strip().lower() == "false" or len(base) < 2:
        return base
    try:
        return corregir_hablantes(base)
    except Exception:
        traceback.print_exc()
        return base   # se conserva la atribución del teléfono


comp._diarizar = diarizar_ia
