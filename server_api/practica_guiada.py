"""Práctica guiada en casa (enlace por WhatsApp) y en vivo.

El profesional arma una rutina con ejercicios del cuadernillo que tienen
guía visual (sostenida, escalera, rampa/glissando o patrón propio). El
paciente abre https://vocalis-lab.vercel.app/?practica=<token>, da su
consentimiento y practica: una pelota sigue su voz. El tono se calcula en
su celular; a la app solo llegan NÚMEROS (porcentaje dentro del camino, F0,
estabilidad, ruido del ambiente). Nunca audio.

Rutas:
- GET  /api/practicas/sugerencias?paciente_id=  (sesión) ejercicios guiables + tono base
- POST /api/practicas                           (sesión) crea la rutina y el enlace
- GET  /api/practicas?paciente_id=              (sesión) rutinas y resultados
- PATCH /api/practicas/{id}                     (sesión) activar / desactivar
- GET  /api/practica/{token}                    (público) rutina para el paciente
- POST /api/practica/{token}/consentimiento     (público)
- POST /api/practica/{token}/sesion             (público) resultados (solo números)
"""
import json
import math
from fechas import dia_ar
import re
import os
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Request

router = APIRouter()

MSG_MIGRACION = ("Falta correr la migración supabase/migracion_2026_11_practica.sql en "
                 "Supabase (SQL Editor).")
GUIAS = ("sostenida", "escalera", "rampa", "patron")
VERSION_CONSENTIMIENTO = "2026-11"

# Ejercicios del cuadernillo (exercise_bank.json) que se pueden guiar con la pelota.
# Qué se mide en cada ejercicio del cuadernillo con guía (medida):
#   tono       altura objetivo (camino de notas): sirenas, escalas, trinos.
#   sostenido  duración y estabilidad (de intensidad; de altura si con_tono).
#   flujo      sonido con ruido sin altura medible (tubo en agua, LaxVox,
#              fricativas, /sh/): continuidad, cortes e intensidad pareja.
#   intensidad dinámica respecto de su nivel cómodo (pareja o arco messa di voce).
#   pulsos     impulsos/ataques rítmicos (método del acento, /ch-ch/, hu-hu-hu).
#   libre      búsqueda o habla sin objetivo tonal: se registra F0 e intensidad.
# modelo: "sonoro" = ejemplo audible antes de cada repetición; "sin_modelo" =
# no se da ejemplo para no condicionar la búsqueda.
GUIA_POR_EJERCICIO = {
    "glissandos": {"medida": "tono", "guia": "rampa", "amplitud": 7, "modelo": "sonoro",
                   "consigna": "Sirena suave sobre /u/ o /m/: subí y bajá siguiendo la rampa."},
    # OJO: algunos ids del banco son históricos y no coinciden con su ficha
    # (tubo_agua = glissandos sobre /m/ o /u/; popote_aire = escalas de 3.ª-5.ª-8.ª;
    # vibracion_labial = /m/ a vocales; humming_m = lectura). La guía sigue a la ficha.
    "tubo_agua": {"medida": "tono", "guia": "rampa", "amplitud": 7, "modelo": "sonoro",
                  "consigna": "Sirena suave sobre /m/ o /u/: subí y bajá siguiendo la rampa, sin quiebres."},
    "popote_aire": {"medida": "tono", "guia": "escalera", "semitonos": [0, 4, 7, 4, 0], "modelo": "sonoro",
                    "consigna": "Escala de 3.ª y 5.ª sobre /a/ o /m+a/: subí y bajá por los escalones, cómodo."},
    "vibracion_labial": {"medida": "sostenido", "guia": "sostenida", "duracion_objetivo_s": 6, "modelo": "sin_modelo",
                         "con_tono": False, "consigna": "/m/ sostenida y abrí a vocal (mmm-u, mmm-i…) con la misma calidad."},
    "humming_m": {"medida": "libre", "guia": "sostenida", "duracion_objetivo_s": 30, "modelo": "sin_modelo",
                  "consigna": "Leé en voz alta tus oraciones, claro y cómodo."},
    "trino_labial": {"medida": "tono", "guia": "escalera", "semitonos": [0, 2, 4, 2, 0], "modelo": "sonoro", "tolerancia_cents": 200,
                     "consigna": "Trino de labios /br/ siguiendo los escalones."},
    "trino_lingual": {"medida": "tono", "guia": "escalera", "semitonos": [0, 2, 4, 2, 0], "modelo": "sonoro", "tolerancia_cents": 200,
                      "consigna": "Trino de lengua /rr/ siguiendo los escalones."},
    "finger_kazoo": {"medida": "tono", "guia": "rampa", "amplitud": 5, "modelo": "sonoro", "tolerancia_cents": 200,
                     "consigna": "Dedo en los labios: sirena suave siguiendo la rampa."},
    "laxvox_agua": {"medida": "flujo", "guia": "sostenida", "duracion_objetivo_s": 8, "modelo": "sin_modelo",
                    "consigna": "Tubo en agua: burbujeo parejo mientras sostenés el sonido."},
    "tubo_aire_libre": {"medida": "flujo", "guia": "sostenida", "duracion_objetivo_s": 8, "modelo": "sin_modelo",
                        "consigna": "Tubo en el aire: sonido continuo y parejo."},
    "fricativas_sonoras": {"medida": "flujo", "guia": "sostenida", "duracion_objetivo_s": 8, "modelo": "sin_modelo",
                           "consigna": "/v/ o /z/ sostenida, sonido parejo."},
    "respiracion_dinamica": {"medida": "flujo", "guia": "sostenida", "duracion_objetivo_s": 6, "modelo": "sin_modelo",
                             "consigna": "/sh/ largo y parejo, sin cortar el aire."},
    "oclusion_nasal": {"medida": "sostenido", "guia": "sostenida", "duracion_objetivo_s": 8, "modelo": "sin_modelo", "con_tono": False,
                       "consigna": "/m/ sostenida en tu tono cómodo, abrí a vocal al final."},
    "vocales_cerradas": {"medida": "sostenido", "guia": "sostenida", "duracion_objetivo_s": 8, "modelo": "sin_modelo", "con_tono": False,
                         "consigna": "/u/ o /i/ sostenida, pareja y sin esfuerzo."},
    "b_prolongada": {"medida": "sostenido", "guia": "sostenida", "duracion_objetivo_s": 5, "modelo": "sin_modelo", "con_tono": False,
                     "consigna": "/b/ prolongada en tono cómodo."},
    "messa_di_voce": {"medida": "intensidad", "guia": "sostenida", "duracion_s": 8, "patron_intensidad": "arco", "margen_db": 4,
                      "modelo": "sonoro", "consigna": "Misma nota: empezá suave, crecé y volvé a suave."},
    "metodo_acento": {"medida": "pulsos", "guia": "sostenida", "pulsos": 6, "tempo_bpm": 80, "modelo": "sonoro",
                      "consigna": "Impulsos rítmicos con apoyo abdominal, siguiendo el pulso."},
    "soplo_fraccionado": {"medida": "pulsos", "guia": "sostenida", "pulsos": 8, "tempo_bpm": 100, "modelo": "sonoro",
                          "consigna": "Chistidos /ch-ch-ch/ cortos y parejos, siguiendo el pulso."},
    "oclusion_succion": {"medida": "pulsos", "guia": "sostenida", "pulsos": 6, "tempo_bpm": 70, "modelo": "sonoro",
                         "consigna": "«Hu hu hu» suaves, en báscula baja, siguiendo el pulso."},
    "frases_balanceadas": {"medida": "libre", "guia": "sostenida", "duracion_objetivo_s": 20, "modelo": "sin_modelo",
                           "consigna": "Leé o decí tus frases en voz conversacional, cómoda."},
    "escalas_vocalicas": {"medida": "libre", "guia": "sostenida", "duracion_objetivo_s": 60, "modelo": "sin_modelo",
                          "consigna": "Contá algo de tu día en voz conversacional, aplicando lo trabajado."},
    "consonantes_fricativas": {"medida": "libre", "guia": "sostenida", "duracion_objetivo_s": 20, "modelo": "sin_modelo",
                               "consigna": "Voz salmodiada con versos o refranes, cómoda."},
}

