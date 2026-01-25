"""Review pipeline orchestration.

Coordinates the full review flow:
1. Retrieve relevant rules via TF-IDF
2. Build system + user prompts
3. Call the LLM for structured observations
4. Parse and validate model output
5. Apply policy layer (confidence gating, strictness bias, dedup, sort)
6. Return a complete ReviewResponse with metadata and timing

Supports two modes:
- Multi-rule (default): All rules in one prompt
- Single-rule: One rule per request, parallel execution

On model failure, returns an empty observation list with an error entry,
preserving the response schema invariant.
"""

import asyncio
import time

from ..config import settings
from ..logging import logger
from ..policy.policy import apply_policy
from ..schemas.request import ReviewRequest
from ..schemas.response import Error, Meta, Observation, ReviewResponse, Usage
from ..schemas.standards import StandardRule, StandardsSet
from ..standards.retriever import StandardsRetriever
from .model_client import ModelClient
from .parser import extract_json, parse_model_output
from .prompt import (
    build_single_rule_prompt,
    build_user_prompt,
    get_single_rule_system_prompt,
    get_system_prompt,
)


async def _evaluate_single_rule(
    content: str,
    rule: StandardRule,
    strictness: str,
    model_client: ModelClient,
) -> tuple[list[Observation], Usage, Error | None]:
    """Evaluate content against a single rule."""
    system_prompt = get_single_rule_system_prompt()
    user_prompt = build_single_rule_prompt(content, rule, strictness)

    try:
        raw_output, usage = await model_client.generate(system_prompt, user_prompt)
    except Exception as e:
        logger.error(f"Single-rule model failure for {rule.standard_ref}: {e}")
        return [], Usage(), Error(code="MODEL_FAILURE", message=f"{rule.standard_ref}: {e}")

    observations = parse_model_output(raw_output, len(content), {rule.standard_ref})
    return observations, usage, None


async def _run_single_rule_mode(
    request: ReviewRequest,
    rules: list[StandardRule],
    model_client: ModelClient,
) -> tuple[list[Observation], Usage, list[Error]]:
    """Run evaluation in single-rule mode (one rule per request)."""
    errors: list[Error] = []
    all_observations: list[Observation] = []
    total_usage = Usage()

    if settings.single_rule_parallel:
        # Parallel execution
        tasks = [
            _evaluate_single_rule(request.content, rule, request.strictness, model_client)
            for rule in rules
        ]
        results = await asyncio.gather(*tasks)

        for obs_list, usage, error in results:
            all_observations.extend(obs_list)
            total_usage.input_tokens += usage.input_tokens
            total_usage.output_tokens += usage.output_tokens
            if error:
                errors.append(error)
    else:
        # Sequential execution
        for rule in rules:
            obs_list, usage, error = await _evaluate_single_rule(
                request.content, rule, request.strictness, model_client
            )
            all_observations.extend(obs_list)
            total_usage.input_tokens += usage.input_tokens
            total_usage.output_tokens += usage.output_tokens
            if error:
                errors.append(error)

    logger.info(f"Single-rule mode: {len(rules)} rules, {len(all_observations)} observations")
    return all_observations, total_usage, errors


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

    # Choose execution mode
    if settings.single_rule_mode:
        observations, usage, rule_errors = await _run_single_rule_mode(
            request, rules, model_client
        )
        errors.extend(rule_errors)
    else:
        # Multi-rule mode (original behavior)
        user_prompt = build_user_prompt(request.content, rules, request.strictness)

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

        observations = parse_model_output(raw_output, len(request.content), known_refs)

        if not observations and raw_output.strip():
            parsed = extract_json(raw_output)
            if parsed is None or "observations" not in parsed:
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

    mode = "single-rule" if settings.single_rule_mode else "multi-rule"
    logger.info(
        f"Review complete ({mode}): standards_set={request.standards_set} "
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
