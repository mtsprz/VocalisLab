"""Criterios clínicos de referencia e interpretación integrada del paciente.

Reglas de oro (para que no haya malas lecturas):
- Cada valor se informa EXACTAMENTE como está guardado, con su fecha y su
  fuente (evaluación, autoevaluación del paciente, anamnesis, análisis).
- Las lecturas salen de reglas fijas con su referencia bibliográfica; el
  texto redactado después solo puede usar estos hallazgos (se verifica que
  no aparezcan números que no estén en los datos).
- Los cortes están todos acá, en un solo lugar, para revisarlos.

Escalas y direcciones:
- Autopercepción 0–10: 0 = muy mala, 10 = excelente (más alto = mejor).
- VHI-10 0–40 (Rosen y cols., 2004): más alto = mayor impacto. Corte de
  normalidad ≤ 11 (Arffa y cols., 2012).
- GRBAS (Hirano, 1981) y RASATI (Pinho y Pontes): cada parámetro 0–3
  (0 normal, 1 leve, 2 moderado, 3 severo). No se suman como porcentaje.
- Ficha de riesgo vocal /207: grupos ≤ 69, 70–138, ≥ 139.
"""
import re
from datetime import date

# ---------------------------------------------------------------- referencias
REF = {
    "autopercepcion": {"baja": 5, "fuente": "Escala 0–10 (0 = muy mala, 10 = excelente)"},
    "vhi10": {"corte": 11, "fuente": "VHI-10 (Rosen y cols., 2004); corte > 11 (Arffa y cols., 2012)"},
    "grbas": {"fuente": "GRBAS (Hirano, 1981): 0 normal · 1 leve · 2 moderado · 3 severo"},
    "rasati": {"fuente": "RASATI (Pinho y Pontes): 0 normal · 1 leve · 2 moderado · 3 severo"},
    "tmf": {"min_varon": 20, "min_mujer": 15, "marcado": 10,
            "fuente": "TMF vocal: varones ≥ 20 s, mujeres ≥ 15 s; < 10 s marcadamente reducido (Farías; Colton y Casper)"},
    "s_vocal": {"alto": 1.2, "bajo": 0.8,
                "fuente": "Cociente /s/ ÷ vocal sostenida: > 1,2 sugiere cierre glótico incompleto; < 0,8 control del flujo aéreo"},
    "jitter": {"corte": 1.04, "fuente": "Jitter local (Praat) > 1,04 %"},
    "shimmer": {"corte": 3.81, "fuente": "Shimmer local (Praat) > 3,81 %"},
    "hnr": {"corte": 18.0, "fuente": "HNR < 18 dB en vocal sostenida"},
    "cpps": {"corte": 14.0, "fuente": "CPPS < 14 dB en vocal sostenida (Praat)"},
    "avqi": {"corte": 2.95, "fuente": "AVQI ≥ 2,95 (Maryn y cols., 2010)"},
    "f0": {"varon": (85, 155), "mujer": (165, 255),
           "fuente": "F0 hablada adulta: varones 85–155 Hz, mujeres 165–255 Hz (Baken)"},
    "riesgo": {"g1": 69, "g2": 138, "fuente": "Ficha de riesgo vocal /207"},
    "demanda": {"alta": 4, "fuente": "Uso profesional de la voz ≥ 4 h/día"},
    "cambio_auto": 2,
    "cambio_vhi": 6,
}
NIVELES = ("normal", "leve", "moderado", "alterado", "sin_dato")
GRADO = {0: "normal", 1: "leve", 2: "moderado", 3: "severo"}


def _num(v):
    try:
        if v is None or v == "" or isinstance(v, bool):
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _f(v, dec=1):
    """Número tal cual, sin ceros de más (7 → '7', 7.25 → '7.25')."""
    if v is None:
        return "—"
    r = round(float(v), dec)
    return str(int(r)) if r == int(r) else str(r)


def _fecha(v):
    return str(v or "")[:10] or None


