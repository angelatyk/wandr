"""Authentication: Google ID-token verification + signed session cookies.

Sessions are stored in an HMAC-signed, tamper-evident cookie (no server-side
session store needed). We deliberately use the stdlib `hmac`/`hashlib` rather
than adding a new dependency.

EventSource (used by the SSE stream) cannot send Authorization headers, so auth
MUST ride on a cookie — the browser sends it automatically on same-origin
requests, including the audio <audio> element and the itinerary stream.
"""

import base64
import hashlib
import hmac
import json
import logging
import time

from fastapi import HTTPException, Request, Response, status

from ai.config.settings import settings
from ai.models.auth import AuthUser

logger = logging.getLogger(__name__)

# Google's token verification libs (transitive dep via google-adk / google-auth).
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

_GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _signing_key() -> bytes:
    secret = settings.session_secret_key
    if not secret:
        # Fail closed: without a secret we cannot issue trustworthy sessions.
        raise RuntimeError(
            "SESSION_SECRET_KEY is not configured. Set a long random value in .env "
            "before enabling authentication."
        )
    return secret.encode("utf-8")


def sign_session(user: AuthUser) -> str:
    """Return an HMAC-signed, expiring session token for a user."""
    payload = {
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "picture": user.picture,
        "exp": int(time.time()) + settings.session_ttl_seconds,
    }
    body = _b64encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64encode(signature)}"


def verify_session(token: str) -> AuthUser | None:
    """Validate a session token's signature + expiry and return the user."""
    if not token or token.count(".") != 1:
        return None
    body, signature = token.split(".", 1)
    expected = hmac.new(_signing_key(), body.encode("ascii"), hashlib.sha256).digest()
    try:
        provided = _b64decode(signature)
    except (ValueError, base64.binascii.Error):
        return None
    if not hmac.compare_digest(expected, provided):
        return None

    try:
        payload = json.loads(_b64decode(body).decode("utf-8"))
    except (ValueError, base64.binascii.Error, UnicodeDecodeError):
        return None

    if int(payload.get("exp", 0)) < int(time.time()):
        return None

    sub = payload.get("sub")
    if not sub:
        return None
    return AuthUser(
        id=sub,
        email=payload.get("email", ""),
        name=payload.get("name", ""),
        picture=payload.get("picture", ""),
    )


def verify_google_id_token(credential: str) -> AuthUser:
    """Verify a Google Identity Services ID token and return the user identity."""
    client_id = settings.google_oauth_client_id
    if not client_id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Google sign-in is not configured on the server.",
        )
    try:
        claims = google_id_token.verify_oauth2_token(
            credential,
            google_requests.Request(),
            client_id,
        )
    except ValueError as exc:
        logger.warning("Google ID token verification failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Google sign-in token.",
        ) from exc

    if claims.get("iss") not in _GOOGLE_ISSUERS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Untrusted token issuer.",
        )

    sub = claims.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject.",
        )

    return AuthUser(
        id=sub,
        email=claims.get("email", ""),
        name=claims.get("name", ""),
        picture=claims.get("picture", ""),
    )


def dev_login_allowed() -> bool:
    """Dev login is only safe on non-HTTPS local setups and must be opt-in.

    Fails closed in production: a secure cookie means we are behind HTTPS, where
    an unauthenticated login shortcut must never be reachable.
    """
    return settings.dev_auth_enabled and not settings.session_cookie_secure


def dev_login_user(email: str | None = None) -> AuthUser:
    """Build a deterministic local user for development sign-in."""
    if not dev_login_allowed():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Dev login is disabled.",
        )
    normalized = (email or "dev@wandr.local").strip().lower()
    # Deterministic id so the same dev email maps to the same trips across logins.
    dev_id = "dev:" + hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]
    return AuthUser(id=dev_id, email=normalized, name="Local Dev", picture="")


def set_session_cookie(response: Response, user: AuthUser) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=sign_session(user),
        max_age=settings.session_ttl_seconds,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite="lax",
    )


def get_optional_user(request: Request) -> AuthUser | None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    return verify_session(token)


def get_current_user(request: Request) -> AuthUser:
    """FastAPI dependency — require a valid session cookie or raise 401."""
    user = get_optional_user(request)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user
