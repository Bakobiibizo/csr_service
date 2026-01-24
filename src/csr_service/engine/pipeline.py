"""Review pipeline orchestration.

Coordinates the full review flow:
1. Retrieve relevant rules via TF-IDF
2. Build system + user prompts
3. Call the LLM for structured observations
4. Parse and validate model output
5. Apply policy layer (confidence gating, strictness bias, dedup, sort)
6. Return a complete ReviewResponse with metadata and timing

On model failure, returns an empty observation list with an error entry,
preserving the response schema invariant.
"""

import time

from ..config import settings
from ..logging import logger
from ..policy.policy import apply_policy
from ..schemas.request import ReviewRequest
from ..schemas.response import Error, Meta, ReviewResponse, Usage
from ..schemas.standards import StandardsSet
from ..standards.retriever import StandardsRetriever
from .model_client import ModelClient
from .parser import parse_model_output
from .prompt import build_user_prompt, get_system_prompt


async def run_review(
    request: ReviewRequest,
    standards_set: StandardsSet,
    retriever: StandardsRetriever,
    model_client: ModelClient,
) -> ReviewResponse:
    start_time = time.time()
    request_id = request.request_id or ""
    errors: list[Error] = []
    usage = Usage()

    # Retrieve relevant rules
    rules = retriever.retrieve(request.content, request.strictness)
    known_refs = {r.standard_ref for r in rules}

    # Build prompts
    user_prompt = build_user_prompt(request.content, rules, request.strictness)

    # Call model
    try:
        raw_output, usage = await model_client.generate(get_system_prompt(), user_prompt)
    except Exception as e:
        logger.error(f"Model failure: {e}")
        latency_ms = int((time.time() - start_time) * 1000)
        return ReviewResponse(
            observations=[],
            meta=Meta(
                request_id=request_id,
                standards_set=request.standards_set,
                strictness=request.strictness,
                policy_version=settings.policy_version,
                model_id=settings.model_id,
                latency_ms=latency_ms,
                usage=usage,
            ),
            errors=[Error(code="MODEL_FAILURE", message=str(e))],
        )

    # Parse model output
    observations = parse_model_output(raw_output, len(request.content), known_refs)

    if not observations and raw_output.strip():
        # Model produced output but we couldn't parse valid observations
        errors.append(
            Error(
                code="MODEL_PARSE_FAILURE",
                message="Model returned output but no valid observations could be extracted",
            )
        )

    # Apply policy
    observations = apply_policy(
        observations=observations,
        strictness=request.strictness,
        min_confidence=request.options.min_confidence,
        max_observations=request.options.max_observations,
    )

    # Strip rationale/excerpts if not requested
    if not request.options.return_rationale:
        for obs in observations:
            obs.rationale = None
    if not request.options.return_excerpts:
        for obs in observations:
            obs.standard_excerpt = None

    latency_ms = int((time.time() - start_time) * 1000)

    logger.info(
        f"Review complete: standards_set={request.standards_set} "
        f"strictness={request.strictness} observations={len(observations)} "
        f"latency_ms={latency_ms}"
    )

    return ReviewResponse(
        observations=observations,
        meta=Meta(
            request_id=request_id,
            standards_set=request.standards_set,
            strictness=request.strictness,
            policy_version=settings.policy_version,
            model_id=settings.model_id,
            latency_ms=latency_ms,
            usage=usage,
        ),
        errors=errors,
    )
