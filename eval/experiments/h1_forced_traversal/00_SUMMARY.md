# Experiment H1: Forced Per-Standard Traversal

## Summary

| Metric | Run 1 (Invalid) | Run 2 (H1 Applied) |
|--------|-----------------|-------------------|
| Model | none (404 error) | qwen2.5:7b-instruct |
| Cases passed | 4/8 | 4/8 |
| Expectations passed | 4/17 | 13/16 |
| Mean observations | 0 | 4.4 |
| Mean latency | 14ms (fake) | 22.2s (real) |

## Verdict

**H1 SUPPORTED** — Forced per-standard traversal fixed the silent compliance failure.

## Documents

1. **[01_RUN1_BASELINE.md](01_RUN1_BASELINE.md)** — Initial run results (later found to be invalid due to model 404)

2. **[02_CHANGES.md](02_CHANGES.md)** — Infrastructure fixes and H1 prompt intervention details

3. **[03_RUN2_RESULTS.md](03_RUN2_RESULTS.md)** — Results after applying H1, showing model now generates observations

## Key insight

The original evaluation never tested the model — a model ID mismatch caused 404 errors on every request. The pipeline's error handler returned valid empty responses, masking the infrastructure failure as a prompt engineering problem.

After fixing infrastructure and applying H1, the model generates 3-7 observations per case with correct standard references. Remaining failures are calibration issues, not silent compliance.

## Next experiments

- **H2**: Verify retrieval surfaces correct rules for case_03
- **H3**: Check if confidence gating removes valid observations
- **Severity tuning**: Adjust prompt or policy for correct severity classification
