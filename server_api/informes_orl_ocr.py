"""VocalisLab Pro — OCR de informes ORL externos (narrativa clínica y manuscrita).

Permite subir el análisis que envía el ORL (foto/captura o PDF con texto/escaneado).
La IA extrae la transcripción integra + hallazgos estructurales y funcionales
mediante visión multimodal (Gemini Flash Vision / Groq Vision). Se guarda en la
historia clínica del paciente como banco de datos. La IA terapéutica lo usa vía
anamnesis (diagnostico_orl / resumen_clinico).
"""
import os
import json
import base64
import traceback
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse

router = APIRouter()

# Modelos con visión en Groq (fallback cuando Gemini no esté disponible)
GROQ_VISION_MODELS = [
    "qwen/qwen3.6-27b",
    "qwen/qwen3.8-27b",
]

# Prompt optimizado para caligrafía médica manuscrita y terminología ORL
EXTRACTION_PROMPT = """Eres un fonoaudiólogo transcriptor experto. Analiza la imagen del informe u orden ORL adjunta escrita a mano alzada o impresa. Transcribe con exactitud los hallazgos anatómicos (pliegues vocales, subglotis) y funcionales (hiperfunción, constricción, movilidad). Utiliza el contexto de la semántica clínica otorrinolaringológica para resolver trazos caligráficos ambiguos o ilegibles.

Devuelve EXCLUSIVAMENTE un JSON válido con esta estructura (sin texto extra):

{
  "texto_transcrito_crudo": "transcripción completa e íntegra del informe escrito a mano o impreso",
  "hallazgos_estructurales": "descripción de hallazgos anatómicos y estructurales (ej: pliegues vocales, mucosa, bordes, lesiones, subglotis)",
  "hallazgos_funcionales": "descripción de hallazgos funcionales (ej: hiperfunción, constricción vestíbulolaringea, hiato, movilidad cordal)",
  "diagnostico_principal": "diagnóstico ORL principal (o null)",
  "metodo_exploracion": "método de exploración utilizado (ej: Nasofibroscopía flexible, Laringostroboscopía, Telelaringoscopía) o null",
  "conducta_sugerida_orl": "conducta o tratamiento sugerido por el ORL (o null)",
  "profesional_orl": "nombre del profesional firmante (o null)",
  "fecha_informe": "fecha del informe (o null)",
  "confianza_extraccion": "alta|media|baja"
}

Reglas: transcribí con fidelidad, sin resumir en texto_transcrito_crudo. Si un campo no figura, usá null. No inventes diagnósticos ni datos.
"""

_supabase = None


def _db():
    global _supabase
    if _supabase is None:
        try:
            from supabase import create_client
            url = os.environ.get("SUPABASE_URL", "")
            key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))
            _supabase = create_client(url, key) if (url and key) else False
        except Exception as e:
            print(f"[informes_orl] Supabase no disponible: {str(e)[:120]}")
            _supabase = False
    return _supabase or None


def _groq_vision_models():
    env = os.environ.get("GROQ_VISION_MODEL", "").strip()
    if env:
        return [m.strip() for m in env.split(",") if m.strip()]
    return list(GROQ_VISION_MODELS)


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError("La IA no devolvió un JSON válido")
    return json.loads(text[start:end])


async def _gemini_vision_extract(image_b64: str, mime: str, prompt: str = None) -> dict:
    """Procesamiento multimodal con Gemini Flash Vision (Opción Primaria VLM)."""
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("GEMINI_API_KEY no configurada")

    import httpx
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt or EXTRACTION_PROMPT},
                {
                    "inline_data": {
                        "mime_type": mime,
                        "data": image_b64
                    }
                }
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 3000,
            "responseMimeType": "application/json"
        }
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code != 200:
            raise RuntimeError(f"Gemini Vision Error ({resp.status_code}): {resp.text[:200]}")
        data = resp.json()
        cands = data.get("candidates", [])
        if not cands:
            raise RuntimeError("Gemini no devolvió resultados")
        parts = cands[0].get("content", {}).get("parts", [])
        if not parts:
            raise RuntimeError("Candidato de Gemini sin partes de texto")
        return _extract_json(parts[0].get("text", ""))


