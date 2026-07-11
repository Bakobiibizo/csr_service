"""
POST /v1/review endpoint.

Accepts instructional content and a standards set, runs the full review
pipeline, and returns structured observations. Requires bearer token auth.
Validates content length and standards set existence before processing.
"""

import asyncio
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import require_auth
from ..config import settings
from ..engine.pipeline import run_review
from ..logging import get_request_id, request_id_ctx
from ..schemas.request import ReviewRequest
from ..schemas.response import ReviewResponse

router = APIRouter(prefix="/v1")
_review_slots = asyncio.Semaphore(settings.max_concurrent_reviews)


def _audit(request_id: str, body: ReviewRequest, status: str) -> None:
    """Persist privacy-safe operational metadata; content is never stored."""
    if not settings.audit_log_path:
        return
    record = {
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": request_id,
        "standards_set": body.standards_set,
        "content_sha256": hashlib.sha256(body.content.encode()).hexdigest(),
        "content_length": len(body.content),
        "status": status,
    }
    path = Path(settings.audit_log_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record, separators=(",", ":")) + "\n")


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

    try:
        async with asyncio.timeout(settings.request_timeout):
            async with _review_slots:
                response = await run_review(
                    request=body,
                    standards_set=standards_sets[body.standards_set],
                    retriever=retrievers[body.standards_set],
                    model_client=model_client,
                )
        _audit(rid, body, "completed")
        return response
    except TimeoutError as exc:
        _audit(rid, body, "timeout")
        raise HTTPException(
            status_code=504,
            detail={"code": "REVIEW_TIMEOUT", "message": "Review exceeded its time limit"},
        ) from exc
