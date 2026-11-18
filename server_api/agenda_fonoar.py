"""Centros de atención e importación de la agenda de Fonoar.

Fonoar manda cada martes (día previo a la atención) un mail a la cuenta del
consultorio con asunto "Fonoar: Turnos del DD/MM/AAAA Mat: NNNN" y una tabla:

    Hora | Paciente | O.Social | Telefono
    Estudios                                  ← fila de sección
    09:30 | ALVAREZ YESICA TTO | IOMA |
    10:00 | CLASE DE CANTO JUAN SORACCO | |
    14:30 | PINEYRO JAVIER EVAL | PARTICULAR |

El campo Paciente trae el nombre (APELLIDO NOMBRE) y códigos: TTO =
tratamiento, EVAL = evaluación, prefijo "CLASE DE CANTO" = clase.

Este módulo:
- parsea el mail (HTML que manda el script de Gmail, o el texto que se pega
  al copiar la tabla desde Gmail);
- crea o actualiza pacientes (centro Fonoar La Plata, obra social, teléfono)
  y crea los turnos sin duplicar (si ya hay un turno de ese paciente a esa
  hora, no se vuelve a crear).

Rutas:
- GET  /api/centros
- POST /api/agenda/importar-fonoar           (sesión de la web; simular=true
                                              muestra la vista previa)
- GET  /api/agenda/clave-script              (sesión: clave para el script)
- GET  /api/agenda/script-gmail              (sesión: script listo para pegar)
- POST /api/agenda/importar-fonoar/script    (script de Gmail, con clave)
"""
import hashlib
import hmac
import re
import traceback
import unicodedata
from html.parser import HTMLParser

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

router = APIRouter()

# Centros de atención. cuadernillo_propio = el centro entrega su propio
# cuadernillo (Fonoar): la app no genera uno, solo hace el seguimiento.
CENTROS = [
    {"id": "fonoar_la_plata", "nombre": "Fonoar La Plata", "cuadernillo_propio": True},
    {"id": "due_brandsen", "nombre": "DUE Brandsen", "cuadernillo_propio": False},
    {"id": "virtual", "nombre": "Atención virtual", "cuadernillo_propio": False},
]
CENTRO_FONOAR = "fonoar_la_plata"

# Códigos del campo Paciente → tipo de turno (valores permitidos en la tabla).
CODIGOS_TIPO = {
    "TTO": "terapia", "TRAT": "terapia", "TRATAMIENTO": "terapia",
    "EVAL": "evaluacion", "EV": "evaluacion", "EVALUACION": "evaluacion",
    "CTRL": "control", "CONTROL": "control",
    "1RA": "primera_vez", "1ERA": "primera_vez", "1VEZ": "primera_vez",
}
TIPO_TEXTO = {"terapia": "Tratamiento", "evaluacion": "Evaluación",
              "control": "Control", "primera_vez": "Primera vez"}
PREFIJOS_MOTIVO = {"CLASE DE CANTO": "Clase de canto"}
OBRAS_CONOCIDAS = {
    "IOMA", "PAMI", "OSDE", "GALENO", "MEDIFE", "OSECAC", "IOSFA", "SWISS",
    "SANCOR", "OMINT", "UNION PERSONAL", "OSPE", "OSPRERA", "OSPACA", "OBSBA",
    "PARTICULAR", "PARTICU", "PART",
}
_HORA = re.compile(r"^\s*(\d{1,2})[:.](\d{2})\s*$")
_FECHA = re.compile(r"Turnos\s+del\s+(\d{1,2})/(\d{1,2})/(\d{4})", re.IGNORECASE)


def _sin_tildes(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", t or "")
                   if unicodedata.category(c) != "Mn")


def clave_nombre(nombre: str) -> frozenset:
    """Nombre normalizado como conjunto de palabras (sin tildes ni orden)."""
    return frozenset(w for w in re.split(r"[^a-z0-9ñ]+", _sin_tildes(nombre).lower()) if len(w) > 1)


def _titulo(texto: str) -> str:
    return " ".join(w.capitalize() for w in texto.split())


def _obra_social(texto: str) -> str:
    t = (texto or "").strip()
    if not t:
        return ""
    if t.upper().startswith("PART"):
        return "Particular"
    return t.upper() if len(t) <= 6 else _titulo(t)


