"""VocalisLab Pro — Motor de mediación universal de prompts clínicos.

ESTILO VISUAL UNIFICADO Y OBLIGATORIO:
- Estilo: "Medical 3D vector diagram" o "Clean 2D clinical vector illustration"
- Prohibido: fotorrealismo, fotos de personas reales, piel real, texto/etiquetas dentro de la imagen
- Paleta: Azul institucional, gris médico, blanco puro, acentos lavanda/púrpura
- Fondo: Blanco puro (#FFFFFF) o transparente, sin fondos de habitaciones ni desenfoques

Toda descripción de maniobra o ejercicio fonoaudiológico (TVSO, terapia
manual, postura, resonancia, articulación o atlas anatómico) pasa por este
pipeline ANTES de llegar a cualquier API de generación.
"""

import unicodedata

# ─── Taxonomía de maniobras ──────────────────────────────────────────

CATEGORIAS = {
    "TVSO": {
        "label": "TVSO y dispositivos",
        "reglas": ("flexible silicone straw/tube entering clear water glass from above, "
                   "shallowly submerged tip 1-2 cm below water surface, realistic water bubbles, "
                   "clean 3D medical vector illustration of semi-occluded vocal tract exercise"),
        "negativo": ("floating test tube, laboratory equipment, submerged sealed tube, "
                     "naked torso, 6 fingers, tube floating in water"),
        "keywords": ["tubo", "tube", "laxvox", "lax vox", "titze", "vaso",
                     "burbuj", "bubbl", "pajita", "popote", "sorbete", "straw",
                     "agua", "water", "resistencia", "soplo", "blow",
                     "botella", "bottle", "copa", "tvso", "semioclu",
                     "flauta", "flute", "mascarilla", "mask"],
    },
    "MANUAL_THERAPY": {
        "label": "Terapia manual / Palpación",
        "reglas": ("non-invasive external physical therapy contact diagram, stylized 3D vector "
                   "hands gently touching intact skin on outer neck and jaw area, modest neutral "
                   "medical gray garment shapes, clean anatomical boundaries, no facial detail"),
        "negativo": ("dissection, internal organs, open skin, surgery, blood, "
                     "extra fingers, distorted hands, naked torso, surgical tools, floating hands, "
                     "realistic face, photographic skin texture"),
        "keywords": ["masaje", "massage", "palpaci", "palpat",
                     "cuello", "neck", "cervical", "mandibul", "jaw",
                     "descompresi", "decompress", "descenso laringeo",
                     "descenso", "shiatsu", "aronson", "roy",
                     "manual", "hombro", "shoulder", "trapecio", "digito",
                     "presion", "pressure", "estiramiento cervical", "relajacion"],
    },
    "ANATOMY": {
        "label": "Diagrama anatómico 3D",
        "reglas": ("clean 3D digital medical atlas render, isolated anatomical model "
                   "of the larynx and vocal folds, educational 3D diagram, pure white background, "
                   "institutional blue and lavender medical color palette, no human hands, no real skin"),
        "negativo": ("human hands, real skin, blood, surgical tools, realistic body context, "
                     "photograph of a person, endoscopic gore, text, labels, gibberish writing"),
        "keywords": ["atlas", "diagrama", "diagram", "anatom", "laringoscop",
                     "endoscop", "tracto vocal", "vocal tract", "cuerdas vocales",
                     "vocal folds", "vocal cords", "cricotiroide", "tiroides",
                     "epiglotis", "aritenoides", "glotis", "corte coronal",
                     "esquema"],
    },
    "RESONANCE": {
        "label": "Resonancia y articulación",
        "reglas": ("stylized 3D vector diagram of head and face in side profile, smooth featureless "
                   "surfaces, relaxed jaw posture lines, natural closed-lip shape, "
                   "clean anatomical lines, subtle lavender resonance highlight on facial mask area"),
        "negativo": ("exaggerated face, medical mask, interior mouth view with hands, "
                     "distorted lips, open screaming mouth, instruments inside mouth, "
                     "realistic eyes, photographic skin"),
        "keywords": ["humming", "/m/", "resonan", "nasal", "mascara facial",
                     "mascara", "colocacion", "articulaci", "vocales", "vowels",
                     "frases", "proyecci", "anterior", "labios", "lips",
                     "boca", "mouth", "tarareo", "nidada", "brillantez"],
    },
    "POSTURE": {
        "label": "Postura y biomecánica",
        "reglas": ("stylized 3D vector diagram of human torso in side view showing rib cage and "
                   "abdominal expansion zones, smooth mannequin-like surfaces, modest neutral shapes, "
                   "biomechanical alignment guides, minimalist clinical style, clean lines, white background"),
        "negativo": ("floating limbs, bad posture, cropped head, unnatural angles, "
                     "contortionist, naked torso, real skin photo, realistic face"),
        "keywords": ["postura", "posture", "respiraci", "breathing", "diafragma",
                     "diaphragm", "costo", "abdominal", "expansion", "apoyo",
                     "alineaci", "alignment", "biomecanica", "relajacion corporal",
                     "bostezo", "yawn", "tronco", "torso", "pélvico", "pelvico",
                     "sedestaci", "bipedo"],
    },
    "GENERAL": {
        "label": "Ejercicio clínico general",
        "reglas": ("stylized medical 3D vector diagram of a speech therapy exercise setup, "
                   "minimalist clinical style, clean lines, professional anatomical accuracy, "
                   "smooth mannequin-like surfaces, no facial detail"),
        "negativo": ("surgery, blood, naked torso, distorted anatomy, real photo, realistic face"),
        "keywords": [],
    },
}

