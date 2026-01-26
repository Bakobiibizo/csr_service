"""Contrastive experiment runner for hypothesis testing.

Compares baseline vs. modified pipeline results and reports deltas.
Can also orchestrate full experiment runs (start service, run eval, compare).

Usage:
    # Compare two existing result files
    python -m eval.experiment_runner compare \
        --baseline eval/experiments/h1_forced_traversal/baseline_results.json \
        --modified eval/experiments/h1_forced_traversal/modified_results.json \
        --output eval/experiments/h1_forced_traversal/comparison.json

    # Run full experiment (swap config, run evals, compare)
    python -m eval.experiment_runner run \
        --experiment-dir eval/experiments/h1_forced_traversal \
        --base-url http://localhost:9020 \
        --token demo-token \
        -n 5
"""

import argparse
import json
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

from src.csr_service.logging import logger, setup_logging


def load_results(path: str) -> dict:
    with open(path) as f:
        return json.load(f)


def compute_case_delta(baseline_case: dict, modified_case: dict) -> dict:
    """Compute delta metrics between baseline and modified results for a single case."""
    case_id = baseline_case.get("case_id", "unknown")

    baseline_obs = baseline_case.get("observation_counts", [0])
    modified_obs = modified_case.get("observation_counts", [0])

    baseline_count = baseline_obs[0] if baseline_obs else 0
    modified_count = modified_obs[0] if modified_obs else 0

    baseline_latency = baseline_case.get("latency", {}).get("mean_ms", 0)
    modified_latency = modified_case.get("latency", {}).get("mean_ms", 0)

    baseline_pass = baseline_case.get("pass", False)
    modified_pass = modified_case.get("pass", False)

    # Extract expectation details
    baseline_exp = {e["check"]: e["passed"] for e in baseline_case.get("expectation_results", [])}
    modified_exp = {e["check"]: e["passed"] for e in modified_case.get("expectation_results", [])}

    # Stability
    baseline_stability = baseline_case.get("repeatability", {})
    modified_stability = modified_case.get("repeatability", {})

    return {
        "case_id": case_id,
        "description": baseline_case.get("description", ""),
        "pass": {
            "baseline": baseline_pass,
            "modified": modified_pass,
            "changed": baseline_pass != modified_pass,
            "direction": "improved"
            if modified_pass and not baseline_pass
            else "regressed"
            if baseline_pass and not modified_pass
            else "unchanged",
        },
        "observation_count": {
            "baseline": baseline_count,
            "modified": modified_count,
            "delta": modified_count - baseline_count,
        },
        "latency_mean_ms": {
            "baseline": baseline_latency,
            "modified": modified_latency,
            "delta": modified_latency - baseline_latency,
        },
        "expectations": {
            "baseline": baseline_exp,
            "modified": modified_exp,
            "flipped": {
                k: {"baseline": baseline_exp.get(k), "modified": modified_exp.get(k)}
                for k in set(list(baseline_exp.keys()) + list(modified_exp.keys()))
                if baseline_exp.get(k) != modified_exp.get(k)
            },
        },
        "stability": {
            "baseline_span": baseline_stability.get("span_stability"),
            "modified_span": modified_stability.get("span_stability"),
            "baseline_severity": baseline_stability.get("severity_stability"),
            "modified_severity": modified_stability.get("severity_stability"),
        },
    }


