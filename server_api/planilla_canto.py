"""Alumnos de canto desde la planilla que comparte Fonoar (Google Sheets).

Planilla "ALUMNOS DE CANTO 2026", pestaña "MATIAS":

    DÍA | HORA | ALUMNOS | EDAD | DNI | CELULAR | EMAIL | NOVIEMBRE | DICIEMBRE …
    MIÉRCOLES | 15 HS | Lara Rozenfeld | 18 | … | $20.000 por TRF el 4/11 …
    18/11 a las 6 hs y 25/11 a las 10 am | 16 HS | Juan Ignacio Soracco | 14 | …
    MIÉRCOLES | 17 HS |                       ← horario libre (se ignora)
    …
    Liquidacion Matias Perez- NOVIEMBRE
    ACTIVIDAD | ALUMNOS | PAGO | DOCENTE 60%
    Canto individual | Lara Rozenfeld | $80,000 | $48,000

Reglas (confirmadas con el profesional):
- DÍA con nombre de día = horario fijo semanal (DÍA + HORA). Una fila sin
  día hereda el último día visto (por defecto miércoles, día de Fonoar).
- DÍA con fechas ("18/11 a las 6 hs y 25/11 a las 10 am") = reemplazos
  puntuales de esa semana; el horario fijo sigue siendo la HORA de la fila.
  "6 hs" sin am/pm y menor a 8 → 18 h.
- Se generan las clases de las próximas 4 semanas (el script corre cada día,
  así que se renuevan solas). No se duplica: si el alumno ya tiene un turno
  ese día (por ejemplo, desde la agenda de Fonoar), no se agrega otro.
- Las columnas con nombre de mes guardan el estado de pago de ese mes.
"""
import hashlib
import hmac
import re
import traceback
import unicodedata
from datetime import date, datetime, timedelta

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter()

SEMANAS = 4
DURACION_CLASE = 60
DIAS = {"lunes": 0, "martes": 1, "miercoles": 2, "jueves": 3, "viernes": 4, "sabado": 5, "domingo": 6}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
         "septiembre", "octubre", "noviembre", "diciembre"]
DIA_DEFECTO = 2  # miércoles


def _n(t) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(t or "").lower())
                   if unicodedata.category(c) != "Mn").strip()


def _hora(texto: str, tarde_si_temprano: bool = True):
    """'15 HS' → (15, 0); '16:30' → (16, 30); '6 hs' → (18, 0); '10 am' → (10, 0)."""
    m = re.search(r"(\d{1,2})(?:[:.](\d{2}))?\s*(am|pm|hs|h)?", _n(texto))
    if not m:
        return None
    h, mi, suf = int(m.group(1)), int(m.group(2) or 0), m.group(3) or ""
    if suf == "pm" and h < 12:
        h += 12
    elif suf != "am" and tarde_si_temprano and h < 8:
        h += 12
    return (h, mi) if 0 <= h <= 23 and 0 <= mi <= 59 else None


def _reemplazos(texto: str, anio: int) -> list:
    """'18/11 a las 6 hs y 25/11 a las 10 am' → [(date(…,11,18), (18,0)), (…,(10,0))]."""
    out = []
    for m in re.finditer(r"(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\s*(?:a\s*las\s*)?([\d:.]+\s*(?:am|pm|hs|h)?)?",
                         _n(texto)):
        d, mes = int(m.group(1)), int(m.group(2))
        a = int(m.group(3)) if m.group(3) else anio
        a = a + 2000 if a < 100 else a
        try:
            f = date(a, mes, d)
        except ValueError:
            continue
        out.append((f, _hora(m.group(4)) if m.group(4) else None))
    return out


