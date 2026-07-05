"""Lightweight RM demo authentication."""

from __future__ import annotations

import hashlib
import hmac

import os

from fastapi import Request
from starlette.responses import RedirectResponse

from app.config import AUTH_COOKIE, AUTH_EXEMPT_PREFIXES, RM_DEMO_PIN

DISABLE_AUTH = os.environ.get("DISABLE_RM_AUTH", "").lower() in ("1", "true")

_TOKEN = hashlib.sha256(f"prospect-assist:{RM_DEMO_PIN}".encode()).hexdigest()


def auth_token() -> str:
    return _TOKEN


def verify_pin(pin: str) -> bool:
    return hmac.compare_digest(pin.strip(), RM_DEMO_PIN)


def is_authenticated(request: Request) -> bool:
    return request.cookies.get(AUTH_COOKIE) == _TOKEN


def is_public_path(path: str) -> bool:
    return path == "/login" or any(path.startswith(p) for p in AUTH_EXEMPT_PREFIXES)


def require_auth(request: Request) -> RedirectResponse | None:
    if DISABLE_AUTH:
        return None
    if is_public_path(request.url.path):
        return None
    if is_authenticated(request):
        return None
    return RedirectResponse(url="/login", status_code=302)
