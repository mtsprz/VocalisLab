"""Fechas y horas del consultorio: TODO en hora de Argentina.

El servidor (Render) corre en UTC: `date.today()` o `datetime.now()` dan el
día/hora de Greenwich (3 h adelantado; después de las 21 h ya es "mañana").
Supabase devuelve los timestamptz en UTC, así que cortar el texto
("2026-11-20T01:30:00+00:00"[:10]) da el día equivocado. Usar siempre este
módulo para: hoy, ahora, el día de un timestamp y los textos para mostrar.
"""
import re
import unicodedata
from datetime import date, datetime, time, timedelta, timezone

try:
    from zoneinfo import ZoneInfo
    ZONA = ZoneInfo("America/Argentina/Buenos_Aires")
except Exception:  # sin base de zonas (Windows sin tzdata): Argentina no tiene horario de verano
    ZONA = timezone(timedelta(hours=-3))

DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
DIAS_CORTOS = ["lun", "mar", "mié", "jue", "vie", "sáb", "dom"]
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]


def ahora_ar() -> datetime:
    return datetime.now(ZONA)


def hoy_ar() -> date:
    return ahora_ar().date()


def a_ar(valor):
    """Timestamp (texto ISO, datetime o date) → datetime en hora de Argentina.
    Una fecha sola se toma al mediodía (no cambia de día). Sin zona: hora
    argentina. Devuelve None si no se puede leer."""
    if valor in (None, ""):
        return None
    if isinstance(valor, datetime):
        dt = valor
    elif isinstance(valor, date):
        return datetime.combine(valor, time(12, 0), ZONA)
    else:
        t = str(valor).strip().replace("Z", "+00:00").replace(" ", "T", 1)
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
            return datetime.combine(date.fromisoformat(t), time(12, 0), ZONA)
        t = re.sub(r"(\.\d{6})\d+", r"\1", t)  # Postgres puede traer más de 6 decimales
        try:
            dt = datetime.fromisoformat(t)
        except ValueError:
            return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=ZONA)
    return dt.astimezone(ZONA)


def dia_ar(valor) -> str:
    """'AAAA-MM-DD' del día en Argentina ('' si no se puede leer)."""
    dt = a_ar(valor)
    return dt.date().isoformat() if dt else ""