def parsear_planilla(filas: list, hoy: date = None) -> dict:
    """filas: valores de la pestaña (lista de listas de texto)."""
    hoy = hoy or __import__("fechas").hoy_ar()
    alumnos, liquidacion, mes_liq = [], [], ""
    idx = None
    dia_actual = DIA_DEFECTO
    en_liq = False
    for fila in filas:
        celdas = [str(c or "").strip() for c in fila]
        normal = [_n(c) for c in celdas]
        unido = " ".join(normal)
        if "liquidacion" in unido:
            en_liq = True
            m = re.search(r"(" + "|".join(MESES) + r")", unido)
            mes_liq = m.group(1).capitalize() if m else ""
            continue
        if en_liq:
            if "actividad" in normal or not any(celdas):
                continue
            if len(celdas) >= 3 and celdas[1]:
                liquidacion.append({"actividad": celdas[0], "alumno": celdas[1],
                                    "pago": celdas[2], "docente": celdas[3] if len(celdas) > 3 else ""})
            elif len(celdas) >= 4 and celdas[3]:
                liquidacion.append({"actividad": "Total", "alumno": "", "pago": celdas[2], "docente": celdas[3]})
            continue
        if idx is None:
            if "alumnos" in normal and "hora" in normal:
                idx = {nombre: i for i, nombre in enumerate(normal) if nombre}
            continue
        def col(nombre):
            i = idx.get(nombre)
            return celdas[i] if i is not None and i < len(celdas) else ""
        dia_txt, nombre = col("dia"), col("alumnos")
        dn = _n(dia_txt)
        for d, n in DIAS.items():
            if d in dn:
                dia_actual = n
                break
        if not nombre:
            continue  # horario libre
        hora = _hora(col("hora"))
        pagos = {m.capitalize(): celdas[i] for m in MESES
                 for nom, i in idx.items() if nom == m and i < len(celdas) and celdas[i]}
        alumnos.append({
            "nombre": " ".join(w.capitalize() for w in nombre.split()),
            "dia_semana": dia_actual, "hora": hora,
            "reemplazos": _reemplazos(dia_txt, hoy.year),
            "edad": col("edad"), "dni": re.sub(r"\D", "", col("dni")),
            "celular": re.sub(r"[^\d+]", "", col("celular")), "email": col("email"),
            "pagos": pagos,
        })
    return {"alumnos": alumnos, "liquidacion": {"mes": mes_liq, "items": liquidacion}}


def clases_proximas(alumno: dict, hoy: date, semanas: int = SEMANAS) -> list:
    """Fechas y horas de las clases de las próximas semanas, con reemplazos."""
    if not alumno.get("hora"):
        return []
    fin = hoy + timedelta(days=7 * semanas)
    reemplazos = alumno.get("reemplazos") or []
    clases = []
    d = hoy
    while d <= fin:
        if d.weekday() == alumno["dia_semana"]:
            # Un reemplazo en la misma semana reemplaza la clase fija.
            lunes = d - timedelta(days=d.weekday())
            if not any(lunes <= f < lunes + timedelta(days=7) for f, _h in reemplazos):
                clases.append((d, alumno["hora"]))
        d += timedelta(days=1)
    for f, h in reemplazos:
        if hoy <= f <= fin:
            clases.append((f, h or alumno["hora"]))
    return sorted(clases)


# ─── Importación ───────────────────────────────────────────────────────

