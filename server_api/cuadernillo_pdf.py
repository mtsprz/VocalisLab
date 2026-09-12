"""
VocalisLab Pro — Motor de Impresión de Cuadernillos (guía visual pedagógica).

Salida accesible para todas las edades (incluye adultos mayores):
- Curva melódica vectorial en CADA ejercicio (ascendente, sirena, sostenido, descendente).
- Pictogramas esquemáticos (cavidad oral, vaso LaxVox, postura corporal).
- Grilla semanal de horarios, registro diario de TME y autoevaluación pre/post.
- Tipografía grande (cuerpo 13pt, pasos 16pt) y lenguaje cotidiano sin jerga.
"""
import os
import re
import json
import tempfile
from xml.sax.saxutils import escape
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, white
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, HRFlowable
)
from reportlab.graphics.shapes import Drawing, Line, String, PolyLine, Circle, Rect, Polygon


PRIMARY = HexColor("#1a237e")
SECONDARY = HexColor("#7c4dff")
ACCENT = HexColor("#00c853")
LIGHT_BG = HexColor("#f5f5f5")
DARK_TEXT = HexColor("#212121")
GRAY_TEXT = HexColor("#616161")
LIGHT_GRAY = HexColor("#e0e0e0")
CARD_BG = HexColor("#fafaff")
CURVE_COLOR = HexColor("#1a237e")
ARROW_COLOR = HexColor("#00c853")

# ─── Lenguaje cotidiano: jerga técnica → palabras simples ──────────
_JERGA = [
    ("presión subglótica", "control del aire al soplar"),
    ("presión subglotica", "control del aire al soplar"),
    ("subglótico", "del aire"),
    ("subglotico", "del aire"),
    ("supraglótico", "de arriba de las cuerdas"),
    ("supraglotico", "de arriba de las cuerdas"),
    ("glótico", "de las cuerdas"),
    ("glotico", "de las cuerdas"),
    ("mucosa cordal", "la capita que recubre las cuerdas"),
    ("pliegues vocales", "cuerdas vocales"),
    ("impedancia acústica", "ayuda del aire para vibrar mejor"),
    ("impedancia acustica", "ayuda del aire para vibrar mejor"),
    ("reactancia acústica", "ayuda del aire"),
    ("reactancia acustica", "ayuda del aire"),
    ("contrapresión acústica", "empuje suave del aire"),
    ("contrapresion acustica", "empuje suave del aire"),
    ("contrapresión", "empuje suave del aire"),
    ("contrapresion", "empuje suave del aire"),
    ("aducción", "cierre suave de las cuerdas"),
    ("aduccion", "cierre suave de las cuerdas"),
    ("abducción", "apertura de las cuerdas"),
    ("abduccion", "apertura de las cuerdas"),
    ("fonación", "emisión de la voz"),
    ("fonacion", "emisión de la voz"),
    ("tesitura modal", "su tono habitual"),
    ("cricotiroideo/tiroaritenoideo", "músculos de la voz"),
    ("costodiafragmático", "con panza y costillas"),
    ("costodiafragmatico", "con panza y costillas"),
    ("costodiafragmática", "con panza y costillas"),
    ("costodiafragmatica", "con panza y costillas"),
    ("tirohioideo", "del cuello"),
    ("tirohioidea", "del cuello"),
    ("hioides", "huesito del cuello"),
    ("maseteros", "músculos de masticar"),
    ("vértex", "coronilla"),
    ("vertex", "coronilla"),
    ("trapecios", "hombros"),
    ("trapecio", "hombro"),
    ("clavicular", "del pecho"),
    ("diafragmático", "con la panza"),
    ("diafragmatico", "con la panza"),
    ("diafragmática", "con la panza"),
    ("diafragmatica", "con la panza"),
    ("costillas flotantes", "costillas bajas"),
    ("capacidad vital", "cantidad de aire"),
    ("apnea", "pausa sin respirar"),
    ("fricativa", "sonido con aire (como la s)"),
    ("báscula", "escala"),
    ("bascula", "escala"),
    ("ATM", "mandíbula"),
]


def _simplificar(texto: str) -> str:
    """Reemplaza jerga técnica por lenguaje cotidiano (insensible a mayúsculas)."""
    if not texto:
        return ""
    out = str(texto)
    for src, dst in _JERGA:
        out = re.sub(re.escape(src), dst, out, flags=re.IGNORECASE)
    return out


def _checkbox() -> Drawing:
    """Casillero vectorial 12x12px para tildar a mano."""
    d = Drawing(14, 14)
    d.add(Rect(1, 1, 12, 12, strokeColor=SECONDARY, strokeWidth=1.2,
               fillColor=white))
    return d


_MOJIBAKE = [
    ("Ã¡", "á"), ("Ã©", "é"), ("Ã­", "í"), ("Ã³", "ó"), ("Ãº", "ú"),
    ("Ã±", "ñ"), ("ÃÁ", "Á"), ("ÃÉ", "É"), ("ÃÍ", "Í"), ("ÃÓ", "Ó"),
    ("ÃÚ", "Ú"), ("ÃÑ", "Ñ"), ("Ã§", "ç"), ("Ã¼", "ü"),
    ("â€œ", '"'), ("â€", '"'), ("â€™", "'"), ("â€˜", "'"),
    ("â€“", "-"), ("â€”", "-"), ("Â", ""), ("Â ", " "),
]


def _sanear(texto: str) -> str:
    """Repara acentos rotos (mojibake), colapsa espacios y evita palabras
    duplicadas consecutivas por reemplazos de jerga."""
    if not texto:
        return ""
    out = str(texto)
    for src, dst in _MOJIBAKE:
        out = out.replace(src, dst)
    # Artefactos de sintaxis tipo $10=voz$ / $0=$ (restos de plantillas)
    out = re.sub(r"\$[^$\n]*\$", "", out)
    out = out.replace("$", "")
    # Backslashes sueltos y corchetes huérfanos (sin contenido útil)
    out = out.replace("\\", "")
    out = re.sub(r"\[[^\[\]\w]*\]", "", out)
    out = re.sub(r"\s+", " ", out).strip()
    # Colapsa palabra duplicada exacta consecutiva ("respiración respiración")
    out = re.sub(r"(?i)\b(\w[\w\-]*)\s+\1\b", r"\1", out)
    # Tildes faltantes frecuentes (palabra completa, preservando mayúsculas)
    for sin, con in _TILDES:
        def _rep(m, _con=con):
            t = m.group(0)
            if t.isupper():
                return _con.upper()
            if t[0].isupper():
                return _con[0].upper() + _con[1:]
            return _con
        out = re.sub(r"\b" + sin + r"\b", _rep, out, flags=re.IGNORECASE)
    # Mayúscula inicial
    if out:
        out = out[0].upper() + out[1:]
    return out


_TILDES = [
    ("manana", "mañana"), ("movilizacion", "movilización"),
    ("respiracion", "respiración"), ("digitopresion", "digitopresión"),
    ("laringea", "laríngea"),
    ("faringea", "faríngea"), ("terapeutico", "terapéutico"),
    ("clinico", "clínico"), ("sintesis", "síntesis"),
    ("diagnostico", "diagnóstico"), ("maximo", "máximo"),
    ("minimo", "mínimo"), ("oido", "oído"), ("area", "área"),
    ("linea", "línea"), ("medico", "médico"), ("sesion", "sesión"),
    ("evaluacion", "evaluación"), ("funcion", "función"),
    ("tension", "tensión"), ("presion", "presión"),
    ("fonico", "fónico"), ("fonica", "fónica"),
    ("acustico", "acústico"), ("acustica", "acústica"),
    ("cronico", "crónico"), ("musculo", "músculo"),
    ("lamina", "lámina"), ("numero", "número"), ("telefono", "teléfono"),
    ("tecnica", "técnica"), ("rapido", "rápido"), ("comun", "común"),
    ("exhalacion", "exhalación"), ("inhalacion", "inhalación"),
    ("vocalizacion", "vocalización"), ("articulacion", "articulación"),
    ("relajacion", "relajación"), ("hidratacion", "hidratación"),
    ("simbolo", "símbolo"),
]


# ─── Clasificación de curva melódica por ejercicio ─────────────────
_CURVA_STACCATO = ("staccato", "stacatto", "punteado", "punteo")
_CURVA_SIRENA = ("sirena", "vibraci", "trill", "fluctu", "tubo_agua", "popote_aire",
                 "escalas_vocalicas", "lax", "laxvox")
