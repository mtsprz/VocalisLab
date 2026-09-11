"""
VocalisLab Pro — Google Calendar & Google Meet API Integration
Sincronización bidireccional: Google Calendar ↔ Agenda de turnos VocalisLab.
Soporte de Google Meet para consultas virtuales con conferenceData.
"""
import os
import time
import json
import traceback
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Form, Request
from fastapi.responses import JSONResponse
import httpx

router = APIRouter()

GOOGLE_CALENDAR_URL = "https://www.googleapis.com/calendar/v3"


def _get_provider():
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


async def _get_user_token(user_id: str) -> str:
    """Get valid Google access token for user."""
    from google_auth import _get_valid_token
    return await _get_valid_token(user_id)


@router.get("/api/calendar/events")
async def get_calendar_events(
    user_id: str = "",
    time_min: str = "",
    time_max: str = "",
    max_results: int = 50,
):
    """Fetch events from Google Calendar for the authenticated user, including Meet links."""
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id requerido")

    try:
        token = await _get_user_token(user_id)

        params = {
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": str(max_results),
        }
        if time_min:
            params["timeMin"] = time_min
        else:
            params["timeMin"] = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"
        if time_max:
            params["timeMax"] = time_max
        else:
            params["timeMax"] = (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{GOOGLE_CALENDAR_URL}/calendars/primary/events",
                headers={"Authorization": f"Bearer {token}"},
                params=params,
            )

        if resp.status_code != 200:
            return JSONResponse(content={"events": [], "error": f"Google API {resp.status_code}"})

        data = resp.json()
        events = []
        for item in data.get("items", []):
            start = item.get("start", {})
            end = item.get("end", {})
            conf = item.get("conferenceData", {})
            entry_points = conf.get("entryPoints", [])
            meet_link = item.get("hangoutLink", "")
            if not meet_link and entry_points:
                meet_link = entry_points[0].get("uri", "")

            desc = item.get("description", "")
            es_virtual = "VIRTUAL" in desc.upper() or bool(meet_link)

            events.append({
                "id": item.get("id"),
                "summary": item.get("summary", ""),
                "description": desc,
                "start_datetime": start.get("dateTime", start.get("date", "")),
                "end_datetime": end.get("dateTime", end.get("date", "")),
                "location": item.get("location", ""),
                "attendees": [a.get("email") for a in item.get("attendees", [])],
                "status": item.get("status", ""),
                "html_link": item.get("htmlLink", ""),
                "meet_link": meet_link,
                "modalidad": "VIRTUAL" if es_virtual else "PRESENCIAL",
            })

        return JSONResponse(content={"events": events})

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        return JSONResponse(content={"events": [], "error": str(e)})


@router.post("/api/calendar/events")
async def create_calendar_event(
    user_id: str = Form(""),
    summary: str = Form(...),
    description: str = Form(""),
    start_datetime: str = Form(...),
    end_datetime: str = Form(...),
    attendee_email: str = Form(""),
    location: str = Form(""),
    modalidad: str = Form("PRESENCIAL"),
    motivo: str = Form(""),
):
    """Create a new event in Google Calendar with Google Meet support."""
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id requerido")

    try:
        token = await _get_user_token(user_id)
        es_virtual = modalidad.strip().upper() == "VIRTUAL"

        if motivo and f"Motivo: {motivo}" not in description:
            desc_completa = f"{description}\nModalidad: {modalidad}\nMotivo: {motivo}".strip()
        else:
            desc_completa = description

        event_body = {
            "summary": summary,
            "description": desc_completa,
            "start": {"dateTime": start_datetime, "timeZone": "America/Argentina/Buenos_Aires"},
            "end": {"dateTime": end_datetime, "timeZone": "America/Argentina/Buenos_Aires"},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 60},
                    {"method": "email", "minutes": 1440},
                ],
            },
        }

        if attendee_email:
            event_body["attendees"] = [{"email": attendee_email}]
        if location and not es_virtual:
            event_body["location"] = location

        params = {}
        if es_virtual:
            params["conferenceDataVersion"] = "1"
            event_body["conferenceData"] = {
                "createRequest": {
                    "requestId": f"vocalislab-{int(time.time() * 1000)}",
                    "conferenceSolutionKey": {"type": "hangoutsMeet"},
                },
            }

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{GOOGLE_CALENDAR_URL}/calendars/primary/events",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                params=params,
                json=event_body,
            )

        if resp.status_code not in (200, 201):
            return JSONResponse(
                status_code=resp.status_code,
                content={"ok": False, "error": f"Google API {resp.status_code}: {resp.text}"}
            )

        created = resp.json()
        conf = created.get("conferenceData", {})
        entry_points = conf.get("entryPoints", [])
        meet_link = created.get("hangoutLink", "")
        if not meet_link and entry_points:
            meet_link = entry_points[0].get("uri", "")

        return JSONResponse(content={
            "ok": True,
            "google_event_id": created.get("id"),
            "html_link": created.get("htmlLink", ""),
            "meet_link": meet_link or None,
            "modalidad": modalidad,
        })

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error creando evento en Google Calendar: {str(e)}")


