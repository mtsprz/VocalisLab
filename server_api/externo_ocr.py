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

VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
]

# Claves acústicas que la IA debe extraer (todas opcionales, null si ausente)
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
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("La IA no devolvió un JSON válido")
    return json.loads(text[start:end])


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
        if es_pdf:
            texto = _pdf_to_text(data)
            if len(texto.strip()) < 100:
                return JSONResponse(content={
                    "ok": False,
                    "error": "El PDF no contiene texto extraíble (parece escaneado). Subí una foto o captura de pantalla del informe.",
                })
            from llm_client import groq_chat
            prompt = (EXTRACTION_PROMPT
                      + "\n\nTEXTO DEL INFORME:\n" + texto[:6000])
            raw, model = groq_chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=1500,
            )
            parsed = _extract_json(raw)
            formato = "pdf-texto"
        else:
            mime = "image/jpeg"
            if fname.endswith(".png") or "png" in ctype:
                mime = "image/png"
            elif fname.endswith(".webp") or "webp" in ctype:
                mime = "image/webp"
            image_b64 = base64.b64encode(data).decode()
            parsed = _vision_extract(image_b64, mime)
            model = "vision"
            formato = "imagen"

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
            "modelo_ia": model if formato == "pdf-texto" else "vision",
        })
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"ok": False, "error": f"Error en OCR: {str(e)[:300]}"})
