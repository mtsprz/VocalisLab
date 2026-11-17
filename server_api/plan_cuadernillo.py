"""Planificador clínico del cuadernillo: áreas a trabajar y variantes por área.

Lógica (inspirada en el cuadernillo estandarizado tipo FONOAR, pero
personalizado desde el inicio):

1. Se lee el caso completo del paciente (diagnóstico ORL, motivo, síntomas,
   GRBAS/RASATI, TME e índice S/Z, acústica, VHI-10, riesgo vocal, ocupación
   y demanda vocal) y se arma un PERFIL: condiciones clínicas con su peso y
   la evidencia que las sostiene ("GRBAS S=2", "diagnóstico: nódulos").
2. Con el perfil se deciden las ÁREAS a estimular. Algunas son base de todo
   programa de voz (cuerpo, respiración, SOVT, transferencia al habla,
   rutinas diarias); otras se activan solo si el caso lo pide (trabajo
   laríngeo, apertura orofaríngea, métodos fisiológicos).
3. Cada área activa se completa hasta un mínimo de variantes (3, o 4 en las
   áreas prioritarias del caso), respetando lo que ya eligió el profesional
   y eligiendo del banco los ejercicios más indicados para ESTE perfil.
4. Nunca se agrega un ejercicio contraindicado para el perfil (ej. empuje
   con nódulos o con hiperfunción) ni uno cuya indicación no corresponde
   (ej. pautas de reflujo sin reflujo).

El profesional decide: el plan propone y explica cada agregado; lo que él
eligió no se quita nunca.
"""
import json
import os
import re

BANK_PATH = os.path.join(os.path.dirname(__file__), "exercise_bank.json")

MINIMO_POR_AREA = 3
MINIMO_AREA_PRIORITARIA = 4

# Orden terapéutico del cuadernillo (de lo corporal a la transferencia).
ORDEN_AREAS = ["corporal", "orofaringeo", "respiratorio", "laringeo", "sovte",
               "metodos", "resonancia", "higiene"]

AREAS = {
    "corporal": "Cuerpo y postura",
    "orofaringeo": "Apertura orofaríngea y articulación",
    "respiratorio": "Respiración",
    "laringeo": "Trabajo laríngeo",
    "sovte": "Tracto vocal semiocluido (SOVT)",
    "metodos": "Métodos fisiológicos",
    "resonancia": "Habla y transferencia",
    "higiene": "Rutinas vocales diarias",
}

# Áreas base de todo programa de rehabilitación vocal.
AREAS_BASE = {
    "corporal": "Acondicionamiento corporal: base de todo programa vocal.",
    "respiratorio": "Soporte respiratorio: base de todo programa vocal.",
    "sovte": "Semioclusión: núcleo del entrenamiento de la fuente vocal.",
    "resonancia": "Transferencia de lo entrenado al habla diaria.",
    "higiene": "Calentamiento y enfriamiento diarios.",
}

# Condición → áreas que activa (si el perfil la trae).
AREAS_POR_CONDICION = {
    "tension_muscular": ["corporal", "laringeo", "orofaringeo"],
    "hiperfuncion": ["laringeo", "orofaringeo", "metodos"],
    "dmt": ["laringeo", "orofaringeo", "metodos"],
    "bruxismo": ["orofaringeo", "corporal"],
    "articulacion": ["orofaringeo"],
    "nodulo": ["laringeo", "metodos"],
    "edema_reinke": ["metodos"],
    "fonotrauma": ["metodos"],
    "laringitis_cronica": ["metodos"],
    "hipofuncion": ["laringeo", "metodos", "respiratorio"],
    "paralisis": ["laringeo", "metodos", "respiratorio"],
    "presbifonia": ["metodos", "respiratorio"],
    "soplo": ["respiratorio", "sovte"],
    "debilidad": ["respiratorio"],
    "fonastenia": ["respiratorio", "sovte", "resonancia"],
    "rigidez": ["sovte", "metodos"],
    "puberfonia": ["metodos"],
    "cantante": ["sovte", "metodos"],
    "docentes": ["higiene", "resonancia"],
    "rlf": ["higiene"],
    "transferencia": ["resonancia"],
}

