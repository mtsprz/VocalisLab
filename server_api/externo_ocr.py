"""VocalisLab Pro — OCR de análisis acústicos externos.

Permite subir el informe acústico realizado por otro profesional (foto/captura
o PDF con texto) y la IA extrae los valores para volcarlos a la historia
clínica del paciente sin necesidad de repetir el análisis con Praat.
"""
import os
import re
import json
import base64
import traceback
from fastapi import APIRouter, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse

router = APIRouter()

# Modelos con visión vigentes en Groq (Llama 4 dados de baja en 2026).
# Se puede sobrescribir con GROQ_VISION_MODEL="m1,m2".
VISION_MODELS = [
    "qwen/qwen3.6-27b",
    "qwen/qwen3.8-27b",
]

# Claves acústicas que la IA debe extraer (todas opcionales, null si ausente).
# Antes el PDF iba como texto a Groq sin pedir JSON y con 1500 tokens: los
# modelos que razonan antes de responder se quedaban sin espacio y la
# respuesta llegaba vacía ("La IA no devolvió un JSON válido"). Ahora Gemini
# lee el archivo completo y Groq queda de respaldo con JSON estricto.
METRIC_KEYS = [
    "f0_mean", "f0_min", "f0_max", "f0_sd",
    "jitter_local_pct", "jitter_rap_pct", "jitter_ppq5_pct",
    "shimmer_local_pct", "shimmer_apq3_pct", "shimmer_apq5_pct",
    "hnr_db", "nhr", "cpps_db", "avqi",
    "mpt_s", "tmf_s", "dsi",
    "f1_hz", "f2_hz", "f3_hz", "f4_hz",
]

EXTRACTION_PROMPT = """Sos un extractor de datos bioacústicos vocales. Analizá este informe de análisis
acústico de la voz (puede ser Praat, VOXplot, MDVP, LingWAVES u otro software) y
devolvé EXCLUSIVAMENTE un JSON válido con esta estructura (sin texto extra):

{
  "valores": {
    "f0_mean": número en Hz o null,
    "f0_min": número en Hz o null,
    "f0_max": número en Hz o null,
    "f0_sd": número en Hz o null,
    "jitter_local_pct": jitter local en % o null,
    "jitter_rap_pct": jitter RAP en % o null,
    "jitter_ppq5_pct": jitter PPQ5 en % o null,
    "shimmer_local_pct": shimmer local en % o null,
    "shimmer_apq3_pct": shimmer APQ3 en % o null,
    "shimmer_apq5_pct": shimmer APQ5 en % o null,
    "hnr_db": HNR en dB o null,
    "nhr": NHR (adimensional) o null,
    "cpps_db": CPPS en dB o null,
    "avqi": AVQI o null,
    "mpt_s": tiempo máximo de fonación en segundos o null,
    "tmf_s": TMF en segundos o null,
    "dsi": DSI o null,
    "f1_hz": F1 en Hz o null,
    "f2_hz": F2 en Hz o null,
    "f3_hz": F3 en Hz o null,
    "f4_hz": F4 en Hz o null
  },
  "origen_detectado": "Praat / VOXplot / MDVP / LingWAVES / manuscrito / desconocido",
  "confianza": "alta / media / baja",
  "observaciones": "aclaraciones breves (unidades ambiguas, valores dudosos, etc.)"
}

Reglas: convertí comas decimales a punto (4,85 % → 4.85). Si un valor no aparece,
usá null. No inventes valores."""


def _vision_models():
    env = os.environ.get("GROQ_VISION_MODEL", "").strip()
    if env:
        return [m.strip() for m in env.split(",") if m.strip()]
    return list(VISION_MODELS)


def _extract_json(text: str) -> dict:
    """JSON de la respuesta del modelo, tolerante a lo que suelen agregar:
    bloques ```json, texto antes/después, comas sobrantes, None/NaN."""
    t = (text or "").strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t, flags=re.IGNORECASE | re.MULTILINE)
    start = t.find("{")
    if start < 0:
        raise ValueError("La IA no devolvió un JSON válido")
    # Primer objeto con llaves balanceadas (ignora texto posterior).
    nivel, fin, en_texto, escape = 0, -1, False, False
    for i, ch in enumerate(t[start:], start):
        if en_texto:
            escape = (ch == "\\") and not escape
            if ch == '"' and not escape:
                en_texto = False
            continue
        if ch == '"':
            en_texto = True
        elif ch == "{":
            nivel += 1
        elif ch == "}":
            nivel -= 1
            if nivel == 0:
                fin = i + 1
                break
    bloque = t[start:fin] if fin > 0 else t[start:]
    intentos = [bloque,
                re.sub(r",\s*([}\]])", r"\1", bloque),
                re.sub(r"\b(None|NaN|nan|undefined)\b", "null",
                       re.sub(r",\s*([}\]])", r"\1", bloque)).replace("True", "true").replace("False", "false")]
    for candidato in intentos:
        try:
            return json.loads(candidato)
        except Exception:
            continue
    raise ValueError("La IA no devolvió un JSON válido")