_CURVA_DESCENSO = ("descenso", "bostezo", "enfriamiento", "suspiro", "le_huche",
                   "shiatsu", "masaje_laringeo", "rotacion", "relaj", "pautas_rlf",
                   "calentamiento")
_CURVA_SOSTENIDO = ("humming", "frases_balanceadas", "respiracion_abdominal",
                    "soplo_escalonado", "consonantes_fricativas", "oclusion_succion",
                    "expansion_costo", "sostenid", "mantener", "lectura")


def _tipo_curva(ex: dict) -> str:
    blob = f"{ex.get('id', '')} {ex.get('name', '')} {ex.get('description', '')}".lower()
    if any(k in blob for k in _CURVA_STACCATO):
        return "staccato"
    if any(k in blob for k in _CURVA_SIRENA):
        return "sirena"
    if any(k in blob for k in _CURVA_DESCENSO):
        return "descendente"
    if any(k in blob for k in _CURVA_SOSTENIDO):
        return "sostenido"
    return "ascendente"


_CURVA_TITULO = {
    "ascendente": "Suba suave de grave a agudo",
    "sirena": "Sirena: suba y baje varias veces",
    "sostenido": "Mantenga el sonido parejo",
    "descendente": "Baje suave de agudo a grave",
    "staccato": "Golpecitos cortos y separados",
}


def _curva_melodica(tipo: str, segundos: str = "") -> Drawing:
    """Gráfico vectorial de la curva melódica (140 x 64 pt)."""
    W, H = 150, 66
    d = Drawing(W, H)
    # Ejes tenues
    d.add(Line(8, 8, 8, H - 8, strokeColor=LIGHT_GRAY, strokeWidth=0.5))
    d.add(Line(8, 8, W - 6, 8, strokeColor=LIGHT_GRAY, strokeWidth=0.5))
    d.add(String(2, H - 12, "agudo", fontName="Helvetica", fontSize=6, fillColor=GRAY_TEXT))
    d.add(String(2, 6, "grave", fontName="Helvetica", fontSize=6, fillColor=GRAY_TEXT))

    if tipo == "ascendente":
        pts = []
        for i in range(21):
            x = 14 + i * (W - 28) / 20
            y = 14 + (W - 28) / 20 * 0 + (i / 20) ** 1.2 * (H - 30)
            pts += [x, y]
        d.add(PolyLine(pts, strokeColor=CURVE_COLOR, strokeWidth=2.2))
        x1, y1 = pts[-2], pts[-1]
        d.add(Polygon([x1, y1 - 5, x1, y1 + 5, x1 + 9, y1],
                      fillColor=ARROW_COLOR, strokeColor=ARROW_COLOR))
    elif tipo == "sirena":
        import math
        pts = []
        n = 80
        for i in range(n + 1):
            x = 14 + i * (W - 28) / n
            y = (H / 2) + math.sin(i / n * math.pi * 2 * 4) * (H / 2 - 14)
            pts += [x, y]
        d.add(PolyLine(pts, strokeColor=CURVE_COLOR, strokeWidth=2.0))
    elif tipo == "sostenido":
        y = H / 2
        d.add(Line(14, y, W - 14, y, strokeColor=CURVE_COLOR, strokeWidth=2.4))
        d.add(Line(14, y - 6, 14, y + 6, strokeColor=CURVE_COLOR, strokeWidth=1.4))
        d.add(Line(W - 14, y - 6, W - 14, y + 6, strokeColor=CURVE_COLOR, strokeWidth=1.4))
        if segundos:
            d.add(String(W / 2 - 14, y + 8, segundos, fontName="Helvetica-Bold",
                         fontSize=7, fillColor=CURVE_COLOR))
    elif tipo == "staccato":
        # Serie de puntos/golpecitos cortos ascendentes
        n = 9
        for i in range(n):
            x = 16 + i * (W - 32) / (n - 1)
            y = 16 + (i / (n - 1)) * (H - 32)
            d.add(Circle(x, y, 3.2, strokeColor=CURVE_COLOR, strokeWidth=1.6,
                         fillColor=CURVE_COLOR))
            d.add(Line(x, y + 4, x, y + 12, strokeColor=ARROW_COLOR, strokeWidth=1.2))
        d.add(String(14, H - 10, "corto-corto-corto", fontName="Helvetica",
                     fontSize=6, fillColor=GRAY_TEXT))
    else:  # descendente
        pts = []
        for i in range(21):
            x = 14 + i * (W - 28) / 20
            y = (H - 16) - (i / 20) ** 1.2 * (H - 30)
            pts += [x, y]
        d.add(PolyLine(pts, strokeColor=CURVE_COLOR, strokeWidth=2.2))
        x1, y1 = pts[-2], pts[-1]
        d.add(Polygon([x1, y1 - 5, x1, y1 + 5, x1 + 9, y1],
                      fillColor=ARROW_COLOR, strokeColor=ARROW_COLOR))
    return d


# ─── Banco de pictogramas esquemáticos ────────────────────────────
def _picto_oral() -> Drawing:
    """Esquema de cavidad oral: boca abierta, lengua plana, velo del paladar."""
    W, H = 150, 92
    d = Drawing(W, H)
    d.add(String(8, H - 10, "Boca abierta y relajada", fontName="Helvetica-Bold",
                 fontSize=7, fillColor=PRIMARY))
    # Óvalo de boca abierta
    d.add(Circle(W / 2, H / 2 - 4, 30, strokeColor=CURVE_COLOR, strokeWidth=2,
                 fillColor=None))
    # Lengua plana (polígono inferior)
    d.add(Polygon([W / 2 - 24, H / 2 - 12, W / 2 + 24, H / 2 - 12,
                   W / 2 + 10, H / 2 - 28, W / 2 - 10, H / 2 - 28],
                  fillColor=HexColor("#ffccbc"), strokeColor=CURVE_COLOR, strokeWidth=1))
    # Velo del paladar (arco superior)
    d.add(PolyLine([W / 2 - 26, H / 2 + 18, W / 2, H / 2 + 28, W / 2 + 26, H / 2 + 18],
                   strokeColor=CURVE_COLOR, strokeWidth=1.6))
    d.add(String(8, 8, "Lengua plana al piso de la boca", fontName="Helvetica",
                 fontSize=6.5, fillColor=GRAY_TEXT))
    d.add(String(W - 78, H / 2 + 30, "velo del paladar", fontName="Helvetica",
                 fontSize=6, fillColor=GRAY_TEXT))
    return d


def _picto_vaso() -> Drawing:
    """Vaso con agua, marca de 1,5 cm y sorbete (LaxVox / SOVT)."""
    W, H = 150, 92
    d = Drawing(W, H)
    d.add(String(8, H - 10, "Vaso con agua (LaxVox)", fontName="Helvetica-Bold",
                 fontSize=7, fillColor=PRIMARY))
    gx, gy, gw, gh = 45, 10, 60, 58
    # Vaso
    d.add(Rect(gx, gy, gw, gh, strokeColor=CURVE_COLOR, strokeWidth=2, fillColor=None))
    # Agua (mitad inferior)
    d.add(Rect(gx + 2, gy + 2, gw - 4, 26, strokeColor=None,
               fillColor=HexColor("#4fc3f7")))
    d.add(String(gx + 6, gy + 10, "agua", fontName="Helvetica-Bold",
                 fontSize=7, fillColor=white))
    # Sorbete diagonal
    d.add(Line(gx + 38, gy + gh + 12, gx + 22, gy + 4,
               strokeColor=HexColor("#e91e63"), strokeWidth=3))
    # Marca de profundidad 1,5 cm
    d.add(Line(gx + gw + 4, gy + 4, gx + gw + 4, gy + 16,
               strokeColor=ARROW_COLOR, strokeWidth=1.2))
    d.add(String(gx + gw + 8, gy + 8, "1,5 cm", fontName="Helvetica-Bold",
                 fontSize=7, fillColor=ARROW_COLOR))
    d.add(String(8, 2, "Sople suave y parejo por el sorbete", fontName="Helvetica",
                 fontSize=6, fillColor=GRAY_TEXT))
    return d