def _es_varon(sexo):
    s = str(sexo or "").strip().lower()
    return s.startswith(("m", "v", "h")) and not s.startswith("mu")


def _es_mujer(sexo):
    s = str(sexo or "").strip().lower()
    return s.startswith(("f", "mu"))


def _h(area, parametro, valor, unidad, fecha, fuente, referencia, lectura, nivel):
    return {"area": area, "parametro": parametro, "valor": valor, "unidad": unidad,
            "fecha": fecha, "fuente": fuente, "referencia": referencia,
            "lectura": lectura, "nivel": nivel}


# ------------------------------------------------------------- autopercepción
def autopercepciones(datos: dict) -> list:
    """Todas las autopercepciones con su fuente y fecha, sin transformar."""
    out = []
    for e in datos.get("evaluaciones") or []:
        v = _num(e.get("autopercepcion_vocal"))
        if v is not None:
            out.append({"valor": int(v) if v == int(v) else v, "fecha": _fecha(e.get("fecha")),
                        "fuente": "registrada en la evaluación"})
    for a in datos.get("autoevaluaciones") or []:
        v = _num(a.get("autopercepcion"))
        if v is not None:
            out.append({"valor": int(v) if v == int(v) else v, "fecha": _fecha(a.get("completada_at") or a.get("creada_at")),
                        "fuente": "respondida por el paciente (enlace)"})
    an = datos.get("anamnesis") or {}
    v = _num(an.get("autopercepcion_voz"))
    if v is not None:
        out.append({"valor": int(v) if v == int(v) else v, "fecha": _fecha(an.get("fecha")), "fuente": "anamnesis"})
    out.sort(key=lambda x: x["fecha"] or "")
    return out


def _dias(a, b):
    try:
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)
    except Exception:
        return None