ETIQUETAS = {
    "tension_muscular": "tensión muscular", "hiperfuncion": "hiperfunción",
    "dmt": "disfonía músculo-tensional", "bruxismo": "bruxismo / mandíbula",
    "articulacion": "articulación", "nodulo": "lesión exofítica (nódulo/pólipo/quiste)",
    "edema_reinke": "edema de Reinke", "fonotrauma": "fonotrauma",
    "laringitis_cronica": "laringitis crónica", "laringitis_aguda": "laringitis aguda",
    "hipofuncion": "hipofunción / cierre glótico incompleto", "paralisis": "parálisis o paresia",
    "presbifonia": "presbifonía", "soplo": "soplosidad / escape de aire",
    "debilidad": "poco aire disponible", "fonastenia": "fatiga vocal",
    "rigidez": "poca flexibilidad tonal", "puberfonia": "puberfonía",
    "cantante": "uso vocal artístico", "docentes": "alta demanda vocal",
    "rlf": "reflujo", "transferencia": "transferencia al habla",
}

# Indicación del banco → condición del perfil (alias/typos del banco).
_ALIAS_INDICACION = {"nodo_cordial": "nodulo", "hiatus": "hipofuncion",
                     "incompetencia_glotica": "hipofuncion",
                     "pre_estreno": "docentes", "post_estreno": "docentes",
                     "flexibilidad": "rigidez"}

# Contraindicaciones del banco que se cruzan con el perfil.
_CONTRA_CRITICAS = {"nodulo", "hiperfuncion", "dmt", "laringitis_aguda"}

_DIFICULTAD = {"basico": 1, "intermedio": 2, "avanzado": 3}

# Áreas donde, si faltan variantes indicadas, se completa con ejercicios
# seguros del área. No incluye laríngeo ni métodos (ahí relajar o empujar
# depende del caso) ni rutinas (las pautas de reflujo son solo para RLF).
AREAS_COMPLEMENTO = {"corporal", "respiratorio", "sovte", "resonancia", "orofaringeo"}
# Indicaciones que, solas, no justifican el ejercicio en otro paciente.
_SOLO_ESPECIFICAS = {"rlf", "cantante", "puberfonia"}

# Diagnóstico / motivo / síntomas en texto libre → condición.
_PATRONES_TEXTO = [
    ("nodulo", r"n[oó]dulo|nodo\s+cord|p[oó]lipo|quiste|granuloma|papiloma|lesi[oó]n (de masa|exof)|exof[ií]tic|engrosamiento"),
    ("edema_reinke", r"reinke|edema"),
    ("paralisis", r"par[aá]lisis|paresia|inmovilidad cord"),
    ("presbifonia", r"presbifon|presbilaring|arqueamiento"),
    ("hipofuncion", r"hipofunc|hiato|hiatus|incompetencia gl|cierre (gl[oó]tico )?incompleto|sulcus|vergeture|atrofia|cierre insuficiente"),
    ("dmt", r"\bdmt\b|m[uú]sculo.?tensi|tensional|hiperfunc"),
    ("hiperfuncion", r"hiperfunc|constricci[oó]n|banda ventricular|supragl[oó]tic|esfuerzo vocal|voz (tensa|apretada)"),
    ("tension_muscular", r"tensi[oó]n (cervical|muscular|de cuello)|contractura|dolor (de |en el )?cuello|cervicalgia"),
    ("bruxismo", r"bruxismo|\batm\b|mand[ií]bula|apretar (los )?dientes"),
    ("rlf", r"reflujo|\brlf\b|\brge\b|\berge\b|acidez|pirosis|ardor"),
    ("laringitis_aguda", r"laringitis aguda"),
    ("laringitis_cronica", r"laringitis cr[oó]nica"),
    ("fonotrauma", r"fonotrauma|abuso vocal|mal uso vocal|grit"),
    ("fonastenia", r"fonastenia|fatiga vocal|cansancio vocal|se cansa (al hablar|la voz)|voz cansada"),
    ("puberfonia", r"puberfon|falsete (persistente|mutacional)"),
    ("soplo", r"soplad|soplosa|aire en la voz|escape de aire|voz d[eé]bil"),
    ("rigidez", r"monoton|rango (tonal )?reducido|no llega a los agudos|quiebres"),
]
_PATRONES_OCUPACION = [
    ("docentes", r"docent|maestr|profesor|locut|operador|telefon|vendedor|abogad|predicador|pastor|instructor|entrenador|call"),
    ("cantante", r"cant|coro|l[ií]ric|m[uú]sic|actor|actriz|teatro"),
]


