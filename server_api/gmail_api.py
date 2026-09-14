"""VocalisLab Pro — Envío directo de cuadernillos por Gmail API.

Usa el OAuth del profesional (scope gmail.send) para enviar el PDF adjunto
sin que tenga que descargarlo ni abrir el redactor de Gmail.

POST /api/gmail/enviar {user_id, to, subject, body, pdf_base64, filename}
GET  /api/gmail/estado?user_id=... (verifica scope/refresh válido)

Nota: el scope gmail.send es nuevo; las sesiones otorgadas antes del cambio
deben re-loguearse con Google para que el consentimiento lo incluya.
"""
import base64
import traceback
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse
import httpx

router = APIRouter()

GMAIL_SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


@router.get("/api/gmail/estado")
async def gmail_estado(user_id: str = ""):
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id requerido")
    try:
        from google_auth import _get_valid_token
        await _get_valid_token(user_id)
        return JSONResponse(content={"ok": True})
    except HTTPException as e:
        raise HTTPException(status_code=503, detail=f"Gmail no disponible: {e.detail}. Re-login con Google requerido.")


@router.post("/api/gmail/enviar")
async def gmail_enviar(request: Request):
    try:
        body = await request.json()
    except Exception:
        body = {}
    user_id = str(body.get("user_id", "")).strip()
    to = str(body.get("to", "")).strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id requerido (sesión Google)")
    if not to or "@" not in to:
        raise HTTPException(status_code=400, detail="Email destino inválido")
    subject = str(body.get("subject", "Tu cuadernillo terapéutico vocal"))[:200]
    text_body = str(body.get("body", ""))
    pdf_b64 = str(body.get("pdf_base64", ""))
    if "," in pdf_b64 and pdf_b64.startswith("data:"):
        pdf_b64 = pdf_b64.split(",", 1)[1]
    try:
        pdf_bytes = base64.b64decode(pdf_b64)
    except Exception:
        raise HTTPException(status_code=400, detail="pdf_base64 inválido")
    if len(pdf_bytes) < 1000:
        raise HTTPException(status_code=400, detail="PDF vacío o corrupto")
    filename = str(body.get("filename", "cuadernillo.pdf")).strip() or "cuadernillo.pdf"
    if not filename.lower().endswith(".pdf"):
        filename += ".pdf"
    try:
        from google_auth import _get_valid_token
        token = await _get_valid_token(user_id)
    except HTTPException as e:
        raise HTTPException(status_code=503, detail=f"{e.detail}. Re-login con Google requerido para habilitar Gmail.")
    try:
        msg = MIMEMultipart()
        msg["To"] = to
        msg["Subject"] = subject
        msg.attach(MIMEText(text_body or "Te comparto tu cuadernillo terapéutico vocal.", "plain", "utf-8"))
        part = MIMEApplication(pdf_bytes, _subtype="pdf")
        part.add_header("Content-Disposition", "attachment", filename=filename)
        msg.attach(part)
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        async with httpx.AsyncClient() as client:
            r = await client.post(
                GMAIL_SEND_URL,
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
                json={"raw": raw},
                timeout=60,
            )
        if r.status_code != 200:
            detail = r.text[:300]
            if "insufficient" in detail.lower() or "scope" in detail.lower():
                raise HTTPException(status_code=503, detail="Gmail sin permiso de envío: cerrá sesión y volvé a entrar con Google para otorgar el permiso.")
            raise HTTPException(status_code=502, detail=f"Gmail {r.status_code}: {detail}")
        return JSONResponse(content={"ok": True, "gmail_id": (r.json() or {}).get("id", ""), "to": to})
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error enviando Gmail: {str(e)[:300]}")