def interpretar_paciente(campo: str) -> dict:
    """'ALVAREZ YESICA TTO' → nombre, tipo y motivo."""
    texto = re.sub(r"\s+", " ", (campo or "").strip())
    motivo = ""
    for prefijo, nombre_motivo in PREFIJOS_MOTIVO.items():
        if texto.upper().startswith(prefijo + " "):
            motivo, texto = nombre_motivo, texto[len(prefijo):].strip()
            break
    palabras = texto.split()
    tipo = ""
    while palabras and palabras[-1].upper().strip(".") in CODIGOS_TIPO:
        tipo = tipo or CODIGOS_TIPO[palabras.pop().upper().strip(".")]
    while palabras and palabras[0].upper().strip(".") in CODIGOS_TIPO:
        tipo = tipo or CODIGOS_TIPO[palabras.pop(0).upper().strip(".")]
    tipo = tipo or ("control" if motivo else "control")
    if not motivo:
        motivo = TIPO_TEXTO.get(tipo, "Consulta de voz")
    return {"nombre": _titulo(" ".join(palabras)), "tipo": tipo, "motivo": motivo,
            "codigo_original": (campo or "").strip()}


class _Tabla(HTMLParser):
    """Filas de las tablas de un HTML como listas de textos de celda."""

    def __init__(self):
        super().__init__()
        self.filas, self._fila, self._celda = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._fila = []
        elif tag in ("td", "th") and self._fila is not None:
            self._celda = []

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._celda is not None and self._fila is not None:
            self._fila.append(re.sub(r"\s+", " ", "".join(self._celda)).strip())
            self._celda = None
        elif tag == "tr" and self._fila is not None:
            self.filas.append(self._fila)
            self._fila = None

    def handle_data(self, data):
        if self._celda is not None:
            self._celda.append(data)


def _filas_desde_texto(texto: str) -> list:
    """Texto pegado desde Gmail: celdas separadas por tabulador (o por 2+
    espacios). Sin separadores, se deduce obra social y teléfono del final."""
    filas = []
    for linea in (texto or "").splitlines():
        if not linea.strip():
            continue
        if "\t" in linea:
            celdas = [c.strip() for c in linea.split("\t")]
        elif re.search(r"\S\s{2,}\S", linea):
            celdas = [c.strip() for c in re.split(r"\s{2,}", linea.strip())]
        else:
            m = re.match(r"^\s*(\d{1,2}[:.]\d{2})\s+(.*)$", linea)
            if not m:
                filas.append([linea.strip()])
                continue
            resto = m.group(2).strip()
            tel = ""
            mt = re.search(r"\s((?:\+?\d[\d\s-]{6,}\d))\s*$", resto)
            if mt:
                tel, resto = mt.group(1).strip(), resto[:mt.start()].strip()
            obra = ""
            palabras = resto.split()
            for n in (2, 1):
                if len(palabras) > n and " ".join(palabras[-n:]).upper() in OBRAS_CONOCIDAS:
                    obra, palabras = " ".join(palabras[-n:]), palabras[:-n]
                    break
            celdas = [m.group(1), " ".join(palabras), obra, tel]
        filas.append(celdas)
    return filas


def parsear_agenda(contenido: str, asunto: str = "") -> dict:
    """{'fecha': 'AAAA-MM-DD' | '', 'turnos': [...], 'avisos': [...]}."""
    contenido = contenido or ""
    m = _FECHA.search(asunto or "") or _FECHA.search(re.sub(r"<[^>]+>", " ", contenido))
    fecha = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else ""
    if "<td" in contenido.lower():
        p = _Tabla()
        p.feed(contenido)
        filas = p.filas
    else:
        filas = _filas_desde_texto(contenido)
    turnos, avisos, seccion = [], [], ""
    for celdas in filas:
        celdas = [c for c in celdas]
        if not celdas or not any(celdas):
            continue
        mh = _HORA.match(celdas[0] or "")
        if not mh:
            texto = " ".join(c for c in celdas if c).strip()
            # Encabezado de la tabla o fila de sección ("Estudios").
            if texto and not re.search(r"\bhora\b|\bpaciente\b", texto, re.IGNORECASE) \
                    and len([c for c in celdas if c]) == 1 and len(texto) <= 40:
                seccion = texto
            continue
        hora = f"{int(mh.group(1)):02d}:{mh.group(2)}"
        campo = celdas[1] if len(celdas) > 1 else ""
        if not campo.strip():
            avisos.append(f"{hora}: fila sin paciente, se omitió.")
            continue
        datos = interpretar_paciente(campo)
        if not datos["nombre"]:
            avisos.append(f"{hora}: no se pudo leer el nombre en «{campo}».")
            continue
        tel = re.sub(r"[^\d+]", "", celdas[3]) if len(celdas) > 3 else ""
        turnos.append({
            "hora": hora, **datos,
            "obra_social": _obra_social(celdas[2] if len(celdas) > 2 else ""),
            "telefono": tel, "seccion": seccion,
        })
    if not fecha:
        avisos.append("No se encontró la fecha («Turnos del DD/MM/AAAA»): indicála a mano.")
    if not turnos:
        avisos.append("No se encontraron turnos en el texto.")
    return {"fecha": fecha, "turnos": turnos, "avisos": avisos}


