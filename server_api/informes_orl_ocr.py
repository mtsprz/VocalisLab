"""VocalisLab Pro — OCR de informes ORL externos (narrativa clínica).

Permite subir el análisis que envía el ORL (foto/captura o PDF con texto).
La IA extrae el texto completo + datos estructurados (diagnóstico principal,
método de exploración, hallazgos, conducta) y se guarda en la historia
clínica del paciente como banco de datos. La IA terapéutica lo usa vía
anamnesis (diagnostico_orl / resumen_clinico).
"""
import os
import json
import base64
import traceback
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse

router = APIRouter()

VISION_MODELS = [
    "meta-llama/llama-4-scout-17b-16e-instruct",
    "meta-llama/llama-4-maverick-17b-128e-instruct",
]

EXTRACTION_PROMPT = """Sos un extractor de informes otorrinolaringológicos. Analizá este informe
médico ORL (puede ser laringoscopía, estroboscopía, nasofibroscopía, audiometría
con informe narrativo, o nota manuscrita) y devolvé EXCLUSIVAMENTE un JSON
válido con esta estructura (sin texto extra):

{
  "texto_extraido": "transcripción fiel y completa del informe, respetando el contenido médico",
  "diagnostico_principal": "diagnóstico principal tal cual figura en el informe, o null",
  "metodo_exploracion": "método usado (ej: Nasofibroscopía flexible, Laringostroboscopía, Telelaringoscopía rígida 70°) o null",
  "hallazgos": ["hallazgo 1", "hallazgo 2"],
  "conducta_sugerida_orl": "conducta o tratamiento sugerido por el ORL, o null",
  "fecha_informe": "fecha del informe si figura, o null",
  "profesional_orl": "nombre del profesional firmante si figura, o null",
  "confianza": "alta / media / baja",
  "observaciones": "aclaraciones breves (letra ilegible, sello tapando texto, etc.)"
}

Reglas: transcribí con fidelidad, sin resumir en texto_extraido. Si un campo no
figura, usá null (o [] para hallazgos). No inventes diagnósticos ni datos."""

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


def _vision_extract(image_b64: str, mime: str) -> dict:
    from groq import Groq
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        raise RuntimeError("GROQ_API_KEY no configurada")
    client = Groq(api_key=key, timeout=90.0)
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
                max_tokens=3000,
            )
            return _extract_json(resp.choices[0].message.content or "")
        except Exception as e:
            last_err = e
            print(f"[informes_orl] Modelo visión {model} falló: {str(e)[:150]}")
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


def _payload(parsed: dict, formato: str, modelo: str, archivo_nombre: str) -> dict:
    datos = {
        "hallazgos": parsed.get("hallazgos") or [],
        "conducta_sugerida_orl": parsed.get("conducta_sugerida_orl"),
        "fecha_informe": parsed.get("fecha_informe"),
        "profesional_orl": parsed.get("profesional_orl"),
    }
    return {
        "ok": True,
        "texto_extraido": (parsed.get("texto_extraido") or "").strip(),
        "diagnostico_principal": parsed.get("diagnostico_principal"),
        "metodo_exploracion": parsed.get("metodo_exploracion"),
        "datos_estructurados": datos,
        "confianza": parsed.get("confianza", "media"),
        "observaciones": parsed.get("observaciones", ""),
        "formato_origen": formato,
        "modelo_ia": modelo,
        "archivo_nombre": archivo_nombre,
    }


@router.post("/api/informes-orl/ocr")
async def ocr_informe_orl(archivo: UploadFile = File(...)):
    """Recibe imagen o PDF con texto de un informe ORL y devuelve la
    transcripción + datos estructurados listos para revisar y guardar."""
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
            if len(texto.strip()) < 100:
                return JSONResponse(content={
                    "ok": False,
                    "error": "El PDF no contiene texto extraíble (parece escaneado). Subí una foto o captura de pantalla del informe.",
                })
            from llm_client import groq_chat
            prompt = (EXTRACTION_PROMPT
                      + "\n\nTEXTO DEL INFORME:\n" + texto[:8000])
            raw, model = groq_chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=3000,
            )
            parsed = _extract_json(raw)
            out = _payload(parsed, "pdf-texto", model, archivo.filename or "")
        else:
            mime = "image/jpeg"
            if fname.endswith(".png") or "png" in ctype:
                mime = "image/png"
            elif fname.endswith(".webp") or "webp" in ctype:
                mime = "image/webp"
            image_b64 = base64.b64encode(data).decode()
            parsed = _vision_extract(image_b64, mime)
            out = _payload(parsed, "imagen", "vision", archivo.filename or "")

        if not out["texto_extraido"] or len(out["texto_extraido"]) < 20:
            return JSONResponse(content={
                "ok": False,
                "error": "No se reconoció texto clínico en el archivo. Probá con una imagen más nítida o completa.",
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
    texto_corregido: str = Form(""),
    datos_estructurados: str = Form("{}"),
    diagnostico_principal: str = Form(""),
    metodo_exploracion: str = Form(""),
    profesional_orl: str = Form(""),
    fecha_informe: str = Form(""),
    confianza: str = Form("media"),
    modelo_ia: str = Form(""),
    observaciones_ia: str = Form(""),
    volcar_anamnesis: str = Form("true"),
):
    """Persiste el informe ORL y, si volcar_anamnesis=true, actualiza la
    anamnesis vigente (diagnostico_orl / metodo_exploracion / resumen_clinico)
    para que la IA terapéutica lo use."""
    try:
        datos = json.loads(datos_estructurados) if datos_estructurados.strip() else {}
    except Exception:
        datos = {}
    sb = _db()
    row = {
        "paciente_id": paciente_id,
        "titulo": titulo or "Informe ORL",
        "tipo_informe": tipo_informe or "ORL",
        "archivo_nombre": archivo_nombre,
        "mime": mime,
        "texto_extraido": texto_extraido,
        "texto_corregido": texto_corregido or None,
        "datos_estructurados": datos,
        "diagnostico_principal": diagnostico_principal or None,
        "metodo_exploracion": metodo_exploracion or None,
        "profesional_orl": profesional_orl or None,
        "fecha_informe": fecha_informe or None,
        "confianza": confianza or "media",
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
            fuente = (f"\n\n[Fuente: informe ORL"
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
            texto_final = (texto_corregido or texto_extraido or "").strip()
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
