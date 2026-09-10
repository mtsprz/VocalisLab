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
    try:
        with open(EXERCISE_BANK_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"sections": [], "presets": []}


def generar_recomendacion_terapeutica(
    paciente: dict,
    anamnesis: dict,
    riesgo_vocal: dict,
    escalas: dict,
    acustica: dict
) -> dict:
    """
    Sintetiza la clínica completa del paciente y genera un plan terapéutico
    personalizado con ejercicios del banco de Farías.
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
    riesgo_total = riesgo_vocal.get("puntaje_total", 0)
    riesgo_grupo = riesgo_vocal.get("grupo", "Grupo 1")
    riesgo_alertas = riesgo_vocal.get("alertas_conductas_3", [])
    subtotales = riesgo_vocal.get("subtotales_dimensiones", {})

    # Escalas
    grbas = escalas.get("grbas", {})
    rasati = escalas.get("rasati", {})
    vhi10 = escalas.get("vhi10_score", 0)
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
                '      "id": "uno de los IDs del banco: le_huche | shiatsu_cabeza | rotacion_hombros | masaje_laringeo | descenso_laringeo | moldeado_vocalico | respiracion_abdominal | expansion_costo_lateral | coordinacion_costo_abdominal | series_automaticas | glissandos | oclusion_nasal | escalas_vocalicas | frases_balanceadas | calentamiento | enfriamiento",\n'
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
                "}\n"
            )

            user_content = f"""
DATOS DEL CASO CLÍNICO:
- Paciente: {nombre} ({edad} años, {sexo}), Ocupación: {ocupacion}, Demanda vocal: {demanda} h/día.
- Anamnesis: Motivo: {anamnesis.get('motivo_consulta', 'N/D')}. Diagnóstico ORL: {anamnesis.get('diagnostico_orl', 'Sin informe laringoscópico previo')}.
  Síntomas: {json.dumps(anamnesis.get('sintomas', {}), ensure_ascii=False)}
- Evaluación de riesgo vocal:
  * Puntaje Total: {riesgo_total}/207 -> {riesgo_grupo}
  * Subtotales: {json.dumps(subtotales, ensure_ascii=False)}
  * Conductas críticas puntuadas con 3 (Mucho/Siempre): {', '.join(riesgo_alertas) if riesgo_alertas else 'Ninguna puntual'}
- Evaluación Perceptual y Dinámica:
  * GRBAS: {json.dumps(grbas)}
  * RASATI: {json.dumps(rasati)}
  * VHI-10: {vhi10}/40
  * TME sostenido: {tme_o} s | TME suave: {tme_s} s | Índice S/O: {indice_so}
- Biometría Acústica Praat:
  * F0 media: {f0} Hz | Jitter local: {jitter}% | Shimmer: {shimmer}%
  * HNR: {hnr} dB | CPPS: {cpps} dB | AVQI: {avqi}

Genera la recomendación terapéutica precisa.
"""
            raw, _model = groq_chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.25,
                max_tokens=2200,
                response_format={"type": "json_object"}
            )
            raw = raw.strip()
            return json.loads(raw)
        except Exception as e:
            traceback.print_exc()

    # 2. Motor Heurístico de Respaldo Clínico (Reglas de Farías 2012 / 2016)
    g_score = grbas.get("G", 0)
    tension_score = max(grbas.get("S", 0), rasati.get("T", 0))
    soplo_score = max(grbas.get("B", 0), rasati.get("S", 0))
    
    selected_exs = []
    
    # Si hay hiperfunción o tensión elevada
    if tension_score >= 2 or (jitter and float(jitter) > 1.2) or riesgo_total > 60:
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

    total_ses = 12 if riesgo_total > 90 else (10 if riesgo_total > 60 else 8)

    return {
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

