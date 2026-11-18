"""Ficha del paciente: archivos en Google Drive.

Informes del ORL, fotos, videos y audios que llegan por WhatsApp (de
pacientes u otorrinos) se guardan en el Google Drive del profesional, en una
carpeta por paciente:

    VocalisLab - Pacientes/
        Alvarez Yesica (a1b2c3d4)/
            2026-11-18 Informe ORL - videolaringoscopia.pdf
            2026-11-18 Video WhatsApp - fonación.mp4

La base (tabla archivos_paciente) guarda solo los datos para listarlos y el
enlace de Drive. Permiso usado: drive.file (la app ve únicamente lo que ella
creó, nunca el resto del Drive).

Rutas (con sesión de la web):
- GET    /api/pacientes/{paciente_id}/archivos
- POST   /api/pacientes/{paciente_id}/archivos   (multipart)
- DELETE /api/archivos/{archivo_id}               (lo manda a la papelera de Drive)
"""
import os
import re
import tempfile
import traceback
from datetime import date

import httpx
from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse

router = APIRouter()

DRIVE = "https://www.googleapis.com/drive/v3"
DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
CARPETA_RAIZ = "VocalisLab - Pacientes"
CARPETA_MIME = "application/vnd.google-apps.folder"
MAX_BYTES = 300 * 1024 * 1024
TROZO = 8 * 1024 * 1024  # múltiplo de 256 KB, como pide la subida reanudable

TIPOS = {
    "informe_orl": "Informe ORL",
    "estudio": "Estudio / evaluación",
    "foto": "Foto",
    "video": "Video",
    "audio": "Audio",
    "documento": "Documento",
}
ORIGENES = {
    "whatsapp_paciente": "WhatsApp del paciente",
    "whatsapp_orl": "WhatsApp del ORL",
    "orl": "ORL (otro medio)",
    "consultorio": "Consultorio",
    "otro": "Otro",
}

MSG_PERMISO = ("Falta el permiso de Google Drive: cerrá sesión en la app y volvé a entrar "
               "con Google para darlo.")
MSG_API = ("Google Drive API no está activada en el proyecto de Google de la app: activala en "
           "console.cloud.google.com → APIs y servicios → Biblioteca → Google Drive API.")
MSG_MIGRACION = ("Falta correr la migración supabase/migracion_2026_11_archivos.sql en Supabase "
                 "(SQL Editor).")


def _sb():
    from api_clinica import supabase
    return supabase


def _uid(request: Request) -> str:
    usuario = getattr(request.state, "usuario", None) or {}
    uid = str(usuario.get("sub") or "")
    if not uid:
        raise HTTPException(status_code=401, detail="Iniciá sesión para usar la plataforma.")
    return uid


async def _token(uid: str) -> str:
    from google_auth import _get_valid_token
    return await _get_valid_token(uid)


def _error_drive(resp: httpx.Response, que: str):
    """Traduce los errores típicos de Drive a un mensaje accionable."""
    texto = resp.text[:400]
    if resp.status_code in (401, 403) and re.search(
            r"insufficient|SCOPE_INSUFFICIENT|insufficientPermissions", texto, re.IGNORECASE):
        raise HTTPException(status_code=403, detail=MSG_PERMISO)
    if resp.status_code == 403 and re.search(r"accessNotConfigured|SERVICE_DISABLED|has not been used",
                                             texto, re.IGNORECASE):
        raise HTTPException(status_code=403, detail=MSG_API)
    raise HTTPException(status_code=502, detail=f"Google Drive ({que}): {resp.status_code} {texto[:200]}")


def _nombre_seguro(texto: str, largo: int = 80) -> str:
    t = re.sub(r"[\\/:*?\"<>|\n\r\t]+", " ", texto or "").strip()
    return re.sub(r"\s+", " ", t)[:largo] or "archivo"


