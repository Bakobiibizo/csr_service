"""Evaluation harness for CSR Service.

Usage:
    python -m eval.runner --cases eval/cases --backend ollama
"""

import argparse
import json
import sys
import time
from pathlib import Path

import httpx

from eval.checker import check_repeatability, compute_latency_stats, validate_schema

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
            return {
                "_status_code": resp.status_code,
                "_error": resp.text,
                "_latency_ms": latency_ms,
            }
    except Exception as e:
        return {"_error": str(e), "_latency_ms": int((time.time() - start) * 1000)}


def evaluate_case(base_url: str, token: str, case: dict, n: int) -> tuple[dict, list[int]]:
    case_id = case.get("id", "unknown")
    case_desc = case.get("description", "")
    expect_error = case.get("expect_error", False)
    print(f"\n[{case_id}] {case_desc}")

    latencies = []
    runs = []
    for _ in range(n):
        result = run_case(base_url, token, case)
        runs.append(result)
        if "_error" not in result or "_status_code" in result:
            latencies.append(result.get("_latency_ms", 0))

    first = runs[0]
    if "_status_code" in first:
        if expect_error:
            print(f"  PASS (expected error, got status {first['_status_code']})")
        else:
            print(f"  FAIL (HTTP {first['_status_code']}): {first.get('_error', '')[:100]}")
        return {"case_id": case_id, "pass": expect_error}, latencies

    if "_error" in first and "_status_code" not in first:
        print(f"  FAIL (connection error): {first['_error'][:100]}")
        return {"case_id": case_id, "pass": False}, latencies

    schema_ok, schema_err = validate_schema(first)
    if not schema_ok:
        print(f"  SCHEMA FAIL: {schema_err[:100]}")
        return {"case_id": case_id, "pass": False}, latencies

    repeatability = check_repeatability(runs)
    obs_counts = [len(r.get("observations", [])) for r in runs]

    print("  Schema: PASS")
    print(f"  Observations: {obs_counts[0]} (range: {min(obs_counts)}-{max(obs_counts)})")
    print(f"  Span stability: {repeatability['span_stability']:.0%}")
    print(f"  Severity stability: {repeatability['severity_stability']:.0%}")
    print(f"  Latency: {runs[0].get('_latency_ms', 0)}ms")

    return {"case_id": case_id, "pass": True, "repeatability": repeatability}, latencies


def main():
    parser = argparse.ArgumentParser(description="CSR Evaluation Harness")
    parser.add_argument("--cases", default="eval/cases", help="Directory with test cases")
    parser.add_argument("--backend", default="ollama", help="Backend name (for display)")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Service base URL")
    parser.add_argument("--token", default=DEFAULT_TOKEN, help="Auth token")
    parser.add_argument("-n", type=int, default=5, help="Repeat count for stability check")
    args = parser.parse_args()

    cases = load_cases(args.cases)
    if not cases:
        print(f"No cases found in {args.cases}")
        sys.exit(1)

    print(f"CSR Evaluation Harness - Backend: {args.backend}")
    print(f"Cases: {len(cases)}, Repeats: {args.n}")
    print("=" * 60)

    all_latencies: list[int] = []
    results = []

    for case in cases:
        result, latencies = evaluate_case(args.base_url, args.token, case, args.n)
        results.append(result)
        all_latencies.extend(latencies)

    print("\n" + "=" * 60)
    latency_stats = compute_latency_stats(all_latencies)
    passed = sum(1 for r in results if r["pass"])
    print(f"Results: {passed}/{len(results)} passed")
    print(f"Latency: mean={latency_stats['mean_ms']}ms, p95={latency_stats['p95_ms']}ms")


if __name__ == "__main__":
    main()
