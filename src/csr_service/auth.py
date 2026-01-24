"""Bearer token authentication dependency.

Validates requests against the configured CSR_AUTH_TOKEN. Unauthenticated
requests receive a 401 with a structured error body.
"""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

_bearer = HTTPBearer(auto_error=False)


async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if credentials is None or credentials.credentials != settings.auth_token:
        raise HTTPException(
            status_code=401,
            detail={"code": "AUTH_FAILED", "message": "Invalid or missing bearer token"},
        )
    return credentials.credentials