async def _buscar_carpeta(client, token, consulta: str):
    r = await client.get(f"{DRIVE}/files", headers={"Authorization": f"Bearer {token}"},
                         params={"q": consulta + f" and mimeType='{CARPETA_MIME}' and trashed=false",
                                 "fields": "files(id,name,webViewLink)", "spaces": "drive"})
    if r.status_code != 200:
        _error_drive(r, "buscar carpeta")
    archivos = r.json().get("files") or []
    return archivos[0] if archivos else None


async def _crear_carpeta(client, token, nombre, padre=None, props=None):
    meta = {"name": nombre, "mimeType": CARPETA_MIME}
    if padre:
        meta["parents"] = [padre]
    if props:
        meta["appProperties"] = props
    r = await client.post(f"{DRIVE}/files", headers={"Authorization": f"Bearer {token}"},
                          params={"fields": "id,name,webViewLink"}, json=meta)
    if r.status_code not in (200, 201):
        _error_drive(r, "crear carpeta")
    return r.json()


async def carpeta_paciente(client, token, paciente: dict) -> dict:
    """Carpeta del paciente (la crea si no existe). Se la reconoce por su
    id de paciente (appProperties), así un cambio de nombre no la duplica."""
    pid = paciente["id"]
    existente = await _buscar_carpeta(
        client, token, f"appProperties has {{ key='vocalislab_paciente' and value='{pid}' }}")
    if existente:
        return existente
    raiz = await _buscar_carpeta(
        client, token, "appProperties has { key='vocalislab' and value='raiz' }")
    if not raiz:
        raiz = await _crear_carpeta(client, token, CARPETA_RAIZ, props={"vocalislab": "raiz"})
    nombre = _nombre_seguro(f"{paciente.get('nombre_completo') or 'Paciente'} ({pid[:8]})")
    return await _crear_carpeta(client, token, nombre, padre=raiz["id"],
                                props={"vocalislab_paciente": pid})


async def subir_a_drive(client, token, ruta: str, nombre: str, mime: str, carpeta_id: str,
                        props: dict) -> dict:
    """Subida reanudable por trozos (sirve para videos grandes sin cargarlos
    enteros en memoria)."""
    total = os.path.getsize(ruta)
    inicio = await client.post(
        DRIVE_UPLOAD, params={"uploadType": "resumable",
                              "fields": "id,name,mimeType,size,webViewLink,thumbnailLink"},
        headers={"Authorization": f"Bearer {token}", "X-Upload-Content-Type": mime,
                 "X-Upload-Content-Length": str(total)},
        json={"name": nombre, "parents": [carpeta_id], "appProperties": props})
    if inicio.status_code != 200 or not inicio.headers.get("location"):
        _error_drive(inicio, "iniciar subida")
    url = inicio.headers["location"]
    with open(ruta, "rb") as f:
        enviado = 0
        while True:
            trozo = f.read(TROZO)
            fin = enviado + len(trozo) - 1
            r = await client.put(url, content=trozo, headers={
                "Content-Range": f"bytes {enviado}-{fin}/{total}" if trozo else f"bytes */{total}"})
            if r.status_code in (200, 201):
                return r.json()
            if r.status_code != 308:
                _error_drive(r, "subir")
            enviado = fin + 1


def _fila_valida(paciente_id: str):
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    filas = sb.table("pacientes").select("id,nombre_completo,nombre").eq("id", paciente_id).execute().data
    if not filas:
        raise HTTPException(status_code=404, detail="Paciente inexistente")
    return sb, filas[0]


def _falta_tabla(e: Exception) -> bool:
    m = str(e).lower()
    return "archivos_paciente" in m and ("does not exist" in m or "could not find" in m
                                          or "pgrst205" in m or "42p01" in m)


@router.get("/api/pacientes/{paciente_id}/archivos")
async def listar_archivos(paciente_id: str, request: Request):
    _uid(request)
    sb = _sb()
    if not sb:
        return {"archivos": [], "tipos": TIPOS, "origenes": ORIGENES}
    try:
        filas = (sb.table("archivos_paciente").select("*").eq("paciente_id", paciente_id)
                 .order("fecha", desc=True).execute().data or [])
    except Exception as e:
        if _falta_tabla(e):
            return JSONResponse(content={"archivos": [], "tipos": TIPOS, "origenes": ORIGENES,
                                         "aviso": MSG_MIGRACION})
        raise
    return {"archivos": filas, "tipos": TIPOS, "origenes": ORIGENES}