def _groq_vision_extract(image_b64: str, mime: str, prompt: str = None,
                         max_tokens: int = 3000) -> dict:
    """Procesamiento con Groq Vision (Fallback Open Source)."""
    from groq import Groq
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("GROQ_API_KEY no configurada")
    client = Groq(api_key=key, timeout=90.0)
    last_err: Exception = RuntimeError("Sin modelos de visión configurados")
    for model in _groq_vision_models():
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt or EXTRACTION_PROMPT},
                        {"type": "image_url",
                         "image_url": {"url": f"data:{mime};base64,{image_b64}"}},
                    ],
                }],
                temperature=0.1,
                max_tokens=max_tokens,
            )
            return _extract_json(resp.choices[0].message.content or "")
        except Exception as e:
            last_err = e
            print(f"[informes_orl] Groq visión {model} falló: {str(e)[:150]}")
            continue
    raise last_err


async def _vision_extract(image_b64: str, mime: str, prompt: str = None) -> tuple[dict, str]:
    """Pipeline multimodal: intenta Gemini Flash Vision primero, luego Groq Vision."""
    if os.environ.get("GEMINI_API_KEY", "").strip():
        try:
            parsed = await _gemini_vision_extract(image_b64, mime, prompt)
            model_used = f"gemini-vision ({os.environ.get('GEMINI_MODEL', 'gemini-2.0-flash')})"
            return parsed, model_used
        except Exception as e:
            print(f"[informes_orl] Gemini Vision falló, probando Groq Vision fallback: {str(e)[:150]}")

    parsed = _groq_vision_extract(image_b64, mime, prompt)
    return parsed, "groq-vision"


def _pdf_render_paginas(data: bytes, max_paginas: int = 3, dpi: int = 200) -> list:
    """Renderiza las primeras páginas de un PDF escaneado a PNG (bytes)."""
    try:
        import pymupdf as fitz
    except ImportError:
        try:
            import fitz
        except ImportError:
            raise RuntimeError("Soporte de PDF escaneado no instalado en el servidor")
    try:
        doc = fitz.open(stream=data, filetype="pdf")
    except Exception as e:
        raise RuntimeError(f"No se pudo abrir el PDF: {str(e)[:150]}")
    if getattr(doc, "needs_pass", False):
        raise RuntimeError("El PDF está protegido con contraseña")
    paginas = []
    for i in range(min(len(doc), max_paginas)):
        try:
            pix = doc.load_page(i).get_pixmap(dpi=dpi)
            paginas.append(pix.tobytes("png"))
        except Exception as e:
            print(f"[informes_orl] No se pudo renderizar página {i + 1}: {str(e)[:120]}")
    doc.close()
    if not paginas:
        raise RuntimeError("No se pudieron renderizar las páginas del PDF")
    return paginas


def _fusionar_paginas(parsed_list: list) -> dict:
    """Fusiona la extracción de N páginas en un único resultado estructurado."""
    textos, est, func = [], [], []
    out = {}
    confianzas = []
    for idx, p in enumerate(parsed_list, 1):
        t = (p.get("texto_transcrito_crudo") or p.get("texto_extraido") or "").strip()
        e = (p.get("hallazgos_estructurales") or "").strip()
        f = (p.get("hallazgos_funcionales") or "").strip()
        if t:
            textos.append(f"--- Página {idx} ---\n{t}")
        if e:
            est.append(e)
        if f:
            func.append(f)
        for k in ("diagnostico_principal", "metodo_exploracion",
                  "conducta_sugerida_orl", "fecha_informe", "profesional_orl"):
            if not out.get(k) and p.get(k):
                out[k] = p[k]
        conf = p.get("confianza_extraccion") or p.get("confianza")
        if conf:
            confianzas.append(str(conf).lower())
    out["texto_transcrito_crudo"] = "\n\n".join(textos)
    out["hallazgos_estructurales"] = "\n".join(est)
    out["hallazgos_funcionales"] = "\n".join(func)
    out["confianza_extraccion"] = ("baja" if "baja" in confianzas
                                  else "media" if "media" in confianzas else "alta")
    obs = [p.get("observaciones") for p in parsed_list if p.get("observaciones")]
    obs.append(f"PDF escaneado: {len(parsed_list)} página(s) procesadas con visión IA.")
    out["observaciones"] = " ".join(o for o in obs if o)
    return out


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