# --------------------------------------------------------------- hallazgos
def hallazgos(datos: dict) -> dict:
    """Lectura clínica por reglas fijas de todos los datos de la ficha."""
    p = datos.get("paciente") or {}
    evals = sorted(datos.get("evaluaciones") or [], key=lambda e: str(e.get("fecha") or ""))
    acus = sorted(datos.get("analisis_acusticos") or [], key=lambda a: str(a.get("fecha") or ""))
    ev = evals[-1] if evals else {}
    ac = acus[-1] if acus else {}
    fev, fac = _fecha(ev.get("fecha")), _fecha(ac.get("fecha"))
    H, faltan, alertas = [], [], []

    # Autopercepción: la más reciente, con su fuente.
    aps = autopercepciones(datos)
    if aps:
        u = aps[-1]
        baja = u["valor"] <= REF["autopercepcion"]["baja"]
        H.append(_h("Autovaloración", "Autopercepción de la voz", u["valor"], "/10", u["fecha"], u["fuente"],
                    REF["autopercepcion"]["fuente"],
                    f"{_f(u['valor'])}/10: {'valoración baja de su voz' if baja else 'valoración conservada de su voz'}",
                    "alterado" if baja else "normal"))
        for x in aps[:-1]:
            d = _dias(x["fecha"], u["fecha"])
            if d is not None and d <= 30 and abs(x["valor"] - u["valor"]) >= REF["cambio_auto"]:
                alertas.append(f"Autopercepción distinta en fechas cercanas: {_f(x['valor'])}/10 ({x['fuente']}, {x['fecha']}) "
                               f"y {_f(u['valor'])}/10 ({u['fuente']}, {u['fecha']}). Confirmar con el paciente.")
    else:
        faltan.append("autopercepción")

    # VHI-10.
    vhi = _num(ev.get("vhi10_score"))
    fvhi, src_vhi = fev, "evaluación"
    auto_vhi = [a for a in (datos.get("autoevaluaciones") or []) if _num(a.get("vhi10_score")) is not None]
    if auto_vhi:
        ult = max(auto_vhi, key=lambda a: str(a.get("completada_at") or ""))
        if not fvhi or _fecha(ult.get("completada_at")) > fvhi:
            vhi, fvhi, src_vhi = _num(ult["vhi10_score"]), _fecha(ult.get("completada_at")), "respondido por el paciente (enlace)"
    if vhi is not None:
        alt = vhi > REF["vhi10"]["corte"]
        H.append(_h("Autovaloración", "VHI-10", int(vhi), "/40", fvhi, src_vhi, REF["vhi10"]["fuente"],
                    f"{_f(vhi)}/40: {'impacto de la voz en su vida por encima de lo esperado' if alt else 'dentro de lo esperado'}",
                    "alterado" if alt else "normal"))
    else:
        faltan.append("VHI-10")

    # GRBAS: se informa el grado general y cada parámetro ≥ 1.
    g = ev.get("grbas") or {}
    if isinstance(g, dict) and any(_num(g.get(k)) is not None for k in "GRBAS"):
        partes = {k: int(_num(g.get(k))) for k in "GRBAS" if _num(g.get(k)) is not None}
        G = partes.get("G", max(partes.values()))
        nombres = {"R": "ronquedad", "B": "soplosidad", "A": "astenia", "S": "tensión"}
        detalle = ", ".join(f"{nombres[k]} {GRADO.get(v, v)} ({k}{v})" for k, v in partes.items() if k != "G" and v >= 1)
        H.append(_h("Percepción", "GRBAS", " ".join(f"{k}{v}" for k, v in partes.items()), "", fev, "evaluación",
                    REF["grbas"]["fuente"],
                    f"Grado general {GRADO.get(G, G)} (G{G})" + (f"; {detalle}" if detalle else ""),
                    {0: "normal", 1: "leve", 2: "moderado"}.get(G, "alterado")))
    else:
        faltan.append("GRBAS")
    r = ev.get("rasati") or {}
    if isinstance(r, dict) and any(_num(v) is not None for v in r.values()):
        partes = {k: int(_num(v)) for k, v in r.items() if _num(v) is not None}
        mx = max(partes.values())
        H.append(_h("Percepción", "RASATI", " ".join(f"{k}{v}" for k, v in partes.items()), "", fev, "evaluación",
                    REF["rasati"]["fuente"], f"Grado máximo {GRADO.get(mx, mx)}",
                    {0: "normal", 1: "leve", 2: "moderado"}.get(mx, "alterado")))

    # Tiempos y cociente.
    tmf = _num(ev.get("tme_o"))
    if tmf:
        varon, mujer = _es_varon(p.get("sexo")), _es_mujer(p.get("sexo"))
        minimo = REF["tmf"]["min_varon"] if varon else REF["tmf"]["min_mujer"] if mujer else None
        if tmf < REF["tmf"]["marcado"]:
            lect, niv = "marcadamente reducido", "alterado"
        elif minimo and tmf < minimo:
            lect, niv = f"reducido para {'varón' if varon else 'mujer'} (mínimo {minimo} s)", "leve"
        elif minimo:
            lect, niv = "dentro de lo esperado", "normal"
        else:
            lect, niv = "sin sexo cargado: no se puede comparar con la referencia", "sin_dato"
        H.append(_h("Aerodinámica", "TMF vocal sostenida", _f(tmf), "s", fev, "evaluación", REF["tmf"]["fuente"],
                    f"{_f(tmf)} s: {lect}", niv))
    else:
        faltan.append("tiempo máximo de fonación")
    ts = _num(ev.get("tme_s"))
    sv = _num(ev.get("indice_so")) or (round(ts / tmf, 2) if ts and tmf else None)
    if sv:
        if sv > REF["s_vocal"]["alto"]:
            lect, niv = "elevado: sugiere cierre glótico incompleto", "alterado"
        elif sv < REF["s_vocal"]["bajo"]:
            lect, niv = "bajo: revisar control del flujo aéreo", "leve"
        else:
            lect, niv = "dentro de lo esperado", "normal"
        H.append(_h("Aerodinámica", "Cociente /s/ ÷ vocal", _f(sv, 2), "", fev, "evaluación",
                    REF["s_vocal"]["fuente"], f"{_f(sv, 2)}: {lect}", niv))

    # Acústica (vocal sostenida).
    if ac:
        for clave, nombre, unidad, ref, mayor_es_peor in (
                ("jitter_local_pct", "Jitter local", "%", "jitter", True),
                ("shimmer_local_pct", "Shimmer local", "%", "shimmer", True),
                ("hnr_db", "HNR", "dB", "hnr", False),
                ("cpps_db", "CPPS", "dB", "cpps", False),
                ("avqi", "AVQI", "", "avqi", True)):
            v = _num(ac.get(clave))
            if v is None:
                continue
            corte = REF[ref]["corte"]
            alt = v >= corte if ref == "avqi" else (v > corte if mayor_es_peor else v < corte)
            H.append(_h("Acústica", nombre, _f(v, 2), unidad, fac, "análisis acústico", REF[ref]["fuente"],
                        f"{_f(v, 2)} {unidad}: {'fuera del rango de referencia' if alt else 'dentro del rango de referencia'}".replace("  ", " "),
                        "alterado" if alt else "normal"))
    else:
        faltan.append("análisis acústico")

    # F0 hablada (solo mediciones conversacionales reales, no vocal sostenida).
    f0s = datos.get("f0_conversacional") or []
    if f0s:
        u = f0s[-1]
        v = _num(u.get("f0_mediana_hz"))
        rango = REF["f0"]["varon"] if _es_varon(p.get("sexo")) else REF["f0"]["mujer"] if _es_mujer(p.get("sexo")) else None
        if v is not None:
            if rango:
                fuera = not (rango[0] <= v <= rango[1])
                lect = f"{_f(v, 0)} Hz: {'fuera' if fuera else 'dentro'} del rango habitual ({rango[0]}–{rango[1]} Hz)"
                niv = "leve" if fuera else "normal"
            else:
                lect, niv = f"{_f(v, 0)} Hz (sin sexo cargado para comparar)", "sin_dato"
            H.append(_h("Acústica", "F0 hablada (conversación)", _f(v, 0), "Hz", _fecha(u.get("fecha")),
                        "medición en conversación", REF["f0"]["fuente"], lect, niv))

    # Riesgo y demanda vocal.
    rv = _num(ev.get("riesgo_vocal_score"))
    if rv is not None:
        grupo = 1 if rv <= REF["riesgo"]["g1"] else 2 if rv <= REF["riesgo"]["g2"] else 3
        H.append(_h("Riesgo y uso vocal", "Riesgo vocal", int(rv), "/207", fev, "evaluación", REF["riesgo"]["fuente"],
                    f"{_f(rv)}/207: grupo {grupo} ({['bajo', 'moderado', 'alto'][grupo - 1]} riesgo)",
                    ["normal", "moderado", "alterado"][grupo - 1]))
    else:
        faltan.append("ficha de riesgo vocal")
    dem = _num(p.get("demanda_vocal_horas"))
    if dem is not None:
        alta = dem >= REF["demanda"]["alta"]
        H.append(_h("Riesgo y uso vocal", "Uso de la voz", _f(dem), "h/día", None, "datos del paciente",
                    REF["demanda"]["fuente"],
                    f"{_f(dem)} h/día{' (' + p['ocupacion'] + ')' if p.get('ocupacion') else ''}: "
                    f"{'alta demanda vocal' if alta else 'demanda vocal moderada'}",
                    "moderado" if alta else "normal"))
    else:
        faltan.append("horas de uso de la voz")

    return {"hallazgos": H, "patrones": patrones(H, datos, evals), "alertas": alertas, "faltan": faltan,
            "referencias": {k: v["fuente"] for k, v in REF.items() if isinstance(v, dict) and "fuente" in v}}


