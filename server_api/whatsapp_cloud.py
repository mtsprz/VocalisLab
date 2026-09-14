"""VocalisLab Pro — Envío directo de cuadernillos por WhatsApp Cloud API (Meta, oficial).

Flujo: subir PDF (POST /{PHONE_ID}/media, multipart) → enviar documento
(POST /{PHONE_ID}/messages con {document: {id, filename, caption}}).

Requiere en el servidor: WHATSAPP_TOKEN, WHATSAPP_PHONE_NUMBER_ID.
Opcional: WHATSAPP_API_VERSION (default v25.0).

Nota: los mensajes libres (documento con caption) solo llegan si el paciente
escribió en las últimas 24 h (ventana de servicio). Fuera de ventana se
necesita una plantilla utility pre-aprobada; en ese caso la API devuelve el
error y el endpoint lo informa para usar el fallback wa.me.
"""
import os
import re
import base64
import traceback
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import httpx

router = APIRouter()


def _cfg():
    token = os.environ.get("WHATSAPP_TOKEN", "").strip()
    phone_id = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "").strip()
    version = os.environ.get("WHATSAPP_API_VERSION", "v25.0").strip() or "v25.0"
    return token, phone_id, version


def _normalizar_destino(to: str) -> str:
    digits = re.sub(r"\D", "", str(to or ""))
    if len(digits) < 8:
        raise HTTPException(status_code=400, detail="Número de WhatsApp inválido")
    return digits


@router.get("/api/whatsapp/estado")
async def whatsapp_estado():
    token, phone_id, version = _cfg()
    return JSONResponse(content={
        "configurado": bool(token and phone_id),
        "version": version,
        "phone_number_id": (phone_id[:4] + "…" + phone_id[-3:]) if phone_id else "",
    })


@router.post("/api/whatsapp/enviar-cuadernillo")
async def whatsapp_enviar_cuadernillo(request: Request):
    """Body: {to, pdf_base64, filename, caption}. Sube el PDF y lo envía
    como documento al paciente. Sin exponer el token al cliente."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    token, phone_id, version = _cfg()
    if not (token and phone_id):
        raise HTTPException(status_code=503, detail="WhatsApp no configurado: faltan WHATSAPP_TOKEN / WHATSAPP_PHONE_NUMBER_ID en el servidor")
    to = _normalizar_destino(body.get("to", ""))
    pdf_b64 = str(body.get("pdf_base64", ""))
    if "," in pdf_b64 and pdf_b64.startswith("data:"):
        pdf_b64 = pdf_b64.split(",", 1)[1]
    try:
        pdf_bytes = base64.b64decode(pdf_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="pdf_base64 inválido")
    if len(pdf_bytes) < 1000:
        raise HTTPException(status_code=400, detail="PDF vacío o corrupto")
    if len(pdf_bytes) > 90 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF mayor a 90 MB")
    filename = str(body.get("filename", "cuadernillo.pdf")).strip() or "cuadernillo.pdf"
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    caption = str(body.get("caption", ""))[:1024]
    headers = {"Authorization": f"Bearer {token}"}
    try:
        async with httpx.AsyncClient() as client:
            # 1) Subir media
            up = await client.post(
                f"https://graph.facebook.com/{version}/{phone_id}/media",
                headers=headers,
                files={"file": (filename, pdf_bytes, "application/pdf")},
                data={"messaging_product": "whatsapp"},
                timeout=120,
            )
            if up.status_code != 200:
                raise HTTPException(status_code=502, detail=f"WhatsApp upload {up.status_code}: {up.text[:300]}")
            media_id = (up.json() or {}).get("id", "")
            if not media_id:
                raise HTTPException(status_code=502, detail="WhatsApp no devolvió media id")
            # 2) Enviar documento
            msg = await client.post(
                f"https://graph.facebook.com/{version}/{phone_id}/messages",
                headers={**headers, "Content-Type": "application/json"},
                json={
                    "messaging_product": "whatsapp",
                    "recipient_type": "individual",
                    "to": to,
                    "type": "document",
                    "document": {"id": media_id, "filename": filename, "caption": caption},
                },
                timeout=60,
            )
            if msg.status_code != 200:
                raise HTTPException(status_code=502, detail=f"WhatsApp send {msg.status_code}: {msg.text[:300]}")
            data = msg.json() or {}
            wamid = (((data.get("messages") or [{}])[0]).get("id", ""))
            return JSONResponse(content={"ok": True, "message_id": wamid, "to": to})
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error enviando WhatsApp: {str(e)[:300]}")
