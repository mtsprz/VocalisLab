"""VocalisLab Pro — Motor de mediación universal de prompts clínicos.

Toda descripción de maniobra o ejercicio fonoaudiológico (TVSO, terapia
manual, postura, resonancia, articulación o atlas anatómico) pasa por este
pipeline ANTES de llegar a cualquier API de generación (Cloudflare/Pixazo/
Gemini/SDXL). Prohibido enviar prompts libres sin sanitización clínica.

Arquitectura en 4 capas:
    [Categoría del ejercicio] + [Detalle específico] +
    [Capa de seguridad clínica] + [Calidad y estilo visual]

Cada categoría aporta sus reglas de prompt obligatorias y su negative
prompt integrado. El clasificador detecta la categoría por keywords ES/EN;
si no hay coincidencias se usa GENERAL (clínico neutro).
"""

import unicodedata

# ─── Taxonomía de maniobras ──────────────────────────────────────────

CATEGORIAS = {
    "TVSO": {
        "label": "TVSO y dispositivos",
        "reglas": ("flexible silicone tube entering the container from above, "
                   "tube tip shallowly submerged 1-2 cm below the water surface, "
                   "realistic bubbles, natural hand grip holding the glass at rest "
                   "on a desk, correct object physics, no floating objects"),
        "negativo": ("floating test tube, laboratory equipment, submerged sealed "
                     "tube, naked torso, 6 fingers, tube floating in water"),
        "keywords": ["tubo", "tube", "laxvox", "lax vox", "titze", "vaso",
                     "burbuj", "bubbl", "pajita", "popote", "sorbete", "straw",
                     "agua", "water", "resistencia", "soplo", "blow",
                     "botella", "bottle", "copa", "tvso", "semioclu",
                     "flauta", "flute", "mascarilla", "mask"],
    },
    "MANUAL_THERAPY": {
        "label": "Terapia manual / Palpación",
        "reglas": ("non-invasive external physical therapy contact, hands gently "
                   "touching intact skin on the outer neck and jaw surface, fully "
                   "clothed person, no internal anatomy visible, calm clinical setting"),
        "negativo": ("dissection, internal organs, open skin, surgery, blood, "
                     "extra fingers, distorted hands, naked torso, surgical tools"),
        "keywords": ["masaje", "massage", "palpaci", "palpat",
                     "cuello", "neck", "cervical", "mandibul", "jaw",
                     "descompresi", "decompress", "descenso laringeo",
                     "descenso", "shiatsu", "aronson", "roy",
                     "manual", "hombro", "shoulder", "trapecio", "digito",
                     "presion", "pressure", "estiramiento cervical", "relajacion"],
    },
    "ANATOMY": {
        "label": "Diagrama anatómico 3D",
        "reglas": ("clean 3D digital medical atlas render, isolated anatomical "
                   "model of the larynx and vocal folds, educational diagram, "
                   "pure white background, no human hands, no real skin, "
                   "no body context"),
        "negativo": ("human hands, real skin, blood, surgical tools, realistic "
                     "body context, photograph of a person, endoscopic gore"),
        "keywords": ["atlas", "diagrama", "diagram", "anatom", "laringoscop",
                     "endoscop", "tracto vocal", "vocal tract", "cuerdas vocales",
                     "vocal folds", "vocal cords", "cricotiroide", "tiroides",
                     "epiglotis", "aritenoides", "glotis", "corte coronal",
                     "esquema"],
    },
    "RESONANCE": {
        "label": "Resonancia y articulación",
        "reglas": ("close-up of a face in side profile, relaxed jaw and facial "
                   "muscles, natural closed-lip posture or gentle vowel "
                   "articulation, subtle acoustic highlight on the facial mask "
                   "and lips area"),
        "negativo": ("exaggerated face, medical mask, interior mouth view with "
                     "hands, distorted lips, open screaming mouth, instruments "
                     "inside mouth"),
        "keywords": ["humming", "/m/", "resonan", "nasal", "mascara facial",
                     "mascara", "colocacion", "articulaci", "vocales", "vowels",
                     "frases", "proyecci", "anterior", "labios", "lips",
                     "boca", "mouth", "tarareo", "nidada", "brillantez"],
    },
    "POSTURE": {
        "label": "Postura y biomecánica",
        "reglas": ("medium or full-body view of a standing or sitting person, "
                   "neutral everyday clothing, neutral spinal alignment, clear "
                   "biomechanical posture, clean studio background"),
        "negativo": ("floating limbs, bad posture, cropped head, unnatural "
                     "angles, contortionist, naked torso"),
        "keywords": ["postura", "posture", "respiraci", "breathing", "diafragma",
                     "diaphragm", "costo", "abdominal", "expansion", "apoyo",
                     "alineaci", "alignment", "biomecanica", "relajacion corporal",
                     "bostezo", "yawn", "tronco", "torso", "pélvico", "pelvico",
                     "sedestaci", "bipedo"],
    },
    "GENERAL": {
        "label": "Ejercicio clínico general",
        "reglas": ("person demonstrating a speech therapy exercise in a clinical "
                   "setting, natural posture, fully clothed"),
        "negativo": ("surgery, blood, naked torso, distorted anatomy"),
        "keywords": [],
    },
}