@router.post("/api/pacientes/{paciente_id}/archivos")
async def subir_archivo(
    paciente_id: str,
    request: Request,
    archivo: UploadFile = File(...),
    tipo: str = Form("documento"),
    origen: str = Form("otro"),
    titulo: str = Form(""),
    fecha: str = Form(""),
    notas: str = Form(""),
):
    uid = _uid(request)
    sb, paciente = _fila_valida(paciente_id)
    tipo = tipo if tipo in TIPOS else "documento"
    origen = origen if origen in ORIGENES else "otro"
    fecha = fecha if re.match(r"^\d{4}-\d{2}-\d{2}$", fecha or "") else date.today().isoformat()
    mime = (archivo.content_type or "application/octet-stream").split(";")[0].strip()
    nombre_orig = archivo.filename or "archivo"
    ext = os.path.splitext(nombre_orig)[1][:10]
    nombre_drive = _nombre_seguro(f"{fecha} {TIPOS[tipo]} - {titulo or os.path.splitext(nombre_orig)[0]}",
                                  120) + ext

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
    tamano = 0
    try:
        while True:
            parte = await archivo.read(1024 * 1024)
            if not parte:
                break
            tamano += len(parte)
            if tamano > MAX_BYTES:
                raise HTTPException(status_code=413, detail="El archivo supera 300 MB.")
            tmp.write(parte)
        tmp.close()
        if tamano == 0:
            raise HTTPException(status_code=400, detail="El archivo está vacío.")
        token = await _token(uid)
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0, connect=20.0)) as client:
            carpeta = await carpeta_paciente(client, token, paciente)
            subido = await subir_a_drive(client, token, tmp.name, nombre_drive, mime, carpeta["id"],
                                         {"vocalislab_paciente": paciente_id, "vocalislab_tipo": tipo})
        fila = {
            "paciente_id": paciente_id, "tipo": tipo, "origen": origen,
            "titulo": titulo or os.path.splitext(nombre_orig)[0], "fecha": fecha,
            "notas": notas, "nombre_archivo": nombre_orig, "mime": mime, "tamano_bytes": tamano,
            "drive_file_id": subido.get("id"), "drive_url": subido.get("webViewLink"),
            "drive_carpeta_url": carpeta.get("webViewLink"), "subido_por": uid,
        }
        try:
            guardada = (sb.table("archivos_paciente").insert(fila).execute().data or [fila])[0]
        except Exception as e:
            if _falta_tabla(e):
                # El archivo ya está en Drive: se avisa para no perderlo de vista.
                return JSONResponse(status_code=409, content={
                    "detail": MSG_MIGRACION + " El archivo SÍ quedó en Drive.",
                    "drive_url": subido.get("webViewLink")})
            raise
        return {"ok": True, "archivo": guardada}
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"No se pudo subir el archivo: {str(e)[:200]}")
    finally:
        try:
            tmp.close()
            os.unlink(tmp.name)
        except Exception:
            pass


@router.delete("/api/archivos/{archivo_id}")
async def borrar_archivo(archivo_id: str, request: Request):
    """Quita el archivo de la ficha y lo manda a la papelera de Drive
    (se puede recuperar desde Drive durante 30 días)."""
    uid = _uid(request)
    sb = _sb()
    if not sb:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    filas = sb.table("archivos_paciente").select("*").eq("id", archivo_id).execute().data or []
    if not filas:
        raise HTTPException(status_code=404, detail="Archivo inexistente")
    fid = filas[0].get("drive_file_id")
    if fid:
        token = await _token(uid)
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.patch(f"{DRIVE}/files/{fid}", headers={"Authorization": f"Bearer {token}"},
                                   json={"trashed": True})
        if r.status_code not in (200, 404):
            _error_drive(r, "mandar a la papelera")
    sb.table("archivos_paciente").delete().eq("id", archivo_id).execute()
    return {"ok": True}