def _picto_postura() -> Drawing:
    """Pictograma de postura corporal erguida y relajada."""
    W, H = 150, 92
    d = Drawing(W, H)
    d.add(String(8, H - 10, "Postura erguida y relajada", fontName="Helvetica-Bold",
                 fontSize=7, fillColor=PRIMARY))
    cx, top = W / 2, H - 20
    # Cabeza
    d.add(Circle(cx, top - 8, 9, strokeColor=CURVE_COLOR, strokeWidth=2, fillColor=None))
    # Tronco
    d.add(Line(cx, top - 17, cx, top - 48, strokeColor=CURVE_COLOR, strokeWidth=2.4))
    # Hombros relajados (línea horizontal baja)
    d.add(Line(cx - 20, top - 22, cx + 20, top - 22, strokeColor=ARROW_COLOR, strokeWidth=2))
    # Brazos caídos
    d.add(Line(cx - 20, top - 22, cx - 24, top - 44, strokeColor=CURVE_COLOR, strokeWidth=1.6))
    d.add(Line(cx + 20, top - 22, cx + 24, top - 44, strokeColor=CURVE_COLOR, strokeWidth=1.6))
    # Piernas
    d.add(Line(cx, top - 48, cx - 12, top - 68, strokeColor=CURVE_COLOR, strokeWidth=2))
    d.add(Line(cx, top - 48, cx + 12, top - 68, strokeColor=CURVE_COLOR, strokeWidth=2))
    # Base
    d.add(Line(cx - 22, top - 68, cx + 22, top - 68, strokeColor=GRAY_TEXT, strokeWidth=1))
    d.add(String(8, 2, "Espalda derecha, hombros sueltos", fontName="Helvetica",
                 fontSize=6, fillColor=GRAY_TEXT))
    return d


_PICTO_ORAL = ("frases_balanceadas", "consonantes_fricativas", "escalas_vocalicas",
               "soplo_escalonado", "apertura", "moldeado", "vocalico", "articul")
_PICTO_VASO = ("tubo_agua", "popote_aire", "oclusion_succion", "lax", "sorbete",
               "sovt", "semioclu")
_PICTO_POSTURA = ("le_huche", "shiatsu", "rotacion_hombros", "masaje_laringeo",
                  "respiracion_abdominal", "expansion_costo", "descenso_laringeo",
                  "pautas_rlf", "calentamiento", "enfriamiento", "relaj",
                  "postura", "hombro", "cuello", "cervical")


def _pictograma(ex: dict):
    blob = f"{ex.get('id', '')} {ex.get('name', '')} {ex.get('description', '')}".lower()
    if any(k in blob for k in _PICTO_VASO):
        return _picto_vaso(), "Vaso con agua y sorbete"
    if any(k in blob for k in _PICTO_ORAL):
        return _picto_oral(), "Cómo poner la boca"
    if any(k in blob for k in _PICTO_POSTURA):
        return _picto_postura(), "Postura del cuerpo"
    # Regla de diagramación: ningún ejercicio sin pictograma → fallback postural
    return _picto_postura(), "Postura del cuerpo"


# ─── Ilustraciones editoriales únicas por ejercicio (SVG line-art) ────
# Estilo: tinta #1E293B, línea 1.5px, fondo blanco, sin rellenos densos.
# Cada ejercicio tiene SU builder: cero duplicación entre ejercicios.
import math as _math

INK = HexColor("#1E293B")
INK_SUAVE = HexColor("#64748B")
FONDO_SUAVE = HexColor("#F1F5F9")


def _flecha(d, x1, y1, x2, y2, color=INK, w=1.5):
    d.add(Line(x1, y1, x2, y2, strokeColor=color, strokeWidth=w))
    ang = _math.atan2(y2 - y1, x2 - x1)
    L, a = 7, 0.42
    d.add(Polygon([x2, y2,
                   x2 - L * _math.cos(ang - a), y2 - L * _math.sin(ang - a),
                   x2 - L * _math.cos(ang + a), y2 - L * _math.sin(ang + a)],
                  fillColor=color, strokeColor=color))


def _cap(d, texto, H=96):
    d.add(String(6, H - 10, texto, fontName="Helvetica-Bold",
                 fontSize=7, fillColor=INK))


def _nota(d, texto, y=8):
    d.add(String(6, y, texto, fontName="Helvetica", fontSize=6,
                 fillColor=INK_SUAVE))


def _svg_cervical_mobility():
    d = Drawing(150, 96)
    _cap(d, "Mueva cuello y hombros")
    d.add(Circle(75, 66, 12, strokeColor=INK, strokeWidth=1.5, fillColor=None))
    d.add(Line(45, 44, 105, 44, strokeColor=INK, strokeWidth=1.5))
    d.add(Line(75, 54, 75, 20, strokeColor=INK, strokeWidth=1.5))
    _flecha(d, 40, 60, 30, 70)
    _flecha(d, 110, 60, 120, 70)
    _flecha(d, 58, 26, 48, 26)
    _flecha(d, 92, 26, 102, 26)
    _nota(d, "Círculos lentos, sin dolor")
    return d


def _svg_breathing_cycle():
    d = Drawing(150, 96)
    _cap(d, "Respire: entra, pausa, sale")
    d.add(Circle(75, 44, 26, strokeColor=INK, strokeWidth=1.5, fillColor=None))
    _flecha(d, 75, 78, 98, 62)
    _flecha(d, 52, 26, 75, 10)
    d.add(String(100, 40, "pausa", fontName="Helvetica", fontSize=6, fillColor=INK_SUAVE))
    _nota(d, "Por nariz adentro, /f/ afuera")
    return d


def _svg_pressure_points():
    d = Drawing(150, 96)
    _cap(d, "Puntos de presión 30 seg")
    d.add(Circle(75, 48, 28, strokeColor=INK, strokeWidth=1.5, fillColor=None))
    for (x, y) in ((75, 76), (47, 48), (103, 48), (75, 30)):
        d.add(Circle(x, y, 4, strokeColor=INK, strokeWidth=1.2, fillColor=INK))
    _nota(d, "Coronilla, sienes y mandíbula")
    return d


def _svg_shoulder_rotation():
    d = Drawing(150, 96)
    _cap(d, "Círculos de hombros")
    d.add(Line(40, 30, 40, 60, strokeColor=INK, strokeWidth=1.5))
    d.add(Line(110, 30, 110, 60, strokeColor=INK, strokeWidth=1.5))
    d.add(Circle(75, 68, 10, strokeColor=INK, strokeWidth=1.5, fillColor=None))
    _flecha(d, 30, 45, 22, 53)
    _flecha(d, 120, 45, 128, 53)
    _nota(d, "10 atrás + 10 adelante")
    return d


def _svg_laryngeal_massage():
    d = Drawing(150, 96)
    _cap(d, "Masaje suave del cuello")
    d.add(Rect(58, 18, 34, 52, strokeColor=INK, strokeWidth=1.5, fillColor=None))
    d.add(Circle(75, 52, 12, strokeColor=INK, strokeWidth=1.2, fillColor=None))
    _flecha(d, 63, 52, 63, 64)
    _flecha(d, 87, 52, 87, 40)
    _nota(d, "Círculos suaves, sin apretar")
    return d


def _svg_larynx_descent():
    d = Drawing(150, 96)
    _cap(d, "Bostezo: la laringe baja")
    # Boca abierta en óvalo suave + garganta en curva
    pts = []
    for i in range(33):
        a = i / 32 * 2 * _math.pi
        pts += [75 + 16 * _math.cos(a), 62 + 10 * _math.sin(a)]
    d.add(PolyLine(pts, strokeColor=INK, strokeWidth=1.5))
    d.add(PolyLine([68, 52, 66, 36, 70, 24, 80, 24, 84, 36, 82, 52],
                   strokeColor=INK, strokeWidth=1.2))
    _flecha(d, 100, 56, 100, 30)
    d.add(String(106, 40, "baja", fontName="Helvetica", fontSize=6, fillColor=INK_SUAVE))
    _nota(d, "Bostezo grande y suspiro")
    return d


def _svg_suction_straw():
    d = Drawing(150, 96)
    _cap(d, "Chupe suave por el sorbete")
    # Labios en curva + sorbete fino
    d.add(PolyLine([28, 44, 38, 38, 52, 38, 60, 44, 52, 50, 38, 50, 28, 44],
                   strokeColor=INK, strokeWidth=1.5))
    d.add(Line(60, 44, 104, 44, strokeColor=INK, strokeWidth=1.5))
    _flecha(d, 104, 44, 66, 44)
    _flecha(d, 128, 44, 114, 44)
    _nota(d, "Mejillas adentro, 10 seg")
    return d


def _svg_diaphragmatic():
    d = Drawing(150, 96)
    _cap(d, "Infle panza y costillas")
    d.add(Rect(55, 20, 40, 50, strokeColor=INK, strokeWidth=1.5, fillColor=None))
    _flecha(d, 55, 45, 35, 45)
    _flecha(d, 95, 45, 115, 45)
    _flecha(d, 75, 20, 75, 8)
    _nota(d, "El pecho quieto, la panza sale")
    return d