# Desempate cuando dos categorías puntúan igual (más específico primero).
_PRIORIDAD = ["TVSO", "MANUAL_THERAPY", "ANATOMY", "RESONANCE", "POSTURE"]

# ─── Capas globales ──────────────────────────────────────────────────

CAPA_SEGURIDAD = ("clinical demonstration, fully clothed person, professional "
                  "medical environment, bright studio lighting")
CAPA_ANATOMIA = ("anatomically correct hands with exactly 5 fingers, intact "
                 "skin, clear physical boundaries between body parts")
CAPA_CALIDAD_REALISTA = ("photorealistic 8k, sharp focus, single centered "
                         "subject, no text, no letters, no watermark, no logo")
CAPA_CALIDAD_LINEA = ("minimalist 2D medical line art, clean black strokes on "
                      "white background, no text, no letters, no shading, "
                      "no colors")
NEGATIVO_BASE = ("extra fingers, deformed hands, missing joints, open neck, "
                 "surgical cut, blood, low quality, blurred, collage, split image")


def _norm(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(texto or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def clasificar_maniobra(texto: str) -> str:
    """Devuelve la categoría (clave de CATEGORIAS) por scoring de keywords.
    Sin coincidencias → GENERAL."""
    t = _norm(texto)
    if not t.strip():
        return "GENERAL"
    mejor, mejor_pts = "GENERAL", 0
    for cat in _PRIORIDAD:
        pts = sum(1 for kw in CATEGORIAS[cat]["keywords"] if _norm(kw) in t)
        if pts > mejor_pts:
            mejor, mejor_pts = cat, pts
    return mejor


def mediar_prompt(detalle: str, categoria: str = "", estilo: str = "realista") -> dict:
    """Ensambla el prompt clínico en 4 capas + negative por categoría.

    Nunca devuelve el detalle en crudo: siempre sale con capa de seguridad,
    capa anatómica y capa de calidad. Retorna dict con
    {categoria, categoria_label, prompt, negative_prompt}.
    """
    detalle = str(detalle or "").strip()[:1500]
    cat = (categoria or "").strip().upper()
    if cat not in CATEGORIAS:
        cat = clasificar_maniobra(detalle)
    reglas = CATEGORIAS[cat]
    est = (estilo or "realista").strip().lower()
    calidad = CAPA_CALIDAD_REALISTA if est.startswith("real") else CAPA_CALIDAD_LINEA
    prompt = f"{detalle}, {reglas['reglas']}, {CAPA_SEGURIDAD}, {CAPA_ANATOMIA}, {calidad}"
    negativo = f"{reglas['negativo']}, {NEGATIVO_BASE}"
    return {
        "categoria": cat,
        "categoria_label": reglas["label"],
        "prompt": prompt,
        "negative_prompt": negativo,
    }