def cargar_secciones(secciones=None):
    """Secciones del banco: las que manda la app (incluyen ejercicios
    aprobados por el profesional) o el banco base del servidor."""
    if secciones:
        return secciones
    with open(BANK_PATH, encoding="utf-8") as f:
        return json.load(f).get("sections", [])


def _num(v):
    try:
        if v is None or v == "":
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


class Perfil:
    """Condiciones clínicas del paciente con peso y evidencia."""

    def __init__(self):
        self.peso = {}
        self.evidencia = {}

    def sumar(self, cond, peso, evidencia):
        self.peso[cond] = self.peso.get(cond, 0) + peso
        ev = self.evidencia.setdefault(cond, [])
        if evidencia not in ev:
            ev.append(evidencia)

    def tiene(self, cond, minimo=1.0):
        return self.peso.get(cond, 0) >= minimo

    def a_lista(self):
        return [{"condicion": c, "etiqueta": ETIQUETAS.get(c, c),
                 "peso": round(p, 1), "evidencia": self.evidencia.get(c, [])}
                for c, p in sorted(self.peso.items(), key=lambda x: -x[1])]


def perfil_clinico(clinica: dict) -> Perfil:
    """Lee todos los datos del paciente y arma el perfil."""
    c = clinica or {}
    pac = c.get("paciente") or {}
    ana = c.get("anamnesis") or {}
    esc = c.get("escalas") or {}
    acu = c.get("acustica") or {}
    rie = c.get("riesgoVocal") or c.get("riesgo_vocal") or {}
    rec = c.get("recomendacion") or {}
    p = Perfil()

    # Texto clínico libre (diagnóstico pesa más que el motivo).
    fuentes = [
        ("diagnóstico", ana.get("diagnostico_orl"), 2.0),
        # Peso bajo: lo redacta el motor a partir de estos mismos datos.
        ("diagnóstico funcional", rec.get("diagnostico_funcional_fonoaudiologico"), 0.5),
        ("motivo", ana.get("motivo_consulta"), 1.0),
        ("resumen clínico", ana.get("resumen_clinico"), 1.0),
        ("antecedentes", ana.get("antecedentes_salud"), 0.8),
    ]
    sint = ana.get("sintomas") or {}
    if isinstance(sint, dict):
        activos = [k.replace("_", " ") for k, v in sint.items()
                   if v not in (None, False, 0, "", "0", "no", "No", "nunca", "Nunca")]
        fuentes.append(("síntomas", ", ".join(activos), 1.0))
    elif isinstance(sint, (list, str)):
        fuentes.append(("síntomas", " ".join(sint) if isinstance(sint, list) else sint, 1.0))
    for nombre, texto, peso in fuentes:
        t = str(texto or "").lower()
        if not t.strip():
            continue
        for cond, pat in _PATRONES_TEXTO:
            m = re.search(pat, t)
            if m:
                p.sumar(cond, peso, f"{nombre}: «{m.group(0)}»")

    # Escalas perceptuales.
    grbas = esc.get("grbas") or {}
    rasati = esc.get("rasati") or {}
    s_tension = max(_num(grbas.get("S")) or 0, _num(rasati.get("T")) or 0)
    if s_tension >= 1:
        ev = f"tensión perceptual {int(s_tension)} (GRBAS S / RASATI T)"
        p.sumar("hiperfuncion", 1.0 * s_tension, ev)
        p.sumar("tension_muscular", 0.8 * s_tension, ev)
    soplo = max(_num(grbas.get("B")) or 0, _num(rasati.get("S")) or 0)
    if soplo >= 1:
        ev = f"soplosidad {int(soplo)} (GRBAS B / RASATI S)"
        p.sumar("soplo", 1.0 * soplo, ev)
        p.sumar("hipofuncion", 0.6 * soplo, ev)
    astenia = _num(grbas.get("A")) or 0
    if astenia >= 1:
        p.sumar("hipofuncion", 0.8 * astenia, f"astenia GRBAS A={int(astenia)}")
        p.sumar("fonastenia", 0.8 * astenia, f"astenia GRBAS A={int(astenia)}")
    aspereza = max(_num(grbas.get("R")) or 0, _num(rasati.get("R")) or 0,
                   _num(rasati.get("A")) or 0)
    if aspereza >= 2:
        p.sumar("rigidez", 0.5, f"ronquedad/aspereza {int(aspereza)}")

    # Tiempos máximos de fonación e índice S/Z.
    sexo = str(pac.get("sexo") or "").lower()
    minimo_tme = 20 if sexo.startswith("m") and not sexo.startswith("mu") else 15
    tme = _num(esc.get("tme_o")) or _num(esc.get("tme_segundos"))
    if tme and tme < minimo_tme:
        p.sumar("debilidad", 1.5, f"TME {tme:.0f} s (< {minimo_tme} s)")
        p.sumar("soplo", 0.5, f"TME {tme:.0f} s")
    so = _num(esc.get("indice_so"))
    if not so:
        ts, to = _num(esc.get("tme_s")), _num(esc.get("tme_o"))
        so = round(ts / to, 2) if ts and to else None
    if so and so > 1.2:
        p.sumar("hipofuncion", 1.5, f"índice S/Z {so} (> 1.2: cierre glótico incompleto)")
    elif so and so < 0.8:
        p.sumar("debilidad", 0.8, f"índice S/Z {so} (< 0.8: control del aire)")

    # Acústica.
    hnr, cpps = _num(acu.get("hnr_db")), _num(acu.get("cpps_db"))
    if hnr is not None and hnr < 18:
        p.sumar("soplo", 0.8, f"HNR {hnr:.1f} dB (< 18)")
    if cpps is not None and cpps < 14:
        p.sumar("soplo", 0.5, f"CPPS {cpps:.1f} dB")
    jitter = _num(acu.get("jitter_local_pct"))
    if jitter is not None and jitter > 1.04:
        p.sumar("rigidez", 0.3, f"jitter {jitter:.2f} %")

    # Impacto y demanda vocal.
    vhi = _num(esc.get("vhi10_score")) or _num(esc.get("vhi10_total"))
    if vhi is not None and vhi > 11:
        p.sumar("transferencia", 1.0, f"VHI-10 {vhi:.0f}/40 (> 11)")
        p.sumar("fonastenia", 0.4, f"VHI-10 {vhi:.0f}/40")
    demanda = _num(pac.get("demanda_vocal_horas"))
    if demanda is not None and demanda >= 4:
        p.sumar("docentes", 1.0, f"demanda vocal {demanda:.0f} h/día")
        p.sumar("transferencia", 0.6, f"demanda vocal {demanda:.0f} h/día")
    ocup = str(pac.get("ocupacion") or "").lower()
    for cond, pat in _PATRONES_OCUPACION:
        m = re.search(pat, ocup)
        if m:
            p.sumar(cond, 1.2, f"ocupación: {pac.get('ocupacion')}")
    riesgo = _num(rie.get("puntaje_total"))
    if riesgo is not None and riesgo > 60:
        p.sumar("docentes", 0.8, f"riesgo vocal {riesgo:.0f}/207")
    for f in (rie.get("factores_prioritarios") or [])[:12]:
        lab = str((f or {}).get("label") or "").lower()
        for cond, pat in _PATRONES_TEXTO:
            if re.search(pat, lab):
                p.sumar(cond, 0.6, f"riesgo vocal: {f.get('label')}")
    return p