def _svg_rib_expansion():
    d = Drawing(150, 96)
    _cap(d, "Abra las costillas bajas")
    for i, r in enumerate((14, 20, 26)):
        d.add(Circle(75, 48, r, strokeColor=INK, strokeWidth=1.2, fillColor=None))
    _flecha(d, 49, 48, 33, 48)
    _flecha(d, 101, 48, 117, 48)
    _nota(d, "Manos a los costados")
    return d


def _svg_stepped_blow():
    d = Drawing(150, 96)
    _cap(d, "Soplo por escalones")
    for i, (x, h) in enumerate(((30, 14), (62, 24), (94, 34))):
        d.add(Rect(x, 18, 24, h, strokeColor=INK, strokeWidth=1.5, fillColor=None))
        d.add(String(x + 8, 24 + h, f"/h{i + 1}", fontName="Helvetica", fontSize=6,
                     fillColor=INK_SUAVE))
    _flecha(d, 22, 30, 28, 30)
    _nota(d, "De aire solo a con voz")
    return d


def _svg_glottal_closure():
    d = Drawing(150, 96)
    _cap(d, "Cierre firme y corto")
    d.add(Line(40, 30, 70, 48, strokeColor=INK, strokeWidth=1.5))
    d.add(Line(110, 30, 80, 48, strokeColor=INK, strokeWidth=1.5))
    _flecha(d, 48, 40, 68, 46)
    _flecha(d, 102, 40, 82, 46)
    d.add(String(60, 58, "/a/ /i/ corto", fontName="Helvetica", fontSize=6,
                 fillColor=INK_SUAVE))
    _nota(d, "Manos bajo la silla")
    return d


def _svg_laxvox_glass():
    d = Drawing(150, 96)
    _cap(d, "Vaso con agua (LaxVox)")
    gx, gy, gw, gh = 50, 10, 50, 56
    d.add(Rect(gx, gy, gw, gh, strokeColor=INK, strokeWidth=1.5, fillColor=None))
    d.add(Rect(gx + 2, gy + 2, gw - 4, 22, strokeColor=None, fillColor=FONDO_SUAVE))
    d.add(Line(gx + 38, gy + gh + 14, gx + 24, gy + 4, strokeColor=INK, strokeWidth=1.5))
    d.add(Line(gx + gw + 4, gy + 4, gx + gw + 4, gy + 15, strokeColor=INK, strokeWidth=1.2))
    d.add(String(gx + gw + 8, gy + 8, "1,5 cm", fontName="Helvetica-Bold",
                 fontSize=7, fillColor=INK))
    _nota(d, "Burbujeo parejo 1 min")
    return d


def _svg_lip_trill():
    d = Drawing(150, 96)
    _cap(d, "Vibración de labios")
    # Labios como curvas suaves + onda senoidal de vibración
    d.add(PolyLine([44, 52, 52, 44, 62, 44, 70, 52, 62, 60, 52, 60, 44, 52],
                   strokeColor=INK, strokeWidth=1.5))
    pts = []
    for i in range(41):
        x = 78 + i * 1.6
        y = 48 + _math.sin(i / 40 * _math.pi * 2 * 3) * 6
        pts += [x, y]
    d.add(PolyLine(pts, strokeColor=INK, strokeWidth=1.5))
    d.add(String(44, 66, "/brrr/", fontName="Helvetica-Bold", fontSize=7, fillColor=INK))
    _nota(d, "Sirenas suaves")
    return d


def _svg_straw_in_air():
    d = Drawing(150, 96)
    _cap(d, "Sorbete al aire (sin vaso)")
    d.add(Circle(40, 48, 10, strokeColor=INK, strokeWidth=1.5, fillColor=None))
    d.add(Line(50, 48, 92, 48, strokeColor=INK, strokeWidth=1.5))
    _flecha(d, 92, 48, 118, 48)
    d.add(Line(118, 30, 118, 66, strokeColor=INK_SUAVE, strokeWidth=0.8))
    _nota(d, "Tonos y sirenas")
    return d


def _svg_fricative_flow():
    d = Drawing(150, 96)
    _cap(d, "Aire continuo /v/ /z/")
    for x in (52, 60, 68):
        d.add(Line(x, 36, x, 60, strokeColor=INK, strokeWidth=1.5))
    pts = [78, 48, 96, 48, 114, 48, 132, 48]
    d.add(PolyLine(pts, strokeColor=INK, strokeWidth=1.5))
    _flecha(d, 132, 48, 140, 48)
    d.add(String(52, 66, "/vvvv/", fontName="Helvetica-Bold", fontSize=7, fillColor=INK))
    _nota(d, "Luego pegue la vocal")
    return d


def _svg_facial_mask():
    d = Drawing(150, 96)
    _cap(d, "Vibra en la máscara")
    # Perfil facial estilizado en curva suave (frente-nariz-labios-mentón)
    perfil = []
    for i in range(41):
        t = i / 40
        x = 52 + _math.sin(t * _math.pi) * 14 + t * 8
        y = 78 - t * 52 + _math.sin(t * _math.pi * 3) * 4
        perfil += [x, y]
    d.add(PolyLine(perfil, strokeColor=INK, strokeWidth=1.5))
    for r in (7, 12, 17):
        pts = []
        for i in range(21):
            a = -0.7 + i * (1.4 / 20)
            pts += [86 + r * _math.cos(a), 48 + r * _math.sin(a)]
        d.add(PolyLine(pts, strokeColor=INK, strokeWidth=1.0))
    d.add(String(44, 16, "/m/", fontName="Helvetica-Bold", fontSize=8, fillColor=INK))
    _nota(d, "Labios juntos, cosquilleo")
    return d


def _svg_vocal_scales():
    d = Drawing(150, 96)
    _cap(d, "Escalones de voz")
    xs = [30, 52, 74, 96, 118]
    for i, x in enumerate(xs):
        y = 22 + i * 8
        d.add(Rect(x, 22, 18, y - 22 + 8 if False else (i + 1) * 8,
                   strokeColor=INK, strokeWidth=1.2, fillColor=None))
        d.add(Circle(x + 9, 22 + (i + 1) * 8 + 4, 2.5, strokeColor=INK,
                     strokeWidth=1, fillColor=INK))
    _nota(d, "Suba y baje 5 notas")
    return d


def _svg_voice_projection():
    d = Drawing(150, 96)
    _cap(d, "Proyecte a 3 metros")
    d.add(Circle(30, 48, 8, strokeColor=INK, strokeWidth=1.5, fillColor=None))
    for r in (18, 32, 46):
        d.add(Circle(30, 48, r, strokeColor=INK, strokeWidth=1.0, fillColor=None))
    d.add(String(96, 44, "3 m", fontName="Helvetica-Bold", fontSize=8, fillColor=INK))
    _flecha(d, 84, 70, 120, 70)
    _nota(d, "Claro y sin gritar")
    return d


def _svg_warmup_flow():
    d = Drawing(150, 96)
    _cap(d, "Calentamiento en 3 pasos")
    for i, (x, tag) in enumerate(((30, "1"), (64, "2"), (98, "3"))):
        d.add(Rect(x, 32, 24, 24, strokeColor=INK, strokeWidth=1.5, fillColor=None))
        d.add(String(x + 9, 40, tag, fontName="Helvetica-Bold", fontSize=9, fillColor=INK))
        if i < 2:
            _flecha(d, x + 24, 44, x + 34, 44)
    _nota(d, "Respira, vibra, habla")
    return d


def _svg_cooldown_flow():
    d = Drawing(150, 96)
    _cap(d, "Enfriamiento en 3 pasos")
    for i, (x, tag) in enumerate(((98, "1"), (64, "2"), (30, "3"))):
        d.add(Rect(x, 32, 24, 24, strokeColor=INK, strokeWidth=1.5, fillColor=None))
        d.add(String(x + 9, 40, tag, fontName="Helvetica-Bold", fontSize=9, fillColor=INK))
    _flecha(d, 98, 44, 88, 44)
    _flecha(d, 64, 44, 54, 44)
    _nota(d, "Baje, sople, silencio")
    return d


