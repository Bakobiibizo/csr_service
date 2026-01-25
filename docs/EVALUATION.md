# Evaluation Framework

## Overview

The CSR Service evaluation framework validates the AI-powered content review pipeline across four dimensions:

1. **Schema correctness** — Responses conform to the `ReviewResponse` Pydantic model
2. **Repeatability/stability** — Repeated runs produce consistent observations (span and severity stability)
3. **Latency** — Response times are tracked per case and overall (mean, min, max, p95)
4. **Semantic correctness** — Observations match expected counts, severities, and standard references

## Prerequisites

- CSR Service running (default: `http://localhost:9020`)
- LLM backend loaded (e.g., `qwen2.5:32b` via Ollama)
- Python dev dependencies installed: `uv pip install -e ".[dev]"`

## Running

```bash
# Quick smoke test (1 run per case)
uv run python -m eval.runner --cases eval/cases -n 1

# Full evaluation (5 runs per case, save JSON results)
uv run python -m eval.runner \
  --cases eval/cases \
  --backend ollama \
  --base-url http://localhost:9020 \
  --token demo-token \
  -n 5 \
  --json-output eval/results/results.json
```

### CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--cases` | `eval/cases` | Directory containing test case JSON files |
| `--backend` | `ollama` | Backend name (for display only) |
| `--base-url` | `http://localhost:9020` | Service base URL |
| `--token` | `demo-token` | Authorization bearer token |
| `-n` | `5` | Number of repeated runs per case (for stability) |
| `--json-output` | (none) | Path to save full results JSON |

When `--json-output` is specified, visualizations are automatically generated in the same directory.

## Test Case Format

Each test case is a JSON file in `eval/cases/`:

```json
{
  "id": "case_02",
  "description": "Missing measurable verbs in objectives - should flag violations",
  "expect_error": false,
  "expectations": {
    "min_obs": 2,
    "max_obs": 8,
    "expected_severities": ["violation", "warning"],
    "expected_refs": ["NAV-TR-3.1.1"],
    "expected_error_code": null
  },
  "request": {
    "content": "...",
    "standards_set": "naval_v3",
    "strictness": "medium"
  }
}
```

### Expectations Fields

| Field | Type | Description |
|-------|------|-------------|
| `min_obs` | `int\|null` | Minimum expected observation count |
| `max_obs` | `int\|null` | Maximum expected observation count |
| `expected_severities` | `list[str]\|null` | Severities that must appear in observations |
| `expected_refs` | `list[str]\|null` | Standard refs that must appear in observations |
| `expected_error_code` | `str\|null` | Error code expected in 4xx response body |

For error cases (`expect_error: true`), set `min_obs`, `max_obs`, `expected_severities`, and `expected_refs` to `null`.

## Checks Performed

| Check | Applies To | Criterion |
|-------|-----------|-----------|
| Schema validation | Success cases | Response parses as `ReviewResponse` |
| Span stability | Success cases (n>1) | Same `span` for matching `standard_ref` across runs |
| Severity stability | Success cases (n>1) | Same `severity` for matching `standard_ref` across runs |
| Observation count | Success cases | `min_obs <= count <= max_obs` |
| Expected severities | Success cases | At least one observation has each listed severity |
| Expected refs | Success cases | At least one observation references each listed ref |
| Expected error code | Error cases | HTTP response body contains the error code string |

## Test Case Inventory

| Case | Description | Standards | Key Expectation |
|------|-------------|-----------|-----------------|
| `case_01` | Clean content | NAV-TR general | 0-3 observations (no violations) |
| `case_02` | Missing measurable verbs | NAV-TR-3.1.1 | 2-8 obs, violations + warnings |
| `case_03` | Unexplained acronyms | NAV-TR-3.3.1 | 2-10 obs, warnings |
| `case_04` | Internal contradictions | NAV-TR-3.2.2 | 1-6 obs, violations |
| `case_05` | Structure problems | NAV-TR-3.4.1 | 2-8 obs, warnings |
| `case_06` | Ambiguous multi-rule | Multiple | 0-5 obs (loose) |
| `case_07` | Empty content | N/A | HTTP 422, EMPTY_CONTENT |
| `case_08` | Invalid standards_set | N/A | HTTP 422, STANDARDS_NOT_FOUND |