# Guías con tiempo para los ejercicios sin medición de voz (redacción propia).
GUIA_POR_EJERCICIO.setdefault('le_huche', {"medida": "pasos", "guia": "sostenida", "modelo": "sin_modelo", "repeticiones_sugeridas": 5, "consigna": 'Disociá: respirá suave y contraé solo la zona indicada; después soltá.', "pasos": [{'tipo': 'inhala', 'segundos': 4, 'texto': 'Inspirá suave por la boca, como diciendo «f»'}, {'tipo': 'accion', 'segundos': 3, 'texto': 'Sin respirar, apretá solo hombros y brazos'}, {'tipo': 'exhala', 'segundos': 6, 'texto': 'Soltá todo y sacá el aire con «sh» suave'}, {'tipo': 'descanso', 'segundos': 3, 'texto': 'Quedate flojo'}]})
GUIA_POR_EJERCICIO.setdefault('shiatsu_cabeza', {"medida": "pasos", "guia": "sostenida", "modelo": "sin_modelo", "repeticiones_sugeridas": 1, "consigna": 'Presión suave y pequeños círculos con los dedos mayor e índice. Nunca debe doler.', "pasos": [{'tipo': 'accion', 'segundos': 15, 'texto': 'Coronilla (vértex)'}, {'tipo': 'accion', 'segundos': 15, 'texto': 'Sienes'}, {'tipo': 'accion', 'segundos': 15, 'texto': 'Entrecejo'}, {'tipo': 'accion', 'segundos': 15, 'texto': 'Articulación de la mandíbula (delante de la oreja)'}, {'tipo': 'accion', 'segundos': 15, 'texto': 'Maseteros (mejillas, al apretar los dientes)'}, {'tipo': 'accion', 'segundos': 15, 'texto': 'Alrededor de los labios'}, {'tipo': 'accion', 'segundos': 20, 'texto': 'Cuello, a los costados'}, {'tipo': 'descanso', 'segundos': 5, 'texto': 'Soltá la mandíbula'}]})
GUIA_POR_EJERCICIO.setdefault('rotacion_hombros', {"medida": "pasos", "guia": "sostenida", "modelo": "sin_modelo", "repeticiones_sugeridas": 1, "consigna": 'Sentado derecho sobre los isquiones. Movimientos lentos, sin dolor.', "pasos": [{'tipo': 'accion', 'segundos': 15, 'texto': 'Rotá los dos hombros hacia atrás'}, {'tipo': 'accion', 'segundos': 15, 'texto': 'Ahora alternados, uno y otro'}, {'tipo': 'accion', 'segundos': 15, 'texto': 'Rotá la cabeza lentamente por delante'}, {'tipo': 'accion', 'segundos': 15, 'texto': 'Llevá el mentón hacia cada hombro'}, {'tipo': 'accion', 'segundos': 15, 'texto': 'Llevá la oreja hacia cada hombro'}, {'tipo': 'descanso', 'segundos': 5, 'texto': 'Volvé al centro y respirá'}]})
GUIA_POR_EJERCICIO.setdefault('masaje_laringeo', {"medida": "pasos", "guia": "sostenida", "modelo": "sin_modelo", "repeticiones_sugeridas": 3, "consigna": 'Masaje suave de los costados de la laringe, de arriba hacia abajo. Sin presionar fuerte.', "pasos": [{'tipo': 'accion', 'segundos': 20, 'texto': 'Masajeá los costados de la laringe hacia abajo'}, {'tipo': 'descanso', 'segundos': 5, 'texto': 'Tragá suave y soltá'}]})
GUIA_POR_EJERCICIO.setdefault('descenso_laringeo', {"medida": "pasos", "guia": "sostenida", "modelo": "sin_modelo", "repeticiones_sugeridas": 8, "consigna": 'Dedo apoyado suave sobre la nuez para sentir que baja. Sin forzar.', "pasos": [{'tipo': 'inhala', 'segundos': 4, 'texto': 'Bostezá lento por la boca (o succioná como con un sorbete)'}, {'tipo': 'accion', 'segundos': 5, 'texto': 'Mantené la laringe baja, sin tensión'}, {'tipo': 'descanso', 'segundos': 4, 'texto': 'Soltá despacio, sin movimientos bruscos'}]})
GUIA_POR_EJERCICIO.setdefault('apertura_fondo_boca', {"medida": "pasos", "guia": "sostenida", "modelo": "sin_modelo", "repeticiones_sugeridas": 10, "consigna": 'Frente al espejo, sentado derecho.', "pasos": [{'tipo': 'accion', 'segundos': 5, 'texto': 'Abrí la boca al máximo cómodo: lengua plana, paladar blando arriba'}, {'tipo': 'descanso', 'segundos': 3, 'texto': 'Cerrá suave, sin apretar'}]})
GUIA_POR_EJERCICIO.setdefault('moldeado_vertical', {"medida": "pasos", "guia": "sostenida", "modelo": "sin_modelo", "repeticiones_sugeridas": 3, "consigna": 'Boca bien abierta y mandíbula suelta; encadená las vocales despacio.', "pasos": [{'tipo': 'sonido', 'segundos': 12, 'texto': 'O – A – O – E – A, lento y cómodo'}, {'tipo': 'sonido', 'segundos': 6, 'texto': 'Decí «¿Hola, cómo estás?» con la misma apertura'}, {'tipo': 'descanso', 'segundos': 4, 'texto': 'Respirá'}]})
GUIA_POR_EJERCICIO.setdefault('respiracion_abdominal', {"medida": "pasos", "guia": "sostenida", "modelo": "sin_modelo", "repeticiones_sugeridas": 10, "consigna": 'Sentado cómodo; podés apoyar las manos en la panza.', "pasos": [{'tipo': 'inhala', 'segundos': 4, 'texto': 'Inspirá por la nariz llevando el aire a la panza'}, {'tipo': 'exhala', 'segundos': 6, 'texto': 'Sacalo por la boca con una «s» suave y pareja'}, {'tipo': 'descanso', 'segundos': 2, 'texto': 'Pausa'}]})
GUIA_POR_EJERCICIO.setdefault('expansion_costo_lateral', {"medida": "pasos", "guia": "sostenida", "modelo": "sin_modelo", "repeticiones_sugeridas": 5, "consigna": 'De pie, manos en las costillas de abajo. Sin subir hombros ni pecho; garganta suelta.', "pasos": [{'tipo': 'inhala', 'segundos': 4, 'texto': 'Inspirá por la nariz abriendo las costillas hacia los costados'}, {'tipo': 'retiene', 'segundos': 5, 'texto': 'Sostené las costillas abiertas, sin cerrar la garganta'}, {'tipo': 'exhala', 'segundos': 6, 'texto': 'Soltá el aire despacio'}, {'tipo': 'descanso', 'segundos': 3, 'texto': 'Pausa'}]})
GUIA_POR_EJERCICIO.setdefault('soplo_escalonado', {"medida": "pasos", "guia": "sostenida", "modelo": "sin_modelo", "repeticiones_sugeridas": 5, "consigna": 'Una mano en la panza y otra en la espalda baja: el aire se expande en todas las direcciones.', "pasos": [{'tipo': 'inhala', 'segundos': 5, 'texto': 'Inspirá por la nariz: panza, costillas y espalda'}, {'tipo': 'retiene', 'segundos': 2, 'texto': 'Sostené sin tensión'}, {'tipo': 'exhala', 'segundos': 8, 'texto': 'Soltá despacio y parejo'}, {'tipo': 'descanso', 'segundos': 3, 'texto': 'Pausa'}]})
GUIA_POR_EJERCICIO.setdefault('calentamiento', {"medida": "pasos", "guia": "sostenida", "modelo": "sin_modelo", "repeticiones_sugeridas": 1, "consigna": 'Antes de usar la voz. Volumen cómodo, sin esfuerzo.', "pasos": [{'tipo': 'sonido', 'segundos': 15, 'texto': 'Bostezo con un suspiro sonoro de agudo a grave'}, {'tipo': 'sonido', 'segundos': 20, 'texto': 'Trino de labios «brrr» suave'}, {'tipo': 'sonido', 'segundos': 20, 'texto': 'Sirena en «u», subiendo y bajando'}, {'tipo': 'sonido', 'segundos': 20, 'texto': '«Mmm» cómodo que se abre a vocales'}, {'tipo': 'descanso', 'segundos': 5, 'texto': 'Listo para usar la voz'}]})
GUIA_POR_EJERCICIO.setdefault('enfriamiento', {"medida": "pasos", "guia": "sostenida", "modelo": "sin_modelo", "repeticiones_sugeridas": 1, "consigna": 'Después de usar mucho la voz. Todo suave.', "pasos": [{'tipo': 'sonido', 'segundos': 15, 'texto': 'Suspiros sonoros de agudo a grave'}, {'tipo': 'sonido', 'segundos': 20, 'texto': '«Mmm» grave y suave'}, {'tipo': 'accion', 'segundos': 20, 'texto': 'Masaje suave de cuello y hombros'}, {'tipo': 'descanso', 'segundos': 30, 'texto': 'Silencio y respiración tranquila'}]})
GUIA_POR_EJERCICIO.setdefault('mano_boca', {"medida": "pasos", "guia": "sostenida", "modelo": "sin_modelo", "repeticiones_sugeridas": 5, "consigna": 'Mano tapando la boca, dejando un pequeño escape de aire entre los dedos.', "pasos": [{'tipo': 'inhala', 'segundos': 3, 'texto': 'Tomá aire'}, {'tipo': 'sonido', 'segundos': 8, 'texto': 'Sonido cómodo contra la mano, sintiendo la vibración'}, {'tipo': 'descanso', 'segundos': 3, 'texto': 'Soltá'}]})
GUIA_POR_EJERCICIO.setdefault('b_prolongada', {"medida": "pasos", "guia": "sostenida", "modelo": "sin_modelo", "repeticiones_sugeridas": 6, "consigna": 'Labios cerrados y mejillas que se inflan un poco; laringe cómoda.', "pasos": [{'tipo': 'inhala', 'segundos': 3, 'texto': 'Tomá aire'}, {'tipo': 'sonido', 'segundos': 5, 'texto': '«Bbbb» prolongada en tono cómodo'}, {'tipo': 'descanso', 'segundos': 3, 'texto': 'Soltá'}]})