def _svg_antireflux():
    d = Drawing(150, 96)
    _cap(d, "Cene temprano, duerma alto")
    d.add(Line(25, 30, 125, 52, strokeColor=INK, strokeWidth=1.5))
    d.add(Line(25, 30, 25, 18, strokeColor=INK, strokeWidth=1.2))
    d.add(Circle(105, 22, 12, strokeColor=INK, strokeWidth=1.2, fillColor=None))
    d.add(Line(105, 22, 105, 14, strokeColor=INK, strokeWidth=1.2))
    d.add(Line(105, 14, 109, 18, strokeColor=INK, strokeWidth=1.2))
    d.add(String(92, 60, "2,5 h", fontName="Helvetica-Bold", fontSize=7, fillColor=INK))
    _nota(d, "Cabecera elevada 15 cm")
    return d


_SVG_POR_EJERCICIO = {
    "rotacion_hombros": (_svg_cervical_mobility, "Movilidad cervical"),
    "respiracion_abdominal": (_svg_diaphragmatic, "Respiración con panza"),
    "tubo_agua": (_svg_laxvox_glass, "Vaso LaxVox"),
    "popote_aire": (_svg_straw_in_air, "Sorbete al aire"),
    "humming_m": (_svg_facial_mask, "Máscara facial"),
    "frases_balanceadas": (_svg_voice_projection, "Proyección vocal"),
    "calentamiento": (_svg_warmup_flow, "Rutina de entrada"),
    "enfriamiento": (_svg_cooldown_flow, "Rutina de salida"),
    "le_huche": (_svg_breathing_cycle, "Ciclo respiratorio"),
    "shiatsu_cabeza": (_svg_pressure_points, "Digitopresión"),
    "masaje_laringeo": (_svg_laryngeal_massage, "Masaje laríngeo"),
    "descenso_laringeo": (_svg_larynx_descent, "Descenso laríngeo"),
    "oclusion_succion": (_svg_suction_straw, "Succión con sorbete"),
    "expansion_costo_lateral": (_svg_rib_expansion, "Expansión costal"),
    "soplo_escalonado": (_svg_stepped_blow, "Soplo escalonado"),
    "empuje_glotico": (_svg_glottal_closure, "Cierre glótico"),
    "vibracion_labial": (_svg_lip_trill, "Trino labial"),
    "consonantes_fricativas": (_svg_fricative_flow, "Fricativas sonoras"),
    "escalas_vocalicas": (_svg_vocal_scales, "Escalas vocales"),
    "pautas_rlf": (_svg_antireflux, "Pautas antirreflujo"),
}


def _ilustracion(ex: dict):
    """Ilustración única por ejercicio (cero duplicación). Fallback: esquema
    técnico genérico rotulado con el propio ejercicio, nunca otro dibujo."""
    ex_id = str(ex.get("id", "")).strip().lower()
    if ex_id in _SVG_POR_EJERCICIO:
        fn, cap = _SVG_POR_EJERCICIO[ex_id]
        try:
            return fn(), cap
        except Exception:
            pass
    # Fallback técnico específico: marco rotulado del procedimiento
    d = Drawing(150, 96)
    nombre = str(ex.get("name", "Ejercicio"))[:34]
    _cap(d, "Procedimiento")
    d.add(Rect(20, 24, 110, 44, strokeColor=INK, strokeWidth=1.5, fillColor=None))
    d.add(String(75, 50, "ver pasos", fontName="Helvetica", fontSize=7,
                 fillColor=INK_SUAVE, textAnchor="middle"))
    d.add(String(75, 38, "abajo", fontName="Helvetica", fontSize=7,
                 fillColor=INK_SUAVE, textAnchor="middle"))
    _nota(d, nombre[:40])
    return d, "Esquema del procedimiento"


# ─── Niveles de Instrucción y Complejización Vocal ────────────────
_NIVEL_NOMBRE = {
    1: "Nivel 1: Concienciación",
    2: "Nivel 2: Ajuste TVSO",
    3: "Nivel 3: Modulación",
    4: "Nivel 4: Transferencia",
}
_NIVEL_DESC = {
    1: "Concienciación y desbloqueo postural/respiratorio, sin carga vocal.",
    2: "Ajuste fisiológico con tracto vocal semiocluido sostenido.",
    3: "Modulación y flexibilidad tonal sobre TVSO y resonancia.",
    4: "Transferencia al habla conversacional y automatización.",
}
_NIVEL_POR_EJERCICIO = {
    "le_huche": 1, "shiatsu_cabeza": 1, "rotacion_hombros": 1,
    "respiracion_abdominal": 1, "expansion_costo_lateral": 1,
    "masaje_laringeo": 1, "pautas_rlf": 1,
    "tubo_agua": 2, "popote_aire": 2, "vibracion_labial": 2,
    "consonantes_fricativas": 2, "oclusion_succion": 2,
    "soplo_escalonado": 2, "empuje_glotico": 2,
    "escalas_vocalicas": 3, "humming_m": 3, "descenso_laringeo": 3,
    "calentamiento": 3, "enfriamiento": 3,
    "frases_balanceadas": 4,
}
_EFECTO_POR_EJERCICIO = {
    "le_huche": "Libera tensión general y ordena la respiración",
    "shiatsu_cabeza": "Afloja mandíbula, sienes y cuello",
    "rotacion_hombros": "Suelta hombros y libera la laringe",
    "respiracion_abdominal": "Aire rendidor sin quedarse sin aire",
    "expansion_costo_lateral": "Más aire disponible al hablar",
    "masaje_laringeo": "Ablanda la musculatura del cuello",
    "pautas_rlf": "Protege las cuerdas del ácido",
    "tubo_agua": "Masaje vocal por presión de aire",
    "popote_aire": "Voz rendidora con poco esfuerzo",
    "vibracion_labial": "Suelta la lengua y empareja la voz",
    "consonantes_fricativas": "Lleva la voz hacia adelante",
    "oclusion_succion": "Baja la laringe y abre la faringe",
    "soplo_escalonado": "Ataque suave sin golpe de glotis",
    "empuje_glotico": "Cierre firme para voces débiles",
    "escalas_vocalicas": "Flexibilidad de agudos y graves",
    "humming_m": "Resonancia clara en la máscara",
    "descenso_laringeo": "Garganta abierta y relajada",
    "calentamiento": "Prepara la voz antes de usarla",
    "enfriamiento": "Devuelve la voz al reposo",
    "frases_balanceadas": "Lleva lo entrenado al habla real",
}


