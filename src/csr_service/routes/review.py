"""
POST /v1/review endpoint.

Accepts instructional content and a standards set, runs the full review
pipeline, and returns structured observations. Requires bearer token auth.
Validates content length and standards set existence before processing.
"""

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import require_auth
from ..config import settings
from ..engine.pipeline import run_review
from ..logging import get_request_id, request_id_ctx
from ..schemas.request import ReviewRequest
from ..schemas.response import ReviewResponse

router = APIRouter(prefix="/v1")


@router.post("/review", response_model=ReviewResponse)
async def review(
    request: Request,
    body: ReviewRequest,
    _token: str = Depends(require_auth),
) -> ReviewResponse:
    # Set request_id context
    rid = body.request_id or get_request_id()
    request_id_ctx.set(rid)
    body.request_id = rid

    # Validate content length
    if not body.content.strip():
        raise HTTPException(
            status_code=422,
            detail={"code": "EMPTY_CONTENT", "message": "Content must not be empty"},
        )
    if len(body.content) > settings.max_content_length:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "CONTENT_TOO_LONG",
                "message": f"Content exceeds maximum length of {settings.max_content_length}",
            },
        )

    # Check standards_set exists
    standards_sets = getattr(request.app.state, "standards_sets", {})
    if body.standards_set not in standards_sets:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "STANDARDS_NOT_FOUND",
                "message": f"Standards set '{body.standards_set}' not found",
            },
        )

    retrievers = getattr(request.app.state, "retrievers", {})
    model_client = getattr(request.app.state, "model_client", None)
    if model_client is None:
        raise HTTPException(
            status_code=503,
            detail={"code": "MODEL_UNAVAILABLE", "message": "Model client not initialized"},
        )

    return await run_review(
        request=body,
        standards_set=standards_sets[body.standards_set],
        retriever=retrievers[body.standards_set],
        model_client=model_client,
    )
