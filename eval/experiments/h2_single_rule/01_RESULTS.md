# H2 Results: Single-Rule Evaluation

**Date**: 2026-01-25
**Model**: qwen2.5:7b-instruct
**Mode**: Single-rule, parallel execution
**Repeats**: 3 per case

## Configuration

```yaml
# .env
CSR_SINGLE_RULE_MODE=true
CSR_SINGLE_RULE_PARALLEL=true
CSR_MODEL_ID=qwen2.5:7b-instruct
```

## Results

| Case | Pass | Observations | Latency | Stability | Notes |
|------|------|--------------|---------|-----------|-------|
| case_01 | FAIL | 5-6 | 32.5s | 70%/100% | Over-count (expected 0-3) |
| case_02 | partial | 5-6 | 29.3s | 67%/100% | NAV-TR-3.1.1 found, missing "warning" |
| case_03 | partial | 12-15 | 51.1s | 60%/100% | **NAV-TR-3.3.1 found**, over-count |
| case_04 | partial | 9 | 44.0s | 22%/100% | NAV-TR-3.2.2 found, over-count |
| case_05 | partial | 5 | 28.0s | 25%/100% | NAV-TR-3.4.1 found, missing "warning" |
| case_06 | **PASS** | 2-3 | 13.5s | 0%/100% | **No longer times out** |
| case_07 | PASS | N/A | 6ms | - | Error case |
| case_08 | PASS | N/A | 6ms | - | Error case |

**Pass rate**: 3/8 cases
**Expectations**: 11/17 checks passed
**Mean latency**: 24.8s

## Comparison to H1 (Multi-Rule)

| Metric | H1 (Multi-Rule) | H2 (Single-Rule) | Delta |
|--------|-----------------|------------------|-------|
| Cases passed | 4/8 | 3/8 | -1 |
| Expectations passed | 13/16 | 11/17 | -2 |
| NAV-TR-3.3.1 found | No | **Yes** | Improved |
| case_06 | timeout | PASS | Improved |
| case_01 | PASS | FAIL | Regressed |
| Mean latency | 22.2s | 24.8s | +2.6s |
| Severity stability | 0-100% | 100% | Improved |

## Findings

### Improvements

1. **Better rule coverage**: NAV-TR-3.3.1 (acronym rule) now correctly identified in case_03
2. **No timeouts**: case_06 completes successfully
3. **Consistent severity**: 100% severity stability (always uses same severity class per rule)

### Regressions

1. **Over-detection**: Generates too many observations
   - case_01: 5-6 vs expected 0-3 (false positives on clean content)
   - case_03: 12-15 vs expected 2-10
   - case_04: 9 vs expected 1-6

2. **Missing severity class**: "warning" not found in most cases (model defaults to "violation")

3. **No latency improvement**: Parallel execution doesn't help because Ollama serializes requests (single GPU)

## Hypothesis Assessment

**H2 is PARTIALLY SUPPORTED.**

Single-rule evaluation improves rule focus (finds NAV-TR-3.3.1, no timeouts), but causes over-detection. The model evaluates each rule in isolation and finds more potential issues, leading to false positives.

## Recommendations

1. **Tighten confidence threshold**: Increase `min_confidence` from 0.55 to 0.7 to filter weak observations
2. **Add severity guidance**: Modify single-rule prompt to clarify when to use "warning" vs "violation"
3. **Post-processing**: Add deduplication for similar observations across rules
4. **Hybrid approach**: Use single-rule for specific problematic rules (like NAV-TR-3.3.1), multi-rule for others
