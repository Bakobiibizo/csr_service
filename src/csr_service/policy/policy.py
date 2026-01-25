"""
Post-processing policy layer for observation filtering and normalization.

Applies deterministic rules to model output, independent of prompting:
- confidence_gate: downgrades or drops observations below min_confidence
- strictness_bias: prevents low-confidence violations based on strictness level
- deduplicate: merges observations on same span + standard_ref
- sort_observations: orders by severity (violation > warning > info), then confidence
- apply_policy: chains all above and truncates to max_observations
"""

from typing import Literal

from ..config import policy_config
from ..schemas.response import Observation

SEVERITY_ORDER = {"violation": 0, "warning": 1, "info": 2}
SEVERITY_DOWNGRADE = {"violation": "warning", "warning": "info", "info": None}


def confidence_gate(observations: list[Observation], min_confidence: float) -> list[Observation]:
    result = []
    for obs in observations:
        if obs.confidence >= min_confidence:
            result.append(obs)
        else:
            # Downgrade severity
            new_severity = SEVERITY_DOWNGRADE.get(obs.severity)
            if new_severity is None:
                continue  # Drop info-level below threshold
            obs.severity = new_severity
            result.append(obs)
    return result


def strictness_bias(
    observations: list[Observation],
    strictness: Literal["low", "medium", "high"],
) -> list[Observation]:
    threshold = policy_config.thresholds.by_strictness.get(strictness, 0.75)
    for obs in observations:
        if obs.severity == "violation" and obs.confidence < threshold:
            obs.severity = "warning"
    return observations


def deduplicate(observations: list[Observation]) -> list[Observation]:
    seen: dict[tuple, Observation] = {}
    for obs in observations:
        key = (tuple(obs.span) if obs.span else None, obs.standard_ref)
        if key in seen:
            if obs.confidence > seen[key].confidence:
                seen[key] = obs
        else:
            seen[key] = obs
    return list(seen.values())


def sort_observations(observations: list[Observation]) -> list[Observation]:
    return sorted(observations, key=lambda o: (SEVERITY_ORDER.get(o.severity, 2), -o.confidence))


def apply_policy(
    observations: list[Observation],
    strictness: Literal["low", "medium", "high"] = "medium",
    min_confidence: float | None = None,
    max_observations: int | None = None,
) -> list[Observation]:
    if min_confidence is None:
        min_confidence = policy_config.defaults.min_confidence
    if max_observations is None:
        max_observations = policy_config.defaults.max_observations
    observations = confidence_gate(observations, min_confidence)
    observations = strictness_bias(observations, strictness)
    observations = deduplicate(observations)
    observations = sort_observations(observations)
    return observations[:max_observations]