def compare_results(baseline: dict, modified: dict) -> dict:
    """Compare full baseline vs. modified result sets."""
    baseline_cases = {r["case_id"]: r for r in baseline.get("results", [])}
    modified_cases = {r["case_id"]: r for r in modified.get("results", [])}

    case_ids = sorted(set(list(baseline_cases.keys()) + list(modified_cases.keys())))

    deltas = []
    for case_id in case_ids:
        if case_id in baseline_cases and case_id in modified_cases:
            deltas.append(compute_case_delta(baseline_cases[case_id], modified_cases[case_id]))

    # Summary
    improved = sum(1 for d in deltas if d["pass"]["direction"] == "improved")
    regressed = sum(1 for d in deltas if d["pass"]["direction"] == "regressed")
    unchanged = sum(1 for d in deltas if d["pass"]["direction"] == "unchanged")

    total_obs_delta = sum(d["observation_count"]["delta"] for d in deltas)
    total_latency_delta = sum(d["latency_mean_ms"]["delta"] for d in deltas)

    return {
        "summary": {
            "cases_compared": len(deltas),
            "improved": improved,
            "regressed": regressed,
            "unchanged": unchanged,
            "total_observation_delta": total_obs_delta,
            "total_latency_delta_ms": total_latency_delta,
            "baseline_pass_rate": f"{baseline.get('cases_passed', 0)}/{baseline.get('cases_total', 0)}",
            "modified_pass_rate": f"{modified.get('cases_passed', 0)}/{modified.get('cases_total', 0)}",
        },
        "deltas": deltas,
    }


def print_comparison(comparison: dict) -> None:
    """Print a human-readable comparison report."""
    summary = comparison["summary"]

    logger.info("%s", "=" * 70)
    logger.info("EXPERIMENT COMPARISON REPORT")
    logger.info("%s", "=" * 70)
    logger.info("")
    logger.info("Cases compared: %s", summary["cases_compared"])
    logger.info(
        "Pass rate: %s (baseline) -> %s (modified)",
        summary["baseline_pass_rate"],
        summary["modified_pass_rate"],
    )
    logger.info(
        "Improved: %s  |  Regressed: %s  |  Unchanged: %s",
        summary["improved"],
        summary["regressed"],
        summary["unchanged"],
    )
    logger.info("Total observation delta: %+d", summary["total_observation_delta"])
    logger.info("Total latency delta: %+dms", summary["total_latency_delta_ms"])
    logger.info("")
    logger.info("%s", "-" * 70)
    logger.info("%s", f"{'Case':<12} {'Pass':<22} {'Obs (B->M)':<16} {'Latency (B->M)':<20}")
    logger.info("%s", "-" * 70)

    for delta in comparison["deltas"]:
        case_id = delta["case_id"]
        pass_info = delta["pass"]
        obs = delta["observation_count"]
        lat = delta["latency_mean_ms"]

        pass_str = f"{pass_info['baseline']}->{pass_info['modified']}"
        if pass_info["changed"]:
            pass_str += f" ({pass_info['direction'][:3].upper()})"

        obs_str = f"{obs['baseline']}->{obs['modified']} ({obs['delta']:+d})"
        lat_str = f"{lat['baseline']}->{lat['modified']}ms ({lat['delta']:+d})"

        logger.info("%s", f"{case_id:<12} {pass_str:<22} {obs_str:<16} {lat_str:<20}")

    logger.info("%s", "-" * 70)
    logger.info("")

    # Detail on flipped expectations
    flipped_cases = [d for d in comparison["deltas"] if d["expectations"]["flipped"]]
    if flipped_cases:
        logger.info("EXPECTATION CHANGES:")
        for delta in flipped_cases:
            logger.info("  %s:", delta["case_id"])
            for check, vals in delta["expectations"]["flipped"].items():
                direction = "PASS" if vals["modified"] else "FAIL"
                logger.info(
                    "    %s: %s -> %s (%s)",
                    check,
                    vals["baseline"],
                    vals["modified"],
                    direction,
                )
        logger.info("")


def run_eval(base_url: str, token: str, cases_dir: str, n: int, output_path: str) -> dict:
    """Run the eval harness and return results."""
    cmd = [
        str(sys.executable),
        "-m",
        "eval.runner",
        "--cases",
        str(Path(cases_dir)),
        "--base-url",
        str(base_url),
        "--token",
        str(token),
        "-n",
        str(n),
        "--json-output",
        str(output_path),
    ]
    cmd_display = " ".join(shlex.quote(arg) for arg in cmd)
    logger.info("  Running: %s", cmd_display)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
        check=False,
        shell=False,
    )
    logger.info("%s", result.stdout)
    if result.returncode != 0:
        logger.error("  STDERR: %s", result.stderr)
        sys.exit(1)

    with open(output_path) as f:
        return json.load(f)


