"""Orientación clínica integral del paciente (cruza TODOS los datos de la app).

- POST /api/ficha/{pid}/orientacion   {etapa?: etapa quirúrgica fijada a mano, pregunta?}
      Junta ficha, anamnesis completa, informes ORL, evaluaciones, acústica,
      F0, autoevaluaciones, plan vigente, práctica en casa, turnos y archivos;
      lectura por criterios fijos + situación quirúrgica; redacta la
      orientación completa (sin cortes) y la GUARDA.
- GET  /api/ficha/{pid}/orientaciones lista guardadas
- PUT  /api/orientaciones/{id}        {texto}: guarda la versión corregida por el profesional

Los números que no coinciden con los datos NO se borran (eso dejaba frases a
medias): se listan para revisar.
"""
import json
import re
import traceback

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

MSG_MIGRACION = ("Para guardar las orientaciones falta correr supabase/migracion_2026_11_orientacion.sql "
                 "en Supabase (SQL Editor). La orientación se generó igual.")


def _sb():
    from api_clinica import supabase
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    return supabase


def _corto(v, n=600):
    s = str(v or "").strip()
    return s if len(s) <= n else s[:n] + "…"


def _limpio(d: dict, excluir=("id", "paciente_id", "token", "created_at", "updated_at")) -> dict:
    return {k: v for k, v in (d or {}).items() if k not in excluir and v not in (None, "", [], {})}


def practica_resumen(sb, pid: str) -> dict:
    try:
        ses = (sb.table("practica_sesiones").select("*").eq("paciente_id", pid)
               .order("creada_at", desc=True).limit(200).execute().data or [])
        rut = sb.table("practicas").select("*").eq("paciente_id", pid).execute().data or []
    except Exception:
        return {}
    if not ses:
        return {"rutinas_enviadas": len(rut), "dias_con_practica": 0}
    nombres = {r["id"]: [e.get("nombre") for e in (r.get("ejercicios") or [])] for r in rut}
    por_ej = {}
    for s in ses:
        for x in s.get("resultados") or []:
            n = (nombres.get(s.get("practica_id")) or [])
            nom = n[x["ejercicio"]] if x.get("ejercicio") is not None and x["ejercicio"] < len(n) else f"ejercicio {x.get('ejercicio')}"
            logro = x.get("logro_pct") if x.get("logro_pct") is not None else x.get("dentro_pct")
            if logro is not None:
                d = por_ej.setdefault(nom, {"medida": x.get("medida") or "tono", "logro": [], "tramo_max_s": [], "cortes": [],
                                            "intensidad_sd_db": [], "altura_no_medible": 0})
                d["logro"].append(logro)
                for k in ("tramo_max_s", "cortes", "intensidad_sd_db"):
                    if x.get(k) is not None:
                        d[k].append(x[k])
                d["altura_no_medible"] += 1 if x.get("altura_no_medible") else 0
    return {"rutinas_enviadas": len(rut),
            "dias_con_practica": len({str(s.get("creada_at"))[:10] for s in ses}),
            "primera": str(ses[-1].get("creada_at"))[:10], "ultima": str(ses[0].get("creada_at"))[:10],
            "por_ejercicio": {k: {"medida": v["medida"], "logro_promedio_pct": round(sum(v["logro"]) / len(v["logro"]), 1),
                                  **{f"{c}_promedio": round(sum(v[c]) / len(v[c]), 1) for c in ("tramo_max_s", "cortes", "intensidad_sd_db") if v[c]},
                                  "veces_altura_no_medible": v["altura_no_medible"]} for k, v in por_ej.items()}}