def _payload(parsed: dict, formato: str, modelo: str, archivo_nombre: str) -> dict:
    texto_crudo = (parsed.get("texto_transcrito_crudo") or parsed.get("texto_extraido") or "").strip()
    estructurales = (parsed.get("hallazgos_estructurales") or "").strip()
    funcionales = (parsed.get("hallazgos_funcionales") or "").strip()
    confianza = parsed.get("confianza_extraccion") or parsed.get("confianza") or "alta"

    # Construir texto completo
    partes = []
    if texto_crudo:
        partes.append(texto_crudo)
    if estructurales and estructurales not in texto_crudo:
        partes.append(f"Hallazgos Estructurales: {estructurales}")
    if funcionales and funcionales not in texto_crudo:
        partes.append(f"Hallazgos Funcionales: {funcionales}")

    texto_extraido = "\n\n".join(partes) if partes else texto_crudo

    datos = {
        "texto_transcrito_crudo": texto_crudo,
        "hallazgos_estructurales": estructurales,
        "hallazgos_funcionales": funcionales,
        "conducta_sugerida_orl": parsed.get("conducta_sugerida_orl"),
        "fecha_informe": parsed.get("fecha_informe"),
        "profesional_orl": parsed.get("profesional_orl"),
        "confianza_extraccion": confianza,
    }

    return {
        "ok": True,
        "texto_extraido": texto_extraido,
        "texto_transcrito_crudo": texto_crudo,
        "hallazgos_estructurales": estructurales,
        "hallazgos_funcionales": funcionales,
        "diagnostico_principal": parsed.get("diagnostico_principal"),
        "metodo_exploracion": parsed.get("metodo_exploracion"),
        "datos_estructurados": datos,
        "confianza": confianza,
        "confianza_extraccion": confianza,
        "observaciones": parsed.get("observaciones", ""),
        "formato_origen": formato,
        "modelo_ia": modelo,
        "archivo_nombre": archivo_nombre,
    }


@router.post("/api/informes-orl/ocr")
async def ocr_informe_orl(archivo: UploadFile = File(...)):
    """Recibe imagen o PDF (impreso o manuscrito) de un informe ORL y devuelve
    la transcripción + hallazgos estructurales/funcionales extraídos por IA."""
    try:
        data = await archivo.read()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error leyendo archivo: {e}")
    if not data or len(data) < 100:
        raise HTTPException(status_code=400, detail="Archivo vacío o demasiado pequeño")
    if len(data) > 12 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Archivo mayor a 12 MB")

    fname = (archivo.filename or "informe-orl").lower()
    ctype = (archivo.content_type or "").lower()
    es_pdf = fname.endswith(".pdf") or "pdf" in ctype

    try:
        if es_pdf:
            texto = _pdf_to_text(data)
            if len(texto.strip()) >= 100:
                from llm_client import groq_chat
                prompt = (EXTRACTION_PROMPT
                          + "\n\nTEXTO DEL INFORME:\n" + texto[:8000])
                raw, model = groq_chat(
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1,
                    max_tokens=3000,
                )
                parsed = _extract_json(raw)
                formato = "pdf-texto"
            else:
                # PDF escaneado / manuscrito:
                paginas = _pdf_render_paginas(data)
                parsed_list = []
                for png in paginas:
                    p_res, m_name = await _vision_extract(
                        base64.b64encode(png).decode(), "image/png")
                    parsed_list.append(p_res)
                parsed = _fusionar_paginas(parsed_list)
                model = "vision"
                formato = "pdf-escaneado"
        else:
            mime = "image/jpeg"
            if fname.endswith(".png") or "png" in ctype:
                mime = "image/png"
            elif fname.endswith(".webp") or "webp" in ctype:
                mime = "image/webp"
            image_b64 = base64.b64encode(data).decode()
            parsed, model = await _vision_extract(image_b64, mime)
            formato = "imagen"

        out = _payload(parsed, formato, model, archivo.filename or "")

        if not out["texto_extraido"] and not out["texto_transcrito_crudo"]:
            return JSONResponse(content={
                "ok": False,
                "error": "No se reconoció texto clínico en el archivo. Probá con una imagen más nítida o de mayor resolución.",
            })
        return JSONResponse(content=out)
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"ok": False, "error": f"Error en OCR: {str(e)[:300]}"})


