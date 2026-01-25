"""
GET /health endpoint for liveness and readiness checks.
"""

from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/health")
async def health(request: Request) -> dict:
    standards_sets = getattr(request.app.state, "standards_sets", {})
    model_client = getattr(request.app.state, "model_client", None)

    return {
        "status": "ok",
        "standards_loaded": len(standards_sets),
        "model_backend": "connected" if model_client else "unavailable",
    }
