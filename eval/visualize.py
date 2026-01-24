"""Visualization module for CSR evaluation results.

Generates PNG charts from the JSON results file:
- Latency bar chart (mean with p95 error bars)
- Observation count chart (with expected range markers)
- Stability heatmap (span/severity stability per case)
- Pass/fail summary grid

Usage:
    python -m eval.visualize eval/results/results.json
"""

import json
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def load_results(results_path: str) -> dict:
    return json.loads(Path(results_path).read_text())


def generate_latency_chart(data: dict, output_dir: Path) -> None:
    """Bar chart of mean latency per case with p95 error bars."""
    results = data["results"]
    case_ids = [r["case_id"] for r in results]
    means = [r["latency"]["mean_ms"] for r in results]
    p95s = [r["latency"]["p95_ms"] for r in results]
    errors = [p95 - mean for mean, p95 in zip(means, p95s)]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(case_ids, means, color="#4C9AFF", edgecolor="none")
    ax.errorbar(
        case_ids, means,
        yerr=[np.zeros(len(errors)), errors],
        fmt="none", ecolor="#FF6B6B", capsize=4, linewidth=1.5,
    )

    ax.set_xlabel("Case ID")
    ax.set_ylabel("Latency (ms)")
    ax.set_title("Response Latency by Case (mean + p95)")
    ax.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / "latency_by_case.png", dpi=150)
    plt.close()


def generate_observation_chart(data: dict, output_dir: Path) -> None:
    """Bar chart of observation counts with expected range markers."""
    results = [r for r in data["results"] if "observation_counts" in r]
    if not results:
        return

    case_ids = [r["case_id"] for r in results]
    obs_counts = [r["observation_counts"][0] for r in results]

    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(case_ids, obs_counts, color="#6BCB77", edgecolor="none")

    # Add expected range markers from expectation_results
    for i, r in enumerate(results):
        for exp in r.get("expectation_results", []):
            if exp["check"] == "observation_count":
                detail = exp["detail"]
                # Parse "N (expected min-max)"
                try:
                    parts = detail.split("expected ")
                    if len(parts) > 1:
                        range_str = parts[1].rstrip(")")
                        min_val, max_val = map(int, range_str.split("-"))
                        ax.plot(
                            [i, i], [min_val, max_val],
                            color="#FF6B6B", linewidth=2, marker="_", markersize=10,
                        )
                except (ValueError, IndexError):
                    pass

    ax.set_xlabel("Case ID")
    ax.set_ylabel("Observation Count")
    ax.set_title("Observations per Case (with expected range)")
    ax.tick_params(axis="x", rotation=45)
    plt.tight_layout()
    plt.savefig(output_dir / "observation_counts.png", dpi=150)
    plt.close()


def generate_stability_heatmap(data: dict, output_dir: Path) -> None:
    """Heatmap of span/severity stability per case."""
    results = [r for r in data["results"] if "repeatability" in r]
    if not results:
        return

    case_ids = [r["case_id"] for r in results]
    span_stab = [r["repeatability"]["span_stability"] for r in results]
    sev_stab = [r["repeatability"]["severity_stability"] for r in results]

    matrix = np.array([span_stab, sev_stab]).T

    fig, ax = plt.subplots(figsize=(6, max(4, len(case_ids) * 0.6)))
    im = ax.imshow(matrix, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")

    ax.set_xticks([0, 1])
    ax.set_xticklabels(["Span Stability", "Severity Stability"])
    ax.set_yticks(range(len(case_ids)))
    ax.set_yticklabels(case_ids)

    # Annotate cells
    for i in range(len(case_ids)):
        for j in range(2):
            val = matrix[i, j]
            color = "white" if val < 0.5 else "black"
            ax.text(j, i, f"{val:.0%}", ha="center", va="center", color=color, fontsize=10)

    ax.set_title("Stability Heatmap")
    plt.colorbar(im, ax=ax, label="Stability")
    plt.tight_layout()
    plt.savefig(output_dir / "stability.png", dpi=150)
    plt.close()


def generate_pass_fail_chart(data: dict, output_dir: Path) -> None:
    """Grid showing pass/fail for each check per case."""
    results = data["results"]
    case_ids = [r["case_id"] for r in results]

    # Collect all unique check names
    all_checks = []
    for r in results:
        for exp in r.get("expectation_results", []):
            if exp["check"] not in all_checks:
                all_checks.append(exp["check"])

    if not all_checks:
        return

    # Build matrix: 1=pass, 0=fail, -1=not applicable
    matrix = np.full((len(case_ids), len(all_checks)), -1.0)
    for i, r in enumerate(results):
        for exp in r.get("expectation_results", []):
            j = all_checks.index(exp["check"])
            matrix[i, j] = 1.0 if exp["passed"] else 0.0

    fig, ax = plt.subplots(figsize=(max(6, len(all_checks) * 1.2), max(4, len(case_ids) * 0.6)))

    # Custom colormap: grey (-1), red (0), green (1)
    from matplotlib.colors import ListedColormap
    cmap = ListedColormap(["#DDDDDD", "#FF6B6B", "#6BCB77"])
    bounds = [-1.5, -0.5, 0.5, 1.5]
    from matplotlib.colors import BoundaryNorm
    norm = BoundaryNorm(bounds, cmap.N)

    im = ax.imshow(matrix, cmap=cmap, norm=norm, aspect="auto")

    ax.set_xticks(range(len(all_checks)))
    ax.set_xticklabels(all_checks, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(case_ids)))
    ax.set_yticklabels(case_ids)

    # Annotate
    for i in range(len(case_ids)):
        for j in range(len(all_checks)):
            val = matrix[i, j]
            if val == 1.0:
                ax.text(j, i, "P", ha="center", va="center", fontsize=9, fontweight="bold")
            elif val == 0.0:
                ax.text(j, i, "F", ha="center", va="center", fontsize=9, fontweight="bold", color="white")
            else:
                ax.text(j, i, "-", ha="center", va="center", fontsize=9, color="#999999")

    ax.set_title("Expectation Pass/Fail by Case")
    plt.tight_layout()
    plt.savefig(output_dir / "pass_fail.png", dpi=150)
    plt.close()


def generate_all(results_path: str) -> None:
    """Generate all visualizations from results JSON."""
    data = load_results(results_path)
    output_dir = Path(results_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)

    generate_latency_chart(data, output_dir)
    generate_observation_chart(data, output_dir)
    generate_stability_heatmap(data, output_dir)
    generate_pass_fail_chart(data, output_dir)


def main():
    if len(sys.argv) < 2:
        print("Usage: python -m eval.visualize <results.json>")
        sys.exit(1)

    results_path = sys.argv[1]
    if not Path(results_path).exists():
        print(f"File not found: {results_path}")
        sys.exit(1)

    generate_all(results_path)
    output_dir = Path(results_path).parent
    print(f"Generated visualizations in: {output_dir}")
    for png in sorted(output_dir.glob("*.png")):
        print(f"  {png.name}")


if __name__ == "__main__":
    main()