@router.post("/api/informes-orl")
async def guardar_informe_orl(
    paciente_id: str = Form(...),
    titulo: str = Form("Informe ORL"),
    tipo_informe: str = Form("ORL"),
    archivo_nombre: str = Form(""),
    mime: str = Form(""),
    texto_extraido: str = Form(""),
    texto_transcrito_crudo: str = Form(""),
    hallazgos_estructurales: str = Form(""),
    hallazgos_funcionales: str = Form(""),
    texto_corregido: str = Form(""),
    datos_estructurados: str = Form("{}"),
    diagnostico_principal: str = Form(""),
    metodo_exploracion: str = Form(""),
    profesional_orl: str = Form(""),
    fecha_informe: str = Form(""),
    confianza: str = Form("alta"),
    modelo_ia: str = Form(""),
    observaciones_ia: str = Form(""),
    volcar_anamnesis: str = Form("true"),
):
    """Persiste el informe ORL y, si volcar_anamnesis=true, actualiza la
    anamnesis vigente para uso del motor de recomendación terapéutica."""
    try:
        datos = json.loads(datos_estructurados) if datos_estructurados.strip() else {}
    except Exception:
        datos = {}

    datos["texto_transcrito_crudo"] = texto_transcrito_crudo or datos.get("texto_transcrito_crudo", "")
    datos["hallazgos_estructurales"] = hallazgos_estructurales or datos.get("hallazgos_estructurales", "")
    datos["hallazgos_funcionales"] = hallazgos_funcionales or datos.get("hallazgos_funcionales", "")

    sb = _db()
    row = {
        "paciente_id": paciente_id,
        "titulo": titulo or "Informe ORL",
        "tipo_informe": tipo_informe or "ORL",
        "archivo_nombre": archivo_nombre,
        "mime": mime,
        "texto_extraido": texto_extraido or texto_transcrito_crudo,
        "texto_corregido": texto_corregido or None,
        "datos_estructurados": datos,
        "diagnostico_principal": diagnostico_principal or None,
        "metodo_exploracion": metodo_exploracion or None,
        "profesional_orl": profesional_orl or None,
        "fecha_informe": fecha_informe or None,
        "confianza": confianza or "alta",
        "modelo_ia": modelo_ia or None,
        "observaciones_ia": observaciones_ia or None,
        "estado": "pendiente_revision",
    }
    saved = None
    if sb:
        try:
            res = sb.table("informes_orl").insert(row).execute()
            saved = res.data[0] if res.data else row
        except Exception as e:
            traceback.print_exc()
            raise HTTPException(status_code=500, detail=f"Error guardando informe: {str(e)[:300]}")
    else:
        saved = {"id": "local", **row}

    volcado = False
    if volcar_anamnesis.lower() in ("1", "true", "si", "sí") and sb:
        try:
            fuente = (f"\n\n[Informe ORL"
                      + (f" — {fecha_informe}" if fecha_informe else "")
                      + (f" — {profesional_orl}" if profesional_orl else "")
                      + "]")
            existente = sb.table("anamnesis").select("id,resumen_clinico").eq(
                "paciente_id", paciente_id).order("fecha", desc=True).limit(1).execute()
            parche = {}
            if diagnostico_principal:
                parche["diagnostico_orl"] = diagnostico_principal
            if metodo_exploracion:
                parche["metodo_exploracion"] = metodo_exploracion

            partes_resumen = []
            if hallazgos_estructurales:
                partes_resumen.append(f"Estructurales: {hallazgos_estructurales}")
            if hallazgos_funcionales:
                partes_resumen.append(f"Funcionales: {hallazgos_funcionales}")
            if not partes_resumen and (texto_corregido or texto_extraido):
                partes_resumen.append(texto_corregido or texto_extraido)

            texto_final = " | ".join(partes_resumen).strip()

            if existente.data:
                rid = existente.data[0]["id"]
                previo = existente.data[0].get("resumen_clinico") or ""
                if texto_final and texto_final not in previo:
                    parche["resumen_clinico"] = (previo + fuente + "\n" + texto_final).strip()
                if parche:
                    sb.table("anamnesis").update(parche).eq("id", rid).execute()
                    volcado = True
            else:
                nuevo = {
                    "paciente_id": paciente_id,
                    "motivo_consulta": "",
                    "diagnostico_orl": diagnostico_principal or "",
                    "metodo_exploracion": metodo_exploracion or "",
                    "sintomas": {},
                    "factores_riesgo": {},
                    "resumen_clinico": (fuente + "\n" + texto_final).strip() if texto_final else "",
                    "transcripcion_audio": "",
                }
                sb.table("anamnesis").insert(nuevo).execute()
                volcado = True
        except Exception:
            traceback.print_exc()

    return JSONResponse(content={"ok": True, "informe": saved, "volcado_anamnesis": volcado})