MEDIDAS = ("tono", "sostenido", "flujo", "intensidad", "pulsos", "libre", "pasos")
MAX_EJERCICIOS = 25  # alcanza para un cuadernillo completo (Fonoar: 23)
# pasos: ejercicio sin medición de voz (cuerpo, masajes, respiración, descenso laríngeo):
# una secuencia de pasos con cuenta regresiva; se registra que se hizo y cuánto duró.
TIPOS_PASO = ("inhala", "retiene", "exhala", "sonido", "accion", "descanso")
TONO_BASE_DEFECTO = {"varon": 110.0, "mujer": 196.0, "otro": 150.0}


def _sb():
    from api_clinica import supabase
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    return supabase


def _ahora():
    return datetime.now(timezone.utc)


def _err_tabla(e):
    if "practica" in str(e):
        raise HTTPException(status_code=503, detail=MSG_MIGRACION)
    raise e


def _sexo(p):
    s = str(p.get("sexo") or "").strip().lower()
    if s.startswith("f") or s.startswith("mu"):
        return "mujer"
    if s.startswith(("m", "v", "h")):
        return "varon"
    return "otro"


def _st(hz, base):
    return 12 * math.log2(hz / base)


def nombre_nota(hz: float) -> str:
    """Nombre de la nota (convención franco-belga, La3 = 440 Hz), como la app."""
    notas = ['Do', 'Do#', 'Re', 'Re#', 'Mi', 'Fa', 'Fa#', 'Sol', 'Sol#', 'La', 'La#', 'Si']
    m = round(69 + 12 * math.log2(hz / 440))
    return f"{notas[m % 12]}{m // 12 - 2}"


def _f(v):
    try:
        f = float(v)
        return f if 50 <= f <= 1200 else None
    except (TypeError, ValueError):
        return None


