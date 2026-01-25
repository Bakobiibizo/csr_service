# Run 1: Initial Baseline

**Date**: 2026-01-24
**Model**: qwen2.5:32b (configured), none (actual)
**Repeats**: 5 per case


## Configuration

```yaml
# .env
CSR_MODEL_ID=qwen2.5:32b
CSR_OLLAMA_BASE_URL=http://localhost:11434/v1
```

```yaml
# config/prompts.yaml (system prompt excerpt)
Rules for observations:
- Only report genuine issues. Do not fabricate problems.
- If the content fully complies with all provided rules, return {"observations": []}

# config/prompts.yaml (user prompt excerpt)
Review the content above against the provided standards rules. Return your observations as JSON.
```

## Results

| Case | Pass | Observations | Latency | Notes |
|------|------|--------------|---------|-------|
| case_01 | PASS | 0 | 20ms | Clean content |
| case_02 | FAIL | 0 | 7ms | Expected 2-8 |
| case_03 | FAIL | 0 | 24ms | Expected 2-10 |
| case_04 | FAIL | 0 | 7ms | Expected 1-6 |
| case_05 | FAIL | 0 | 16ms | Expected 2-8 |
| case_06 | PASS | 0 | 7ms | Within 0-5 |
| case_07 | PASS | N/A | 3ms | Error case |
| case_08 | PASS | N/A | 3ms | Error case |

**Pass rate**: 4/8 cases
**Expectations**: 4/17 checks passed
**Mean latency**: 14ms

## Observations

1. All content cases return exactly 0 observations
2. Latencies are suspiciously fast (7-24ms) for LLM inference
3. Cases 02-05 fail because no violations detected despite obvious issues in content

## Interpretation at the time

Assumed the model was concluding "no issues" due to passive prompt framing. Formed hypothesis H1: forced per-standard traversal would fix the silent compliance behavior.

## Post-hoc finding

**These results are invalid.** Investigation revealed:

```
Error code: 404 - model 'qwen2.5:32b' not found
```

The configured model ID (`qwen2.5:32b`) did not match the Ollama model name (`qwen2.5:32b-instruct`). Every request hit a 404, the pipeline's error handler returned `{"observations": []}`, and the eval harness recorded this as "model found no issues."

The 7-24ms latencies were HTTP round-trip + error handling, not model inference.

## Files

- Results: `baseline_results.json`
- Prompts: `baseline_prompts.yaml`