def _barra_complejidad(nivel: int):
    """Barra vectorial de 4 segmentos (rellenos según nivel)."""
    cells, widths = [], []
    for i in range(1, 5):
        cells.append("")
        widths.append(9 * mm)
    t = Table([cells], colWidths=widths, rowHeights=[5 * mm])
    style = [('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
             ('LEFTPADDING', (0, 0), (-1, -1), 1),
             ('RIGHTPADDING', (0, 0), (-1, -1), 1),
             ('BOX', (0, 0), (-1, -1), 0.6, INK_SUAVE)]
    for i in range(1, 5):
        if i <= nivel:
            style.append(('BACKGROUND', (i - 1, 0), (i - 1, 0), SECONDARY))
        else:
            style.append(('BACKGROUND', (i - 1, 0), (i - 1, 0), white))
    t.setStyle(TableStyle(style))
    return t


# ─── Propósitos en lenguaje cotidiano por sección ─────────────────
_PROPOSITO_SECCION = {
    "corporal": "Para aflojar el cuello, los hombros y la mandíbula, así la voz sale sin esfuerzo.",
    "laringeo": "Para bajar y soltar la laringe y hablar sin apretar la garganta.",
    "respiratorio": "Para aprender a usar bien el aire al hablar, sin quedarse sin aire.",
    "sovte": "Ejercicios con la boca casi cerrada que masajean y cuidan las cuerdas vocales.",
    "resonancia": "Para llevar la voz hacia adelante y que suene clara sin gritar.",
    "higiene": "Para cuidar la voz todos los días, como el calentamiento de un deportista.",
}

_ICONO_SECCION = {
    "corporal": "C", "laringeo": "L", "respiratorio": "R",
    "sovte": "S", "resonancia": "V", "higiene": "H",
}


def _get_styles():
    styles = getSampleStyleSheet()

    def _add(name, **kw):
        if name in styles:
            return
        styles.add(ParagraphStyle(name, **kw))

    _add('CoverTitle', parent=styles['Title'], fontSize=28, textColor=PRIMARY,
         spaceAfter=6 * mm, alignment=TA_CENTER, leading=34)
    _add('CoverSubtitle', parent=styles['Normal'], fontSize=14, textColor=SECONDARY,
         alignment=TA_CENTER, spaceAfter=4 * mm)
    _add('SectionTitle', parent=styles['Heading1'], fontSize=18, textColor=PRIMARY,
         spaceBefore=8 * mm, spaceAfter=4 * mm, leading=22)
    _add('ExerciseTitle', parent=styles['Heading2'], fontSize=18, textColor=SECONDARY,
         spaceBefore=2 * mm, spaceAfter=1 * mm, leading=22)
    _add('CuadBody', parent=styles['Normal'], fontSize=13, textColor=DARK_TEXT,
         alignment=TA_JUSTIFY, leading=17, spaceAfter=2 * mm)
    _add('PropositoText', parent=styles['Normal'], fontSize=13, textColor=PRIMARY,
         alignment=TA_LEFT, leading=17, spaceAfter=2 * mm)
    _add('StepText', parent=styles['Normal'], fontSize=16, textColor=DARK_TEXT,
         leading=21, spaceAfter=2 * mm)
    _add('CaptionText', parent=styles['Normal'], fontSize=10, textColor=GRAY_TEXT,
         alignment=TA_CENTER, leading=12)
    _add('GridText', parent=styles['Normal'], fontSize=8, textColor=DARK_TEXT,
         alignment=TA_CENTER, leading=10)
    _add('ContractTitle', parent=styles['Heading2'], fontSize=16, textColor=PRIMARY,
         spaceBefore=8 * mm, spaceAfter=3 * mm)
    _add('ContractText', parent=styles['Normal'], fontSize=12, textColor=DARK_TEXT,
         leading=16, spaceAfter=2 * mm)
    _add('FooterText', parent=styles['Normal'], fontSize=9, textColor=GRAY_TEXT,
         alignment=TA_CENTER)
    _add('PageNumber', parent=styles['Normal'], fontSize=9, textColor=GRAY_TEXT,
         alignment=TA_CENTER)
    return styles


def _prof(profesional: dict, key: str, default: str = "") -> str:
    """Lee un dato del profesional con fallback seguro."""
    if not isinstance(profesional, dict):
        return default
    v = profesional.get(key, default)
    return str(v or default).strip()


def _descargar_logo(url: str):
    """Descarga el logo del profesional a un temporal. Devuelve path o None."""
    url = (url or "").strip()
    if not url or not url.lower().startswith(("http://", "https://")):
        return None
    try:
        import httpx
        r = httpx.get(url, timeout=15, follow_redirects=True)
        if r.status_code != 200 or len(r.content) < 500:
            return None
        ctype = r.headers.get("content-type", "")
        ext = ".png"
        if "jpeg" in ctype or "jpg" in ctype:
            ext = ".jpg"
        elif "webp" in ctype:
            ext = ".webp"
        tmp = tempfile.NamedTemporaryFile(suffix=ext, delete=False)
        tmp.write(r.content)
        tmp.close()
        return tmp.name
    except Exception:
        return None


def _isologo_onda() -> Drawing:
    """Isologo vectorial: onda sonora + arcos de resonancia (marca del consultorio)."""
    W, H = 220, 72
    d = Drawing(W, H)
    # Arcos de resonancia a la izquierda
    for r in (14, 24, 34):
        pts = []
        for i in range(25):
            a = -0.9 + i * (1.8 / 24)
            pts += [52 + r * _math.cos(a), 36 + r * _math.sin(a)]
        d.add(PolyLine(pts, strokeColor=SECONDARY, strokeWidth=1.5))
    # Onda sonora continua
    pts = []
    for i in range(81):
        x = 66 + i * (W - 76) / 80
        y = 36 + _math.sin(i / 80 * _math.pi * 2 * 3) * 16 * _math.sin(i / 80 * _math.pi)
        pts += [x, y]
    d.add(PolyLine(pts, strokeColor=PRIMARY, strokeWidth=2))
    # Nodo central
    d.add(Circle(52, 36, 4, strokeColor=PRIMARY, strokeWidth=1.5,
                 fillColor=PRIMARY))
    return d


def _fondo_portada(canvas, doc):
    """Fondo cálido + marco elegante solo para la portada."""
    canvas.saveState()
    canvas.setFillColor(HexColor("#F8FAFC"))
    canvas.rect(0, 0, A4[0], A4[1], stroke=0, fill=1)
    canvas.setStrokeColor(SECONDARY)
    canvas.setLineWidth(1.2)
    canvas.rect(12 * mm, 12 * mm, A4[0] - 24 * mm, A4[1] - 24 * mm,
                stroke=1, fill=0)
    canvas.setStrokeColor(LIGHT_GRAY)
    canvas.setLineWidth(0.6)
    canvas.rect(14.5 * mm, 14.5 * mm, A4[0] - 29 * mm, A4[1] - 29 * mm,
                stroke=1, fill=0)
    canvas.restoreState()
    _add_page_number(canvas, doc)


def _build_cover(styles, titulo, paciente_nombre, sesiones, fecha, profesional=None):
    """Portada editorial médica limpia, centrada, marca blanca personal."""
    elements = []
    profesional = profesional if isinstance(profesional, dict) else {}

    elements.append(Spacer(1, 26 * mm))
    elements.append(_isologo_onda())
    elements.append(Spacer(1, 8 * mm))

    nombre = _prof(profesional, "profesional_nombre", "Lic. Matías Pérez")
    elements.append(Paragraph(escape(nombre), styles['CoverTitle']))
    rol = " ".join(x for x in [
        _prof(profesional, "profesional_titulo", "Fonoaudiólogo"),
        ("M.P. " + _prof(profesional, "profesional_matricula")) if _prof(profesional, "profesional_matricula") else "",
    ] if x).strip()
    elements.append(Paragraph(escape(rol), styles['CoverSubtitle']))
    elements.append(Paragraph("Consultorio de Voz y Rehabilitación Vocal",
                              styles['CoverSubtitle']))
    contacto = "  |  ".join(x for x in [
        _prof(profesional, "profesional_telefono"),
        _prof(profesional, "profesional_email"),
    ] if x).strip()
    if contacto:
        elements.append(Paragraph(escape(contacto), styles['CoverSubtitle']))
    redes = "  |  ".join(x for x in [
        _prof(profesional, "profesional_instagram"),
        _prof(profesional, "profesional_direccion"),
    ] if x).strip()
    if redes:
        elements.append(Paragraph(escape(redes), styles['CoverSubtitle']))

    logo_path = _descargar_logo(_prof(profesional, "profesional_logo_url"))
    if logo_path:
        try:
            from reportlab.platypus import Image as RLImage
            from reportlab.lib.utils import ImageReader
            iw, ih = ImageReader(logo_path).getSize()
            max_w, max_h = 45 * mm, 24 * mm
            scale = min(max_w / iw, max_h / ih, 1.0)
            logo_img = RLImage(logo_path, width=iw * scale, height=ih * scale)
            logo_img.hAlign = 'CENTER'
            elements.append(Spacer(1, 4 * mm))
            elements.append(logo_img)
        except Exception:
            pass

    elements.append(Spacer(1, 10 * mm))
    elements.append(Paragraph(escape(titulo or ""), styles['CoverSubtitle']))
    elements.append(Spacer(1, 8 * mm))

    info_data = [
        ["Paciente:", paciente_nombre or "Sin especificar"],
        ["Fecha de inicio:", fecha],
        ["Sesiones:", str(sesiones)],
        ["Profesional:", _prof(profesional, "profesional_nombre", "Su fonoaudiólogo/a")],
    ]
    info_table = Table(info_data, colWidths=[45 * mm, 90 * mm])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 12),
        ('TEXTCOLOR', (0, 0), (0, -1), PRIMARY),
        ('TEXTCOLOR', (1, 0), (1, -1), DARK_TEXT),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LINEBELOW', (0, -1), (-1, -1), 0.5, LIGHT_GRAY),
    ]))
    elements.append(info_table)
    elements.append(PageBreak())
    return elements


def _build_contract(styles, contrato):
    elements = []
    elements.append(Paragraph("Contrato Terapéutico", styles['ContractTitle']))
    elements.append(HRFlowable(width="100%", color=SECONDARY, thickness=1))
    elements.append(Spacer(1, 4 * mm))

    if isinstance(contrato, str):
        try:
            contrato = json.loads(contrato)
        except Exception:
            contrato = {}

    if contrato.get("frecuencia"):
        elements.append(Paragraph(
            f"<b>Frecuencia de las sesiones:</b> {escape(str(contrato['frecuencia']))}",
            styles['ContractText']
        ))
    if contrato.get("duracion_sesion"):
        elements.append(Paragraph(
            f"<b>Duración aproximada:</b> {escape(str(contrato['duracion_sesion']))}",
            styles['ContractText']
        ))
    if contrato.get("pautas_ausencias"):
        elements.append(Paragraph(
            f"<b>Pautas de asistencia:</b> {escape(str(contrato['pautas_ausencias']))}",
            styles['ContractText']
        ))

    elements.append(Spacer(1, 6 * mm))
    elements.append(Paragraph(
        "Este cuadernillo lo preparó su fonoaudiólogo/a según su evaluación. "
        "Haga los ejercicios con regularidad y sin forzar. Si siente dolor o "
        "molestia, pare y consulte a su profesional.",
        styles['ContractText']
    ))

    elements.append(Spacer(1, 8 * mm))
    elements.append(HRFlowable(width="40%", color=LIGHT_GRAY, thickness=0.5))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph("Firma del profesional: ___________________________", styles['ContractText']))
    elements.append(Paragraph("Firma del paciente:    ___________________________", styles['ContractText']))
    elements.append(Spacer(1, 4 * mm))

    return elements