# ─── Importación a la base ─────────────────────────────────────────────

def _sb():
    from api_clinica import supabase
    return supabase


_CAMPOS_NUEVOS = ("centro", "obra_social", "origen")


def _insertar_paciente(sb, datos: dict) -> tuple:
    """Inserta tolerando una base sin migrar: sin columnas nuevas o con DNI
    obligatorio. Devuelve (fila, avisos)."""
    avisos = []
    fila = dict(datos)
    for _ in range(3):
        try:
            return (sb.table("pacientes").insert(fila).execute().data or [fila])[0], avisos
        except Exception as e:
            msg = str(e).lower()
            if any(c in msg for c in _CAMPOS_NUEVOS) and ("column" in msg or "pgrst204" in msg):
                fila = {k: v for k, v in fila.items() if k not in _CAMPOS_NUEVOS}
                avisos.append("Falta correr la migración SQL: centro y obra social no se guardaron.")
                continue
            if "dni" in msg and ("null" in msg or "not-null" in msg):
                fila["dni"] = "SD-" + hashlib.sha1(fila["nombre_completo"].encode()).hexdigest()[:8]
                avisos.append("Falta correr la migración SQL: se cargó un DNI provisorio (SD-…).")
                continue
            raise
    raise RuntimeError("No se pudo crear el paciente")


def _actualizar_paciente(sb, pid: str, cambios: dict) -> list:
    if not cambios:
        return []
    try:
        sb.table("pacientes").update(cambios).eq("id", pid).execute()
        return []
    except Exception:
        base = {k: v for k, v in cambios.items() if k not in _CAMPOS_NUEVOS}
        if base:
            sb.table("pacientes").update(base).eq("id", pid).execute()
        return ["Falta correr la migración SQL: centro y obra social no se guardaron."]


def importar_agenda(agenda: dict, centro: str = CENTRO_FONOAR, simular: bool = False,
                    sb=None) -> dict:
    """Crea/actualiza pacientes y turnos de la agenda parseada."""
    sb = sb or _sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    fecha = agenda.get("fecha") or ""
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", fecha):
        raise HTTPException(status_code=400, detail="Falta la fecha de la agenda (AAAA-MM-DD).")
    try:
        existentes = sb.table("pacientes").select("*").limit(5000).execute().data or []
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"No se pudo leer pacientes: {e}")
    indice = {}
    for p in existentes:
        indice.setdefault(clave_nombre(p.get("nombre_completo") or p.get("nombre") or ""), []).append(p)

    def buscar(nombre):
        k = clave_nombre(nombre)
        if k in indice:
            return indice[k]
        # Coincidencia parcial (ej. falta un segundo nombre), mínimo 2 palabras.
        return [p for kk, ps in indice.items() for p in ps
                if len(k) >= 2 and len(kk) >= 2 and (k <= kk or kk <= k)]

    resultado = {"fecha": fecha, "centro": centro, "simulacion": simular,
                 "pacientes_nuevos": 0, "pacientes_actualizados": 0,
                 "turnos_nuevos": 0, "turnos_existentes": 0, "detalle": [],
                 "avisos": list(agenda.get("avisos") or [])}
    for t in agenda.get("turnos") or []:
        item = {"hora": t["hora"], "paciente": t["nombre"], "tipo": t["tipo"],
                "obra_social": t.get("obra_social", ""), "telefono": t.get("telefono", "")}
        candidatos = buscar(t["nombre"])
        if len(candidatos) > 1:
            resultado["avisos"].append(
                f"{t['hora']} {t['nombre']}: hay {len(candidatos)} pacientes parecidos; se usó el primero, revisalo.")
        paciente = candidatos[0] if candidatos else None
        if paciente:
            item["accion_paciente"] = "existente"
            cambios = {}
            if t.get("telefono") and not paciente.get("telefono"):
                cambios["telefono"] = t["telefono"]
            if t.get("obra_social") and not paciente.get("obra_social"):
                cambios["obra_social"] = t["obra_social"]
            if not paciente.get("centro"):
                cambios["centro"] = centro
            if cambios:
                item["accion_paciente"] = "actualizado"
                if not simular:
                    resultado["avisos"] += _actualizar_paciente(sb, paciente["id"], cambios)
                resultado["pacientes_actualizados"] += 1
        else:
            item["accion_paciente"] = "nuevo"
            resultado["pacientes_nuevos"] += 1
            if not simular:
                paciente, avisos = _insertar_paciente(sb, {
                    "nombre_completo": t["nombre"], "nombre": t["nombre"], "dni": None,
                    "telefono": t.get("telefono", ""), "centro": centro,
                    "obra_social": t.get("obra_social", ""), "origen": "agenda_fonoar",
                    "notas_iniciales": f"Alta automática desde la agenda de Fonoar ({fecha}).",
                })
                resultado["avisos"] += avisos
                indice.setdefault(clave_nombre(t["nombre"]), []).append(paciente)
        fecha_hora = f"{fecha}T{t['hora']}:00-03:00"
        ya = False
        if paciente and paciente.get("id"):
            try:
                ya = bool(sb.table("turnos").select("id").eq("paciente_id", paciente["id"])
                          .eq("fecha_hora", fecha_hora).execute().data)
            except Exception:
                ya = False
        if ya:
            item["accion_turno"] = "existente"
            resultado["turnos_existentes"] += 1
        else:
            item["accion_turno"] = "nuevo"
            resultado["turnos_nuevos"] += 1
            if not simular:
                notas = "Importado de la agenda de Fonoar"
                if t.get("seccion"):
                    notas += f" · Sección: {t['seccion']}"
                if t.get("obra_social"):
                    notas += f" · O. social: {t['obra_social']}"
                notas += f" · Original: {t.get('codigo_original', '')}"
                sb.table("turnos").insert({
                    "paciente_id": paciente["id"], "fecha_hora": fecha_hora,
                    "duracion_min": 30, "tipo": t["tipo"], "estado": "programado",
                    "modalidad": "PRESENCIAL", "motivo": t["motivo"], "notas": notas,
                }).execute()
        resultado["detalle"].append(item)
    resultado["avisos"] = list(dict.fromkeys(resultado["avisos"]))
    return resultado