def _condiciones_ejercicio(ex):
    return {_ALIAS_INDICACION.get(i, i) for i in (ex.get("indications") or [])}


def motivo_exclusion(ex, perfil: Perfil):
    """Texto si el ejercicio está contraindicado para el perfil, o None."""
    for tag in ex.get("contraindications") or []:
        tag = _ALIAS_INDICACION.get(tag, tag)
        if tag in _CONTRA_CRITICAS and perfil.tiene(tag):
            ev = "; ".join(perfil.evidencia.get(tag, [])[:2])
            return f"contraindicado con {ETIQUETAS.get(tag, tag)} ({ev})"
    return None


def puntaje(ex, perfil: Perfil):
    """Qué tan indicado está el ejercicio para este paciente. None = no
    corresponde (indicación específica que el paciente no tiene)."""
    conds = _condiciones_ejercicio(ex)
    coincide = [c for c in conds if c in perfil.peso]
    general = "general" in conds
    if not coincide and not general:
        return None, []
    total = sum(perfil.peso[c] for c in coincide) + (0.5 if general else 0)
    nivel = _DIFICULTAD.get(ex.get("difficulty"), 2)
    # Progresión: primero lo básico; lo avanzado solo con indicación clara.
    total += {1: 0.6, 2: 0.3, 3: 0.0}[nivel]
    if nivel == 3 and sum(perfil.peso[c] for c in coincide) < 2:
        return None, []
    return total, sorted(coincide, key=lambda c: -perfil.peso[c])


