"""Ficha integral del paciente: todo en una hoja + comparación de estudios.

- GET  /api/ficha/{paciente_id}
    Datos, cuadro clínico (anamnesis), informes ORL, evaluaciones (escalas,
    riesgo, VHI, TME) y análisis acústicos ordenados por fecha (evolución),
    F0 conversacional, autoevaluaciones, plan terapéutico vigente, turnos y
    archivos de la ficha (imágenes y videos en Google Drive).
- POST /api/ficha/{paciente_id}/analisis-imagenes
    {archivo_ids: [1 o 2 ids], pregunta?}: análisis automático ORIENTATIVO de
    imágenes/videos (laringoscopía, estroboscopía) con Gemini: describe lo
    observable y, con dos estudios, la evolución entre ambos. Nunca reemplaza
    el informe del ORL.
"""
import base64
import json
import traceback

import httpx
from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

MAX_BYTES_IMAGEN = 18 * 1024 * 1024  # límite de envío directo a Gemini


def _sb():
    from api_clinica import supabase
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    return supabase


def _lista(sb, tabla, pid, orden, campo_pac="paciente_id", limite=50, desc=False):
    try:
        return (sb.table(tabla).select("*").eq(campo_pac, pid).order(orden, desc=desc)
                .limit(limite).execute().data or [])
    except Exception:
        return []


def _f0_conversacional(sb, pid):
    ses = _lista(sb, "companion_sessions", pid, "recorded_at", campo_pac="patient_id", limite=60)
    if not ses:
        return []
    try:
        ac = (sb.table("session_acoustics").select("session_id, task_type, f0_median_hz")
              .in_("session_id", [s["id"] for s in ses]).execute().data or [])
    except Exception:
        return []
    por_ses = {a["session_id"]: a["f0_median_hz"] for a in ac
               if a.get("task_type") == "conversacion_espontanea" and a.get("f0_median_hz")}
    return [{"fecha": str(s.get("recorded_at") or "")[:10], "f0_mediana_hz": por_ses[s["id"]],
             "origen": (s.get("device_info") or {}).get("contexto") or (s.get("device_info") or {}).get("origen") or "companion"}
            for s in ses if s["id"] in por_ses]


@router.get("/api/ficha/{paciente_id}")
async def ficha(paciente_id: str):
    sb = _sb()
    filas = sb.table("pacientes").select("*").eq("id", paciente_id).execute().data or []
    if not filas:
        raise HTTPException(status_code=404, detail="Paciente inexistente")
    p = filas[0]
    anamnesis = _lista(sb, "anamnesis", paciente_id, "fecha", desc=True, limite=1)
    recs = _lista(sb, "recomendaciones_terapeuticas", paciente_id, "creada_at", desc=True, limite=1)
    turnos = _lista(sb, "turnos", paciente_id, "fecha_hora", limite=200)
    auto = [a for a in _lista(sb, "autoevaluaciones", paciente_id, "creada_at")
            if a.get("estado") == "completada"]
    for a in auto:
        a.pop("token", None)
    informes = _lista(sb, "informes_orl", paciente_id, "fecha")
    for i in informes:
        i.pop("texto_extraido", None)  # pesado; queda el corregido y lo estructurado
    return {
        "paciente": p,
        "anamnesis": anamnesis[0] if anamnesis else None,
        "informes_orl": informes,
        "evaluaciones": _lista(sb, "evaluaciones_clinicas", paciente_id, "fecha"),
        "analisis_acusticos": _lista(sb, "analisis_acusticos", paciente_id, "fecha"),
        "f0_conversacional": _f0_conversacional(sb, paciente_id),
        "autoevaluaciones": auto,
        "plan_vigente": recs[0] if recs else None,
        "turnos": {"total": len(turnos),
                   "realizados": len([t for t in turnos if t.get("estado") == "completado"]),
                   "primero": str(turnos[0]["fecha_hora"])[:10] if turnos else None},
        "archivos": _lista(sb, "archivos_paciente", paciente_id, "fecha"),
    }


async def _descargar_drive(token: str, fid: str) -> tuple:
    async with httpx.AsyncClient(timeout=120, follow_redirects=True) as c:
        meta = await c.get(f"https://www.googleapis.com/drive/v3/files/{fid}",
                           headers={"Authorization": f"Bearer {token}"}, params={"fields": "mimeType,size,name"})
        if meta.status_code != 200:
            from archivos_drive import _error_drive
            _error_drive(meta, "leer archivo")
        info = meta.json()
        if int(info.get("size") or 0) > MAX_BYTES_IMAGEN:
            raise HTTPException(status_code=413, detail=(
                f"«{info.get('name')}» pesa más de 18 MB: para analizarlo subí una captura (foto) del "
                "momento clave del video."))
        r = await c.get(f"https://www.googleapis.com/drive/v3/files/{fid}",
                        headers={"Authorization": f"Bearer {token}"}, params={"alt": "media"})
        if r.status_code != 200:
            from archivos_drive import _error_drive
            _error_drive(r, "descargar archivo")
        return r.content, info.get("mimeType") or "application/octet-stream", info.get("name") or ""