def perfil_tonal(sb, pid: str, paciente: dict) -> dict:
    """Todas las mediciones de F0 del paciente, con fecha y origen, y la
    propuesta clínica de tono de inicio y rango de trabajo.

    Tono de inicio = F0 CONVERSACIONAL más reciente (evaluación o sesión de
    voz); si no hay, la F0 de vocal sostenida del análisis acústico (avisado).
    Nunca un valor inventado: sin mediciones, el profesional lo carga.
    Rango de trabajo = el rango clínico del paciente (ficha) > el rango medido
    en su análisis acústico > la referencia normativa por sexo y edad."""
    fuentes = []
    try:
        from ficha_integral import _f0_conversacional
        for x in _f0_conversacional(sb, pid):
            if _f(x.get("f0_mediana_hz")):
                fuentes.append({"tipo": "conversacional", "hz": round(float(x["f0_mediana_hz"]), 1),
                                "fecha": x.get("fecha"), "origen": "sesión de voz (habla espontánea)"})
    except Exception:
        pass
    try:
        for e in (sb.table("evaluaciones_clinicas").select("*").eq("paciente_id", pid).execute().data or []):
            if _f(e.get("f0_conversacional_hz")):
                fuentes.append({"tipo": "conversacional", "hz": round(float(e["f0_conversacional_hz"]), 1),
                                "fecha": dia_ar(e.get("fecha")), "origen": "evaluación (Riesgo & Escalas)"})
    except Exception:
        pass
    medidos = []
    try:
        for a in (sb.table("analisis_acusticos").select("*").eq("paciente_id", pid).execute().data or []):
            if _f(a.get("f0_mean")):
                fuentes.append({"tipo": "sostenida", "hz": round(float(a["f0_mean"]), 1),
                                "fecha": dia_ar(a.get("fecha")), "origen": "análisis acústico (vocal sostenida)"})
            lo, hi = _f(a.get("f0_min")), _f(a.get("f0_max"))
            if lo and hi and hi > lo and _st(hi, lo) >= 3:
                medidos.append({"min_hz": round(lo, 1), "max_hz": round(hi, 1), "fecha": dia_ar(a.get("fecha"))})
    except Exception:
        pass
    for x in fuentes:
        x["nota"] = nombre_nota(x["hz"])
    fuentes.sort(key=lambda x: x["fecha"] or "")
    conv = [x for x in fuentes if x["tipo"] == "conversacional"]
    sost = [x for x in fuentes if x["tipo"] == "sostenida"]
    if conv:
        b = conv[-1]
        base = {"hz": b["hz"], "nota": b["nota"], "origen": f"F0 conversacional · {b['origen']} · {b['fecha']}", "confiable": True}
    elif sost:
        b = sost[-1]
        base = {"hz": b["hz"], "nota": b["nota"], "confiable": False,
                "origen": f"F0 de vocal sostenida ({b['fecha']}): no hay F0 conversacional medida, confirmala"}
    else:
        base = {"hz": None, "nota": None, "confiable": False,
                "origen": "Sin F0 medida: cargá el tono de inicio (medilo en Pitch Meter o en la evaluación)"}
    lo, hi = _f(paciente.get("f0_ref_min_hz")), _f(paciente.get("f0_ref_max_hz"))
    if lo and hi and hi > lo:
        rango = {"min_hz": lo, "max_hz": hi, "origen": "rango clínico cargado en la ficha del paciente"}
    elif medidos:
        m = sorted(medidos, key=lambda x: x["fecha"])[-1]
        rango = {"min_hz": m["min_hz"], "max_hz": m["max_hz"], "origen": f"rango medido en el análisis acústico ({m['fecha']})"}
    else:
        rango = {"min_hz": None, "max_hz": None, "origen": "sin rango medido"}
        try:
            from companion import _rangos, elegir_rango_normativo, _edad
            r = elegir_rango_normativo(_rangos(sb), paciente.get("sexo_referencia") or paciente.get("sexo") or "",
                                       _edad(paciente.get("fecha_nacimiento") or ""))
            if r and _f(r.get("f0_min_hz")) and _f(r.get("f0_max_hz")):
                rango = {"min_hz": float(r["f0_min_hz"]), "max_hz": float(r["f0_max_hz"]),
                         "origen": f"referencia normativa por sexo y edad ({r.get('fuente') or 'tabla'}): confirmala"}
        except Exception:
            pass
    for k in ("min_hz", "max_hz"):
        rango[k.replace("hz", "nota")] = nombre_nota(rango[k]) if rango.get(k) else None
    if base["hz"] and rango.get("min_hz") and not rango["min_hz"] <= base["hz"] <= rango["max_hz"]:
        base["aviso"] = "El tono de inicio queda fuera del rango de trabajo: revisá ambos."
    return {"tono_base": base, "rango": rango, "mediciones": fuentes[-8:]}


def tono_base(sb, pid: str, paciente: dict) -> dict:
    return perfil_tonal(sb, pid, paciente)["tono_base"]


def limites_hz(e: dict) -> tuple:
    """Nota más grave y más aguda que pide el ejercicio."""
    if e["guia"] == "sostenida":
        semis = [0]
    elif e["guia"] == "rampa":
        semis = [0, e["amplitud"]]
    else:
        semis = e["semitonos"]
    return e["base_hz"] * 2 ** (min(semis) / 12), e["base_hz"] * 2 ** (max(semis) / 12)


def ajustar_a_rango(e: dict, base: float, lo, hi) -> dict:
    """Acota la plantilla del ejercicio para que no salga del rango de trabajo."""
    e = dict(e)
    if not (lo and hi and base):
        return e
    tope = math.floor(_st(hi, base) + 1e-6)
    if e.get("guia") == "rampa":
        e["amplitud"] = max(1, min(int(e.get("amplitud") or 7), tope))
    elif e.get("guia") in ("escalera", "patron") and e.get("semitonos"):
        e["semitonos"] = [s for s in e["semitonos"] if s <= tope] or [0]
        if len(e["semitonos"]) < 2:
            e["semitonos"] = [0, min(2, max(tope, 0)), 0] if tope >= 1 else [0, 0]
    return e


def nombre_limpio(nombre) -> str:
    """Saca la numeración del cuadernillo («10.1 Glissandos…» → «Glissandos…»)."""
    return re.sub(r"^\s*\d+(?:\.\d+)*\.?\s+", "", str(nombre or "")).strip()


def usa_tono(e: dict) -> bool:
    """El ejercicio tiene una altura objetivo (se valida contra el rango)."""
    return e.get("medida", "tono") == "tono" or (e.get("medida") == "sostenido" and bool(e.get("con_tono")))


def normalizar_ejercicio(e: dict, base_defecto) -> dict:
    """Valida y completa un ejercicio; rechaza valores fuera de rango."""
    medida = str(e.get("medida") or "tono")
    if medida not in MEDIDAS:
        raise HTTPException(status_code=400, detail=f"Tipo de medición inválido: {medida}")
    guia = str(e.get("guia") or ("sostenida" if medida != "tono" else ""))
    if guia not in GUIAS:
        raise HTTPException(status_code=400, detail=f"Tipo de guía inválido: {guia or 'vacío'}")
    out = {"bank_id": e.get("bank_id") or None, "nombre": (nombre_limpio(e.get("nombre")) or "Ejercicio")[:80],
           "medida": medida, "guia": guia,
           "modelo": "sin_modelo" if e.get("modelo") == "sin_modelo" else "sonoro",
           "consigna": str(e.get("consigna") or "")[:300],
           "repeticiones": max(1, min(20, int(e.get("repeticiones") or 3))),
           "tolerancia_cents": max(25, min(400, int(e.get("tolerancia_cents") or 100)))}
    if e.get("origen") in ORIGENES_PRACTICA:
        out["origen"] = e["origen"]
    if e.get("ref_cuadernillo"):
        out["ref_cuadernillo"] = str(e["ref_cuadernillo"])[:60]
    if e.get("numero_cuadernillo"):
        out["numero_cuadernillo"] = str(e["numero_cuadernillo"])[:8]
    if medida == "sostenido":
        out["con_tono"] = bool(e.get("con_tono"))
    necesita_tono = usa_tono(out)
    try:
        base = float(e.get("base_hz") or base_defecto) if (e.get("base_hz") or base_defecto) else None
    except (TypeError, ValueError):
        raise HTTPException(status_code=400, detail="Tono base inválido")
    if necesita_tono and base is None:
        raise HTTPException(status_code=400, detail=f"«{out['nombre']}» necesita tono de inicio.")
    if base is not None:
        if not 60 <= base <= 1000:
            raise HTTPException(status_code=400, detail="El tono base va de 60 a 1000 Hz.")
        out["base_hz"] = round(base, 1)
    if medida in ("sostenido", "flujo", "libre"):
        out["duracion_objetivo_s"] = max(2.0, min(60.0, float(e.get("duracion_objetivo_s") or e.get("duracion_s") or (20 if medida == "libre" else 8))))
        out["margen_db"] = max(2.0, min(15.0, float(e.get("margen_db") or 6)))
    elif medida == "intensidad":
        out["duracion_s"] = max(3.0, min(30.0, float(e.get("duracion_s") or 8)))
        out["patron_intensidad"] = "arco" if e.get("patron_intensidad") == "arco" else "pareja"
        out["margen_db"] = max(2.0, min(15.0, float(e.get("margen_db") or 4)))
    elif medida == "pasos":
        pasos = []
        for x in (e.get("pasos") or [])[:12]:
            if not isinstance(x, dict) or not str(x.get("texto") or "").strip():
                continue
            pasos.append({"tipo": x.get("tipo") if x.get("tipo") in TIPOS_PASO else "accion",
                          "segundos": max(1, min(120, int(float(x.get("segundos") or 5)))),
                          "texto": str(x["texto"]).strip()[:120]})
        if not pasos:
            raise HTTPException(status_code=400, detail=f"«{out['nombre']}» no tiene pasos.")
        out["pasos"] = pasos
    elif medida == "pulsos":
        out["pulsos"] = max(2, min(30, int(e.get("pulsos") or 6)))
        out["tempo_bpm"] = max(30, min(200, int(e.get("tempo_bpm") or 80)))
    if medida == "tono" or (medida == "sostenido" and out.get("con_tono")):
        if guia == "sostenida":
            out["duracion_s"] = max(2.0, min(30.0, float(e.get("duracion_objetivo_s") or e.get("duracion_s") or 6)))
        elif guia == "rampa":
            out["amplitud"] = max(1, min(24, int(e.get("amplitud") or 7)))
            out["duracion_s"] = max(2.0, min(20.0, float(e.get("duracion_s") or 6)))
        else:
            semis = [int(x) for x in (e.get("semitonos") or [])][:24]
            if len(semis) < 2 or any(abs(x) > 24 for x in semis):
                raise HTTPException(status_code=400, detail="La escalera necesita de 2 a 24 notas, dentro de ±24 semitonos.")
            out["semitonos"] = semis
            out["nota_s"] = max(0.5, min(5.0, float(e.get("nota_s") or 1.2)))
        tope = base * 2 ** (max(out.get("semitonos") or [out.get("amplitud", 0)]) / 12)
        if tope > 1200:
            raise HTTPException(status_code=400, detail="El ejercicio sube por encima de 1200 Hz: bajá el tono base.")
    return out