def _to_number(v):
    """Normaliza '215,4 Hz' / '1,42%' / '15.8 dB' → float. None si no parseable."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().lower()
    if not s or s in ("null", "none", "n/d", "nd", "-", "--"):
        return None
    s = re.sub(r"[^0-9,.\-+e]", "", s)
    if not s:
        return None
    # coma decimal española: "4,85" → "4.85" (si no hay punto ya)
    if "," in s and "." not in s:
        s = s.replace(",", ".")
    elif "," in s and "." in s:
        s = s.replace(",", "")  # separador de miles
    try:
        return float(s)
    except Exception:
        return None


def _normalize_valores(raw: dict) -> dict:
    out = {}
    raw = raw or {}
    for k in METRIC_KEYS:
        out[k] = _to_number(raw.get(k))
    return out


def _vision_extract(image_b64: str, mime: str) -> dict:
    from groq import Groq
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("GROQ_API_KEY no configurada")
    client = Groq(api_key=key, timeout=60.0)
    last_err: Exception = RuntimeError("Sin modelos de visión configurados")
    for model in _vision_models():
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": EXTRACTION_PROMPT},
                        {"type": "image_url",
                         "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                    ],
                }],
                temperature=0.1,
                max_tokens=1500,
            )
            return _extract_json(resp.choices[0].message.content or "")
        except Exception as e:
            last_err = e
            print(f"[externo_ocr] Modelo visión {model} falló: {str(e)[:150]}")
            continue
    raise last_err


def _gemini_extract(data: bytes, mime: str) -> tuple:
    """Gemini lee el archivo completo (PDF con tablas o gráficos, PDF
    escaneado o imagen) y devuelve JSON estricto. Devuelve (datos, modelo)."""
    from llm_client import gemini_generate, gemini_texto
    parts = [{"text": EXTRACTION_PROMPT},
             {"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}}]
    resp, modelo = gemini_generate(parts, {"temperature": 0.1, "maxOutputTokens": 4096,
                                           "responseMimeType": "application/json"}, timeout=120)
    return _extract_json(gemini_texto(resp)), modelo


def _pdf_to_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        raise RuntimeError("Soporte PDF no instalado en el servidor")
    import io
    reader = PdfReader(io.BytesIO(data))
    parts = []
    for page in reader.pages[:8]:
        try:
            parts.append(page.extract_text() or "")
        except Exception:
            pass
    return "\n".join(parts)


@router.post("/api/analisis-externo/ocr")
async def ocr_analisis_externo(archivo: UploadFile = File(...)):
    """Recibe imagen (foto/captura) o PDF con texto de un análisis externo y
    devuelve los valores acústicos extraídos por IA listos para volcar."""
    try:
        data = await archivo.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {e}")
    if not data or len(data) < 100:
        raise HTTPException(status_code=400, detail="Archivo vacío o demasiado pequeño")
    if len(data) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo mayor a 12 MB")

    fname = (archivo.filename or "").lower()
    ctype = (archivo.content_type or "").lower()
    es_pdf = fname.endswith(".pdf") or "pdf" in ctype

    try:
        mime = "application/pdf" if es_pdf else "image/jpeg"
        if fname.endswith(".png") or "png" in ctype:
            mime = "image/png"
        elif fname.endswith(".webp") or "webp" in ctype:
            mime = "image/webp"
        errores = []
        parsed, model, formato = None, "", ""
        # 1) Gemini: lee el archivo tal cual (tablas, gráficos, escaneados).
        if os.environ.get("GEMINI_API_KEY", "").strip():
            try:
                parsed, model = _gemini_extract(data, mime)
                formato = "pdf" if es_pdf else "imagen"
            except Exception as e:
                errores.append(f"Gemini: {str(e)[:150]}")
                print(f"[externo_ocr] Gemini falló: {str(e)[:200]}")
        # 2) Respaldo Groq: texto del PDF (JSON estricto) o visión para imágenes.
        if parsed is None and es_pdf:
            texto = _pdf_to_text(data)
            if len(texto.strip()) >= 100:
                try:
                    from llm_client import groq_chat
                    raw, model = groq_chat(
                        messages=[{"role": "user", "content": EXTRACTION_PROMPT
                                   + "\n\nTEXTO DEL INFORME:\n" + texto[:12000]}],
                        temperature=0.1, max_tokens=4000,
                        response_format={"type": "json_object"}, timeout=90)
                    parsed = _extract_json(raw)
                    formato = "pdf-texto"
                except Exception as e:
                    errores.append(f"Groq: {str(e)[:150]}")
            else:
                errores.append("el PDF no tiene texto (escaneado) y solo Gemini puede leerlo")
        elif parsed is None:
            try:
                parsed = _vision_extract(base64.b64encode(data).decode(), mime)
                model, formato = "groq-vision", "imagen"
            except Exception as e:
                errores.append(f"Groq visión: {str(e)[:150]}")
        if parsed is None:
            return JSONResponse(content={
                "ok": False,
                "error": "No se pudo leer el informe con ningún modelo: " + " | ".join(errores),
            })

        valores = _normalize_valores(parsed.get("valores", {}))
        if not any(v is not None for v in valores.values()):
            return JSONResponse(content={
                "ok": False,
                "error": "No se reconocieron valores acústicos en el archivo. Probá con una imagen más nítida o completa.",
                "origen_detectado": parsed.get("origen_detectado", "desconocido"),
            })

        return JSONResponse(content={
            "ok": True,
            "valores": valores,
            "origen_detectado": parsed.get("origen_detectado", "desconocido"),
            "confianza": parsed.get("confianza", "media"),
            "observaciones": parsed.get("observaciones", ""),
            "formato_origen": formato,
            "modelo_ia": model,
        })
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"ok": False, "error": f"Error en OCR: {str(e)[:300]}"})