def _get(H, parametro):
    return next((h for h in H if h["parametro"] == parametro), None)


def patrones(H, datos, evals) -> list:
    """Cruces de datos: solo cuando hay datos que los sostienen."""
    out = []
    an = datos.get("anamnesis") or {}
    diag = str(an.get("diagnostico_orl") or "").strip()
    grbas = (evals[-1].get("grbas") if evals else None) or {}
    B, S = _num(grbas.get("B")) or 0, _num(grbas.get("S")) or 0
    sv, hnr, cpps = _get(H, "Cociente /s/ ÷ vocal"), _get(H, "HNR"), _get(H, "CPPS")
    vhi, auto = _get(H, "VHI-10"), _get(H, "Autopercepción de la voz")
    acus_alt = [h for h in H if h["area"] == "Acústica" and h["nivel"] == "alterado"]

    ev = []
    if B >= 1:
        ev.append(f"soplosidad B{int(B)}")
    if sv and sv["nivel"] == "alterado":
        ev.append(f"cociente /s/ ÷ vocal {sv['valor']}")
    if hnr and hnr["nivel"] == "alterado":
        ev.append(f"HNR {hnr['valor']} dB")
    if cpps and cpps["nivel"] == "alterado":
        ev.append(f"CPPS {cpps['valor']} dB")
    if len(ev) >= 2:
        out.append({"patron": "Compatible con cierre glótico incompleto / componente hipofuncional",
                    "evidencia": ev, "sugerencia": "Correlacionar con el informe ORL (cierre glótico en la estroboscopía)."})

    ev = []
    if S >= 1:
        ev.append(f"tensión S{int(S)}")
    if re.search(r"hiperfunc|tensional|\bdmt\b|m[uú]sculo tens", diag.lower()):
        ev.append(f"diagnóstico: {diag}")
    if _get(H, "Uso de la voz") and _get(H, "Uso de la voz")["nivel"] == "moderado":
        ev.append(f"uso de la voz {_get(H, 'Uso de la voz')['valor']} h/día")
    if len(ev) >= 2:
        out.append({"patron": "Componente hiperfuncional / tensional", "evidencia": ev,
                    "sugerencia": "Priorizar relajación, SOVT y equilibrio de la musculatura; evitar empuje."})

    if vhi and vhi["nivel"] == "alterado" and not acus_alt and _get(H, "Jitter local"):
        out.append({"patron": "El impacto que percibe el paciente es mayor que lo que muestra la acústica",
                    "evidencia": [f"VHI-10 {vhi['valor']}/40", "acústica dentro de referencia"],
                    "sugerencia": "Explorar demanda, contexto laboral y componente emocional; la acústica en vocal sostenida no refleja todo el uso real."})
    if vhi and vhi["nivel"] == "normal" and len(acus_alt) >= 2:
        out.append({"patron": "Alteración medida con baja percepción del problema",
                    "evidencia": [f"VHI-10 {vhi['valor']}/40"] + [f"{h['parametro']} {h['valor']}" for h in acus_alt[:3]],
                    "sugerencia": "Trabajar conciencia vocal y adherencia (el paciente puede no registrar el problema)."})
    if auto and vhi and auto["nivel"] == "normal" and vhi["nivel"] == "alterado":
        out.append({"patron": "Autovaloración y VHI-10 no coinciden",
                    "evidencia": [f"autopercepción {auto['valor']}/10", f"VHI-10 {vhi['valor']}/40"],
                    "sugerencia": "Repreguntar: la voz puede sonar bien pero costarle (fatiga, esfuerzo)."})

    rv, uso = _get(H, "Riesgo vocal"), _get(H, "Uso de la voz")
    if rv and uso and rv["nivel"] in ("moderado", "alterado") and uso["nivel"] == "moderado":
        out.append({"patron": "Carga vocal elevada", "evidencia": [f"riesgo vocal {rv['valor']}/207", f"{uso['valor']} h/día"],
                    "sugerencia": "Higiene y economía vocal, pausas y amplificación si corresponde."})

    # Evolución (primera vs. última evaluación).
    if len(evals) >= 2:
        a, b = evals[0], evals[-1]
        cambios = []
        va, vb = _num(a.get("vhi10_score")), _num(b.get("vhi10_score"))
        if va is not None and vb is not None and abs(vb - va) >= REF["cambio_vhi"]:
            cambios.append(f"VHI-10 {_f(va)} → {_f(vb)} ({'mejora' if vb < va else 'empeora'})")
        aa, ab = _num(a.get("autopercepcion_vocal")), _num(b.get("autopercepcion_vocal"))
        if aa is not None and ab is not None and abs(ab - aa) >= REF["cambio_auto"]:
            cambios.append(f"autopercepción {_f(aa)} → {_f(ab)} ({'mejora' if ab > aa else 'empeora'})")
        if cambios:
            out.append({"patron": f"Evolución entre {_fecha(a.get('fecha'))} y {_fecha(b.get('fecha'))}",
                        "evidencia": cambios, "sugerencia": "Reevaluar el plan según la dirección del cambio."})
    return out