# ─── Origen de la práctica: coherencia con el cuadernillo del paciente ─────

ORIGENES_PRACTICA = {"cuadernillo": "Cuadernillo de la app", "fonoar": "Cuadernillo de Fonoar",
                     "tvso": "Tracto vocal semiocluido (tubos) y descenso laríngeo",
                     "sueltos": "Ejercicios sueltos"}
# Secuencia clínica del apartado de tracto vocal semiocluido: preparación con
# descenso laríngeo, tubos (de menor a mayor resistencia/variación) y transferencia.
SECUENCIA_TVSO = [
    ("descenso_laringeo", "Descenso laríngeo · bostezo o succión"),
    ("oclusion_succion", "Descenso laríngeo · «hu hu hu»"),
    ("laxvox_agua", "Tubos · tubo en agua"),
    ("tubo_aire_libre", "Tubos · tubo en el aire"),
    ("finger_kazoo", "Semioclusión · dedo en los labios"),
    ("mano_boca", "Semioclusión · mano sobre la boca"),
    ("trino_labial", "Semioclusión · trino de labios"),
    ("b_prolongada", "Semioclusión · /b/ prolongada"),
    ("fricativas_sonoras", "Semioclusión · /v/ /z/ sostenidas"),
    ("oclusion_nasal", "Transferencia · /m/ a vocales"),
]
CATALOGO_FONOAR = os.path.join(os.path.dirname(__file__), "cuadernillo_fonoar.json")


def cuadernillo_vigente(sb, pid: str):
    """Último cuadernillo generado en la app para el paciente: ejercicios en orden."""
    try:
        filas = (sb.table("cuadernillos_paciente").select("id, titulo, fecha_creacion, ejercicios_seleccionados")
                 .eq("paciente_id", pid).order("fecha_creacion", desc=True).limit(1).execute().data or [])
    except Exception:
        return None
    if not filas:
        return None
    f = filas[0]
    ejercicios = []
    for i, e in enumerate(f.get("ejercicios_seleccionados") or []):
        eid = e.get("id") if isinstance(e, dict) else e
        if eid:
            ejercicios.append({"id": eid, "nombre": nombre_limpio((e.get("name") or e.get("nombre")) if isinstance(e, dict) else eid),
                               "orden": (e.get("orden") if isinstance(e, dict) else None) or i + 1})
    return {"id": f.get("id"), "titulo": f.get("titulo") or "Cuadernillo", "fecha": dia_ar(f.get("fecha_creacion")),
            "ejercicios": ejercicios}


def catalogo_fonoar():
    """Cuadernillo de Fonoar cargado (server_api/cuadernillo_fonoar.json), o None.
    Formato: {"ejercicios": [{"numero": "10.1", "nombre": "...", "bank_id": "tubo_agua"}]}"""
    try:
        with open(CATALOGO_FONOAR, encoding="utf-8") as fh:
            datos = json.load(fh)
        return datos if datos.get("ejercicios") else None
    except Exception:
        return None


def origen_automatico(paciente: dict, cuad) -> str:
    from agenda_fonoar import CENTROS
    propio = {c["id"] for c in CENTROS if c.get("cuadernillo_propio")}
    if (paciente.get("centro") or "") in propio:
        return "fonoar"
    return "cuadernillo" if cuad and cuad["ejercicios"] else "sueltos"


def cuadro_clinico(sb, pid: str, paciente: dict) -> dict:
    """Textos clínicos del paciente por fuente, para verificar contraindicaciones."""
    fuentes = {}
    try:
        an = (sb.table("anamnesis").select("*").eq("paciente_id", pid).order("fecha", desc=True)
              .limit(1).execute().data or [])
        if an:
            fuentes["la anamnesis"] = " ".join(str(an[0].get(k) or "") for k in ("diagnostico_orl", "motivo_consulta"))
    except Exception:
        pass
    try:
        inf = (sb.table("informes_orl").select("*").eq("paciente_id", pid).order("fecha", desc=True)
               .limit(3).execute().data or [])
        for i in inf:
            cuando = i.get("fecha_informe") or dia_ar(i.get("fecha"))
            fuentes[f"el informe ORL del {cuando}"] = " ".join(
                str(i.get(k) or "") for k in ("diagnostico_principal",))
    except Exception:
        pass
    if paciente.get("notas_iniciales"):
        fuentes["las notas iniciales"] = str(paciente["notas_iniciales"])
    return {k: v for k, v in fuentes.items() if v.strip()}