def _build_exercise_card(styles, exercise, idx, seccion_id=""):
    """Tarjeta pedagógica: encabezado + propósito + curva + pictograma + pasos con casillas."""
    elements = []

    name = _sanear(_simplificar(exercise.get("name", "Ejercicio sin nombre")))
    desc = _sanear(_simplificar(exercise.get("description", "")))
    proposito = _PROPOSITO_SECCION.get(
        seccion_id, "Para entrenar y cuidar su voz todos los días.")
    icono = _ICONO_SECCION.get(seccion_id, "V")

    # Encabezado de tarjeta: ícono + título + propósito
    header_data = [[
        Paragraph(f"<font size=22 color='#ffffff'><b>{icono}</b></font>",
                  ParagraphStyle('IconCell', parent=styles['Normal'],
                                 alignment=TA_CENTER, textColor=white)),
        [
            Paragraph(f"{idx}. {escape(name)}", styles['ExerciseTitle']),
            Paragraph(f"<i>¿Para qué sirve? {escape(proposito)}</i>",
                      styles['PropositoText']),
        ],
    ]]
    header_table = Table(header_data, colWidths=[18 * mm, 140 * mm])
    header_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), SECONDARY),
        ('ROUNDEDCORNERS', [4, 4, 4, 4]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 2 * mm))

    # Badge de Nivel de Instrucción + efecto clínico (diferenciador)
    ex_id = str(exercise.get("id", "")).strip().lower()
    nivel = _NIVEL_POR_EJERCICIO.get(ex_id, 2)
    efecto = _EFECTO_POR_EJERCICIO.get(ex_id, "Entrena y cuida su voz")
    badge = Table([[
        Paragraph(f"<b>{_NIVEL_NOMBRE.get(nivel, 'Nivel 2: Ajuste TVSO')}</b>",
                  ParagraphStyle('BadgeCell', parent=styles['Normal'],
                                 fontSize=10, textColor=white, alignment=TA_CENTER)),
        Paragraph(f"Efecto: {escape(efecto)}",
                  ParagraphStyle('EfectoCell', parent=styles['Normal'],
                                 fontSize=10, textColor=DARK_TEXT, alignment=TA_LEFT)),
    ]], colWidths=[52 * mm, 120 * mm])
    badge.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), PRIMARY),
        ('ROUNDEDCORNERS', [3, 3, 3, 3]),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(badge)
    elements.append(Paragraph(
        f"<i>{escape(_NIVEL_DESC.get(nivel, ''))}</i>", styles['CaptionText']))
    elements.append(Spacer(1, 2 * mm))

    if desc:
        elements.append(Paragraph(escape(desc), styles['CuadBody']))

    # Ilustración IA autónoma (Pixazo/Gemini/proveedor pago, o modo libre);
    # si no hay nada configurado, dibujo vectorial. Nunca se rompe el PDF.
    try:
        from imagen_terapeutica import generar_imagen_ejercicio, imagen_ia_habilitada
        ai_img = generar_imagen_ejercicio(name, desc, exercise.get("id", "")) if imagen_ia_habilitada() else None
    except Exception:
        ai_img = None
    if ai_img:
        try:
            from reportlab.platypus import Image as RLImage
            from reportlab.lib.utils import ImageReader
            iw, ih = ImageReader(ai_img).getSize()
            max_w, max_h = 120 * mm, 70 * mm
            sc = min(max_w / iw, max_h / ih, 1.0)
            im = RLImage(ai_img, width=iw * sc, height=ih * sc)
            im.hAlign = 'CENTER'
            elements.append(im)
            elements.append(Paragraph("Ilustración de apoyo generada para este ejercicio",
                                      styles['CaptionText']))
            elements.append(Spacer(1, 2 * mm))
        except Exception:
            pass

    # Maquetación editorial: instrucciones + casillas a la IZQUIERDA,
    # panel gráfico (curva + ilustración única) a la DERECHA.
    tipo = _tipo_curva(exercise)
    duration = exercise.get("duration_min", "")
    seg_label = f"{duration} min" if tipo == "sostenido" and duration else ""
    curva = _curva_melodica(tipo, segundos=seg_label)
    ilust, ilust_cap = _ilustracion(exercise)

    panel_grafico = [
        curva,
        Paragraph(f"Su voz debe sonar así:<br/>{_CURVA_TITULO[tipo]}",
                  styles['CaptionText']),
        ilust,
        Paragraph(f"Dibujo: {ilust_cap}", styles['CaptionText']),
    ]
    if duration:
        panel_grafico.append(Paragraph(
            f"<b>{duration} min por día</b>", styles['CaptionText']))

    # Pasos numerados con casillas grandes para tildar (columna izquierda)
    steps = exercise.get("steps", []) or []
    if steps:
        rows = []
        for i, step in enumerate(steps, 1):
            txt = _sanear(_simplificar(step))
            rows.append([
                _checkbox(),
                Paragraph(f"<b>{i}.</b> &nbsp;{escape(txt)}", styles['StepText']),
            ])
        pasos_tabla = Table(rows, colWidths=[12 * mm, 92 * mm])
        pasos_tabla.setStyle(TableStyle([
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LINEBELOW', (0, 0), (-1, -2), 0.4, LIGHT_GRAY),
            ('LEFTPADDING', (0, 0), (-1, -1), 1),
            ('RIGHTPADDING', (0, 0), (-1, -1), 1),
        ]))
    else:
        pasos_tabla = Paragraph("Siga la curva y el dibujo de la derecha.",
                                styles['CuadBody'])

    complejidad = Table([[
        Paragraph("<b>Nivel de complejidad:</b>", styles['CaptionText']),
        _barra_complejidad(nivel),
        Paragraph(f"<b>{nivel}/4</b>", styles['CaptionText']),
    ]], colWidths=[52 * mm, 40 * mm, 12 * mm])
    complejidad.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 1),
        ('RIGHTPADDING', (0, 0), (-1, -1), 1),
    ]))
    dosis_txt = f"<b>Dosis: {duration} min/día</b>" if duration else ""
    left_cell = [pasos_tabla, Spacer(1, 2 * mm), complejidad]
    if dosis_txt:
        left_cell.append(Paragraph(dosis_txt, styles['CuadBody']))

    card = Table([[left_cell, panel_grafico]], colWidths=[108 * mm, 64 * mm])
    card.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LEFTPADDING', (0, 0), (-1, -1), 2),
        ('RIGHTPADDING', (0, 0), (-1, -1), 2),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('BOX', (0, 0), (-1, -1), 0.6, LIGHT_GRAY),
        ('LINEBELOW', (0, 0), (-1, 0), 0, white),
        ('BACKGROUND', (1, 0), (1, 0), FONDO_SUAVE),
    ]))
    elements.append(card)
    elements.append(Spacer(1, 3 * mm))

    phrases = exercise.get("phrases", []) or []
    if phrases:
        elements.append(Spacer(1, 2 * mm))
        elements.append(Paragraph("<b>Frases para practicar (lea en voz alta y clara):</b>",
                                  styles['CuadBody']))
        for phrase in phrases:
            elements.append(Table(
                [[_checkbox(),
                  Paragraph(escape(_sanear(_simplificar(str(phrase)))),
                            styles['StepText'])]],
                colWidths=[12 * mm, 148 * mm],
                style=TableStyle([
                    ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                    ('TOPPADDING', (0, 0), (-1, -1), 2),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ])))

    elements.append(Spacer(1, 4 * mm))
    elements.append(HRFlowable(width="100%", color=SECONDARY, thickness=1))
    elements.append(Spacer(1, 4 * mm))
    return elements


