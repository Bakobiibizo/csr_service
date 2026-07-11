"""Bearer token authentication dependency.

Validates requests against the configured CSR_AUTH_TOKEN. Unauthenticated
requests receive a 401 with a structured error body.
Just using a simple bearer token for the demo, but this could be replaced with a more robust authentication system.
"""

import secrets

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

_bearer = HTTPBearer(auto_error=False)


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    configured = [token.strip() for token in settings.auth_tokens.split(",") if token.strip()]
    if not configured:
        configured = [settings.auth_token]
    supplied = credentials.credentials if credentials is not None else ""
    valid = any(secrets.compare_digest(supplied, token) for token in configured)
    if not valid:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_FAILED", "message": "Invalid or missing bearer token"},
        )
    return supplied