@router.get("/api/practicas/sugerencias")
async def sugerencias(paciente_id: str, origen: str = "auto"):
    sb = _sb()
    p = (sb.table("pacientes").select("*").eq("id", paciente_id).execute().data or [{}])[0]
    if not p:
        raise HTTPException(status_code=404, detail="Paciente inexistente")
    perfil = perfil_tonal(sb, paciente_id, p)
    base = perfil["tono_base"]
    rango = perfil["rango"]
    from api_clinica import banco_ejercicios_completo
    _secciones = banco_ejercicios_completo().get("sections", [])
    banco = {e["id"]: e for s in _secciones for e in s.get("exercises", []) if e.get("id")}
    seccion_de = {e["id"]: nombre_limpio(s.get("name")) for s in _secciones for e in s.get("exercises", []) if e.get("id")}
    plan_ids = []
    try:
        rec = (sb.table("recomendaciones_terapeuticas").select("*").eq("paciente_id", paciente_id)
               .order("creada_at", desc=True).limit(1).execute().data or [])
        if rec:
            plan_ids = [x.get("id") for x in (rec[0].get("recomendacion") or {}).get("ejercicios_recomendados") or []]
    except Exception:
        pass
    # Contraindicaciones con TODO el cuadro clínico: anamnesis, informes ORL y notas iniciales.
    fuentes = cuadro_clinico(sb, paciente_id, p)
    diag = " ".join(fuentes.values())
    # De dónde salen los ejercicios: cuadernillo de la app, de Fonoar o sueltos.
    cuad = cuadernillo_vigente(sb, paciente_id)
    auto = origen_automatico(p, cuad)
    elegido = origen if origen in ORIGENES_PRACTICA else auto
    aviso = ""
    # Entradas en orden: (clave única, id del banco, orden, referencia para el paciente, ajuste de guía).
    # Un mismo ejercicio del banco puede estar con distinto número (Fonoar 12, 13 y 14 = escalas).
    entradas, sin_guia, vistos, bloque_de, numero_de = [], [], {}, {}, {}
    if elegido == "fonoar":
        cat = catalogo_fonoar()
        if cat:
            for i, e in enumerate(cat["ejercicios"]):
                bid = e.get("bank_id")
                ref = f"Cuadernillo Fonoar · {e.get('numero')}. {e.get('nombre')}".replace("Rutina. ", "")
                if bid in GUIA_POR_EJERCICIO and bid in banco:
                    vistos[bid] = vistos.get(bid, 0) + 1
                    clave = bid if vistos[bid] == 1 else f"{bid}~{e.get('numero')}"
                    bloque_de[clave] = AREAS_FONOAR.get(e.get("area"), e.get("area") or "")
                    entradas.append((clave, bid, i, ref, e.get("guia") or {}, e.get("nombre")))
                    numero_de[clave] = str(e.get("numero") or "") if e.get("numero") != "Rutina" else ""
                else:
                    sin_guia.append({"orden": e.get("numero"), "nombre": e.get("nombre")})
        else:
            aviso = ("Todavía no está cargado el cuadernillo de Fonoar: se muestran todos los ejercicios. "
                     "Cuando se cargue, la práctica sigue su numeración.")
    elif elegido == "tvso":
        for i, (bid, ref) in enumerate(SECUENCIA_TVSO):
            if bid in GUIA_POR_EJERCICIO and bid in banco:
                entradas.append((bid, bid, i + 1, ref, {}, None))
    elif elegido == "cuadernillo":
        if cuad and cuad["ejercicios"]:
            for e in cuad["ejercicios"]:
                if e["id"] in GUIA_POR_EJERCICIO and e["id"] in banco and e["id"] not in vistos:
                    vistos[e["id"]] = 1
                    entradas.append((e["id"], e["id"], e["orden"], f"Tu cuadernillo · ejercicio {e['orden']}", {}, None))
                    numero_de[e["id"]] = str(e["orden"])
                elif e["id"] not in GUIA_POR_EJERCICIO:
                    sin_guia.append({"orden": e["orden"],
                                     "nombre": nombre_limpio(banco.get(e["id"], {}).get("name") or e["nombre"])})
        else:
            aviso = "El paciente no tiene un cuadernillo generado en la app: se muestran todos los ejercicios."
    con_ref = bool(entradas)
    if not con_ref:
        entradas = [(i, i, None, None, {}, None) for i in GUIA_POR_EJERCICIO if i in banco]
    from recomendar_motor import verificar_contraindicaciones
    seguros, excluidos = verificar_contraindicaciones(sorted({e[1] for e in entradas}), fuentes=fuentes)
    seguros = set(seguros)
    lista = []
    for clave, bid, orden, ref, ajuste, nombre_ref in entradas:
        if bid not in seguros:
            continue
        g = dict(GUIA_POR_EJERCICIO[bid], **ajuste)
        if usa_tono(g):
            g = ajustar_a_rango(g, base["hz"], rango.get("min_hz"), rango.get("max_hz"))
        item = dict(g, bank_id=clave, nombre=nombre_limpio(nombre_ref or banco[bid].get("name", bid)),
                    base_hz=base["hz"], en_plan=bid in plan_ids, origen=elegido if con_ref else "sueltos")
        if ref:
            item["ref_cuadernillo"], item["orden_cuadernillo"] = ref, orden
        if numero_de.get(clave):
            item["numero_cuadernillo"] = numero_de[clave]  # lo único que ve el paciente
        # Bloque para seleccionar de a grupos: área del cuadernillo de Fonoar, etapa del
        # apartado de tubos, o sección del banco.
        item["bloque"] = bloque_de.get(clave) or (ref.split(" · ")[0] if elegido == "tvso" and ref else "") or seccion_de.get(bid, "")
        lista.append(item)
    if not con_ref:
        lista.sort(key=lambda x: (not x["en_plan"], x["nombre"]))
    sug_tol = {"cents": 100, "motivo": "margen normal (1 semitono)"}
    try:
        ev = (sb.table("evaluaciones_clinicas").select("*").eq("paciente_id", paciente_id)
              .order("fecha", desc=True).limit(1).execute().data or [])
        g_val = ((ev[0].get("grbas") or {}).get("G") if ev else None)
        if g_val is not None and float(g_val) >= 2:
            sug_tol = {"cents": 200, "motivo": f"disfonía grado G{int(float(g_val))}: margen amplio (2 semitonos)"}
    except Exception:
        pass
    return {"tono_base": base, "rango": rango, "mediciones": perfil["mediciones"], "tolerancia_sugerida": sug_tol,
            "ejercicios": lista, "excluidos": excluidos,
            "origen": elegido, "origen_auto": auto, "origenes": ORIGENES_PRACTICA, "aviso_origen": aviso,
            "cuadernillo": ({"id": cuad["id"], "titulo": cuad["titulo"], "fecha": cuad["fecha"],
                             "total": len(cuad["ejercicios"]),
                             "con_guia": len([e for e in cuad["ejercicios"] if e["id"] in GUIA_POR_EJERCICIO])}
                            if cuad else None),
            "sin_guia": sin_guia, "fonoar_cargado": bool(catalogo_fonoar()),
            "fonoar": ({"total": len(catalogo_fonoar()["ejercicios"]), "con_guia": len([x for x in lista if x.get("ref_cuadernillo")])}
                       if elegido == "fonoar" and catalogo_fonoar() else None)}


