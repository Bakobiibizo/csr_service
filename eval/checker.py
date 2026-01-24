"""Evaluation checker utilities.

Provides schema validation, repeatability analysis (span and severity
stability across repeated runs), and latency statistics (mean/p95).
"""

from pydantic import ValidationError

from src.csr_service.schemas.response import ReviewResponse


def validate_schema(response_data: dict) -> tuple[bool, str]:
    try:
        ReviewResponse.model_validate(response_data)
        return True, ""
    except ValidationError as e:
        return False, str(e)


def check_repeatability(runs: list[dict]) -> dict:
    if len(runs) < 2:
        return {"span_stability": 1.0, "severity_stability": 1.0}

    total_comparisons = 0
    span_matches = 0
    severity_matches = 0

    baseline = runs[0]
    baseline_obs = baseline.get("observations", [])

    for run in runs[1:]:
        run_obs = run.get("observations", [])
        # Compare by standard_ref matching
        baseline_refs = {o["standard_ref"]: o for o in baseline_obs}
        run_refs = {o["standard_ref"]: o for o in run_obs}

        common_refs = set(baseline_refs) & set(run_refs)
        for ref in common_refs:
            total_comparisons += 1
            if baseline_refs[ref].get("span") == run_refs[ref].get("span"):
                span_matches += 1
            if baseline_refs[ref].get("severity") == run_refs[ref].get("severity"):
                severity_matches += 1

    if total_comparisons == 0:
        return {"span_stability": 1.0, "severity_stability": 1.0}

    return {
        "span_stability": span_matches / total_comparisons,
        "severity_stability": severity_matches / total_comparisons,
    }


def compute_latency_stats(latencies: list[int]) -> dict:
    if not latencies:
        return {"mean_ms": 0, "min_ms": 0, "max_ms": 0, "p95_ms": 0}

    latencies_sorted = sorted(latencies)
    mean = sum(latencies) / len(latencies)
    p95_idx = int(len(latencies_sorted) * 0.95)
    p95 = latencies_sorted[min(p95_idx, len(latencies_sorted) - 1)]

    return {
        "mean_ms": int(mean),
        "min_ms": latencies_sorted[0],
        "max_ms": latencies_sorted[-1],
        "p95_ms": p95,
    }


def check_expectations(
    response_data: dict, expectations: dict, expect_error: bool = False
) -> list[dict]:
    """Check response against case expectations.

    Returns list of {"check": str, "passed": bool, "detail": str}.
    """
    results = []

    if expect_error:
        expected_code = expectations.get("expected_error_code")
        if expected_code:
            error_text = response_data.get("_error", "")
            passed = expected_code in error_text
            results.append({
                "check": "expected_error_code",
                "passed": passed,
                "detail": f"expected '{expected_code}' in response"
                + ("" if passed else f", got: {error_text[:80]}"),
            })
        return results

    observations = response_data.get("observations", [])
    obs_count = len(observations)

    min_obs = expectations.get("min_obs")
    max_obs = expectations.get("max_obs")
    if min_obs is not None and max_obs is not None:
        passed = min_obs <= obs_count <= max_obs
        results.append({
            "check": "observation_count",
            "passed": passed,
            "detail": f"{obs_count} (expected {min_obs}-{max_obs})",
        })

    expected_severities = expectations.get("expected_severities")
    if expected_severities:
        found_severities = {o.get("severity") for o in observations}
        for sev in expected_severities:
            passed = sev in found_severities
            results.append({
                "check": f"expected_severity:{sev}",
                "passed": passed,
                "detail": f"{'found' if passed else 'NOT found'} in observations",
            })

    expected_refs = expectations.get("expected_refs")
    if expected_refs:
        found_refs = {o.get("standard_ref") for o in observations}
        for ref in expected_refs:
            passed = ref in found_refs
            results.append({
                "check": f"expected_ref:{ref}",
                "passed": passed,
                "detail": f"{'found' if passed else 'NOT found'} in observations",
            })

    return results
