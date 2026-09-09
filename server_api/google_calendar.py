"""
VocalisLab Pro — Google Calendar API Integration
Sincronización bidireccional: Google Calendar ↔ Agenda de turnos VocalisLab.
"""
import os
import traceback
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Form
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
    """Fetch events from Google Calendar for the authenticated user."""
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
            events.append({
                "id": item.get("id"),
                "summary": item.get("summary", ""),
                "description": item.get("description", ""),
                "start_datetime": start.get("dateTime", start.get("date", "")),
                "end_datetime": end.get("dateTime", end.get("date", "")),
                "location": item.get("location", ""),
                "attendees": [a.get("email") for a in item.get("attendees", [])],
                "status": item.get("status", ""),
                "html_link": item.get("htmlLink", ""),
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
):
    """Create a new event in Google Calendar."""
    if not user_id:
        raise HTTPException(status_code=401, detail="user_id requerido")

    try:
        token = await _get_user_token(user_id)

        event_body = {
            "summary": summary,
            "description": description,
            "start": {"dateTime": start_datetime, "timeZone": "America/Argentina/Buenos_Aires"},
            "end": {"dateTime": end_datetime, "timeZone": "America/Argentina/Buenos_Aires"},
            "reminders": {
                "useDefault": False,
                "overrides": [
                    {"method": "popup", "minutes": 30},
                    {"method": "email", "minutes": 1440},
                ],
            },
        }
        if attendee_email:
            event_body["attendees"] = [{"email": attendee_email}]
        if location:
            event_body["location"] = location

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{GOOGLE_CALENDAR_URL}/calendars/primary/events",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json",
                },
                json=event_body,
            )

        if resp.status_code not in (200, 201):
            return JSONResponse(content={"ok": False, "error": f"Google API {resp.status_code}: {resp.text}"})

        created = resp.json()
        return JSONResponse(content={
            "ok": True,
            "google_event_id": created.get("id"),
            "html_link": created.get("htmlLink", ""),
        })

    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error creando evento: {str(e)}")


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
    notas: str = Form(""),
):
    """Sync a VocalisLab turno to Google Calendar (create event)."""
    start = fecha_hora
    # Calculate end time
    try:
        from datetime import datetime as dt
        start_dt = dt.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = start_dt + timedelta(minutes=duracion_min)
        end = end_dt.isoformat()
    except Exception:
        end = start

    summary = f"Atención Vocal: {paciente_nombre}"
    description = f"Sesión de fonoaudiología en VocalisLab Pro.\n{notas}" if notas else "Sesión de fonoaudiología en VocalisLab Pro."

    return await create_calendar_event(
        user_id=user_id,
        summary=summary,
        description=description,
        start_datetime=start,
        end_datetime=end,
        attendee_email=paciente_email,
    )