def expediente(datos: dict, practica: dict, situacion: dict) -> dict:
    """Todo lo que sabe la app del paciente, compacto y sin datos de contacto."""
    p = datos["paciente"]
    from criterios_clinicos import _num
    edad = None
    try:
        from datetime import date
        fn = date.fromisoformat(str(p.get("fecha_nacimiento"))[:10])
        hoy = date.today()
        edad = hoy.year - fn.year - ((hoy.month, hoy.day) < (fn.month, fn.day))
    except Exception:
        pass
    plan = (datos.get("plan_vigente") or {}).get("recomendacion") or {}
    return {
        "paciente": {"edad": edad, "sexo": p.get("sexo"), "ocupacion": p.get("ocupacion"),
                     "horas_de_voz_por_dia": _num(p.get("demanda_vocal_horas")),
                     "tipo_atencion": p.get("tipo_atencion") or "voz"},
        "anamnesis": {k: (_corto(v) if isinstance(v, str) else v)
                      for k, v in _limpio(datos.get("anamnesis") or {}, ("id", "paciente_id", "created_at")).items()},
        "informes_orl": [{"fecha": i.get("fecha_informe") or str(i.get("fecha") or "")[:10],
                          "diagnostico": i.get("diagnostico_principal"), "metodo": i.get("metodo_exploracion"),
                          "profesional": i.get("profesional_orl"),
                          "hallazgos": {k: _corto(v, 500) for k, v in (i.get("datos_estructurados") or {}).items()
                                        if k in ("hallazgos_estructurales", "hallazgos_funcionales", "recomendaciones", "conducta") and v},
                          "texto": _corto(i.get("texto_corregido"), 1500)} for i in datos.get("informes_orl") or []],
        "situacion_quirurgica": {k: situacion[k] for k in ("etiqueta", "origen", "evidencia")},
        "evaluaciones": [{k: e.get(k) for k in ("fecha", "grbas", "rasati", "vhi10_score", "riesgo_vocal_score", "tme_o",
                                                 "tme_s", "indice_so", "autopercepcion_vocal", "f0_conversacional_hz")
                          if e.get(k) not in (None, "", {})} | ({"observaciones": _corto(e["observaciones"], 300)} if e.get("observaciones") else {})
                         for e in datos.get("evaluaciones") or []],
        "analisis_acusticos": [{k: a.get(k) for k in ("fecha", "f0_mean", "jitter_local_pct", "shimmer_local_pct", "hnr_db",
                                                      "cpps_db", "avqi", "origen", "fuente") if a.get(k) not in (None, "")}
                               for a in datos.get("analisis_acusticos") or []],
        "f0_conversacional": datos.get("f0_conversacional") or [],
        "autoevaluaciones": [{"fecha": str(a.get("completada_at") or "")[:10], "autopercepcion": a.get("autopercepcion"),
                              "vhi10": a.get("vhi10_score"), "riesgo": a.get("riesgo_vocal_score"),
                              "comentario": _corto(a.get("comentario"), 300)} for a in datos.get("autoevaluaciones") or []],
        "plan_vigente": {"fecha": str((datos.get("plan_vigente") or {}).get("creada_at") or "")[:10],
                         "diagnostico_funcional": plan.get("diagnostico_funcional_fonoaudiologico"),
                         "objetivos": plan.get("objetivos_terapeuticos"),
                         "ejercicios": [e.get("name") or e.get("id") for e in plan.get("ejercicios_recomendados") or []][:15]} if plan else None,
        "practica_en_casa": practica,
        "turnos": datos.get("turnos"),
        "archivos": [{"fecha": a.get("fecha"), "tipo": a.get("tipo"), "titulo": a.get("titulo"), "notas": _corto(a.get("notas"), 200)}
                     for a in datos.get("archivos") or []][-20:],
        "lectura_por_criterios": {k: datos["lectura"][k] for k in ("hallazgos", "patrones", "alertas", "faltan")},
    }


_VALOR_CLINICO = re.compile(r"(?<![\w/.,])(\d+(?:[.,]\d+)?)\s*(/10|/40|/207|Hz|dB|%|h/d[ií]a|s\b|seg\b)")