def _build_weekly_grid(styles):
    """Grilla de horarios semanales Lun-Vie de 7 a 22 h."""
    elements = []
    elements.append(Paragraph("Mi Horario Semanal de Ejercicios", styles['SectionTitle']))
    elements.append(HRFlowable(width="100%", color=SECONDARY, thickness=1))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "Marque con una <b>X dos turnos por día</b> para hacer sus ejercicios "
        "(por ejemplo, a la mañana y a la tarde). Trate de cumplirlos toda la semana.",
        styles['CuadBody']))

    header = ["Hora", "Lunes", "Martes", "Miércoles", "Jueves", "Viernes"]
    data = [header]
    for h in range(7, 23):
        data.append([f"{h:02d}:00", "", "", "", "", ""])

    col_w = [16 * mm, 28 * mm, 28 * mm, 28 * mm, 28 * mm, 28 * mm]
    table = Table(data, colWidths=col_w, repeatRows=1)
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('GRID', (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
    ]
    table.setStyle(TableStyle(style_cmds))
    elements.append(table)
    elements.append(Spacer(1, 3 * mm))
    return elements


def _build_tme_log(styles):
    """Tabla de registro diario de TME en segundos."""
    elements = []
    elements.append(Paragraph("Mi Registro Diario de Aire (TME en segundos)",
                              styles['SectionTitle']))
    elements.append(HRFlowable(width="100%", color=SECONDARY, thickness=1))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "Una vez por día, tome aire y largue el aire con una <b>S</b> suave "
        "todo lo que pueda. Anote cuántos segundos duró y cómo sintió su voz. "
        "Así vemos cómo mejora su control del aire.",
        styles['CuadBody']))

    data = [["Fecha", "Segundos logrados", "Sensación vocal", "[ ]"]]
    for _ in range(12):
        data.append(["", "", "", "[ ]"])
    table = Table(data, colWidths=[32 * mm, 38 * mm, 62 * mm, 28 * mm],
                  repeatRows=1)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
    ]))
    elements.append(table)
    elements.append(Spacer(1, 3 * mm))
    return elements


_VHI_SIMPLE = [
    "Mi voz me dificulta que me entiendan.",
    "Siento que tengo que esforzarme para hablar.",
    "Mi voz me limita en mi vida personal y social.",
    "Pierdo el control de mi voz o se me corta.",
    "Mi voz se cansa cuando hablo mucho.",
]


def _build_self_assessment(styles):
    """Autoevaluación vocal 0-10 + VHI simplificado antes/después."""
    elements = []
    elements.append(Paragraph("¿Cómo Va Mi Voz? (autoevaluación)",
                              styles['SectionTitle']))
    elements.append(HRFlowable(width="100%", color=SECONDARY, thickness=1))
    elements.append(Spacer(1, 2 * mm))
    elements.append(Paragraph(
        "Complete esta página <b>antes de empezar</b> y otra vez <b>al terminar "
        "las 8 sesiones</b>. Así vemos juntos si el tratamiento está funcionando.",
        styles['CuadBody']))

    elements.append(Paragraph(
        "<b>1) Del 0 al 10, ¿qué puntaje le da hoy a su voz?</b> "
        "(0 = sin voz / muy mala, 10 = voz óptima). Marque con una X:",
        styles['CuadBody']))
    scale_row = ["Antes:"] + [f"[ {n} ]" for n in range(11)]
    scale_row2 = ["Después:"] + [f"[ {n} ]" for n in range(11)]
    scale_table = Table([scale_row, scale_row2],
                        colWidths=[22 * mm] + [12 * mm] * 11)
    scale_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
    ]))
    elements.append(scale_table)
    elements.append(Spacer(1, 4 * mm))

    elements.append(Paragraph(
        "<b>2) ¿Con qué frecuencia le pasan estas cosas?</b> "
        "0 = Nunca &nbsp;&nbsp; 1 = Casi nunca &nbsp;&nbsp; 2 = A veces &nbsp;&nbsp; "
        "3 = Casi siempre &nbsp;&nbsp; 4 = Siempre",
        styles['CuadBody']))
    vhi_data = [["Situación", "Antes (0-4)", "Después (0-4)"]]
    for item in _VHI_SIMPLE:
        vhi_data.append([item, "[0] [1] [2] [3] [4]", "[0] [1] [2] [3] [4]"])
    vhi_table = Table(vhi_data, colWidths=[80 * mm, 40 * mm, 40 * mm],
                      repeatRows=1)
    vhi_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY),
        ('TEXTCOLOR', (0, 0), (-1, 0), white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 11),
        ('ALIGN', (1, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('GRID', (0, 0), (-1, -1), 0.5, LIGHT_GRAY),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [white, LIGHT_BG]),
    ]))
    elements.append(vhi_table)
    elements.append(Spacer(1, 3 * mm))
    elements.append(Paragraph(
        "<b>¿Mejoró su puntaje?</b> Si su nota del 0 al 10 subió 2 o más puntos, "
        "o si estas frases le pasan menos seguido, el tratamiento está funcionando bien. "
        "Felicitaciones por su constancia.",
        styles['CuadBody']))
    return elements


def _add_page_number(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 9)
    canvas.setFillColor(GRAY_TEXT)
    canvas.drawCentredString(A4[0] / 2, 15 * mm, f"Página {doc.page}")
    canvas.setFont('Helvetica', 8)
    canvas.drawString(15 * mm, 15 * mm, getattr(doc, '_prof_pie_izq', ''))
    canvas.drawRightString(A4[0] - 15 * mm, 15 * mm, getattr(doc, '_prof_pie_der', ''))
    canvas.restoreState()


def generar_cuadernillo_pdf(
    paciente_nombre: str,
    titulo: str,
    sesiones: int,
    ejercicios: list,
    contrato: dict,
    notas: str = "",
    profesional: dict = None,
) -> str:
    fecha = __import__('datetime').datetime.now().strftime("%d/%m/%Y")
    profesional = profesional if isinstance(profesional, dict) else {}

    tmp_file = tempfile.NamedTemporaryFile(suffix=".pdf", delete=False)
    pdf_path = tmp_file.name
    tmp_file.close()

    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=A4,
        topMargin=18 * mm,
        bottomMargin=25 * mm,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        title=titulo or "Cuadernillo Terapéutico Vocal",
        author=_prof(profesional, "profesional_nombre", "Lic. Matías Pérez"),
        subject="Cuadernillo terapéutico vocal personalizado",
        keywords="fonoaudiología, voz, terapia vocal, ejercicios",
    )

    styles = _get_styles()
    story = []

    pie_izq = _prof(profesional, "profesional_nombre")
    pie_der = _prof(profesional, "profesional_telefono") or _prof(profesional, "profesional_email")
    doc._prof_pie_izq = pie_izq
    doc._prof_pie_der = pie_der

    story.extend(_build_cover(styles, titulo, paciente_nombre, sesiones, fecha,
                              profesional=profesional))
    story.extend(_build_contract(styles, contrato))

    story.append(Paragraph("Mis Ejercicios de Voz", styles['SectionTitle']))
    story.append(HRFlowable(width="100%", color=SECONDARY, thickness=1))
    story.append(Spacer(1, 2 * mm))
    story.append(Paragraph(
        "Cada ejercicio trae su dibujo de cómo debe sonar su voz. "
        "Siga los pasos en orden y tilde cada casilla cuando lo complete.",
        styles['CuadBody']))

    for idx, ex in enumerate(ejercicios, 1):
        ex = dict(ex or {})
        story.extend(_build_exercise_card(styles, ex, idx,
                                          seccion_id=str(ex.get("seccion_id", ""))))

    story.append(PageBreak())
    story.extend(_build_weekly_grid(styles))
    story.append(PageBreak())
    story.extend(_build_tme_log(styles))
    story.append(PageBreak())
    story.extend(_build_self_assessment(styles))

    if notas:
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph("Notas de su Profesional", styles['SectionTitle']))
        story.append(HRFlowable(width="100%", color=SECONDARY, thickness=1))
        story.append(Spacer(1, 4 * mm))
        story.append(Paragraph(escape(_simplificar(notas)), styles['CuadBody']))

    story.append(Spacer(1, 15 * mm))
    firma_txt = _prof(profesional, "profesional_nombre", "Su profesional tratante")
    story.append(Paragraph(
        f"Este material fue preparado por {escape(firma_txt)} para uso exclusivo "
        "del paciente. Si siente dolor o molestia, suspenda los ejercicios y consulte.",
        styles['FooterText']
    ))

    doc.build(story, onFirstPage=_fondo_portada, onLaterPages=_add_page_number)
    return pdf_path