@router.get("/api/informes-orl")
async def listar_informes_orl(paciente_id: str = Query(...), limit: int = Query(20)):
    sb = _db()
    if not sb:
        return JSONResponse(content=[])
    try:
        res = sb.table("informes_orl").select("*").eq("paciente_id", paciente_id)\
            .order("fecha", desc=True).limit(limit).execute()
        return JSONResponse(content=res.data or [])
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error listando informes: {str(e)[:300]}")


@router.put("/api/informes-orl/{informe_id}")
async def actualizar_informe_orl(
    informe_id: str,
    texto_corregido: str = Form(""),
    estado: str = Form(""),
    diagnostico_principal: str = Form(""),
    metodo_exploracion: str = Form(""),
):
    sb = _db()
    if not sb:
        raise HTTPException(status_code=500, detail="Base de datos no configurada")
    parche = {}
    if texto_corregido:
        parche["texto_corregido"] = texto_corregido
    if estado in ("pendiente_revision", "validado", "descartado"):
        parche["estado"] = estado
    if diagnostico_principal:
        parche["diagnostico_principal"] = diagnostico_principal
    if metodo_exploracion:
        parche["metodo_exploracion"] = metodo_exploracion
    if not parche:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    try:
        res = sb.table("informes_orl").update(parche).eq("id", informe_id).execute()
        return JSONResponse(content={"ok": True, "informe": (res.data[0] if res.data else parche)})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error actualizando informe: {str(e)[:300]}")


@router.delete("/api/informes-orl/{informe_id}")
async def eliminar_informe_orl(informe_id: str):
    sb = _db()
    if not sb:
        raise HTTPException(status_code=500, detail="Base de datos no configurada")
    try:
        sb.table("informes_orl").delete().eq("id", informe_id).execute()
        return JSONResponse(content={"ok": True})
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error eliminando informe: {str(e)[:300]}")
