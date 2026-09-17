"""VocalisLab — Validadores del cuadernillo (CUADERNILLO_SPEC.md §6, §8).

- ILUSTRACION_MAP: familia -> (archivo SVG, caption fijo). La ilustración se
  asigna por FAMILIA, nunca por ejercicio individual.
- validar_familias(ejercicios): cada ejercicio debe traer familia conocida y,
  si trae override `ilustracion`, debe pertenecer a su familia.
- lint_catalog(bank): reporta (no reescribe) hallazgos de texto en el catálogo
  y KB: espacios dobles, fragmentos pegados, paréntesis sin cerrar, palabras
  repetidas, consignas en infinitivo.
- svg_text_boxes(path): bboxes aproximadas de los <text> de un SVG para t8.
"""
import re
import xml.etree.ElementTree as ET

# Familia -> (archivo svg, caption fijo de §6)
ILUSTRACION_MAP = {
    "respiracion": ("ciclo_respiratorio.svg", "Así se mueve tu aire"),
    "masaje": ("puntos_shiatsu.svg", "Dónde presionar"),
    "postural": ("esquema_hombros.svg", "Cómo moverte"),
    "articulacion": ("boca_vocales.svg", "Cómo articulás"),
    "tonal": ("sirena.svg", "Así suena tu voz"),
    "sovte": ("m_vocales.svg", "Así vibrás"),
    "habla": ("aros_distancia.svg", "Así llega tu voz"),
    "rutina": ("secuencia_pasos.svg", "El orden de tu rutina"),
    "higiene": (None, ""),
}

# Primitivas permitidas por familia (vocabulario de §6; el subconjunto en
# svg/ cubre el seed de mapeo; tabla_registro se renderiza como tabla HTML).
PRIMITIVAS_POR_FAMILIA = {
    "respiracion": {"ciclo_respiratorio.svg", "franja_tiempos.svg"},
    "masaje": {"puntos_shiatsu.svg", "zona_cuello.svg"},
    "postural": {"esquema_hombros.svg", "flechas_cervicales.svg"},
    "articulacion": {"boca_vocales.svg", "salmodia.svg"},
    "tonal": {"curva_f0_asc.svg", "curva_f0_desc.svg", "sirena.svg",
              "escala_3ra.svg", "escala_5ta_8va.svg"},
    "sovte": {"pajilla.svg", "trill_labios.svg", "m_vocales.svg"},
    "habla": {"aros_distancia.svg"},
    "rutina": {"secuencia_pasos.svg"},
    "higiene": set(),
}

# Componentes no-SVG permitidos por familia (se renderizan como HTML).
TABLA_COMPONENTES = {"habla": {"tabla_registro"}}

# Override de primitiva por código de ejercicio (seed de §6; el catálogo manda).
ILUSTRACION_OVERRIDE = {
    "expansion_costo_lateral": "franja_tiempos.svg",   # 9.2
    "masaje_laringeo": "zona_cuello.svg",              # 8.1
    "descenso_laringeo": "zona_cuello.svg",            # 8.2
    "popote_aire": "escala_3ra.svg",                   # 10.3
    "glissandos": "curva_f0_asc.svg",                  # 10.7
}

FAMILIAS = set(PRIMITIVAS_POR_FAMILIA)


def ilustracion_para(familia: str, codigo: str = "", override: str = "") -> tuple:
    """Devuelve (archivo_svg|None, caption). Override validado contra familia."""
    if familia not in FAMILIAS:
        raise ValueError(f"Familia desconocida: {familia!r}")
    if override:
        permitidas = PRIMITIVAS_POR_FAMILIA[familia]
        if override not in permitidas:
            raise ValueError(
                f"Ilustración {override!r} no pertenece a la familia {familia!r}")
        caption = ILUSTRACION_MAP[familia][1]
        return override, caption
    if codigo and codigo in ILUSTRACION_OVERRIDE:
        return ILUSTRACION_OVERRIDE[codigo], ILUSTRACION_MAP[familia][1]
    return ILUSTRACION_MAP[familia]


def validar_familias(ejercicios: list) -> list:
    """Valida familia + override de cada ejercicio. Devuelve lista de errores."""
    errores = []
    for i, ex in enumerate(ejercicios or []):
        fam = (ex.get("familia") or "").strip()
        if not fam:
            errores.append(f"ejercicios[{i}]: falta 'familia' (requerido)")
            continue
        if fam not in FAMILIAS:
            errores.append(f"ejercicios[{i}]: familia desconocida {fam!r}")
            continue
        ov = (ex.get("ilustracion") or "").strip()
        if ov and ov not in PRIMITIVAS_POR_FAMILIA[fam] \
                and ov not in TABLA_COMPONENTES.get(fam, set()):
            errores.append(
                f"ejercicios[{i}]: ilustración {ov!r} no pertenece a {fam!r}")
    return errores