## Interpreting Results

### Pass/Fail

A case **passes** when:
- Error cases: HTTP status is 4xx as expected, and error code matches (if specified)
- Success cases: Schema validates AND all expectation checks pass

### Stability Thresholds

- **100%**: Perfect consistency across runs (ideal for deterministic prompts)
- **80%+**: Acceptable for LLM-based analysis
- **<60%**: Indicates prompt or temperature issues

### Latency

- Sub-100ms typically indicates cached/short-circuit responses
- 500ms-5s is normal for LLM inference on content review
- >10s suggests model loading or queue backlog

## Adding New Cases

1. Create a new JSON file in `eval/cases/` following the naming convention: `case_NN_description.json`
2. Set the required fields:
   - `id`: Unique case identifier (e.g., `case_09`)
   - `description`: Human-readable description
   - `expect_error`: `true` for error cases, `false` for success cases
   - `request`: The review request body (`content`, `standards_set`, `strictness`)
3. Add `expectations`:
   - For success cases: Set `min_obs`, `max_obs`, `expected_severities`, `expected_refs`
   - For error cases: Set `expected_error_code`, nullify observation fields
4. Run the eval: `uv run python -m eval.runner --cases eval/cases -n 5 --json-output eval/results/results.json`
5. Review results and adjust expectation ranges if needed

## Results

### Latest Results (H1 + qwen2.5:7b-instruct)

After applying the H1 forced-traversal prompt intervention:

| Case | Pass | Observations | Latency (mean) | Notes |
|------|------|-------------|----------------|-------|
| case_01 | PASS | 2-4 | 16.8s | Within expected 0-3 |
| case_02 | **PASS** | 3-5 | 20.8s | NAV-TR-3.1.1 correctly identified |
| case_03 | partial | 4-5 | 23.7s | Count OK, wrong ref surfaced |
| case_04 | partial | 3-7 | 28.7s | Ref found, slight over-count |
| case_05 | partial | 5 | 25.9s | Ref found, missing severity |
| case_06 | timeout | - | - | Infrastructure issue |
| case_07 | PASS | N/A | 7ms | Error case |
| case_08 | PASS | N/A | 3ms | Error case |

**Pass rate**: 4/8 cases, **13/16 expectations passed**

### Historical Context

The original baseline (4/8 pass, 14ms latency) was **invalid** — a model ID mismatch caused 404 errors on every request. The pipeline's error handler returned empty observations, masking the infrastructure failure. See [eval/experiments/h1_forced_traversal/01_RUN1_BASELINE.md](../eval/experiments/h1_forced_traversal/01_RUN1_BASELINE.md) for details.

### Experiment Results

| Experiment | Pass Rate | Key Finding |
|------------|-----------|-------------|
| H1: Forced Traversal | 4/8, 13/16 exp | Fixed silent compliance, model now generates observations |
| H4: Single-Rule Mode | 3/8, 11/17 exp | Better rule coverage, but over-detection |

For full analysis, see:
- [RESEARCH_OVERVIEW.md](RESEARCH_OVERVIEW.md) — Methodology and recommendations
- [eval/experiments/](../eval/experiments/) — Detailed experiment documentation

### Visualizations

Generated in `eval/results/`:

- `latency_by_case.png` — Mean latency per case with p95 error bars
- `observation_counts.png` — Observation counts with expected range markers
- `stability.png` — Span/severity stability heatmap
- `pass_fail.png` — Expectation pass/fail grid per case

## Visualization

To regenerate charts from an existing results file:

```bash
uv run python -m eval.visualize eval/results/results.json
```

This produces four PNG files in the same directory as the results JSON:

1. **latency_by_case.png** — Bar chart with mean latency and p95 error bars
2. **observation_counts.png** — Bar chart with expected range overlay
3. **stability.png** — Red-to-green heatmap of span/severity stability
4. **pass_fail.png** — Grid showing P (pass), F (fail), or - (not applicable) per check