def run_experiment(args):
    """Run a full experiment: baseline eval, swap config, modified eval, compare."""
    experiment_dir = Path(args.experiment_dir)
    baseline_prompts = experiment_dir / "baseline_prompts.yaml"
    modified_prompts = experiment_dir / "modified_prompts.yaml"
    config_path = Path("config/prompts.yaml")

    if not baseline_prompts.exists():
        logger.error("ERROR: %s not found", baseline_prompts)
        sys.exit(1)
    if not modified_prompts.exists():
        logger.error("ERROR: %s not found", modified_prompts)
        sys.exit(1)

    baseline_output = str(experiment_dir / "baseline_results.json")
    modified_output = str(experiment_dir / "modified_results.json")
    comparison_output = str(experiment_dir / "comparison.json")

    # Phase 1: Baseline
    logger.info("\n[PHASE 1] Running baseline evaluation...")
    logger.info("  Config: %s", baseline_prompts)
    shutil.copy2(str(baseline_prompts), str(config_path))
    logger.info("  NOTE: Service must be restarted to pick up config change.")
    logger.info("  Waiting %ss for service restart...", args.restart_delay)
    time.sleep(args.restart_delay)

    baseline = run_eval(args.base_url, args.token, args.cases, args.n, baseline_output)

    # Phase 2: Modified
    logger.info("\n[PHASE 2] Running modified evaluation...")
    logger.info("  Config: %s", modified_prompts)
    shutil.copy2(str(modified_prompts), str(config_path))
    logger.info("  NOTE: Service must be restarted to pick up config change.")
    logger.info("  Waiting %ss for service restart...", args.restart_delay)
    time.sleep(args.restart_delay)

    modified = run_eval(args.base_url, args.token, args.cases, args.n, modified_output)

    # Phase 3: Compare
    logger.info("\n[PHASE 3] Comparing results...")
    comparison = compare_results(baseline, modified)
    print_comparison(comparison)

    with open(comparison_output, "w") as f:
        json.dump(comparison, f, indent=2)
    logger.info("Comparison saved to: %s", comparison_output)

    # Restore modified config (the intervention we want to keep)
    shutil.copy2(str(modified_prompts), str(config_path))


def compare_command(args):
    """Compare two existing result files."""
    baseline = load_results(args.baseline)
    modified = load_results(args.modified)

    comparison = compare_results(baseline, modified)
    print_comparison(comparison)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(comparison, f, indent=2)
        logger.info("Comparison saved to: %s", args.output)


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="CSR Experiment Runner")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Compare command
    compare_parser = subparsers.add_parser("compare", help="Compare two result files")
    compare_parser.add_argument("--baseline", required=True, help="Baseline results JSON")
    compare_parser.add_argument("--modified", required=True, help="Modified results JSON")
    compare_parser.add_argument("--output", help="Output comparison JSON")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run full experiment")
    run_parser.add_argument("--experiment-dir", required=True, help="Experiment directory")
    run_parser.add_argument("--base-url", default="http://localhost:9020", help="Service URL")
    run_parser.add_argument("--token", default="demo-token", help="Auth token")
    run_parser.add_argument("--cases", default="eval/cases", help="Test cases directory")
    run_parser.add_argument("-n", type=int, default=5, help="Repeats per case")
    run_parser.add_argument(
        "--restart-delay",
        type=int,
        default=5,
        help="Seconds to wait after config swap for service restart",
    )

    args = parser.parse_args()

    if args.command == "compare":
        compare_command(args)
    elif args.command == "run":
        run_experiment(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