_PRIORIDAD = ["TVSO", "MANUAL_THERAPY", "ANATOMY", "RESONANCE", "POSTURE"]

# ─── Capas globales de Estilo y Seguridad ───────────────────────────
# Fotorrealismo PROHIBIDO en toda la app (directiva clínica 2026):
# solo "Medical 3D vector" o "Flat 2D clinical vector", fondo blanco puro.

PROMPT_3D_VECTOR = (
    "Medical 3D vector diagram of {detalle}, {reglas_cat}, minimalist clinical style, "
    "clean lines, professional anatomical accuracy, pure white background #FFFFFF, "
    "medical textbook illustration style, 8k, soft shadows, institutional blue "
    "and lavender accents, no text, no labels, no watermark"
)

PROMPT_2D_VECTOR = (
    "Flat 2D clinical vector diagram of {detalle}, {reglas_cat}, minimalist medical "
    "infographic style, clean geometric lines, professional anatomical accuracy, "
    "pure white background #FFFFFF, institutional blue, medical gray and lavender "
    "palette, no text, no labels, no watermark, no shading"
)

# Alias legacy: el estilo por defecto histórico se mapea al vector 3D médico.
PROMPT_POSITIVO_MASTER = PROMPT_3D_VECTOR

PROMPT_NEGATIVO_MANDATORIO = (
    "photorealistic, real human photo, real skin, photographic, cinematic photo, "
    "real person, photo background, consulting room, bedroom, furniture, bokeh, "
    "extra fingers, mutated hands, deformed fingers, 6 fingers, floating hands, "
    "dislocated limbs, distorted anatomy, text, labels, gibberish writing, letters, "
    "words, captions, arrows with text, blurry, noisy background, realistic faces"
)


def normalizar_estilo(estilo: str = "") -> str:
    """Canoniza el estilo visual. Solo dos valores posibles:
    '3d_vector' (default, ilustración médica 3D) o 'vector_2d' (diagrama plano).
    Los valores legacy 'realista'→3d_vector y 'lineart'→vector_2d se migran solos."""
    est = str(estilo or "").strip().lower()
    if "line" in est or est in ("vector_2d", "2d", "flat", "plano"):
        return "vector_2d"
    return "3d_vector"


def _norm(texto: str) -> str:
    nfkd = unicodedata.normalize("NFKD", str(texto or "").lower())
    return "".join(c for c in nfkd if not unicodedata.combining(c))


def clasificar_maniobra(texto: str) -> str:
    """Devuelve la categoría (clave de CATEGORIAS) por scoring de keywords."""
    t = _norm(texto)
    if not t.strip():
        return "GENERAL"
    mejor, mejor_pts = "GENERAL", 0
    for cat in _PRIORIDAD:
        pts = sum(1 for kw in CATEGORIAS[cat]["keywords"] if _norm(kw) in t)
        if pts > mejor_pts:
            mejor, mejor_pts = cat, pts
    return mejor


def mediar_prompt(detalle: str, categoria: str = "", estilo: str = "3d_vector") -> dict:
    """Ensambla el prompt clínico en la arquitectura de 4 capas con estilo médico
    vectorial 3D o plano 2D (fotorrealismo prohibido, sin texto en la imagen).
    Retorna dict con {categoria, categoria_label, estilo, prompt, negative_prompt}.
    """
    detalle = str(detalle or "").strip()[:1500]
    cat = (categoria or "").strip().upper()
    if cat not in CATEGORIAS:
        cat = clasificar_maniobra(detalle)
    reglas = CATEGORIAS[cat]
    est = normalizar_estilo(estilo)
    template = PROMPT_2D_VECTOR if est == "vector_2d" else PROMPT_3D_VECTOR
    prompt = template.format(detalle=detalle, reglas_cat=reglas["reglas"])
    negativo = f"{reglas['negativo']}, {PROMPT_NEGATIVO_MANDATORIO}"

    return {
        "categoria": cat,
        "categoria_label": reglas["label"],
        "estilo": est,
        "prompt": prompt,
        "negative_prompt": negativo,
    }
