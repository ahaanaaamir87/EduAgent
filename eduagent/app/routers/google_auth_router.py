"""
Google OAuth2 login flow.

Required .env keys (add these to your .env file):
    GOOGLE_CLIENT_ID=<your-client-id>
    GOOGLE_CLIENT_SECRET=<your-client-secret>
    GOOGLE_REDIRECT_URI=http://localhost:8000/auth/google/callback
"""
import os
import secrets
import httpx

from dotenv import load_dotenv
from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.auth import hash_password

router = APIRouter(prefix="/auth/google", tags=["google-oauth"])

GOOGLE_AUTH_URL  = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO  = "https://www.googleapis.com/oauth2/v3/userinfo"


def _get_creds():
    """Read credentials fresh from .env on every call."""
    load_dotenv(override=True)
    return (
        os.getenv("GOOGLE_CLIENT_ID", ""),
        os.getenv("GOOGLE_CLIENT_SECRET", ""),
        os.getenv("GOOGLE_REDIRECT_URI", "http://localhost:8000/auth/google/callback"),
    )


@router.get("")
def google_login(request: Request):
    client_id, client_secret, redirect_uri = _get_creds()
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=503,
            detail="Google OAuth is not configured. Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to your .env file.",
        )

    state = secrets.token_urlsafe(16)
    request.session["oauth_state"] = state

    params = {
        "client_id":     client_id,
        "redirect_uri":  redirect_uri,
        "response_type": "code",
        "scope":         "openid email profile",
        "state":         state,
        "access_type":   "online",
    }
    url = GOOGLE_AUTH_URL + "?" + "&".join(f"{k}={v}" for k, v in params.items())
    return RedirectResponse(url)


@router.get("/callback")
async def google_callback(request: Request, code: str = "", state: str = "", db: Session = Depends(get_db)):
    client_id, client_secret, redirect_uri = _get_creds()
    if not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured.")

    saved_state = request.session.pop("oauth_state", None)
    if not saved_state or saved_state != state:
        raise HTTPException(status_code=400, detail="Invalid OAuth state — possible CSRF.")

    if not code:
        raise HTTPException(status_code=400, detail="No authorisation code returned by Google.")

    # Exchange code for tokens
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code":          code,
                "client_id":     client_id,
                "client_secret": client_secret,
                "redirect_uri":  redirect_uri,
                "grant_type":    "authorization_code",
            },
        )

    if token_resp.status_code != 200:
        raise HTTPException(status_code=502, detail=f"Failed to exchange code with Google: {token_resp.text}")

    access_token = token_resp.json().get("access_token")

    # Fetch user info
    async with httpx.AsyncClient() as client:
        info_resp = await client.get(
            GOOGLE_USERINFO,
            headers={"Authorization": f"Bearer {access_token}"},
        )
    if info_resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch user info from Google.")

    info  = info_resp.json()
    email = info.get("email", "").lower().strip()
    name  = info.get("name") or email.split("@")[0]

    if not email:
        raise HTTPException(status_code=400, detail="Google did not return an email address.")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            name=name,
            email=email,
            hashed_password=hash_password(secrets.token_urlsafe(32)),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    request.session["user_id"] = user.id
    return RedirectResponse(url="/dashboard", status_code=302)