PROMPT_IMAGENES = """Sos un asistente para un fonoaudiólogo especializado en voz. Te paso {n}
estudio(s) por imagen de laringe/cuerdas vocales (laringoscopía, videolaringoestroboscopía,
nasofibroscopía o fotos de informes), con su fecha, y datos clínicos del paciente.

Tarea:
1. Por cada estudio, describí SOLO lo observable: calidad de la imagen, cierre glótico (si se ve),
   aspecto de los bordes libres, presencia/ausencia de lesiones (forma, ubicación, lateralidad),
   simetría, coloración, mucosa, estructuras supraglóticas. Si algo no se puede evaluar, decilo.
2. {comparacion}
3. Relacioná con los datos clínicos aportados (escalas, acústica, diagnóstico ORL) sin forzar.
4. Sugerí qué conviene confirmar con el ORL o en la evaluación.

Reglas: no diagnostiques; usá lenguaje prudente ("compatible con", "se observaría"); si la imagen no
alcanza, decilo. Español rioplatense, claro y técnico para un fonoaudiólogo. Texto plano con títulos
cortos. Terminá con: "Análisis orientativo: no reemplaza el informe del otorrinolaringólogo."

Datos clínicos:
{clinica}
{pregunta}"""


@router.post("/api/ficha/{paciente_id}/analisis-imagenes")
async def analizar_imagenes(paciente_id: str, request: Request):
    usuario = getattr(request.state, "usuario", None) or {}
    uid = str(usuario.get("sub") or "")
    body = await request.json()
    ids = [str(i) for i in (body.get("archivo_ids") or [])][:2]
    if not ids:
        raise HTTPException(status_code=400, detail="Elegí una o dos imágenes o videos.")
    sb = _sb()
    archivos = []
    for aid in ids:
        f = sb.table("archivos_paciente").select("*").eq("id", aid).eq("paciente_id", paciente_id).execute().data or []
        if not f or not f[0].get("drive_file_id"):
            raise HTTPException(status_code=404, detail="Archivo inexistente en la ficha.")
        archivos.append(f[0])
    archivos.sort(key=lambda a: str(a.get("fecha") or ""))
    from google_auth import _get_valid_token
    token = await _get_valid_token(uid)
    datos = await ficha(paciente_id)
    clinica = {
        "anamnesis": {k: (datos["anamnesis"] or {}).get(k) for k in ("motivo_consulta", "diagnostico_orl", "metodo_exploracion")},
        "informes_orl": [{k: i.get(k) for k in ("fecha_informe", "diagnostico_principal", "metodo_exploracion")}
                         for i in datos["informes_orl"]][-3:],
        "evaluaciones": [{k: e.get(k) for k in ("fecha", "grbas", "vhi10_score", "tme_o", "riesgo_vocal_score")}
                         for e in datos["evaluaciones"]][-3:],
        "acustica": [{k: a.get(k) for k in ("fecha", "f0_mean", "jitter_local_pct", "shimmer_local_pct", "hnr_db", "cpps_db", "avqi")}
                     for a in datos["analisis_acusticos"]][-3:],
    }
    partes = [{"text": PROMPT_IMAGENES.format(
        n=len(archivos),
        comparacion=("Compará ambos estudios en orden cronológico: qué cambió, qué se mantiene y si la "
                     "evolución parece favorable, estable o desfavorable." if len(archivos) == 2
                     else "Un solo estudio: no hay comparación."),
        clinica=json.dumps(clinica, ensure_ascii=False, default=str),
        pregunta=f"Pregunta del profesional: {body['pregunta']}" if body.get("pregunta") else "")}]
    for a in archivos:
        contenido, mime, nombre = await _descargar_drive(token, a["drive_file_id"])
        partes.append({"text": f"Estudio del {a.get('fecha')} — {a.get('titulo') or nombre}"
                               f"{' — notas: ' + a['notas'] if a.get('notas') else ''}"})
        partes.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(contenido).decode()}})
    try:
        from llm_client import gemini_generate, gemini_texto
        resp, modelo = gemini_generate(partes, {"temperature": 0.2, "maxOutputTokens": 3000}, timeout=180)
        texto = gemini_texto(resp).strip()
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"No se pudo analizar: {str(e)[:200]}")
    if not texto:
        raise HTTPException(status_code=502, detail="El análisis volvió vacío; probá de nuevo.")
    return {"ok": True, "texto": texto, "modelo": modelo,
            "estudios": [{"id": a["id"], "fecha": a.get("fecha"), "titulo": a.get("titulo")} for a in archivos]}