def valores_a_revisar(texto: str, permitidos: set) -> list:
    """Valores clínicos (con unidad o escala) del texto que no están en los
    datos. No se borran: se muestran para que el profesional los revise."""
    out = []
    for m in _VALOR_CLINICO.finditer(texto or ""):
        n = m.group(1).replace(",", ".")
        if n not in permitidos:
            v = f"{m.group(1)} {m.group(2)}".replace(" /", "/")
            if v not in out:
                out.append(v)
    return out


CONDUCTA_ETAPA = {
    "postquirurgica": (
        "POSTQUIRÚRGICA: respetar el reposo vocal y los tiempos que indicó el cirujano (no fijes días vos); "
        "reintroducción vocal gradual y supervisada; empezar por ejercicios de mínimo impacto (SOVT suaves, "
        "flujo aéreo, voz confidencial evitando susurro forzado), sin empuje ni ataques duros; vigilar signos de "
        "alarma (dolor, disfonía que empeora, hemoptisis) y coordinar controles con el ORL antes de progresar."),
    "prequirurgica": (
        "PREQUIRÚRGICA: terapia vocal prequirúrgica (higiene y economía vocal, eliminar conductas de abuso, "
        "coordinación fonorrespiratoria, SOVT) para llegar a la cirugía en mejores condiciones y con hábitos que "
        "eviten la recidiva; documentar la línea de base (escalas, acústica) para comparar después; preparar al "
        "paciente para el reposo y el posoperatorio. Valorar con el ORL si la terapia puede cambiar la indicación."),
    "a_definir": (
        "LESIÓN QUE PUEDE REQUERIR CIRUGÍA: la conducta la define el ORL. Indicar terapia vocal como primera "
        "etapa (prueba terapéutica) con reevaluación objetiva pautada; derivar o reconsultar al ORL si no hay "
        "respuesta o hay signos de alarma."),
    "no_quirurgica": "SIN INDICACIÓN QUIRÚRGICA: tratamiento conservador (terapia vocal) como primera línea.",
    "sin_datos": ("SIN DIAGNÓSTICO ORL: la orientación es provisoria; recomendar evaluación laríngea "
                  "(laringoscopía/estroboscopía) antes de cerrar el plan."),
}

PROMPT = """Sos un fonoaudiólogo especialista en voz de Argentina escribiendo para la historia clínica.
Tenés el EXPEDIENTE COMPLETO del paciente (todo lo que registró la app, en JSON). Cruzá absolutamente todos
los datos y redactá una ORIENTACIÓN CLÍNICA completa.

Marco clínico: rehabilitación vocal según Farías (Ejercicios que restauran la función vocal; Disfonías),
Le Huche y Allali (La voz), Cobeta, Núñez y Fernández (Patología de la voz, SEORL). Usá su marco conceptual
(hiperfunción/hipofunción, coordinación fonorrespiratoria, higiene y economía vocal, SOVT, resonancia,
fases de la terapia) sin inventar citas textuales ni páginas.

Situación quirúrgica: {etapa}. Conducta de referencia para esta etapa: {conducta}

REGLAS ESTRICTAS
- La "lectura_por_criterios" es la interpretación oficial de los números: no la contradigas.
- Escribí los números exactamente como figuran (sin calcular, redondear ni convertir escalas).
  Autopercepción 0–10: 0 = muy mala, 10 = excelente. VHI-10: más alto = más impacto.
- No diagnostiques patología orgánica (es del ORL): usá "compatible con", "sugiere".
- Si algo no está en el expediente, no lo inventes: ponelo en "Datos a completar".
- Los ejercicios que nombres tienen que ser del cuadernillo: {ejercicios}
- Considerá ocupación, horas de uso de la voz, tipo de atención (voz/canto) y la práctica en casa.
- Escribí completo, frases terminadas, sin cortar. Texto plano con estos títulos exactos:

1. Síntesis del cuadro
2. Correlación de los datos
3. Situación quirúrgica y conducta
4. Orientación terapéutica por fases (objetivos, ejercicios y frecuencia, criterio para pasar de fase)
5. Higiene y uso vocal en su contexto
6. Pronóstico y reevaluación (qué medir y cuándo)
7. Derivaciones e interconsultas (solo si los datos lo justifican)
8. Datos a completar o confirmar

Terminá con: "Orientación de apoyo al criterio profesional."
{pregunta}
EXPEDIENTE:
{expediente}"""


