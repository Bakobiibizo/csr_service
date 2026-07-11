"""
GET /health endpoint for liveness and readiness checks.
"""

from fastapi import APIRouter, Request, Response, status

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


@router.get("/ready")
async def ready(request: Request, response: Response) -> dict:
    standards_sets = getattr(request.app.state, "standards_sets", {})
    model_client = getattr(request.app.state, "model_client", None)
    provider_ready = False
    if model_client is not None:
        probe = getattr(model_client, "is_ready", None)
        provider_ready = await probe() if probe else True
    ready_now = bool(standards_sets) and provider_ready
    if not ready_now:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return {
        "status": "ready" if ready_now else "not_ready",
        "ready": ready_now,
        "standards_ready": bool(standards_sets),
        "provider_ready": provider_ready,
    }