# ---------------------------------------------------- control del texto redactado
_NUM = re.compile(r"(?<![\w/])(\d+(?:[.,]\d+)?)")


def numeros_permitidos(lectura: dict, datos: dict) -> set:
    import json
    texto = json.dumps(lectura, ensure_ascii=False, default=str) + json.dumps(
        {k: datos.get(k) for k in ("paciente", "anamnesis")}, ensure_ascii=False, default=str)
    nums = set()
    for m in _NUM.findall(texto):
        n = m.replace(",", ".")
        nums.add(n)
        try:
            f = float(n)
            nums.update({_f(f, 0), _f(f, 1), _f(f, 2)})
        except ValueError:
            pass
    nums.update(str(i) for i in range(0, 4))  # grados 0–3, ordinales
    return nums


def verificar_texto(texto: str, permitidos: set) -> tuple:
    """Quita las oraciones con números que no están en los datos."""
    limpio, quitadas = [], []
    for linea in texto.splitlines():
        oraciones = re.split(r"(?<=[.;])\s+", linea)
        buenas = []
        for o in oraciones:
            ajenos = [n for n in _NUM.findall(o) if n.replace(",", ".") not in permitidos
                      and not re.fullmatch(r"(19|20)\d\d", n)]
            if ajenos:
                quitadas.append(o.strip())
            else:
                buenas.append(o)
        if buenas or not linea.strip():
            limpio.append(" ".join(buenas))
    return "\n".join(limpio).strip(), quitadas