@router.post("/api/ficha/{paciente_id}/orientacion")
async def generar(paciente_id: str, request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    from ficha_integral import ficha
    from criterios_clinicos import situacion_quirurgica, numeros_permitidos
    sb = _sb()
    datos = await ficha(paciente_id)
    sit = situacion_quirurgica(datos, body.get("etapa") or None)
    exp = expediente(datos, practica_resumen(sb, paciente_id), sit)
    if len(datos["lectura"]["hallazgos"]) < 2 and not exp["informes_orl"] and not exp["anamnesis"]:
        raise HTTPException(status_code=400, detail="Hay muy pocos datos cargados para una orientación clínica.")
    try:
        from api_clinica import banco_ejercicios_completo
        nombres = [e.get("name") for s in banco_ejercicios_completo().get("sections", []) for e in s.get("exercises", [])]
    except Exception:
        nombres = []
    prompt = PROMPT.format(etapa=sit["etiqueta"], conducta=CONDUCTA_ETAPA[sit["etapa"]],
                           ejercicios="; ".join(n for n in nombres if n)[:4000] or "(banco no disponible)",
                           pregunta=f"\nPregunta puntual del profesional: {str(body['pregunta'])[:500]}\n" if body.get("pregunta") else "",
                           expediente=json.dumps(exp, ensure_ascii=False, default=str))
    try:
        from llm_client import gemini_texto_completo
        texto, modelo, completo = gemini_texto_completo(prompt, temperature=0.15)
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=f"No se pudo generar la orientación: {str(e)[:200]}")
    permitidos = numeros_permitidos(datos["lectura"], {"paciente": exp, "anamnesis": {}})
    revisar = valores_a_revisar(texto, permitidos)
    fila = {"paciente_id": paciente_id, "texto": texto, "etapa_quirurgica": sit["etapa"], "modelo": modelo,
            "completo": completo, "valores_a_revisar": revisar, "situacion": sit}
    guardada, aviso = None, ""
    try:
        guardada = (sb.table("orientaciones_clinicas").insert(fila).execute().data or [None])[0]
    except Exception as e:
        aviso = MSG_MIGRACION if "orientaciones" in str(e) else f"No se pudo guardar: {str(e)[:150]}"
    return {"ok": True, "id": (guardada or {}).get("id"), "creada_at": (guardada or {}).get("creada_at"),
            "texto": texto, "completo": completo, "valores_a_revisar": revisar, "situacion": sit,
            "modelo": modelo, "aviso": aviso}


@router.get("/api/ficha/{paciente_id}/orientaciones")
async def listar(paciente_id: str):
    sb = _sb()
    try:
        filas = (sb.table("orientaciones_clinicas").select("*").eq("paciente_id", paciente_id)
                 .order("creada_at", desc=True).limit(30).execute().data or [])
    except Exception as e:
        if "orientaciones" in str(e):
            return {"orientaciones": [], "aviso": MSG_MIGRACION}
        raise
    return {"orientaciones": filas}


@router.put("/api/orientaciones/{orientacion_id}")
async def editar(orientacion_id: str, request: Request):
    body = await request.json()
    texto = str(body.get("texto") or "").strip()
    if not texto:
        raise HTTPException(status_code=400, detail="El texto está vacío.")
    sb = _sb()
    sb.table("orientaciones_clinicas").update({"texto": texto[:60000], "editado": True}).eq("id", orientacion_id).execute()
    return {"ok": True}
