"""
VocalisLab Pro — Motor de Recomendación IA Fonoaudiológico
Basado en Farías (2012, 2016), Le Huche y correlación multidimensional:
Anamnesis + Ficha de Riesgo Vocal (69 ítems) + Escalas Clínicas + Acústica Praat.
"""
import os
import json
import traceback
EXERCISE_BANK_PATH = os.path.join(os.path.dirname(__file__), "exercise_bank.json")


def _load_bank():
    # Mismo banco que el cuadernillo, con los ejercicios que aprobó el profesional.
    try:
        from api_clinica import banco_ejercicios_completo
        bank = banco_ejercicios_completo()
        if bank.get("sections"):
            return bank
    except Exception as e:
        print(f"[recomendar_motor] banco completo no disponible, uso el base: {e}")
    try:
        with open(EXERCISE_BANK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sections": [], "presets": []}


_PRECAUCIONES_CACHE = None


def precauciones_por_bank_id():
    """bank_id ejercicio → texto de precauciones (fichas_clinicas.json).

    Se usa para imprimir el STOP por ejercicio en el PDF aunque el frontend
    mande los ejercicios sin ese campo.
    """
    global _PRECAUCIONES_CACHE
    if _PRECAUCIONES_CACHE is None:
        _PRECAUCIONES_CACHE = {}
        try:
            path = os.path.join(os.path.dirname(__file__), "fichas_clinicas.json")
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            fichas = raw.get("fichas", raw) if isinstance(raw, dict) else raw
            for fc in (fichas or []):
                bid = str(fc.get("bank_id", "")).strip().lower()
                prec = str(fc.get("precauciones", "")).strip()
                if bid and prec and bid not in _PRECAUCIONES_CACHE:
                    _PRECAUCIONES_CACHE[bid] = prec
        except Exception as e:
            print(f"[recomendar_motor] no se pudieron cargar precauciones: {e}")
    return _PRECAUCIONES_CACHE


# Mapeo tag de contraindicación del banco → patrones en el diagnóstico/motivo.
# Si el diagnóstico matchea y el ejercicio tiene ese tag, se EXCLUYE del
# cuadernillo (error clínicamente inadmisible, ej: empuje + nódulos).
CONTRA_MAP = {
    "nodulo": [r"n[oó]dulo", r"p[oó]lipo", r"quiste", r"reinke", r"edema",
               r"lesi[oó]n (de masa|exof)", r"exof[ií]", r"papiloma", r"granuloma"],
    "hiperfuncion": [r"hiperfunc", r"\bdmt\b", r"m[uú]sculo tens", r"espasm[oó]dica"],
    "dmt": [r"\bdmt\b", r"hiperfunc", r"tensional"],
    "laringitis_aguda": [r"laringitis aguda"],
}

_EXERCISE_INDEX = None


def _exercise_index():
    """id ejercicio → {contraindications, name} (cache en memoria)."""
    global _EXERCISE_INDEX
    if _EXERCISE_INDEX is None:
        _EXERCISE_INDEX = {}
        bank = _load_bank()
        for s in bank.get("sections", []):
            for e in s.get("exercises", []):
                if e.get("id"):
                    _EXERCISE_INDEX[e["id"]] = {
                        "name": e.get("name", e["id"]),
                        "contraindications": e.get("contraindications", []) or [],
                    }
    return _EXERCISE_INDEX


def verificar_contraindicaciones(exercise_ids, diagnostico_texto=""):
    """
    Retorna (seguros, excluidos). excluidos = [{id, name, motivo}].
    Sin diagnóstico no se excluye nada (se informa como no verificado).
    """
    import re as _re
    idx = _exercise_index()
    diag = (diagnostico_texto or "").lower()
    seguros, excluidos = [], []
    for eid in (exercise_ids or []):
        info = idx.get(eid, {"name": eid, "contraindications": []})
        motivo = None
        for tag in info["contraindications"]:
            for pat in CONTRA_MAP.get(tag, []):
                if _re.search(pat, diag):
                    motivo = (
                        f"Contraindicado con este cuadro ('{tag}'): "
                        f"el diagnóstico menciona un patrón compatible."
                    )
                    break
            if motivo:
                break
        if motivo:
            excluidos.append({"id": eid, "name": info["name"], "motivo": motivo})
        else:
            seguros.append(eid)
    return seguros, excluidos


def _ids_por_area(bank) -> str:
    """Lista real de IDs del banco agrupada por área, para el prompt."""
    return "\n".join(
        f"  {s.get('id')}: " + ", ".join(e.get("id") for e in s.get("exercises", []) if e.get("id"))
        for s in bank.get("sections", []))


def _completar_con_plan(rec: dict, clinica: dict, bank: dict) -> dict:
    """Pasa la recomendación por el planificador del cuadernillo: descarta
    IDs inexistentes o contraindicados y completa cada área a trabajar con
    al menos 3 variantes indicadas para el paciente."""
    from plan_cuadernillo import armar_plan
    secciones = bank.get("sections", [])
    validos = {e.get("id"): e for s in secciones for e in s.get("exercises", [])}
    propuestos = [e for e in (rec.get("ejercicios_recomendados") or [])
                  if isinstance(e, dict)]
    alertas = list(rec.get("alertas_seguridad") or [])
    invalidos = [e.get("id") for e in propuestos if e.get("id") not in validos]
    if invalidos:
        alertas.append("Se descartaron ejercicios que no existen en el banco: "
                       + ", ".join(str(i) for i in invalidos) + ".")
    propuestos = [e for e in propuestos if e.get("id") in validos]
    plan = armar_plan([e["id"] for e in propuestos], dict(clinica, recomendacion=rec),
                      secciones=secciones)
    contra = {a["id"]: a["motivo"] for a in plan["alertas"]}
    for eid, motivo in contra.items():
        alertas.append(f"EXCLUIDO POR SEGURIDAD: {validos[eid].get('name', eid)} — {motivo}.")
    previos = {e["id"]: e for e in propuestos}
    items = {it["id"]: (a, it) for a in plan["areas"] for it in a["ejercicios"]}
    finales = []
    for eid in plan["ejercicios_ids"]:
        if eid in contra:
            continue
        if eid in previos:
            finales.append(previos[eid])
            continue
        area, it = items[eid]
        ex = validos[eid]
        finales.append({
            "id": eid, "name": ex.get("name", eid),
            "justificacion": it["motivo"],
            "dosificacion": f"{ex.get('duration_min', 5)} min por día",
            "prioridad": "Alta" if area["prioritaria"] else "Media",
        })
    rec["ejercicios_recomendados"] = finales
    rec["alertas_seguridad"] = alertas
    rec["plan_areas"] = plan["areas"]
    rec["perfil_clinico"] = plan["perfil"]
    return rec


def generar_recomendacion_terapeutica(
    paciente: dict, anamnesis: dict, riesgo_vocal: dict, escalas: dict,
    acustica: dict, extras: dict = None) -> dict:
    """Recomendación terapéutica completada por áreas (ver
    _completar_con_plan). Si el planificador falla, se devuelve la base."""
    rec = _recomendacion_base(paciente, anamnesis, riesgo_vocal, escalas,
                              acustica, extras)
    try:
        clinica = {"paciente": paciente, "anamnesis": anamnesis,
                   "riesgoVocal": riesgo_vocal, "escalas": escalas,
                   "acustica": acustica}
        return _completar_con_plan(rec, clinica, _load_bank())
    except Exception:
        traceback.print_exc()
        return rec


def _recomendacion_base(
    paciente: dict,
    anamnesis: dict,
    riesgo_vocal: dict,
    escalas: dict,
    acustica: dict,
    extras: dict = None
) -> dict:
    """
    Sintetiza la clínica completa del paciente y genera un plan terapéutico
    personalizado con ejercicios del banco de Farías.
    extras (hidratado server-side): {"informe_orl": {...}, "evolucion": [...],
    "basal": {...}, "actual": {...}}.
    """
    groq_key = os.environ.get("GROQ_API_KEY")
    bank = _load_bank()
    
    # 1. Preparar resumen clínico para el prompt o motor heurístico
    nombre = paciente.get("nombre_completo", "Paciente")
    edad = paciente.get("edad", "N/D")
    sexo = paciente.get("sexo", "N/D")
    ocupacion = paciente.get("ocupacion", "Sin ocupación especificada")
    demanda = paciente.get("demanda_vocal_horas", "N/D")

    # Riesgo Vocal
    # Sin dato = "sin dato" (antes 0 / "Grupo 1": un faltante se leía como bajo riesgo).
    riesgo_total = riesgo_vocal.get("puntaje_total")
    if riesgo_total in (None, ""):
        riesgo_total, riesgo_grupo = "sin dato", "sin ficha de riesgo cargada"
    else:
        try:
            _rt = float(riesgo_total)
            riesgo_grupo = riesgo_vocal.get("grupo") or (
                "Grupo 1 (Bajo Riesgo)" if _rt <= 69 else "Grupo 2 (Riesgo Moderado)" if _rt <= 138 else "Grupo 3 (Alto Riesgo)")
        except (TypeError, ValueError):
            riesgo_grupo = riesgo_vocal.get("grupo") or "sin grupo"
    try:
        riesgo_num = float(riesgo_total)  # solo para reglas de respaldo
    except (TypeError, ValueError):
        riesgo_num = 0.0
    riesgo_alertas = riesgo_vocal.get("alertas_conductas_3", [])
    subtotales = riesgo_vocal.get("subtotales_dimensiones", {})
    # Factores prioritarios: ítems con 2 o 3 → ejes del plan terapéutico
    prioritarios = riesgo_vocal.get("factores_prioritarios", []) or []
    prioritarios_txt = "; ".join(
        f"{p.get('label', '')} ({p.get('puntaje', '')})" for p in prioritarios[:12]
    ) if prioritarios else ""

    # Escalas
    grbas = escalas.get("grbas", {})
    rasati = escalas.get("rasati", {})
    vhi10 = escalas.get("vhi10_score")
    if vhi10 in (None, ""):
        vhi10 = "sin dato"
    tme_s = escalas.get("tme_s")
    tme_o = escalas.get("tme_o")
    indice_so = escalas.get("indice_so")
    if not indice_so and tme_s and tme_o and float(tme_o) > 0:
        indice_so = round(float(tme_s) / float(tme_o), 2)

    # Acústica
    f0 = acustica.get("f0_mean")
    jitter = acustica.get("jitter_local_pct")
    shimmer = acustica.get("shimmer_local_pct")
    hnr = acustica.get("hnr_db")
    cpps = acustica.get("cpps_db")
    avqi = acustica.get("avqi")

    if groq_key:
        try:
            from llm_client import groq_chat

            system_prompt = (
                "Eres el 'Motor de Recomendación Clínica y Terapéutica Vocal' de VocalisLab Pro, "
                "diseñado para Fonoaudiólogos especialistas en voz.\n"
                "Tu marco conceptual y metodológico se rige estrictamente por:\n"
                "1. Farías, Patricia (2012). 'Ejercicios que restauran la función vocal'.\n"
                "2. Farías, Patricia (2016). 'Guía clínica para el especialista en laringe y voz'.\n"
                "3. Cuadernillo Terapéutico Vocal.\n"
                "4. Técnicas miofasciales, Le Huche y Semioclusión del Tracto Vocal (SOVTE).\n\n"
                "Debes devolver EXCLUSIVAMENTE un objeto JSON válido con las siguientes claves obligatorias:\n"
                "{\n"
                '  "sintesis_fisiopatologica": "Análisis exhaustivo integrando riesgo vocal, patrón perceptual y acústica.",\n'
                '  "diagnostico_funcional_fonoaudiologico": "Definición del cuadro funcional vocal (ej. Disfonía músculo tensional grado II, Incompetencia glótica compensatoria, etc.)",\n'
                '  "objetivos_terapeuticos": ["Obj 1", "Obj 2", "Obj 3"],\n'
                '  "ejercicios_recomendados": [\n'
                '    {\n'
                '      "id": "un ID EXACTO del banco (ver lista por área abajo)",\n'
                '      "name": "Nombre exacto del ejercicio",\n'
                '      "justificacion": "Por qué es prioritario según su fisiopatología",\n'
                '      "dosificacion": "Series, repeticiones y tiempo recomendado",\n'
                '      "prioridad": "Alta | Media | Mantenimiento"\n'
                '    }\n'
                '  ],\n'
                '  "pautas_higiene_prioritarias": ["Pauta 1 dirigida a las conductas con puntaje 3", "Pauta 2"],\n'
                '  "plan_sesiones": {\n'
                '    "frecuencia": "ej. 2 veces por semana",\n'
                '    "duracion_min": 30,\n'
                '    "total_sesiones_sugeridas": 10,\n'
                '    "etapas": "Fase 1: ... Fase 2: ... Fase 3: ..."\n'
                '  }\n'
                "}\n\n"
                "REGLAS DE SELECCIÓN:\n"
                "- Usá solo IDs de esta lista (área: ids):\n" + _ids_por_area(bank) + "\n"
                "- Elegí al menos 3 ejercicios por cada área que el caso necesite trabajar "
                "(variantes del mismo objetivo, de lo básico a lo avanzado), justificando cada uno "
                "con datos del paciente.\n"
                "- Nunca elijas un ejercicio contraindicado para el diagnóstico.\n"
            )

            _extras = extras or {}
            _orl = _extras.get("informe_orl") or {}
            _orl_txt = ""
            if _orl:
                _orl_txt = (
                    f"\n- Informe ORL validado (DB): {(_orl.get('diagnostico') or 's/diagnóstico')} "
                    f"[{(_orl.get('metodo') or 's/método')}]. "
                    f"Hallazgos: {str(_orl.get('estructurales') or '')[:300]} / {str(_orl.get('funcionales') or '')[:300]} "
                    f"Texto: {str(_orl.get('texto') or '')[:500]}"
                )
            _evo_txt = ""
            _basal, _actual = _extras.get("basal"), _extras.get("actual")
            if _basal and _actual:
                def _n(v):
                    try:
                        return v if v is None else round(float(v), 1)
                    except Exception:
                        return v
                _evo_txt = (
                    f"\n- Evolución basal→actual ({len(_extras.get('evolucion', []))} evaluaciones): "
                    f"autopercepción {_n(_basal.get('autopercepcion_vocal'))}→{_n(_actual.get('autopercepcion_vocal'))}/10, "
                    f"VHI-10 {_n(_basal.get('vhi10_score'))}→{_n(_actual.get('vhi10_score'))}/40, "
                    f"riesgo {_n(_basal.get('riesgo_vocal_score'))}→{_n(_actual.get('riesgo_vocal_score'))}/207, "
                    f"TME-O {_n(_basal.get('tme_o'))}→{_n(_actual.get('tme_o'))}s."
                )

            # Lectura por los mismos criterios fijos que la ficha integral,
            # para que el plan no reinterprete números (ni invierta escalas).
            try:
                from criterios_clinicos import hallazgos as _hallazgos
                _ev = dict(escalas or {})
                _ev["riesgo_vocal_score"] = riesgo_vocal.get("puntaje_total")
                _ev.setdefault("autopercepcion_vocal", anamnesis.get("autopercepcion_voz"))
                _lect = _hallazgos({"paciente": paciente or {}, "anamnesis": anamnesis or {},
                                    "evaluaciones": [_ev], "analisis_acusticos": [acustica] if acustica else []})
                _lect_txt = "\n".join(f"  * {h['parametro']}: {h['lectura']} [{h['nivel']}]" for h in _lect["hallazgos"])
                _lect_txt += "".join(f"\n  * Patrón: {x['patron']} ({'; '.join(x['evidencia'])})" for x in _lect["patrones"])
                from criterios_clinicos import situacion_quirurgica, ETAPAS
                _orl_x = (_extras.get("informe_orl") or {}) if isinstance(_extras, dict) else {}
                _sq = situacion_quirurgica({"anamnesis": anamnesis or {}, "informes_orl": [{
                    "diagnostico_principal": _orl_x.get("diagnostico"), "texto_corregido": _orl_x.get("texto"),
                    "datos_estructurados": {"hallazgos_estructurales": _orl_x.get("estructurales"),
                                            "hallazgos_funcionales": _orl_x.get("funcionales")}}] if _orl_x else []})
                _lect_txt += f"\n  * Situación quirúrgica: {_sq['etiqueta']}" + (
                    f" (registro: {_sq['evidencia'][0]['texto']})" if _sq["evidencia"] else "")
                if _sq["etapa"] == "postquirurgica":
                    _lect_txt += ("\n  * POSTQUIRÚRGICO: respetar el reposo indicado por el cirujano; reintroducción gradual, "
                                  "solo ejercicios de mínimo impacto al inicio (SOVT suaves, flujo), sin empuje.")
                elif _sq["etapa"] == "prequirurgica":
                    _lect_txt += "\n  * PREQUIRÚRGICO: terapia prequirúrgica (higiene, eliminar abuso, coordinación, SOVT) y línea de base."
            except Exception as _e:
                print(f"[recomendar_motor] lectura clínica no disponible: {_e}")
                _lect_txt = "  (no disponible)"

            user_content = f"""
ESCALAS Y DIRECCIÓN (no invertir): Autopercepción 0–10 (0 = muy mala, 10 = excelente).
VHI-10 0–40 (más alto = más impacto; > 11 alterado). GRBAS y RASATI 0–3 por parámetro (0 normal, 3 severo).
Riesgo vocal /207 (más alto = más riesgo). Usá los números exactamente como figuran.

LECTURA CLÍNICA POR CRITERIOS FIJOS (respetala; no la contradigas):
{_lect_txt}

DATOS DEL CASO CLÍNICO:
- Paciente: {nombre} ({edad} años, {sexo}), Ocupación: {ocupacion}, Demanda vocal: {demanda} h/día.
- Anamnesis: Motivo: {anamnesis.get('motivo_consulta', 'N/D')}. Diagnóstico ORL: {anamnesis.get('diagnostico_orl', 'Sin informe laringoscópico previo')}.
  Síntomas: {json.dumps(anamnesis.get('sintomas', {}), ensure_ascii=False)}
  Autopercepción voz: {anamnesis.get('autopercepcion_voz', 'N/D')}/10. Antecedentes: {(anamnesis.get('antecedentes_salud') or 'N/D')[:300]}.{_orl_txt}{_evo_txt}
- Evaluación de riesgo vocal:
  * Puntaje Total: {riesgo_total}/207 -> {riesgo_grupo}
  * Subtotales: {json.dumps(subtotales, ensure_ascii=False)}
  * Conductas críticas puntuadas con 3 (Mucho/Siempre): {', '.join(riesgo_alertas) if riesgo_alertas else 'Ninguna puntual'}
  * Factores prioritarios a trabajar en el plan (puntaje 2 o 3): {prioritarios_txt if prioritarios_txt else 'Ninguno'}
- Evaluación Perceptual y Dinámica:
  * GRBAS: {json.dumps(grbas)}
  * RASATI: {json.dumps(rasati)}
  * VHI-10: {vhi10}/40
  * TMF vocal sostenida: {tme_o} s | TME /s/: {tme_s} s | Cociente /s/ ÷ vocal: {indice_so}
- Biometría Acústica Praat:
  * F0 media: {f0} Hz | Jitter local: {jitter}% | Shimmer: {shimmer}%
  * HNR: {hnr} dB | CPPS: {cpps} dB | AVQI: {avqi}

Genera la recomendación terapéutica precisa.
"""
            # Los modelos que razonan gastan parte del límite pensando: con
            # 2200 el JSON llegaba cortado y se caía al motor de reglas.
            from externo_ocr import _extract_json
            raw = ""
            try:
                raw, _model = groq_chat(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=0.25,
                    max_tokens=8000,
                    response_format={"type": "json_object"},
                    timeout=90.0,
                )
                rec = _extract_json(raw)
                if isinstance(rec, dict) and rec.get("ejercicios_recomendados") is not None:
                    return rec
            except Exception as e:
                print(f"[recomendar_motor] Groq sin JSON completo ({str(e)[:120]}); pruebo Gemini")
            from llm_client import gemini_generate, gemini_texto
            resp, _model = gemini_generate(
                [{"text": system_prompt + "\n\n" + user_content}],
                {"temperature": 0.25, "maxOutputTokens": 16000, "responseMimeType": "application/json"},
                timeout=150)
            return _extract_json(gemini_texto(resp))
        except Exception as e:
            traceback.print_exc()

    # 2. Motor Heurístico de Respaldo Clínico (Reglas de Farías 2012 / 2016)
    g_score = grbas.get("G", 0)
    tension_score = max(grbas.get("S", 0), rasati.get("T", 0))
    soplo_score = max(grbas.get("B", 0), rasati.get("S", 0))
    
    selected_exs = []
    
    # Si hay hiperfunción o tensión elevada
    if tension_score >= 2 or (jitter and float(jitter) > 1.2) or riesgo_num > 60:
        selected_exs.append({
            "id": "le_huche",
            "name": "Técnica de Le Huche",
            "justificacion": "Desactivar tensión cordal y patrón constrictor supraglótico mediante respiración en apnea.",
            "dosificacion": "10 repeticiones diarias antes de iniciar actividades vocales.",
            "prioridad": "Alta"
        })
        selected_exs.append({
            "id": "masaje_laringeo",
            "name": "Masaje Laríngeo Lateral",
            "justificacion": "Descenso pasivo de la laringe e inhibición de la musculatura perilaríngea hiperactiva.",
            "dosificacion": "3 minutos en región tirohioidea con movimientos circulares.",
            "prioridad": "Alta"
        })
        selected_exs.append({
            "id": "descenso_laringeo",
            "name": "Descenso Laringeo Activo",
            "justificacion": "Favorecer la báscula laríngea baja para aumentar el tracto vocal y relajar el tiroaritenoideo.",
            "dosificacion": "5 ciclos de bostezo y emisión /u/ grave.",
            "prioridad": "Media"
        })
    
    # Si hay soplo / incompetencia o astenia
    if soplo_score >= 1 or (hnr and float(hnr) < 18.0) or (indice_so and float(indice_so) < 0.8):
        selected_exs.append({
            "id": "oclusion_nasal",
            "name": "Oclusión Nasal /m/ a Vocales",
            "justificacion": "Mejorar la impedancia acústica y el contacto glótico sin impacto traumático (Semioclusión).",
            "dosificacion": "3 series de 5 emisiones prolongadas de /m/ proyectadas a vocal.",
            "prioridad": "Alta"
        })
        selected_exs.append({
            "id": "coordinacion_costo_abdominal",
            "name": "Coordinación Costo-Abdominal",
            "justificacion": "Restablecer el apoyo aéreo subglótico constante para evitar caídas de presión fonatoria.",
            "dosificacion": "5 minutos diarios con emisión sostenida de /s/ y /z/.",
            "prioridad": "Media"
        })

    # Trabajo de rango y flexibilidad
    selected_exs.append({
        "id": "glissandos",
        "name": "Glissandos Ascendentes y Descendentes",
        "justificacion": "Favorecer la elongación simétrica del cricotiroideo y evitar rigidez cordal.",
        "dosificacion": "10 glissandos suaves en rango cómodo sin quebrar el timbre.",
        "prioridad": "Media"
    })
    
    # Rutinas protectoras
    selected_exs.append({
        "id": "calentamiento",
        "name": "Calentamiento Vocal (Pre-Exigencia)",
        "justificacion": "Acondicionamiento reológico y muscular de la mucosa cordal previo al uso laboral.",
        "dosificacion": "5 minutos previo a la jornada de demanda vocal.",
        "prioridad": "Alta"
    })
    selected_exs.append({
        "id": "enfriamiento",
        "name": "Enfriamiento Vocal (Post-Exigencia)",
        "justificacion": "Recuperación de la longitud de reposo del ligamento vocal y drenaje de ácido láctico.",
        "dosificacion": "5 minutos al finalizar la jornada.",
        "prioridad": "Alta"
    })

    pautas = [
        "Hidratación target: ingerir entre 2 y 2.5 litros de agua a temperatura ambiente al día.",
        "Evitar carraspeo o tos fuerte; sustituir por deglución consciente o sorbos de agua.",
        "Monitorear intensidad vocal en ambientes ruidosos evitando competir con ruido de fondo."
    ]
    if riesgo_alertas:
        pautas.insert(0, f"Control prioritario de las conductas de riesgo de grado 3: {', '.join(riesgo_alertas[:3])}.")
    if prioritarios_txt:
        pautas.insert(0, f"Factores prioritarios del plan (puntaje 2-3): {prioritarios_txt}.")

    # Reglas de seguridad del manual (Farías): exofíticas + S/O
    alertas_seguridad = []
    texto_diag = f"{anamnesis.get('diagnostico_orl', '')} {anamnesis.get('motivo_consulta', '')}".lower()
    import re as _re
    hay_exofitica = bool(_re.search(
        r"n[oó]dulo|p[oó]lipo|quiste|edema(\s+de\s+reinke)?|lesi[oó]n (de masa|exof)",
        texto_diag))
    if hay_exofitica:
        antes = len(selected_exs)
        selected_exs = [e for e in selected_exs if e.get("id") != "empuje_glotico"]
        if len(selected_exs) < antes:
            alertas_seguridad.append(
                "EXCLUIDO POR SEGURIDAD: empuje glótico contraindicado con lesión "
                "exofítica (nódulos/pólipos/quiste/edema): riesgo de trauma mecánico cordal.")
    try:
        so_val = float(indice_so) if indice_so else 0
    except Exception:
        so_val = 0
    if so_val > 1.2 and not hay_exofitica:
        if not any(e.get("id") == "empuje_glotico" for e in selected_exs):
            selected_exs.insert(0, {
                "id": "empuje_glotico",
                "name": "Técnica de Empuje (Pushing)",
                "justificacion": "Incompetencia glótica (S/O > 1.2): aducción refleja por esfuerzo para vencer el hiato aéreo.",
                "dosificacion": "3 series de 10 emisiones ¡KIP!/¡TEP! en días alternos.",
                "prioridad": "Alta"
            })
        alertas_seguridad.append(
            "Incompetencia glótica (índice S/O > 1.2): se prioriza aducción (empuje) + SOVTE de alta carga.")

    total_ses = 12 if riesgo_num > 90 else (10 if riesgo_num > 60 else 8)

    return {
        "alertas_seguridad": alertas_seguridad,
        "sintesis_fisiopatologica": f"Paciente {sexo} de {edad} años con demanda vocal de {demanda} h/día y puntaje de riesgo vocal de {riesgo_total} ({riesgo_grupo}). Se observa compromiso biomecánico con grado de disfonía G{g_score} y tensión asociada T{tension_score}, correlacionado con perturbación acústica.",
        "diagnostico_funcional_fonoaudiologico": "Sobreesfuerzo Vocal e Hiperfunción Laríngea con Patrón Hipercinético" if tension_score >= 2 else "Incompetencia Glótica Funcional con Desbalance Resonancial",
        "objetivos_terapeuticos": [
            "Desactivar constricción supraglótica e hipertonía cervical.",
            "Optimizar el soporte aerodinámico costo-diafragmático.",
            "Establecer la técnica de semioclusión para fonación económica y resonante."
        ],
        "ejercicios_recomendados": selected_exs,
        "pautas_higiene_prioritarias": pautas,
        "plan_sesiones": {
            "frecuencia": "2 veces por semana",
            "duracion_min": 30,
            "total_sesiones_sugeridas": total_ses,
            "etapas": "Fase 1: Trabajo corporal, respiratorio y desfonación tensa. Fase 2: Flexibilización glótica con SOVTE y resonancia. Fase 3: Transferencia a voz proyectada e integración laboral."
        }
    }

