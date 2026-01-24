"""Multi-layer JSON extraction and observation validation.

Handles non-ideal model outputs through three extraction strategies:
1. Direct JSON parse
2. Code-fence extraction (```json ... ```)
3. Brace extraction (first { ... } in text)

Each observation is validated individually: invalid spans are nullified,
unknown standard_refs are rejected, and confidence is clamped to [0, 1].
This ensures partial model output is salvaged rather than discarded entirely.
"""

import json
import re
import uuid

from ..logging import logger
from ..schemas.response import Observation

VALID_SEVERITIES = {"info", "warning", "violation"}
VALID_CATEGORIES = {
    "clarity",
    "accuracy",
    "structure",
    "accessibility",
    "pedagogy",
    "compliance",
    "other",
}


def extract_json(raw: str) -> dict | None:
    # Try direct parse
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Try code-fence extraction
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)```", raw, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # Try brace extraction
    brace_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group(0))
        except json.JSONDecodeError:
            pass

    return None


def validate_observation(
    obs_data: dict, content_length: int, known_refs: set[str]
) -> Observation | None:
    try:
        # Validate and clamp confidence
        confidence = obs_data.get("confidence", 0.0)
        if not isinstance(confidence, (int, float)):
            confidence = 0.5
        confidence = max(0.0, min(1.0, float(confidence)))
        obs_data["confidence"] = confidence

        # Validate severity
        severity = obs_data.get("severity", "info")
        if severity not in VALID_SEVERITIES:
            obs_data["severity"] = "info"

        # Validate category
        category = obs_data.get("category", "other")
        if category not in VALID_CATEGORIES:
            obs_data["category"] = "other"

        # Validate span
        span = obs_data.get("span")
        if span is not None:
            if (
                not isinstance(span, list)
                or len(span) != 2
                or not all(isinstance(x, int) for x in span)
                or span[0] < 0
                or span[0] >= span[1]
                or span[1] > content_length
            ):
                obs_data["span"] = None

        # Validate standard_ref
        ref = obs_data.get("standard_ref", "")
        if ref not in known_refs:
            return None

        # Require message
        if not obs_data.get("message"):
            return None

        # Add id
        obs_data["id"] = uuid.uuid4().hex[:12]

        return Observation.model_validate(obs_data)
    except Exception as e:
        logger.debug(f"Observation validation failed: {e}")
        return None


def parse_model_output(raw: str, content_length: int, known_refs: set[str]) -> list[Observation]:
    data = extract_json(raw)
    if data is None:
        logger.warning("Failed to extract JSON from model output")
        return []

    raw_observations = data.get("observations", [])
    if not isinstance(raw_observations, list):
        return []

    observations = []
    for obs_data in raw_observations:
        if not isinstance(obs_data, dict):
            continue
        obs = validate_observation(obs_data, content_length, known_refs)
        if obs is not None:
            observations.append(obs)

    return observations