# ─── Clave del script de Gmail ─────────────────────────────────────────

def clave_script() -> str:
    from sesion_web import _secreto
    return hmac.new(_secreto(), b"agenda-fonoar-script", hashlib.sha256).hexdigest()[:40]


# ─── Rutas ─────────────────────────────────────────────────────────────

@router.get("/api/centros")
async def listar_centros():
    return {"centros": CENTROS}


@router.post("/api/agenda/importar-fonoar")
async def importar_fonoar(request: Request):
    """Body: {contenido (texto pegado o HTML), asunto?, fecha? (AAAA-MM-DD),
    centro?, simular?}. Con simular=true no escribe nada (vista previa)."""
    body = await request.json()
    agenda = parsear_agenda(body.get("contenido") or "", body.get("asunto") or "")
    if body.get("fecha"):
        agenda["fecha"] = str(body["fecha"])[:10]
        agenda["avisos"] = [a for a in agenda["avisos"] if "fecha" not in a.lower()]
    try:
        return JSONResponse(content={"ok": True, **importar_agenda(
            agenda, centro=body.get("centro") or CENTRO_FONOAR,
            simular=bool(body.get("simular")))})
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"ok": False, "error": f"No se pudo importar: {str(e)[:200]}"})


@router.get("/api/agenda/clave-script")
async def ver_clave_script():
    return {"clave": clave_script()}


@router.get("/api/agenda/script-gmail")
async def script_gmail():
    """Script de Google listo para pegar, con la clave ya incluida."""
    import os
    from fastapi.responses import PlainTextResponse
    ruta = os.path.join(os.path.dirname(__file__), "recursos", "apps_script_agenda_fonoar.gs")
    with open(ruta, encoding="utf-8") as f:
        return PlainTextResponse(f.read().replace("__CLAVE_AGENDA__", clave_script()))


@router.post("/api/agenda/importar-fonoar/script")
async def importar_fonoar_script(request: Request):
    """Lo llama el script de Google en el Gmail del consultorio, con la
    clave en el header X-Clave-Agenda. Body: {html, asunto}."""
    clave = request.headers.get("x-clave-agenda", "")
    if not clave or not hmac.compare_digest(clave, clave_script()):
        raise HTTPException(status_code=401, detail="Clave de agenda inválida")
    body = await request.json()
    agenda = parsear_agenda(body.get("html") or body.get("contenido") or "", body.get("asunto") or "")
    try:
        return JSONResponse(content={"ok": True, **importar_agenda(agenda)})
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"ok": False, "error": str(e)[:200]})
