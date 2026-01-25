# Run 2: After H1 Intervention

**Date**: 2026-01-25
**Model**: qwen2.5:7b-instruct
**Repeats**: 3 per case


## Configuration

```yaml
# .env
CSR_MODEL_ID=qwen2.5:7b-instruct
CSR_OLLAMA_BASE_URL=http://localhost:11434/v1
```

```yaml
# config/prompts.yaml (system prompt excerpt)
Rules for observations:
- Do not invent issues that are not evidenced in the text. Every observation must cite specific content that triggers the rule.
- You MUST evaluate each provided rule against the content individually. Do not skip rules.
- An empty observations list is only appropriate when you have checked every provided rule and none are violated.

# config/prompts.yaml (user prompt excerpt)
Evaluate the content against EACH rule listed above, one rule at a time:
1. For each rule, identify whether the content violates that specific rule.
2. If violated, locate the specific text span that triggers the violation and report it as an observation.
3. If a rule is satisfied by the content, move to the next rule without reporting it.
```

## Results

| Case | Pass | Observations | Latency | Stability (span/sev) | Notes |
|------|------|--------------|---------|---------------------|-------|
| case_01 | PASS | 2-4 | 16.8s | 50% / 0% | Within 0-3 expected |
| case_02 | **PASS** | 3-5 | 20.8s | 0% / 100% | All checks pass, NAV-TR-3.1.1 found |
| case_03 | FAIL | 4-5 | 23.7s | 12% / 62% | NAV-TR-3.3.1 not in observations |
| case_04 | FAIL | 3-7 | 28.7s | 0% / 83% | Over-count (7 > max 6) |
| case_05 | FAIL | 5 | 25.9s | 0% / 57% | Missing severity "warning" |
| case_06 | FAIL | - | timeout | - | Connection error |
| case_07 | PASS | N/A | 7ms | - | Error case |
| case_08 | PASS | N/A | 5ms | - | Error case |

**Pass rate**: 4/8 cases
**Expectations**: 13/16 checks passed (excluding timeout)
**Mean latency**: 22.2s

## Detailed expectation results

### case_01 (clean content)
- observation_count: PASS (2, expected 0-3)

### case_02 (missing measurable verbs)
- observation_count: PASS (5, expected 2-8)
- expected_severity:violation: PASS
- expected_severity:warning: PASS
- expected_ref:NAV-TR-3.1.1: PASS

### case_03 (unexplained acronyms)
- observation_count: PASS (5, expected 2-10)
- expected_severity:warning: PASS
- expected_ref:NAV-TR-3.3.1: **FAIL** — not found in observations

### case_04 (internal contradictions)
- observation_count: **FAIL** (7, expected 1-6)
- expected_severity:violation: PASS
- expected_ref:NAV-TR-3.2.2: PASS

### case_05 (structure problems)
- observation_count: PASS (5, expected 2-8)
- expected_severity:warning: **FAIL** — not found
- expected_ref:NAV-TR-3.4.1: PASS

### case_06 (ambiguous multi-rule)
- **TIMEOUT** — connection error during eval

### case_07/08 (error cases)
- PASS — correct HTTP 422 responses

## Comparison to Run 1

| Case | Run 1 Obs | Run 2 Obs | Delta | Status |
|------|-----------|-----------|-------|--------|
| case_01 | 0 | 2-4 | +2-4 | borderline FPs |
| case_02 | 0 | 3-5 | +3-5 | **FIXED** |
| case_03 | 0 | 4-5 | +4-5 | partial (wrong ref) |
| case_04 | 0 | 3-7 | +3-7 | partial (over-count) |
| case_05 | 0 | 5 | +5 | partial (wrong severity) |
| case_06 | 0 | - | - | timeout |

## Conclusion

**Hypothesis H1 is SUPPORTED.**

The forced per-standard traversal prompt change eliminated the "silent compliance" failure mode. The model went from generating **zero observations** to generating **3-7 observations per case** with correct standard references.

### What worked
- Model now actively checks each rule
- Correct violations identified (NAV-TR-3.1.1, NAV-TR-3.2.2, NAV-TR-3.4.1)
- Observation counts in expected ranges for most cases

### Remaining issues
- **case_03**: NAV-TR-3.3.1 not surfaced — likely retrieval issue (H2)
- **case_04**: Over-generating (7 vs max 6) — may need stricter threshold
- **case_05**: Wrong severity class — model using "violation" instead of "warning"
- **Stability**: Span stability is low (0-50%) — observations vary across runs

## Files

- Results: `modified_results_7b.json`
- Prompts: `modified_prompts.yaml`