def importar_planilla(datos: dict, sb=None, hoy: date = None, simular: bool = False) -> dict:
    from agenda_fonoar import CENTRO_FONOAR, _actualizar_paciente, _insertar_paciente, clave_nombre
    if sb is None:
        from api_clinica import supabase as sb
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    hoy = hoy or __import__("fechas").hoy_ar()
    existentes = sb.table("pacientes").select("*").limit(5000).execute().data or []
    por_dni = {re.sub(r"\D", "", str(p.get("dni") or "")): p for p in existentes if p.get("dni")}
    por_nombre = {}
    for p in existentes:
        por_nombre.setdefault(clave_nombre(p.get("nombre_completo") or p.get("nombre") or ""), []).append(p)

    res = {"simulacion": simular, "alumnos_nuevos": 0, "alumnos_actualizados": 0,
           "clases_nuevas": 0, "clases_existentes": 0, "detalle": [], "avisos": [],
           "liquidacion": datos.get("liquidacion")}
    for a in datos.get("alumnos") or []:
        k = clave_nombre(a["nombre"])
        cand = ([por_dni[a["dni"]]] if a.get("dni") and a["dni"] in por_dni else
                por_nombre.get(k) or [p for kk, ps in por_nombre.items() for p in ps
                                      if len(k) >= 2 and len(kk) >= 2 and (k <= kk or kk <= k)])
        alumno = cand[0] if cand else None
        datos_canto = {"edad": a.get("edad"), "pagos": a.get("pagos") or {},
                       "horario": f"{list(DIAS)[a['dia_semana']].capitalize()} "
                                  f"{a['hora'][0]:02d}:{a['hora'][1]:02d}" if a.get("hora") else ""}
        item = {"alumno": a["nombre"], "horario": datos_canto["horario"], "pagos": a.get("pagos") or {}}
        if alumno:
            item["accion"] = "existente"
            cambios = {"tipo_atencion": "canto", "datos_canto": datos_canto}
            for campo, valor in (("telefono", a.get("celular")), ("email", a.get("email")), ("dni", a.get("dni"))):
                if valor and not str(alumno.get(campo) or "").strip() or (campo == "dni" and valor and
                                                                          str(alumno.get("dni") or "").startswith("SD-")):
                    cambios[campo] = valor
            if not alumno.get("centro"):
                cambios["centro"] = CENTRO_FONOAR
            item["accion"] = "actualizado"
            res["alumnos_actualizados"] += 1
            if not simular:
                base = {c: v for c, v in cambios.items() if c in ("telefono", "email", "dni")}
                nuevos = {c: v for c, v in cambios.items() if c not in base}
                if base:
                    try:
                        sb.table("pacientes").update(base).eq("id", alumno["id"]).execute()
                    except Exception as e:
                        res["avisos"].append(f"{a['nombre']}: no se actualizaron datos de contacto ({str(e)[:80]}).")
                res["avisos"] += _actualizar_paciente(sb, alumno["id"], nuevos)
        else:
            item["accion"] = "nuevo"
            res["alumnos_nuevos"] += 1
            if not simular:
                alumno, avisos = _insertar_paciente(sb, {
                    "nombre_completo": a["nombre"], "nombre": a["nombre"], "dni": a.get("dni") or None,
                    "telefono": a.get("celular", ""), "email": a.get("email", ""),
                    "centro": CENTRO_FONOAR, "origen": "planilla_canto",
                    "tipo_atencion": "canto", "datos_canto": datos_canto,
                    "notas_iniciales": f"Alumno/a de canto (planilla de Fonoar). Edad: {a.get('edad') or 's/d'}.",
                })
                res["avisos"] += avisos
                por_nombre.setdefault(k, []).append(alumno)
        clases = clases_proximas(a, hoy)
        item["clases"] = [f"{f.strftime('%d/%m')} {h[0]:02d}:{h[1]:02d}" for f, h in clases]
        for f, h in clases:
            ya = False
            if alumno and alumno.get("id"):
                try:
                    ya = bool(sb.table("turnos").select("id").eq("paciente_id", alumno["id"])
                              .gte("fecha_hora", f"{f.isoformat()}T00:00:00-03:00")
                              .lte("fecha_hora", f"{f.isoformat()}T23:59:59-03:00").execute().data)
                except Exception:
                    ya = False
            if ya:
                res["clases_existentes"] += 1
                continue
            res["clases_nuevas"] += 1
            if not simular:
                sb.table("turnos").insert({
                    "paciente_id": alumno["id"],
                    "fecha_hora": f"{f.isoformat()}T{h[0]:02d}:{h[1]:02d}:00-03:00",
                    "duracion_min": DURACION_CLASE, "tipo": "control", "estado": "programado",
                    "modalidad": "PRESENCIAL", "motivo": "Clase de canto",
                    "notas": "Importado de la planilla de alumnos de canto (Fonoar)",
                }).execute()
        res["detalle"].append(item)
    res["avisos"] = list(dict.fromkeys(res["avisos"]))
    return res


# ─── Rutas ─────────────────────────────────────────────────────────────

def _clave_script() -> str:
    from agenda_fonoar import clave_script
    return clave_script()


def _filas_desde_texto(texto: str) -> list:
    """Texto pegado desde Google Sheets (celdas separadas por tabulador)."""
    return [linea.split("\t") for linea in (texto or "").splitlines()]


def _ejecutar(body: dict) -> JSONResponse:
    filas = body.get("filas") or _filas_desde_texto(body.get("contenido") or "")
    datos = parsear_planilla(filas)
    if not datos["alumnos"]:
        return JSONResponse(content={"ok": False, "error": "No se encontraron alumnos (¿falta la fila de títulos DÍA | HORA | ALUMNOS?)."})
    try:
        return JSONResponse(content={"ok": True, **importar_planilla(datos, simular=bool(body.get("simular")))})
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"ok": False, "error": f"No se pudo importar: {str(e)[:200]}"})


@router.post("/api/canto/importar-planilla")
async def importar(request: Request):
    """Desde la app (pegado manual). Body: {contenido | filas, simular?}."""
    return _ejecutar(await request.json())


@router.post("/api/canto/importar-planilla/script")
async def importar_script(request: Request):
    """Desde el script de Google (cada día). Header X-Clave-Agenda."""
    clave = request.headers.get("x-clave-agenda", "")
    if not clave or not hmac.compare_digest(clave, _clave_script()):
        raise HTTPException(status_code=401, detail="Clave inválida")
    return _ejecutar(await request.json())