def txt(valor, hora: bool = True, anio: bool = False) -> str:
    """'jue 26/11 10:00' (en castellano y hora de Argentina)."""
    dt = a_ar(valor)
    if not dt:
        return str(valor or "")
    s = f"{DIAS_CORTOS[dt.weekday()]} {dt.strftime('%d/%m')}"
    if anio:
        s += dt.strftime("/%Y")
    if hora and not (isinstance(valor, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", valor.strip())):
        s += dt.strftime(" %H:%M")
    return s


def largo(d) -> str:
    """'jueves 26 de noviembre de 2026'."""
    dt = a_ar(d)
    return f"{DIAS[dt.weekday()]} {dt.day} de {MESES[dt.month - 1]} de {dt.year}" if dt else ""


def iso_ar(dia: date, hhmm: str) -> str:
    """Timestamp con zona para guardar un turno: '2026-11-26T10:00:00-03:00'."""
    h, m = hhmm.split(":")
    return datetime.combine(dia, time(int(h), int(m)), ZONA).isoformat()


# ─── Lenguaje natural → fecha y hora (sin depender del modelo) ─────────

def _n(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower())
                   if unicodedata.category(c) != "Mn").strip()


_DIA_IDX = {_n(d): i for i, d in enumerate(DIAS)}
_MES_IDX = {_n(m): i + 1 for i, m in enumerate(MESES)} | {"setiembre": 9}


def resolver_fecha(texto, hoy: date = None) -> date:
    """'hoy', 'mañana', 'pasado mañana', 'jueves', 'el próximo martes',
    'martes que viene', 'en 3 días', '26/11', '26/11/2026', '26 de noviembre',
    '2026-11-26'. Un día de semana es el PRÓXIMO con ese nombre: dicho el
    mismo día, es el de la semana siguiente salvo 'este jueves' (= hoy).
    Una fecha sin año ya pasada se toma del año siguiente."""
    hoy = hoy or hoy_ar()
    t = _n(str(texto or ""))
    este = bool(re.match(r"(para )?(este|esta)\s", t))
    t = re.sub(r"^(el|la|para el|para la|este|esta)\s+", "", t).strip(" .,")
    if not t:
        raise ValueError("Falta la fecha.")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", t):
        return date.fromisoformat(t)
    if t == "hoy":
        return hoy
    if t in ("manana", "mañana"):
        return hoy + timedelta(days=1)
    if t in ("pasado manana", "pasado"):
        return hoy + timedelta(days=2)
    m = re.fullmatch(r"en (\d{1,2}) dias?", t)
    if m:
        return hoy + timedelta(days=int(m.group(1)))
    m = re.fullmatch(r"(?:(?:el )?proximo |(?:el )?siguiente )?(\w+?)(?: (?:que viene|proximo|de la semana que viene))?", t)
    if m and m.group(1) in _DIA_IDX:
        objetivo = _DIA_IDX[m.group(1)]
        delta = (objetivo - hoy.weekday()) % 7
        if delta == 0 and not este:  # "el viernes" dicho un viernes = el de la semana próxima
            delta = 7
        if re.search(r"semana que viene", t) and delta < 7:
            # "el martes de la semana que viene": el martes de la semana próxima (lunes a domingo).
            lunes_prox = hoy + timedelta(days=7 - hoy.weekday())
            return lunes_prox + timedelta(days=objetivo)
        return hoy + timedelta(days=delta)
    # "jueves 26/11" o "jueves 26": se valida que coincidan.
    m = re.fullmatch(r"(\w+?) (\d{1,2}(?:[/-]\d{1,2}(?:[/-]\d{2,4})?)?(?: de \w+(?: de \d{4})?)?)", t)
    if m and m.group(1) in _DIA_IDX:
        d = resolver_fecha(m.group(2), hoy)
        if d.weekday() != _DIA_IDX[m.group(1)]:
            raise ValueError(f"El {d.strftime('%d/%m/%Y')} es {DIAS[d.weekday()]}, no {DIAS[_DIA_IDX[m.group(1)]]}. "
                             "¿Qué fecha es?")
        return d
    m = re.fullmatch(r"(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?", t)
    if m:
        dd, mm, aa = int(m.group(1)), int(m.group(2)), m.group(3)
        return _armar(dd, mm, aa, hoy)
    m = re.fullmatch(r"(\d{1,2}) de (\w+)(?: (?:de )?(\d{4}))?", t)
    if m and m.group(2) in _MES_IDX:
        return _armar(int(m.group(1)), _MES_IDX[m.group(2)], m.group(3), hoy)
    m = re.fullmatch(r"(\d{1,2})", t)
    if m:  # "el 26": este mes, o el que viene si ya pasó
        dd = int(m.group(1))
        d = _armar(dd, hoy.month, str(hoy.year), hoy)
        if d < hoy:
            mes = hoy.month % 12 + 1
            d = _armar(dd, mes, str(hoy.year + (1 if mes == 1 else 0)), hoy)
        return d
    raise ValueError(f"No entiendo la fecha «{texto}». Decímela como «jueves», «26/11» o «26 de noviembre».")


def _armar(dd: int, mm: int, aa, hoy: date) -> date:
    try:
        if aa:
            a = int(aa)
            return date(a + 2000 if a < 100 else a, mm, dd)
        d = date(hoy.year, mm, dd)
        return d if d >= hoy - timedelta(days=1) else date(hoy.year + 1, mm, dd)
    except ValueError:
        raise ValueError(f"La fecha {dd:02d}/{mm:02d} no existe.")


def resolver_hora(texto) -> str:
    """'10', '10:30', '10.30', '10hs', '10 y media', '9 y cuarto', '5 de la tarde',
    '17h' → 'HH:MM'. De 1 a 7 sin aclaración se toma como de la tarde
    (no hay atención de madrugada)."""
    t = _n(str(texto or ""))
    t = re.sub(r"(\d)\s*h(?=\d)", r"\1:", t)                 # 17h30 → 17:30
    t = re.sub(r"(\d)\s*(?:hs|hrs?|h)\b\.?", r"\1", t)       # 10hs → 10
    t = re.sub(r"^(a las|las|a la|la)\s+", "", t).strip(" .")
    tarde = bool(re.search(r"de la (tarde|noche)|\bpm\b", t))
    t = re.sub(r"de la (manana|tarde|noche)|\b[ap]m\b", "", t).strip()
    m = re.fullmatch(r"(\d{1,2})(?:\s*[:.]\s*(\d{2}))?\s*(y media|y cuarto|menos cuarto)?", t)
    if not m:
        raise ValueError(f"No entiendo la hora «{texto}». Decímela como «10:30».")
    h, mi = int(m.group(1)), int(m.group(2) or 0)
    if m.group(3) == "y media":
        mi = 30
    elif m.group(3) == "y cuarto":
        mi = 15
    if tarde and h < 12:
        h += 12
    elif not tarde and 1 <= h <= 7:
        h += 12
    if m.group(3) == "menos cuarto":
        h, mi = h - 1, 45
    if not (0 <= h <= 23 and 0 <= mi <= 59):
        raise ValueError(f"La hora «{texto}» no es válida.")
    return f"{h:02d}:{mi:02d}"
