"""Evaluation harness for CSR Service.

Usage:
    python -m eval.runner --cases eval/cases --backend ollama
    python -m eval.runner --cases eval/cases -n 5 --json-output eval/results/results.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

from eval.checker import (
    check_expectations,
    check_repeatability,
    compute_latency_stats,
    validate_schema,
)
from src.csr_service.logging import logger, setup_logging

DEFAULT_BASE_URL = "http://localhost:9020"
DEFAULT_TOKEN = "demo-token"


def load_cases(cases_dir: str) -> list[dict]:
    path = Path(cases_dir)
    cases = []
    for f in sorted(path.glob("*.json")):
        cases.append(json.loads(f.read_text()))
    return cases


def run_case(base_url: str, token: str, case: dict) -> dict:
    request_body = case.get("request", {})
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    start = time.time()
    try:
        resp = httpx.post(
            f"{base_url}/v1/review",
            json=request_body,
            headers=headers,
            timeout=60.0,
        )
        latency_ms = int((time.time() - start) * 1000)

        if resp.status_code == 200:
            data = resp.json()
            data["_latency_ms"] = latency_ms
            return data
        else:
            error_body = resp.text
            try:
                error_json = resp.json()
                error_body = json.dumps(error_json)
            except Exception:
                pass
            return {
                "_status_code": resp.status_code,
                "_error": error_body,
                "_latency_ms": latency_ms,
            }
    except Exception as e:
        return {"_error": str(e), "_latency_ms": int((time.time() - start) * 1000)}


def evaluate_case(base_url: str, token: str, case: dict, n: int) -> tuple[dict, list[int]]:
    case_id = case.get("id", "unknown")
    case_desc = case.get("description", "")
    expect_error = case.get("expect_error", False)
    expectations = case.get("expectations", {})
    logger.info("\n[%s] %s", case_id, case_desc)

    latencies: list[int] = []
    runs = []
    for _ in range(n):
        result = run_case(base_url, token, case)
        runs.append(result)
        latencies.append(result.get("_latency_ms", 0))

    first = runs[0]
    case_latency = compute_latency_stats(latencies)
    case_result = {
        "case_id": case_id,
        "description": case_desc,
        "latency": case_latency,
    }

    # Error case handling
    if "_status_code" in first:
        if expect_error:
            logger.info("  Expected error: PASS (HTTP %s)", first["_status_code"])
            exp_results = check_expectations(first, expectations, expect_error=True)
            case_result["pass"] = True
            case_result["expectation_results"] = exp_results
            _print_expectations(exp_results)
        else:
            logger.error("  FAIL (HTTP %s): %s", first["_status_code"], first.get("_error", "")[:100])
            case_result["pass"] = False
            case_result["expectation_results"] = []
        _print_latency(case_latency)
        return case_result, latencies

    if "_error" in first and "_status_code" not in first:
        logger.error("  FAIL (connection error): %s", first["_error"][:100])
        case_result["pass"] = False
        case_result["expectation_results"] = []
        return case_result, latencies

    # Schema validation
    schema_ok, schema_err = validate_schema(first)
    if not schema_ok:
        logger.error("  Schema: FAIL - %s", schema_err[:100])
        case_result["pass"] = False
        case_result["expectation_results"] = []
        return case_result, latencies

    # Repeatability
    repeatability = check_repeatability(runs)
    obs_counts = [len(r.get("observations", [])) for r in runs]

    logger.info("  Schema: PASS")
    logger.info(
        "  Observations: %s (range: %s-%s across %s runs)",
        obs_counts[0],
        min(obs_counts),
        max(obs_counts),
        n,
    )
    logger.info(
        "  Span stability: %.0f%%  |  Severity stability: %.0f%%",
        repeatability["span_stability"] * 100,
        repeatability["severity_stability"] * 100,
    )
    _print_latency(case_latency)

    # Expectations
    exp_results = check_expectations(first, expectations, expect_error=False)
    _print_expectations(exp_results)

    all_passed = all(r["passed"] for r in exp_results) if exp_results else True
    case_result["pass"] = all_passed
    case_result["repeatability"] = repeatability
    case_result["observation_counts"] = obs_counts
    case_result["expectation_results"] = exp_results

    return case_result, latencies


def _print_latency(latency: dict) -> None:
    logger.info("  Latency: mean=%sms, p95=%sms", latency["mean_ms"], latency["p95_ms"])


def _print_expectations(exp_results: list[dict]) -> None:
    if not exp_results:
        return
    logger.info("  Expectations:")
    for r in exp_results:
        status = "PASS" if r["passed"] else "FAIL"
        logger.info("    %s: %s (%s)", r["check"], status, r["detail"])


def main():
    parser = argparse.ArgumentParser(description="CSR Evaluation Harness")
    parser.add_argument("--cases", default="eval/cases", help="Directory with test cases")
    parser.add_argument("--backend", default="ollama", help="Backend name (for display)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Service base URL")
    parser.add_argument("--token", default=DEFAULT_TOKEN, help="Auth token")
    parser.add_argument("-n", type=int, default=5, help="Repeat count for stability check")
    parser.add_argument("--json-output", type=str, default=None, help="Path to save JSON results")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if not cases:
        logger.error("No cases found in %s", args.cases)
        sys.exit(1)

    logger.info("CSR Evaluation Harness - Backend: %s", args.backend)
    logger.info("Cases: %s, Repeats: %s", len(cases), args.n)
    logger.info("%s", "=" * 60)

    all_latencies: list[int] = []
    results = []

    for case in cases:
        result, case_latencies = evaluate_case(args.base_url, args.token, case, args.n)
        results.append(result)
        if case_latencies:
            all_latencies.extend(case_latencies)

    logger.info("\n%s", "=" * 60)
    passed = sum(1 for r in results if r.get("pass"))
    total_expectations = sum(len(r.get("expectation_results", [])) for r in results)
    expectations_passed = sum(
        sum(1 for e in r.get("expectation_results", []) if e["passed"]) for r in results
    )
    overall_latency = compute_latency_stats(all_latencies)

    logger.info("Results: %s/%s cases passed", passed, len(results))
    if total_expectations > 0:
        logger.info("Expectations: %s/%s checks passed", expectations_passed, total_expectations)
    logger.info(
        "Latency (overall): mean=%sms, p95=%sms",
        overall_latency["mean_ms"],
        overall_latency["p95_ms"],
    )

    if args.json_output:
        output_path = Path(args.json_output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_data = {
            "backend": args.backend,
            "repeats": args.n,
            "cases_passed": passed,
            "cases_total": len(results),
            "expectations_passed": expectations_passed,
            "expectations_total": total_expectations,
            "overall_latency": overall_latency,
            "results": results,
        }
        output_path.write_text(json.dumps(output_data, indent=2))
        logger.info("\nResults saved to: %s", args.json_output)

        # Auto-generate visualizations
        try:
            from eval.visualize import generate_all

            generate_all(str(output_path))
            logger.info("Visualizations generated in: %s", str(output_path.parent))
        except ImportError:
            logger.info("(matplotlib not available, skipping visualizations)")
        except Exception as e:
            logger.error("(visualization error: %s)", e)


if __name__ == "__main__":
    setup_logging()
    main()