# ------------------------------------------------------- situación quirúrgica
ETAPAS = {
    "postquirurgica": "Postquirúrgica",
    "prequirurgica": "Prequirúrgica (cirugía indicada o programada)",
    "a_definir": "Lesión que puede requerir cirugía: conducta a definir con el ORL",
    "no_quirurgica": "Sin indicación quirúrgica registrada (tratamiento conservador)",
    "sin_datos": "Sin datos suficientes",
}
_PAT_POST = (r"post\s*-?\s*(operatori|quir[uú]rg|cirug)|posoperatori|se (lo |la )?oper[oó]|fue operad|"
             r"operad[oa] (de|el|en)|cirug[ií]a (realizada|previa|reciente)|microcirug[ií]a (realizada|el|en)|"
             r"ex[ée]resis (realizada|de)|cordectom[ií]a|tiroidectom[ií]a|fonocirug[ií]a realizada|"
             r"intervenid[oa] quir")
_PAT_PRE = (r"pre\s*-?\s*quir|indicaci[oó]n quir[uú]rg|se indica (cirug|microcirug)|candidat[oa] a (cirug|microcirug)|"
            r"cirug[ií]a (programada|indicada|pendiente)|microcirug[ií]a (programada|indicada|pendiente)|"
            r"turno (de|para) cirug|evaluar (cirug|resoluci[oó]n quir)|resoluci[oó]n quir[uú]rg")