def _areas_activas(perfil: Perfil, seleccion_areas):
    """{area: motivo} y set de áreas prioritarias."""
    peso_area, por_que = {}, {}
    for cond, peso in sorted(perfil.peso.items(), key=lambda x: -x[1]):
        if peso < 1:
            continue
        for area in AREAS_POR_CONDICION.get(cond, []):
            peso_area[area] = peso_area.get(area, 0) + peso
            por_que.setdefault(area, []).append(ETIQUETAS.get(cond, cond))
    activas = {}
    for area in set(AREAS_BASE) | set(por_que) | set(seleccion_areas):
        if area in por_que:
            activas[area] = "Por " + ", ".join(por_que[area][:3]) + "."
        elif area in AREAS_BASE:
            activas[area] = AREAS_BASE[area]
        else:
            activas[area] = "Elegida por el profesional."
    # Prioritarias: las 2 áreas con más peso en el caso (si el peso es real).
    top = sorted(peso_area.items(), key=lambda x: -x[1])[:2]
    prioritarias = {a for a, w in top if w >= 3}
    return activas, prioritarias


def armar_plan(seleccion_ids, clinica, secciones=None, minimo=MINIMO_POR_AREA):
    """Plan del cuadernillo. Devuelve dict con ejercicios_ids (ordenados),
    áreas con su motivo, ejercicios agregados con su porqué, excluidos y
    el perfil clínico usado."""
    secciones = cargar_secciones(secciones)
    perfil = perfil_clinico(clinica)
    por_id, area_de = {}, {}
    for s in secciones:
        for e in s.get("exercises") or []:
            if e.get("id"):
                por_id[e["id"]] = e
                area_de[e["id"]] = s.get("id")
    seleccion = [i for i in dict.fromkeys(seleccion_ids or []) if i in por_id]
    sel_set = set(seleccion)

    activas, prioritarias = _areas_activas(perfil, {area_de[i] for i in seleccion})
    excluidos = []
    areas_out = []
    elegidos = []
    for s in secciones:
        area = s.get("id")
        if area not in activas:
            continue
        objetivo = MINIMO_AREA_PRIORITARIA if area in prioritarias else minimo
        objetivo = max(objetivo, minimo)
        items = []
        for i in seleccion:
            if area_de.get(i) == area:
                motivo = motivo_exclusion(por_id[i], perfil)
                items.append({"id": i, "name": por_id[i].get("name", i),
                              "origen": "profesional",
                              "motivo": "Elegido por el profesional.",
                              "alerta": motivo})
        candidatos = []
        for e in s.get("exercises") or []:
            if e["id"] in sel_set:
                continue
            mot = motivo_exclusion(e, perfil)
            if mot:
                excluidos.append({"id": e["id"], "name": e.get("name", e["id"]),
                                  "area": area, "motivo": mot})
                continue
            pts, por = puntaje(e, perfil)
            if pts is None:
                continue
            candidatos.append((pts, _DIFICULTAD.get(e.get("difficulty"), 2), e, por))
        candidatos.sort(key=lambda x: (-x[0], x[1]))
        for pts, _, e, por in candidatos:
            if len(items) >= objetivo:
                break
            if por:
                motivo = "Indicado por " + ", ".join(ETIQUETAS.get(c, c) for c in por[:3])
                ev = perfil.evidencia.get(por[0], [])[:2]
                if ev:
                    motivo += f" ({'; '.join(ev)})"
                motivo += "."
            else:
                motivo = "Variante de uso general para el área."
            items.append({"id": e["id"], "name": e.get("name", e["id"]),
                          "origen": "agregado", "motivo": motivo})
        # Áreas base sin variantes indicadas suficientes: se completan con
        # ejercicios seguros del área (no avanzados, no contraindicados).
        if len(items) < objetivo and area in AREAS_COMPLEMENTO:
            usados = {it["id"] for it in items}
            for e in s.get("exercises") or []:
                if len(items) >= objetivo:
                    break
                conds = _condiciones_ejercicio(e)
                if (e["id"] in usados or motivo_exclusion(e, perfil)
                        or _DIFICULTAD.get(e.get("difficulty"), 2) == 3
                        or conds <= _SOLO_ESPECIFICAS):
                    continue
                items.append({"id": e["id"], "name": e.get("name", e["id"]),
                              "origen": "agregado",
                              "motivo": "Variante complementaria del área (sin indicación "
                                        "específica para este caso)."})
        # Orden dentro del área: progresión de lo básico a lo avanzado.
        items.sort(key=lambda it: _DIFICULTAD.get(por_id[it["id"]].get("difficulty"), 2))
        faltan = max(0, objetivo - len(items))
        areas_out.append({
            "id": area, "nombre": AREAS.get(area, s.get("name", area)),
            "motivo": activas[area], "prioritaria": area in prioritarias,
            "objetivo": objetivo, "cantidad": len(items), "faltan": faltan,
            "aviso": (f"El banco no tiene más ejercicios indicados para este caso en "
                      f"«{AREAS.get(area, area)}»: faltan {faltan}. Podés sumar "
                      f"variantes al banco.") if faltan else "",
            "ejercicios": items,
        })
    orden = {a: n for n, a in enumerate(ORDEN_AREAS)}
    areas_out.sort(key=lambda a: orden.get(a["id"], len(ORDEN_AREAS)))
    for a in areas_out:
        elegidos.extend(it["id"] for it in a["ejercicios"])
    # Lo elegido que no pertenece a ninguna sección conocida queda al final.
    elegidos += [i for i in (seleccion_ids or []) if i not in elegidos and i not in por_id]
    return {
        "ejercicios_ids": elegidos,
        "areas": areas_out,
        "agregados": [it for a in areas_out for it in a["ejercicios"] if it["origen"] == "agregado"],
        "alertas": [{"id": it["id"], "name": it["name"], "motivo": it["alerta"]}
                    for a in areas_out for it in a["ejercicios"] if it.get("alerta")],
        "excluidos": excluidos,
        "perfil": perfil.a_lista(),
    }
