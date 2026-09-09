"""
VocalisLab Pro - Google OAuth 2.0 + Calendar API Integration
"""
import os
import json
import time
import traceback
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Request, Form
from fastapi.responses import JSONResponse, HTMLResponse
import httpx

router = APIRouter()

GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get("GOOGLE_REDIRECT_URI", "https://vocalislab.onrender.com/api/auth/callback/google")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://vocalis-lab.vercel.app")

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_CALENDAR_URL = "https://www.googleapis.com/calendar/v3"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/calendar.events",
    "https://www.googleapis.com/auth/calendar.readonly",
]

_tokens_store: dict = {}


def _get_provider():
    """Lazy-load Supabase client."""
    try:
        from supabase import create_client
        url = os.environ.get("SUPABASE_URL", "")
        key = os.environ.get("SUPABASE_SERVICE_KEY", os.environ.get("SUPABASE_ANON_KEY", ""))
        if url and key:
            return create_client(url, key)
    except Exception:
        pass
    return None


@router.get("/api/auth/google/url")
async def get_google_auth_url():
    """Generate Google OAuth 2.0 authorization URL."""
    if not GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=500, detail="GOOGLE_CLIENT_ID no configurado")

    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": "vocalislab_auth",
    }
    query = "&".join(f"{k}={v}" for k, v in params.items())
    auth_url = f"{GOOGLE_AUTH_URL}?{query}"
    return JSONResponse(content={"url": auth_url})


@router.get("/api/auth/callback/google")
async def google_callback(code: str = "", state: str = ""):
    """Handle Google OAuth callback, exchange code for tokens, return to frontend."""
    if not code:
        return HTMLResponse(content="<script>alert('Error: No authorization code received'); window.close();</script>")

    try:
        async with httpx.AsyncClient() as client:
            token_response = await client.post(GOOGLE_TOKEN_URL, data={
                "code": code,
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "redirect_uri": GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
            })

        if token_response.status_code != 200:
            return HTMLResponse(content="<script>alert('Error exchanging token'); window.close();</script>")

        tokens = token_response.json()
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")
        expires_in = tokens.get("expires_in", 3600)

        async with httpx.AsyncClient() as client:
            user_response = await client.get(GOOGLE_USERINFO_URL, headers={
                "Authorization": f"Bearer {access_token}"
            })

        user_info = {}
        if user_response.status_code == 200:
            user_info = user_response.json()

        user_data = {
            "id": user_info.get("id", ""),
            "email": user_info.get("email", ""),
            "name": user_info.get("name", ""),
            "picture": user_info.get("picture", ""),
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_expires_at": int(time.time()) + expires_in,
        }

        supabase = _get_provider()
        if supabase:
            try:
                supabase.table("usuarios_google").upsert({
                    "google_id": user_data["id"],
                    "email": user_data["email"],
                    "name": user_data["name"],
                    "picture": user_data["picture"],
                    "access_token": access_token,
                    "refresh_token": refresh_token,
                    "token_expires_at": user_data["token_expires_at"],
                }, on_conflict="google_id").execute()
            except Exception as e:
                print(f"[google_auth] Error guardando tokens en Supabase: {e}")

        _tokens_store[user_data["id"]] = user_data

        frontend_data = json.dumps({
            "id": user_data["id"],
            "email": user_data["email"],
            "name": user_data["name"],
            "picture": user_data["picture"],
            "access_token": access_token,
        })
        import base64
        encoded = base64.b64encode(frontend_data.encode()).decode()

        return HTMLResponse(content=f"""
            <html><body><script>
                const data = JSON.parse(atob('{encoded}'));
                localStorage.setItem('vocalislab_user', JSON.stringify(data));
                window.location.href = '{FRONTEND_URL}';
            </script></body></html>
        """)

    except Exception as e:
        traceback.print_exc()
        return HTMLResponse(content=f"<script>alert('Error: {str(e)}'); window.location.href='{FRONTEND_URL}';</script>")


async def _refresh_access_token(refresh_token: str) -> dict:
    """Refresh an expired Google access token."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(GOOGLE_TOKEN_URL, data={
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
    if resp.status_code != 200:
        raise Exception("Failed to refresh token")
    return resp.json()


async def _get_valid_token(user_id: str) -> str:
    """Get a valid access token, refreshing if necessary."""
    user_data = _tokens_store.get(user_id)
    if not user_data:
        supabase = _get_provider()
        if supabase:
            try:
                result = supabase.table("usuarios_google").select("*").eq("google_id", user_id).execute()
                if result.data:
                    user_data = result.data[0]
            except Exception:
                pass

    if not user_data:
        raise HTTPException(status_code=401, detail="Usuario no autenticado con Google")

    expires_at = user_data.get("token_expires_at", 0)
    if time.time() > expires_at - 300:
        refresh_token = user_data.get("refresh_token")
        if refresh_token:
            new_tokens = await _refresh_access_token(refresh_token)
            user_data["access_token"] = new_tokens["access_token"]
            user_data["token_expires_at"] = int(time.time()) + new_tokens.get("expires_in", 3600)
            _tokens_store[user_id] = user_data

            supabase = _get_provider()
            if supabase:
                try:
                    supabase.table("usuarios_google").update({
                        "access_token": new_tokens["access_token"],
                        "token_expires_at": user_data["token_expires_at"],
                    }).eq("google_id", user_id).execute()
                except Exception:
                    pass

    return user_data["access_token"]


@router.get("/api/auth/me")
async def get_current_user(user_id: str = ""):
    """Get current authenticated user info."""
    if not user_id:
        return JSONResponse(content={"authenticated": False})

    user_data = _tokens_store.get(user_id)
    if not user_data:
        supabase = _get_provider()
        if supabase:
            try:
                result = supabase.table("usuarios_google").select("google_id, email, name, picture").eq("google_id", user_id).execute()
                if result.data:
                    user_data = result.data[0]
            except Exception:
                pass

    if not user_data:
        return JSONResponse(content={"authenticated": False})

    return JSONResponse(content={
        "authenticated": True,
        "id": user_data.get("id") or user_data.get("google_id"),
        "email": user_data.get("email"),
        "name": user_data.get("name"),
        "picture": user_data.get("picture"),
    })


@router.post("/api/auth/logout")
async def logout(user_id: str = Form("")):
    """Logout user and clear tokens."""
    if user_id and user_id in _tokens_store:
        del _tokens_store[user_id]
    return JSONResponse(content={"ok": True})
