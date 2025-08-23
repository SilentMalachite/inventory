from __future__ import annotations

import os
import secrets
from typing import Optional

from fastapi import Depends, Header, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials


http_basic = HTTPBasic(auto_error=False)


def require_api_key(x_api_key: Optional[str] = Header(None, alias="X-API-Key")) -> None:
    """Require API key via X-API-Key header when INVENTORY_API_KEY is configured.

    - If INVENTORY_API_KEY is unset/empty: allow all (dev/test friendliness)
    - Else: compare using constant-time and raise 401 on mismatch
    """
    required = os.environ.get("INVENTORY_API_KEY", "").strip()
    if not required:
        return
    if not x_api_key or not secrets.compare_digest(x_api_key, required):
        raise HTTPException(status_code=401, detail="Unauthorized")


def require_basic_auth(credentials: Optional[HTTPBasicCredentials] = Depends(http_basic)) -> None:
    """Optional HTTP Basic auth for web endpoints.

    Enabled when both INVENTORY_BASIC_USER and INVENTORY_BASIC_PASS are set.
    """
    user = os.environ.get("INVENTORY_BASIC_USER", "").strip()
    pwd = os.environ.get("INVENTORY_BASIC_PASS", "").strip()
    if not user or not pwd:
        return
    if credentials is None:
        # No credentials provided and required
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not (secrets.compare_digest(credentials.username, user) and secrets.compare_digest(credentials.password, pwd)):
        raise HTTPException(status_code=401, detail="Unauthorized")


def get_csrf_token(request: Request) -> str:
    """Get or create CSRF token bound to the current session."""
    token = request.session.get("csrf_token")
    if not token:
        token = secrets.token_urlsafe(32)
        request.session["csrf_token"] = token
    return token


def validate_csrf_or_400(request: Request, token_from_form: Optional[str]) -> None:
    """Validate CSRF token; raise 400 on failure."""
    expected = request.session.get("csrf_token")
    if not expected or not token_from_form or not secrets.compare_digest(str(token_from_form), str(expected)):
        raise HTTPException(status_code=400, detail="Invalid CSRF token")