@router.post("/api/practicas")
async def crear(request: Request):
    body = await request.json()
    pid = str(body.get("paciente_id") or "").strip()
    if not pid:
        raise HTTPException(status_code=400, detail="Elegí un paciente.")
    sb = _sb()
    p = (sb.table("pacientes").select("*").eq("id", pid).execute().data or [{}])[0]
    if not p:
        raise HTTPException(status_code=404, detail="Paciente inexistente")
    ejercicios = body.get("ejercicios") or []
    if not 1 <= len(ejercicios) <= MAX_EJERCICIOS:
        raise HTTPException(status_code=400, detail=f"La rutina lleva de 1 a {MAX_EJERCICIOS} ejercicios.")
    if body.get("confirmado") is not True:
        raise HTTPException(status_code=400, detail="Confirmá que revisaste la rutina antes de enviarla.")
    # El rango tonal solo hace falta si algún ejercicio tiene altura objetivo
    # (una rutina de cuerpo, respiración y masajes no lo necesita).
    con_altura = any(usa_tono(e) for e in ejercicios if isinstance(e, dict))
    rango = body.get("rango") or {}
    lo, hi = _f(rango.get("min_hz")), _f(rango.get("max_hz"))
    if not (lo and hi and _st(hi, lo) >= 2):
        if con_altura:
            raise HTTPException(status_code=400, detail="Falta el rango de trabajo (mínimo y máximo en Hz, al menos 2 semitonos).")
        lo = hi = None
    base = tono_base(sb, pid, p)["hz"]
    ejercicios = [normalizar_ejercicio(e, base) for e in ejercicios]
    for e in ejercicios:
        if not usa_tono(e):
            if lo and hi:
                e["rango_min_hz"], e["rango_max_hz"] = round(lo, 1), round(hi, 1)
            continue
        grave, agudo = limites_hz(e)
        if grave < lo * 2 ** (-0.5 / 12) or agudo > hi * 2 ** (0.5 / 12):
            raise HTTPException(status_code=400, detail=(
                f"«{e['nombre']}» va de {nombre_nota(grave)} ({grave:.0f} Hz) a {nombre_nota(agudo)} ({agudo:.0f} Hz): "
                f"sale del rango de trabajo {nombre_nota(lo)}–{nombre_nota(hi)} ({lo:.0f}–{hi:.0f} Hz). "
                "Bajá la amplitud o cambiá el tono de inicio."))
        e["rango_min_hz"], e["rango_max_hz"] = round(lo, 1), round(hi, 1)
    if body.get("guardar_rango_paciente") and lo and hi:
        try:
            sb.table("pacientes").update({"f0_ref_min_hz": round(lo, 1), "f0_ref_max_hz": round(hi, 1)}).eq("id", pid).execute()
        except Exception as e:
            print(f"[practica] no se guardó el rango en la ficha: {e}")
    veces = max(1, min(4, int(body.get("veces_por_dia") or 2)))
    from nombres import saludo_de_paciente
    saludo = str(body.get("saludo") or "").strip()[:60] or saludo_de_paciente(p)
    dias = max(1, min(90, int(body.get("vence_dias") or 30)))
    token = secrets.token_urlsafe(18)
    fila = {"token": token, "paciente_id": pid, "activa": True, "saludo": saludo,
            "ejercicios": ejercicios, "indicaciones": str(body.get("indicaciones") or "")[:500],
            "vence_at": (_ahora() + timedelta(days=dias)).isoformat(),
            "veces_por_dia": veces, "rango": {"min_hz": round(lo, 1), "max_hz": round(hi, 1)} if lo and hi else None}
    try:
        guardada = (sb.table("practicas").insert(fila).execute().data or [fila])[0]
    except Exception as e:
        if "veces_por_dia" in str(e) or "rango" in str(e):
            # Sin la migración v2: se guarda igual (el rango viaja en cada ejercicio).
            fila.pop("veces_por_dia"); fila.pop("rango")
            try:
                guardada = (sb.table("practicas").insert(fila).execute().data or [fila])[0]
            except Exception as e2:
                _err_tabla(e2)
        else:
            _err_tabla(e)
    frontend = os.environ.get("FRONTEND_URL", "https://vocalis-lab.vercel.app").rstrip("/")
    return {"ok": True, "id": guardada.get("id"), "enlace": f"{frontend}/?practica={token}",
            "vence_at": fila["vence_at"], "nombre": saludo, "telefono": p.get("telefono") or ""}


@router.get("/api/practicas")
async def listar(paciente_id: str):
    sb = _sb()
    try:
        rutinas = (sb.table("practicas").select("*").eq("paciente_id", paciente_id)
                   .order("creada_at", desc=True).limit(20).execute().data or [])
        sesiones = (sb.table("practica_sesiones").select("*").eq("paciente_id", paciente_id)
                    .order("creada_at", desc=True).limit(200).execute().data or [])
    except Exception as e:
        if "practica" in str(e):
            return {"practicas": [], "sesiones": [], "aviso": MSG_MIGRACION}
        raise
    frontend = os.environ.get("FRONTEND_URL", "https://vocalis-lab.vercel.app").rstrip("/")
    for r in rutinas:
        r["enlace"] = f"{frontend}/?practica={r.pop('token', '')}"
    veces = int((rutinas[0].get("veces_por_dia") if rutinas else None) or 2)
    return {"practicas": rutinas, "sesiones": sesiones, "adherencia": adherencia(sesiones, veces, 14)}


@router.patch("/api/practicas/{practica_id}")
async def cambiar(practica_id: str, request: Request):
    body = await request.json()
    sb = _sb()
    sb.table("practicas").update({"activa": bool(body.get("activa"))}).eq("id", practica_id).execute()
    return {"ok": True}


# ------------------------------------------------------------------ público
def _rutina(sb, token: str) -> dict:
    try:
        filas = sb.table("practicas").select("*").eq("token", token).execute().data or []
    except Exception as e:
        _err_tabla(e)
    if not filas:
        raise HTTPException(status_code=404, detail="El enlace no existe. Pedile uno nuevo a tu fonoaudiólogo.")
    return filas[0]


def _disponible(r: dict) -> str:
    if not r.get("activa"):
        return "pausada"
    try:
        if datetime.fromisoformat(str(r["vence_at"]).replace("Z", "+00:00")) < _ahora():
            return "vencida"
    except Exception:
        pass
    return "activa"


AR = timezone(timedelta(hours=-3))


def adherencia(sesiones: list, veces_por_dia: int, dias: int = 14) -> dict:
    """Prácticas por día (hora de Argentina). Una práctica = una tanda (todos
    los ejercicios hechos en una misma apertura), no cada ejercicio."""
    por_dia = {}
    for s in sesiones:
        res = s.get("resultados") or []
        if res and all((r or {}).get("medida") == "sz" for r in res):
            continue  # la medición s/z sola no es una práctica
        try:
            t = datetime.fromisoformat(str(s.get("creada_at")).replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=timezone.utc)
        except Exception:
            continue
        dia = t.astimezone(AR).date().isoformat()
        tanda = (s.get("ambiente") or {}).get("tanda") or s.get("id")
        por_dia.setdefault(dia, set()).add(tanda)
    hoy = _ahora().astimezone(AR).date()
    serie = []
    for i in range(dias - 1, -1, -1):
        d = (hoy - timedelta(days=i)).isoformat()
        serie.append({"dia": d, "practicas": len(por_dia.get(d, ()))})
    cumplidos = sum(1 for x in serie if x["practicas"] >= veces_por_dia)
    return {"hoy": serie[-1]["practicas"], "veces_por_dia": veces_por_dia, "serie": serie,
            "dias_cumplidos": cumplidos, "dias_con_practica": sum(1 for x in serie if x["practicas"])}


@router.get("/api/practica/{token}")
async def ver(token: str):
    sb = _sb()
    r = _rutina(sb, token)
    veces = int(r.get("veces_por_dia") or 2)
    try:
        ses = sb.table("practica_sesiones").select("*").eq("practica_id", r["id"]).execute().data or []
    except Exception:
        ses = []
    ad = adherencia(ses, veces, 7)
    return {"ok": True, "nombre": r.get("saludo") or "", "estado": _disponible(r),
            "veces_por_dia": veces, "practicas_hoy": ad["hoy"], "semana": ad["serie"],
            "voz": __import__("voz_guia").claves_grabadas(sb),
            "ejercicios": r.get("ejercicios") or [], "indicaciones": r.get("indicaciones") or "",
            "consentimiento": bool(r.get("consentimiento_at")),
            "version_consentimiento": VERSION_CONSENTIMIENTO,
            "profesional": "Matías Pérez · Fonoaudiólogo"}


@router.post("/api/practica/{token}/consentimiento")
async def consentir(token: str, request: Request):
    body = await request.json()
    if body.get("acepta") is not True:
        raise HTTPException(status_code=400, detail="Para usar la práctica hace falta aceptar.")
    sb = _sb()
    r = _rutina(sb, token)
    sb.table("practicas").update({
        "consentimiento_at": _ahora().isoformat(),
        "consentimiento": {"version": VERSION_CONSENTIMIENTO, "medir_voz": True, "audio": False,
                           "agente": str(request.headers.get("user-agent") or "")[:200]},
    }).eq("id", r["id"]).execute()
    return {"ok": True}