_PAT_LESION = (r"p[oó]lipo|quiste|edema de reinke|reinke|papiloma|leucoplas|granuloma|sulcus|"
               r"lesi[oó]n (de masa|exof[ií]tica)|exof[ií]tic|hemorragia (cordal|submucosa)|ectasia|varice")
_PAT_NEG = r"\b(sin|no|descarta|descartad[oa]|niega)\b[^.;\n]{0,25}$"


def _textos_clinicos(datos: dict) -> list:
    an = datos.get("anamnesis") or {}
    out = [("diagnóstico ORL", an.get("diagnostico_orl"), an.get("fecha")),
           ("motivo de consulta", an.get("motivo_consulta"), an.get("fecha")),
           ("antecedentes", an.get("antecedentes_salud"), an.get("fecha")),
           ("resumen clínico", an.get("resumen_clinico"), an.get("fecha"))]
    for i in datos.get("informes_orl") or []:
        de = i.get("datos_estructurados") if isinstance(i.get("datos_estructurados"), dict) else {}
        for k in ("diagnostico_principal", "texto_corregido", "hallazgos_estructurales", "hallazgos_funcionales",
                  "recomendaciones", "conducta", "texto_transcrito_crudo"):
            v = i.get(k) or de.get(k)
            if v:
                out.append((f"informe ORL {i.get('fecha_informe') or _fecha(i.get('fecha')) or ''}".strip(),
                            v if isinstance(v, str) else str(v), i.get("fecha")))
    for e in datos.get("evaluaciones") or []:
        if e.get("observaciones"):
            out.append((f"observaciones {_fecha(e.get('fecha'))}", e["observaciones"], e.get("fecha")))
    for a in datos.get("archivos") or []:
        t = " ".join(str(a.get(k) or "") for k in ("titulo", "notas"))
        if t.strip():
            out.append((f"archivo {_fecha(a.get('fecha'))}", t, a.get("fecha")))
    return [(n, str(t), f) for n, t, f in out if t and str(t).strip()]


def _buscar(pat, texto):
    for m in re.finditer(pat, texto, flags=re.IGNORECASE):
        antes = texto[max(0, m.start() - 40):m.start()]
        if re.search(_PAT_NEG, antes, flags=re.IGNORECASE):
            continue  # "sin indicación quirúrgica", "no se operó"…
        ini, fin = max(0, m.start() - 60), min(len(texto), m.end() + 60)
        return "…" + texto[ini:fin].replace("\n", " ").strip() + "…"
    return None


def situacion_quirurgica(datos: dict, manual: str = None) -> dict:
    """Etapa quirúrgica deducida de TODOS los textos, con la frase que la
    sostiene. El profesional puede fijarla a mano (manual manda)."""
    evid = {"postquirurgica": [], "prequirurgica": [], "a_definir": []}
    for nombre, texto, fecha in _textos_clinicos(datos):
        for etapa, pat in (("postquirurgica", _PAT_POST), ("prequirurgica", _PAT_PRE), ("a_definir", _PAT_LESION)):
            frag = _buscar(pat, texto)
            if frag:
                evid[etapa].append({"fuente": nombre, "fecha": _fecha(fecha), "texto": frag})
    if manual in ETAPAS:
        etapa, origen = manual, "indicada por el profesional"
    elif evid["postquirurgica"]:
        etapa, origen = "postquirurgica", "deducida de los registros"
    elif evid["prequirurgica"]:
        etapa, origen = "prequirurgica", "deducida de los registros"
    elif evid["a_definir"]:
        etapa, origen = "a_definir", "deducida de los registros"
    elif (datos.get("anamnesis") or {}).get("diagnostico_orl") or datos.get("informes_orl"):
        etapa, origen = "no_quirurgica", "deducida de los registros"
    else:
        etapa, origen = "sin_datos", "sin diagnóstico ORL cargado"
    return {"etapa": etapa, "etiqueta": ETAPAS[etapa], "origen": origen,
            "evidencia": evid.get(etapa, []) if etapa in evid else [],
            "otras": {k: v for k, v in evid.items() if k != etapa and v}}