# ─── Lint de texto (reporta, no reescribe) ────────────────────────────

_REPETIDA_ALLOW = {"hu", "ha", "m", "u", "i", "e", "o", "a", "do", "mi",
                   "sol", "si", "la", "el"}


def _revisar_texto(texto: str, donde: str, out: list):
    if not isinstance(texto, str) or not texto.strip():
        return
    if "  " in texto:
        out.append(f"{donde}: espacios dobles")
    if re.search(r"\)[a-záéíóúñ]", texto):
        out.append(f"{donde}: fragmento pegado tipo ')x'")
    if texto.count("(") != texto.count(")"):
        out.append(f"{donde}: paréntesis sin cerrar")
    for m in re.finditer(r"\b([A-Za-zÁÉÍÓÚáéíóúñÑ]{3,}) \1\b", texto,
                         flags=re.IGNORECASE):
        if m.group(1).lower() not in _REPETIDA_ALLOW:
            out.append(f"{donde}: palabra repetida {m.group(0)!r}")


def lint_consigna_persona(consigna: str) -> str:
    """'infinitivo' si la consigna arranca en infinitivo, 'primera' si en 1ª
    persona, '?' si no se puede determinar. Heurística, solo para reporte."""
    if not consigna or not consigna.strip():
        return "?"
    primera = re.sub(r"^[\d.\s\-–—a-zA-Z]\)?\s*", "", consigna.strip())
    tok = re.match(r"([A-Za-zÁÉÍÓÚáéíóúñÑ]+)", primera)
    if not tok:
        return "?"
    w = tok.group(1).lower()
    if re.match(r"^[a-záéíóúñ]+(ar|er|ir)(se|me|nos|te|les?)?$", w):
        return "infinitivo"
    return "primera"


def lint_catalog(bank: dict) -> list:
    """Aplica el lint de §8.6 al catálogo. Devuelve lista de hallazgos."""
    out = []
    for s in (bank or {}).get("sections", []):
        for e in s.get("exercises", []):
            base = f"{e.get('id', '?')}"
            _revisar_texto(e.get("name", ""), base + ".name", out)
            _revisar_texto(e.get("description", ""), base + ".description", out)
            for j, st in enumerate(e.get("steps", []) or []):
                _revisar_texto(st, f"{base}.steps[{j}]", out)
                if lint_consigna_persona(st) == "infinitivo":
                    out.append(f"{base}.steps[{j}]: consigna en infinitivo "
                               f"(requiere aprobación profesional para 1ª persona)")
    return out


# ─── Bboxes de SVG (t8) ───────────────────────────────────────────────

def svg_text_boxes(path: str, view_w: float = 240.0,
                   view_h: float = 160.0) -> tuple:
    """Bboxes aproximadas (x, y, w, h) de cada <text> del SVG.

    y en SVG crece hacia abajo: bbox = (x, y - size, w, size).
    Devuelve (boxes, errores) donde errores lista textos fuera del viewBox.
    Ancho aprox: 0.6 * font-size por caracter.
    """
    tree = ET.parse(path)
    root = tree.getroot()
    boxes = []
    errores = []
    for el in root.iter():
        if not el.tag.endswith("text"):
            continue
        txt = "".join(el.itertext()).strip()
        if not txt:
            continue
        try:
            x = float(el.get("x", "0"))
            y = float(el.get("y", "0"))
            size = float(el.get("font-size", "10"))
        except ValueError:
            errores.append(f"texto con coordenadas inválidas: {txt!r}")
            continue
        w = len(txt) * 0.6 * size
        anchor = (el.get("text-anchor", "start") or "start").strip()
        x0 = x - w if anchor == "end" else (x - w / 2 if anchor == "middle"
                                            else x)
        box = (x0, y - size, w, size)
        boxes.append((txt, box))
        if x0 < 0 or y - size < 0 or x0 + w > view_w or y > view_h:
            errores.append(f"texto fuera de viewBox: {txt!r}")
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            (_, (x1, y1, w1, h1)) = boxes[i]
            (_, (x2, y2, w2, h2)) = boxes[j]
            if x1 < x2 + w2 and x2 < x1 + w1 and y1 < y2 + h2 and y2 < y1 + h1:
                errores.append(
                    f"textos solapados: {boxes[i][0]!r} / {boxes[j][0]!r}")
    return boxes, errores
