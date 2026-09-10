"""
VocalisLab Pro - Asistente Clinico IA (RAG hibrido)
Primary cache: Supabase (patologias, ejercicios, patologia_ejercicio_relacion)
Secondary engine: Gemini API (gemini-2.0-flash) con fallback a Groq y a motor heuristico.
"""
import os
import json
import traceback
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
import httpx

router = APIRouter()

BANK_PATH = os.path.join(os.path.dirname(__file__), "exercise_bank.json")


def _supabase():
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


def _load_bank():
    try:
        with open(BANK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sections": [], "presets": []}


def _kb_ranked_exercises(patologia_id: str = "", triggers: list = None):
    """Primary cache: Supabase RAG tables. Fallback: exercise_bank.json presets."""
    triggers = triggers or []
    sb = _supabase()
    if sb and patologia_id:
        try:
            rel = sb.table("patologia_ejercicio_relacion").select(
                "peso, trigger_clinico, ejercicios(id, nombre, descripcion)"
            ).eq("patologia_id", patologia_id).order("peso", desc=True).execute()
            ranked = []
            for row in (rel.data or []):
                ex = row.get("ejercicios") or {}
                ranked.append({
                    "id": ex.get("id", ""),
                    "nombre": ex.get("nombre", ""),
                    "descripcion": ex.get("descripcion", ""),
                    "peso": row.get("peso", 5),
                    "trigger": row.get("trigger_clinico", ""),
                })
            if ranked:
                return {"source": "supabase", "ejercicios": ranked}
        except Exception as e:
            print(f"[ai_clinical] KB supabase no disponible: {e}")
    # Fallback JSON bank
    bank = _load_bank()
    preset = next((p for p in bank.get("presets", []) if p.get("id") == patologia_id), None)
    lookup = {}
    for s in bank.get("sections", []):
        for e in s.get("exercises", []):
            lookup[e["id"]] = e
    ranked = []
    if preset:
        for eid in preset.get("exercise_ids", []):
            e = lookup.get(eid, {})
            ranked.append({
                "id": eid,
                "nombre": e.get("name", eid),
                "descripcion": e.get("description", ""),
                "peso": 7,
                "trigger": "",
            })
    return {"source": "exercise_bank.json", "ejercicios": ranked}


async def _call_gemini(prompt: str) -> str:
    """Llama a Gemini via REST (sin dependencias nuevas)."""
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY no configurada")
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    body = {"contents": [{"parts": [{"text": prompt}]}], "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048}}
    async with httpx.AsyncClient(timeout=45) as client:
        resp = await client.post(url, json=body)
    if resp.status_code != 200:
        raise RuntimeError(f"Gemini API {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        raise RuntimeError(f"Respuesta Gemini inesperada: {str(data)[:300]}")


async def _call_groq(prompt: str) -> str:
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key:
        raise RuntimeError("GROQ_API_KEY no configurada")
    from groq import Groq
    client = Groq(api_key=groq_key, timeout=30.0)
    resp = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": "Sos un asistente fonoaudiologico experto en voz. Respondes en español rioplatense, con rigor clinico."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.4,
        max_tokens=2048,
    )
    return resp.choices[0].message.content or ""


@router.get("/api/ai/kb/patologias")
async def kb_patologias():
    sb = _supabase()
    if sb:
        try:
            res = sb.table("patologias").select("*").order("nombre").execute()
            if res.data:
                return JSONResponse(content={"source": "supabase", "patologias": res.data})
        except Exception as e:
            print(f"[ai_clinical] patologias fallback: {e}")
    bank = _load_bank()
    pats = [{"id": p.get("id"), "nombre": p.get("name"), "descripcion": p.get("description"), "categoria": "preset"} for p in bank.get("presets", [])]
    return JSONResponse(content={"source": "exercise_bank.json", "patologias": pats})


@router.get("/api/ai/kb/ejercicios")
async def kb_ejercicios(patologia_id: str = ""):
    return JSONResponse(content=_kb_ranked_exercises(patologia_id))


@router.post("/api/ai/clinical-assistant")
async def clinical_assistant(request: Request):
    """
    Body JSON:
    {
      "paciente": {...}, "anamnesis": {...}, "escalas": {...},
      "acustica": {...}, "patologia_id": "dmt",
      "pregunta": "texto libre opcional"
    }
    """
    try:
        body = await request.json()
    except Exception:
        body = {}
    paciente = body.get("paciente", {})
    anamnesis = body.get("anamnesis", {})
    escalas = body.get("escalas", {})
    acustica = body.get("acustica", {})
    patologia_id = body.get("patologia_id", "")
    pregunta = body.get("pregunta", "")

    kb = _kb_ranked_exercises(patologia_id)
    kb_lines = "\n".join([f"- [{e.get('peso')}/10] {e.get('nombre')} ({e.get('id')}): {e.get('descripcion','')[:160]}" + (f" | Trigger: {e.get('trigger')}" if e.get('trigger') else "") for e in kb.get("ejercicios", [])[:14]]) or "(sin ejercicios rankeados)"

    grbas = escalas.get("grbas", {})
    prompt = f"""Sos el Asistente Clinico de VocalisLab Pro para fonoaudiologos especialistas en voz.
Marco bibliografico: Farias (2012) Ejercicios que restauran la funcion vocal; Farias (2016) Guia clinica para el especialista en laringe y voz; Le Huche (fisiologia); Titze (SOVTE).

PACIENTE: {json.dumps(paciente, ensure_ascii=False)[:1200]}
ANAMNESIS: {json.dumps(anamnesis, ensure_ascii=False)[:1500]}
ESCALAS: GRBAS={json.dumps(grbas, ensure_ascii=False)[:600]} RASATI={json.dumps(escalas.get('rasati',{}), ensure_ascii=False)[:400]} VHI-10={escalas.get('vhi10_score','N/D')} TME-S={escalas.get('tme_s','N/D')} TME-O={escalas.get('tme_o','N/D')}
ACUSTICA PRAAT: {json.dumps(acustica, ensure_ascii=False)[:1200]}
CUADRO SOSPECHADO (patologia_id): {patologia_id or 'a definir'}
EJERCICIOS CANDIDATOS DEL CACHE (fuente: {kb.get('source')}):
{kb_lines}
PREGUNTA DEL PROFESIONAL: {pregunta or 'Generar orientacion y plan terapeutico.'}

Devolve EXCLUSIVAMENTE JSON valido con estas claves:
{{
  "orientacion_diagnostica": "razonamiento clinico en 4-8 lineas",
  "plan_terapeutico": ["sesion/fase 1...", "fase 2...", "fase 3..."],
  "ejercicios_propuestos": [{{"id": "...", "nombre": "...", "dosificacion": "...", "fundamento": "..."}}],
  "fundamentacion_fisiologica": "con cita de Autor/Libro del catalogo",
  "alertas": ["bandera roja o derivacion si aplica"]
}}"""

    engine = "heuristic"
    texto = ""
    try:
        texto = await _call_gemini(prompt)
        engine = f"supabase+gemini({os.environ.get('GEMINI_MODEL','gemini-2.0-flash')})" if kb.get("source") == "supabase" else "gemini"
    except Exception as e1:
        print(f"[ai_clinical] Gemini fallo: {e1}. Probando Groq...")
        try:
            texto = await _call_groq(prompt)
            engine = "supabase+groq" if kb.get("source") == "supabase" else "groq"
        except Exception as e2:
            print(f"[ai_clinical] Groq fallo: {e2}. Usando heuristica.")
            texto = ""

    if texto:
        # Intentar extraer JSON de la respuesta del LLM
        try:
            start = texto.find("{")
            end = texto.rfind("}") + 1
            parsed = json.loads(texto[start:end])
            parsed["ok"] = True
            parsed["engine"] = engine
            parsed["kb_source"] = kb.get("source")
            parsed["ejercicios_cache"] = kb.get("ejercicios", [])
            return JSONResponse(content=parsed)
        except Exception:
            pass  # cae al heuristico con el texto crudo
        return JSONResponse(content={
            "ok": True, "engine": engine, "kb_source": kb.get("source"),
            "orientacion_diagnostica": texto[:3000],
            "plan_terapeutico": [], "ejercicios_propuestos": [],
            "fundamentacion_fisiologica": "", "alertas": [],
            "ejercicios_cache": kb.get("ejercicios", []),
        })

    # Heuristica: usa el preset del banco como plan
    bank = _load_bank()
    preset = next((p for p in bank.get("presets", []) if p.get("id") == patologia_id), None)
    lookup = {}
    for s in bank.get("sections", []):
        for e in s.get("exercises", []):
            lookup[e["id"]] = e
    props = []
    if preset:
        for eid in preset.get("exercise_ids", [])[:8]:
            e = lookup.get(eid, {})
            props.append({"id": eid, "nombre": e.get("name", eid), "dosificacion": f"{e.get('duration_min',5)} min por sesion", "fundamento": e.get("description", "")[:200]})
    return JSONResponse(content={
        "ok": True, "engine": "heuristic", "kb_source": kb.get("source"),
        "orientacion_diagnostica": f"Cuadro compatible con {preset.get('name') if preset else 'evaluacion funcional pendiente'}: {preset.get('description') if preset else ''}",
        "plan_terapeutico": [
            f"Fase 1 (sesiones 1-4): descontracturacion y SOVTE suave ({preset.get('frecuencia') if preset else '2 veces por semana'})",
            "Fase 2 (sesiones 5-9): resonancia anterior y transferencia al habla",
            "Fase 3 (sesiones 10+): mantenimiento, higiene y autonomia",
        ],
        "ejercicios_propuestos": props,
        "fundamentacion_fisiologica": "Farias (2012, 2016): la semioclusion (SOVTE/LaxVox) ecualiza presiones y masajea la mucosa; Le Huche: la relajacion diferencial reduce la hiperfuncion compensatoria.",
        "alertas": ["Derivar a ORL si disfonia > 15 dias, disnea, disfagia o hemoptisis."],
        "ejercicios_cache": kb.get("ejercicios", []),
    })