@router.post("/api/calendar/create-event")
async def create_event_json(request: Request):
    """
    Endpoint compatible con JSON payload del prompt arquitectónico:
    {
      "user_id": string,
      "pacienteNombre": string,
      "pacienteEmail": string,
      "modalidad": 'VIRTUAL' | 'PRESENCIAL',
      "fecha": 'YYYY-MM-DD',
      "horaInicio": 'HH:MM',
      "horaFin": 'HH:MM',
      "motivoConsulta": string
    }
    """
    try:
        body = await request.json()
    except Exception:
        body = {}

    user_id = body.get("user_id", "")
    paciente_nombre = body.get("pacienteNombre", "Paciente")
    paciente_email = body.get("pacienteEmail", "")
    modalidad = body.get("modalidad", "PRESENCIAL")
    fecha = body.get("fecha", datetime.utcnow().strftime("%Y-%m-%d"))
    hora_inicio = body.get("horaInicio", "10:00")
    hora_fin = body.get("horaFin", "10:45")
    motivo = body.get("motivoConsulta", "Especialidad Voz")

    start_datetime = f"{fecha}T{hora_inicio}:00"
    end_datetime = f"{fecha}T{hora_fin}:00"
    summary = f"Atención Vocal: {paciente_nombre}"
    description = f"Consulta Fonoaudiológica — Consultorio de Voz.\nPaciente: {paciente_nombre}\nModalidad: {modalidad}\nMotivo: {motivo}"

    return await create_calendar_event(
        user_id=user_id,
        summary=summary,
        description=description,
        start_datetime=start_datetime,
        end_datetime=end_datetime,
        attendee_email=paciente_email,
        modalidad=modalidad,
        motivo=motivo,
    )


@router.delete("/api/calendar/events/{event_id}")
async def delete_calendar_event(event_id: str, user_id: str = ""):
    """Delete an event from Google Calendar."""
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id requerido")

    try:
        token = await _get_user_token(user_id)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.delete(
                f"{GOOGLE_CALENDAR_URL}/calendars/primary/events/{event_id}",
                headers={"Authorization": f"Bearer {token}"},
            )

        if resp.status_code in (200, 204):
            return JSONResponse(content={"ok": True})
        return JSONResponse(content={"ok": False, "error": f"Google API {resp.status_code}"})

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error eliminando evento: {str(e)}")


@router.put("/api/calendar/events/{event_id}")
async def update_calendar_event(
    event_id: str,
    user_id: str = Form(""),
    summary: str = Form(""),
    description: str = Form(""),
    start_datetime: str = Form(""),
    end_datetime: str = Form(""),
):
    """Update an existing event in Google Calendar."""
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id requerido")

    try:
        token = await _get_user_token(user_id)

        event_body = {}
        if summary:
            event_body["summary"] = summary
        if description:
            event_body["description"] = description
        if start_datetime:
            event_body["start"] = {"dateTime": start_datetime, "timeZone": "America/Argentina/Buenos_Aires"}
        if end_datetime:
            event_body["end"] = {"dateTime": end_datetime, "timeZone": "America/Argentina/Buenos_Aires"}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.patch(
                f"{GOOGLE_CALENDAR_URL}/calendars/primary/events/{event_id}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=event_body,
            )

        if resp.status_code == 200:
            return JSONResponse(content={"ok": True})
        return JSONResponse(content={"ok": False, "error": f"Google API {resp.status_code}"})

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error actualizando evento: {str(e)}")


@router.post("/api/calendar/sync-turno")
async def sync_turno_to_calendar(
    user_id: str = Form(""),
    paciente_nombre: str = Form(""),
    paciente_email: str = Form(""),
    fecha_hora: str = Form(""),
    duracion_min: int = Form(30),
    modalidad: str = Form("PRESENCIAL"),
    motivo: str = Form(""),
    notas: str = Form(""),
):
    """Sync a VocalisLab turno to Google Calendar and return Meet link if virtual."""
    start = fecha_hora
    try:
        from datetime import datetime as dt
        start_dt = dt.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = start_dt + timedelta(minutes=duracion_min)
        end = end_dt.isoformat()
    except Exception:
        end = start

    summary = f"Atención Vocal: {paciente_nombre}"
    description = f"Sesión de fonoaudiología — Consultorio de Voz.\nModalidad: {modalidad}\nMotivo: {motivo}\n{notas}".strip()

    return await create_calendar_event(
        user_id=user_id,
        summary=summary,
        description=description,
        start_datetime=start,
        end_datetime=end,
        attendee_email=paciente_email,
        modalidad=modalidad,
        motivo=motivo,
    )