def _num(v, lo, hi):
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or not lo <= f <= hi:
        return None
    return round(f, 2)


def resultado_sz(x: dict) -> dict:
    """Medición s/z: hasta 3 intentos de /s/ y de /z/ (segundos). El índice
    se calcula acá con el mejor intento de cada uno (no se confía en el cliente)."""
    def intentos(k):
        vals = [_num(v, 1, 120) for v in (x.get(k) or [])[:3]]
        return [v for v in vals if v is not None]
    s, z = intentos("s"), intentos("z")
    if not s and not z:
        raise HTTPException(status_code=400, detail="La medición s/z no tiene intentos válidos.")
    s_max, z_max = (max(s) if s else None), (max(z) if z else None)
    return {"ejercicio": -1, "medida": "sz", "s_intentos": s, "z_intentos": z, "s_max_s": s_max, "z_max_s": z_max,
            "indice_sz": round(s_max / z_max, 2) if s_max and z_max else None}


def limpiar_resultado(x: dict, n_ejercicios: int) -> dict:
    if x.get("medida") == "sz":
        return resultado_sz(x)
    i = int(x.get("ejercicio") if x.get("ejercicio") is not None else -1)
    if not 0 <= i < n_ejercicios:
        raise HTTPException(status_code=400, detail="Ejercicio inexistente en la rutina.")
    medida = x.get("medida") if x.get("medida") in MEDIDAS else None
    return {"ejercicio": i, "medida": medida,
            "repeticiones": int(_num(x.get("repeticiones"), 0, 50) or 0),
            "logro_pct": _num(x.get("logro_pct"), 0, 100),
            # Altura
            "dentro_pct": _num(x.get("dentro_pct"), 0, 100),
            "octava_pct": _num(x.get("octava_pct"), 0, 100),
            "f0_mediana_hz": _num(x.get("f0_mediana_hz"), 50, 1500),
            "f0_min_hz": _num(x.get("f0_min_hz"), 50, 1500),
            "f0_max_hz": _num(x.get("f0_max_hz"), 50, 1500),
            "desvio_cents": _num(x.get("desvio_cents"), 0, 2400),
            "altura_no_medible": bool(x.get("altura_no_medible")),
            # Sonido, periodicidad y continuidad
            "voz_pct": _num(x.get("voz_pct"), 0, 100),
            "periodicidad_pct": _num(x.get("periodicidad_pct"), 0, 100),
            "sonido_s": _num(x.get("sonido_s"), 0, 3600),
            "tramo_max_s": _num(x.get("tramo_max_s"), 0, 3600),
            "cortes": int(_num(x.get("cortes"), 0, 1000) or 0),
            # Intensidad (dB relativos: sobre el ruido del lugar / respecto de su nivel cómodo)
            "intensidad_media_db": _num(x.get("intensidad_media_db"), -20, 100),
            "intensidad_rango_db": _num(x.get("intensidad_rango_db"), 0, 100),
            "intensidad_sd_db": _num(x.get("intensidad_sd_db"), 0, 60),
            "intensidad_dentro_pct": _num(x.get("intensidad_dentro_pct"), 0, 100),
            # Pulsos
            "pulsos": int(_num(x.get("pulsos"), 0, 500) or 0),
            "pulsos_regularidad_pct": _num(x.get("pulsos_regularidad_pct"), 0, 100),
            "duracion_s": _num(x.get("duracion_s"), 0, 3600)}


@router.post("/api/practica/{token}/sesion")
async def guardar_sesion(token: str, request: Request):
    body = await request.json()
    sb = _sb()
    r = _rutina(sb, token)
    estado = _disponible(r)
    if estado != "activa":
        raise HTTPException(status_code=409, detail=f"La práctica está {estado}.")
    if not r.get("consentimiento_at"):
        raise HTTPException(status_code=403, detail="Falta aceptar el consentimiento.")
    n = len(r.get("ejercicios") or [])
    resultados = [limpiar_resultado(x, n) for x in (body.get("resultados") or [])][:50]
    if not resultados:
        raise HTTPException(status_code=400, detail="No hay resultados para guardar.")
    amb = body.get("ambiente") or {}
    fila = {"practica_id": r["id"], "paciente_id": r["paciente_id"], "resultados": resultados,
            "ambiente": {"ruido_dbfs": _num(amb.get("ruido_dbfs"), -120, 0),
                         "silencioso": bool(amb.get("silencioso")),
                         "tanda": str(amb.get("tanda") or "")[:40] or None,
                         # F0 cómoda medida hoy antes de practicar y su distancia al tono de inicio.
                         "calibracion_hz": _num(amb.get("calibracion_hz"), 50, 1500),
                         "calibracion_st": _num(amb.get("calibracion_st"), -36, 36),
                         "calibracion_db": _num(amb.get("calibracion_db"), -120, 0)},
            "modo": "vivo" if body.get("modo") == "vivo" else "casa",
            "comentario": str(body.get("comentario") or "")[:500]}
    sb.table("practica_sesiones").insert(fila).execute()
    for x in resultados:
        if x.get("medida") == "sz" and x.get("indice_sz") is not None:
            try:
                from asistente import avisar
                p = sb.table("pacientes").select("nombre_completo").eq("id", r["paciente_id"]).execute().data or []
                nombre = (p[0].get("nombre_completo") if p else "") or "Un paciente"
                avisar(f"{nombre} midió su índice s/z en casa: {x['indice_sz']} "
                       f"(/s/ {x['s_max_s']} s · /z/ {x['z_max_s']} s).")
            except Exception:
                pass
    return {"ok": True}


# ─── Cuadernillo de Fonoar (consulta para la pantalla de cuadernillos) ─────

AREAS_FONOAR = {"corporal": "El trabajo corporal", "respiratorio": "El trabajo respiratorio",
                "vocalizaciones": "Ejercicios de vocalizaciones", "rutinas": "Rutinas de calentamiento y enfriamiento"}


@router.get("/api/cuadernillos/fonoar")
async def cuadernillo_fonoar():
    """El cuadernillo de Fonoar cargado, por áreas, con el tipo de guía de cada número."""
    cat = catalogo_fonoar()
    if not cat:
        raise HTTPException(status_code=404, detail="El cuadernillo de Fonoar no está cargado.")
    tipos = {"tono": "con altura (pelotita)", "sostenido": "sonido sostenido", "flujo": "sonido con aire",
             "intensidad": "volumen", "pulsos": "pulsos", "libre": "habla libre", "pasos": "con tiempo"}
    areas = []
    for e in cat["ejercicios"]:
        g = GUIA_POR_EJERCICIO.get(e.get("bank_id")) or {}
        item = {"numero": e.get("numero"), "nombre": e.get("nombre"), "bank_id": e.get("bank_id"),
                "guia": tipos.get(g.get("medida"), "sin guía")}
        area = AREAS_FONOAR.get(e.get("area"), e.get("area") or "Otros")
        if not areas or areas[-1]["area"] != area:
            areas.append({"area": area, "ejercicios": []})
        areas[-1]["ejercicios"].append(item)
    return {"titulo": cat.get("titulo"), "total": len(cat["ejercicios"]), "areas": areas,
            "aviso": "Solo numeración y títulos, para ubicar cada ejercicio en el cuadernillo en papel del paciente."}
