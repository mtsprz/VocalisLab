"""Voz guía del profesional: frases e indicaciones grabadas con su propia voz.

En la práctica guiada del paciente, cada indicación ("Escuchá", "Ahora vos",
"Respirá"…) y la consigna de cada ejercicio suenan con la voz del
fonoaudiólogo. Si una frase no está grabada, se usa la voz del celular.

Rutas:
- GET    /api/voz-guia                      (sesión) frases sugeridas y cuáles están grabadas
- PUT    /api/voz-guia/{clave}              (sesión) {audio_b64, mime, duracion_s}
- DELETE /api/voz-guia/{clave}              (sesión)
- GET    /api/voz-guia/{clave}/audio        (sesión) para escucharla en la app
- GET    /api/practica/{token}/voz/{clave}  (público, valida el enlace del paciente)
"""
import base64
import re
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response

router = APIRouter()

MSG_MIGRACION = "Falta correr supabase/migracion_2026_11_voz_guia.sql en Supabase (SQL Editor)."
MAX_BYTES = 3 * 1024 * 1024
MIMES = ("audio/wav", "audio/x-wav", "audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg")

FRASES = [
    ("bienvenida", "Hola, vamos a hacer tu práctica de voz. Buscá un lugar tranquilo."),
    ("silencio", "Quedate en silencio unos segundos."),
    ("escucha_nota", "Escuchá tu nota."),
    ("hace_mmm", "Ahora hacé mmm en esa misma nota."),
    ("afinado", "Muy bien, estás en tu nota."),
    ("de_nuevo", "Probemos de nuevo. Escuchá la nota y buscala con tu voz."),
    ("escucha", "Escuchá."),
    ("ahora_vos", "Ahora vos."),
    ("respira", "Respirá."),
    ("fin_bien", "Muy bien, terminaste el ejercicio."),
    ("fin", "Terminaste. Buen trabajo."),
]
TEXTOS = dict(FRASES)
_CLAVE = re.compile(r"^(?:[a-z_]{2,30}|ej:[a-z0-9_]{2,60})$")


def _sb():
    from api_clinica import supabase
    if not supabase:
        raise HTTPException(status_code=503, detail="Supabase no configurado")
    return supabase


def _validar_clave(clave: str) -> str:
    if not _CLAVE.match(clave or ""):
        raise HTTPException(status_code=400, detail="Clave de frase inválida.")
    return clave


def claves_grabadas(sb) -> list:
    try:
        return [f["clave"] for f in (sb.table("voz_guia").select("clave").execute().data or [])]
    except Exception:
        return []


def _audio(sb, clave: str) -> Response:
    try:
        filas = sb.table("voz_guia").select("*").eq("clave", clave).execute().data or []
    except Exception as e:
        if "voz_guia" in str(e):
            raise HTTPException(status_code=503, detail=MSG_MIGRACION)
        raise
    if not filas:
        raise HTTPException(status_code=404, detail="Frase no grabada")
    datos = base64.b64decode(filas[0]["audio_b64"])
    return Response(content=datos, media_type=filas[0].get("mime") or "audio/wav",
                    headers={"Cache-Control": "private, max-age=600"})


@router.get("/api/voz-guia")
async def listar():
    sb = _sb()
    try:
        filas = sb.table("voz_guia").select("clave, duracion_s, actualizada_at").execute().data or []
        aviso = ""
    except Exception as e:
        filas, aviso = [], (MSG_MIGRACION if "voz_guia" in str(e) else str(e)[:150])
    grab = {f["clave"]: f for f in filas}
    from practica_guiada import GUIA_POR_EJERCICIO
    try:
        from api_clinica import banco_ejercicios_completo
        nombres = {e["id"]: e.get("name") for s in banco_ejercicios_completo().get("sections", [])
                   for e in s.get("exercises", []) if e.get("id")}
    except Exception:
        nombres = {}
    frases = [{"clave": c, "texto": t, "grabada": c in grab, **{k: grab.get(c, {}).get(k) for k in ("duracion_s", "actualizada_at")}}
              for c, t in FRASES]
    ejercicios = [{"clave": f"ej:{bid}", "texto": g["consigna"], "nombre": nombres.get(bid, bid), "grabada": f"ej:{bid}" in grab,
                   **{k: grab.get(f"ej:{bid}", {}).get(k) for k in ("duracion_s", "actualizada_at")}}
                  for bid, g in GUIA_POR_EJERCICIO.items()]
    return {"frases": frases, "ejercicios": ejercicios, "aviso": aviso}


@router.put("/api/voz-guia/{clave}")
async def guardar(clave: str, request: Request):
    _validar_clave(clave)
    body = await request.json()
    mime = str(body.get("mime") or "audio/wav").split(";")[0]
    if mime not in MIMES:
        raise HTTPException(status_code=400, detail="Formato de audio no admitido.")
    try:
        datos = base64.b64decode(str(body.get("audio_b64") or ""), validate=True)
    except Exception:
        raise HTTPException(status_code=400, detail="Audio inválido.")
    if not 200 < len(datos) <= MAX_BYTES:
        raise HTTPException(status_code=400, detail="La grabación está vacía o es muy larga (máximo 3 MB).")
    sb = _sb()
    fila = {"clave": clave, "mime": mime, "audio_b64": base64.b64encode(datos).decode(),
            "duracion_s": float(body.get("duracion_s") or 0) or None,
            "actualizada_at": datetime.now(timezone.utc).isoformat()}
    try:
        sb.table("voz_guia").upsert(fila).execute()
    except Exception as e:
        if "voz_guia" in str(e):
            raise HTTPException(status_code=503, detail=MSG_MIGRACION)
        raise
    return {"ok": True}


@router.delete("/api/voz-guia/{clave}")
async def borrar(clave: str):
    _validar_clave(clave)
    _sb().table("voz_guia").delete().eq("clave", clave).execute()
    return {"ok": True}


@router.get("/api/voz-guia/{clave}/audio")
async def escuchar(clave: str):
    return _audio(_sb(), _validar_clave(clave))


@router.get("/api/practica/{token}/voz/{clave}")
async def escuchar_paciente(token: str, clave: str):
    sb = _sb()
    from practica_guiada import _rutina
    _rutina(sb, token)  # el enlace tiene que existir
    return _audio(sb, _validar_clave(clave))
