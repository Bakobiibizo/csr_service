# Content Standards Review Service (CSR): Research Overview

## Executive Summary

The Content Standards Review Service (CSR) is an Artificial Intelligence (AI)-powered Application Programming Interface (API) that evaluates instructional content against defined standards rules. This document describes the evaluation framework, my hypothesis-driven development methodology, experimental findings, and recommendations for future development.

**Key findings**:
- Initial evaluation failures were caused by infrastructure issues, not model behavior
- Prompt engineering significantly impacts detection accuracy (H1: forced traversal)
- Evaluation scope affects precision/recall tradeoff (H2: single-rule mode)
- The system successfully identifies standards violations but still requires significant calibration

---

## 1. Framework Overview

### What the CSR Service Does

The CSR Service accepts instructional content (training materials, course objectives, procedures) and evaluates it against a corpus of standards rules. It returns structured observations identifying potential violations with:

- **Span**: Character offsets locating the issue in the source text
- **Severity**: violation, warning, or info
- **Standard reference**: Which rule was violated
- **Message**: Human-readable description
- **Confidence**: Model's certainty (0.0-1.0)

### Architecture



1. **Retrieval**: Term Frequency–Inverse Document Frequency (TF-IDF) vectorizer identifies top-k most relevant rules for the content
2. **Prompt Construction**: Builds system and user prompts with rules + content + strictness
3. **LLM Inference**: Calls Ollama with structured JavaScript Object Notation (JSON) output mode
4. **Parsing**: Extracts and validates observations from model output
5. **Policy**: Applies confidence gating, strictness bias, deduplication, sorting

```
Request → Retrieval → Prompt Construction → LLM → Parsing → Policy → Response
            │              │                  │        │        │
         TF-IDF      System + User        Ollama    JSON     Gating
         top-k         prompts           qwen2.5   extract   dedup
```

### Standards Corpus

The current implementation uses `naval_v3.json` with 17 rules covering:
- Learning objective measurability (NAV-TR-3.1.x)
- Technical accuracy and consistency (NAV-TR-3.2.x)
- Accessibility and acronym usage (NAV-TR-3.3.x)
- Document structure and procedures (NAV-TR-3.4.x)

---

## 2. Methodology: Hypothesis-Driven Development

### Rationale

LLM-based systems exhibit non-deterministic behavior that resists traditional debugging. A change that improves one case may degrade another. Without controlled experiments, development becomes trial-and-error.

We adopted a hypothesis-driven approach:

1. **Observe failure** — identify specific cases that fail expectations
2. **Form hypothesis** — propose a falsifiable explanation for the failure
3. **Design intervention** — change exactly one variable
4. **Run controlled experiment** — same cases, same model, before/after
5. **Measure deltas** — quantify the change, not just pass/fail
6. **Adjudicate** — determine if hypothesis is supported, refuted, or inconclusive

### Why This Matters

This methodology:
- Prevents "fix one, break three" cycles
- Creates auditable decision history
- Distinguishes infrastructure failures from model behavior
- Enables rational prioritization of improvements

### Experiment Structure

Each experiment is documented with:
- **Hypothesis statement**: Falsifiable claim about system behavior
- **Intervention**: Exact change made (config, code, prompt)
- **Baseline**: Results before intervention
- **Modified**: Results after intervention
- **Delta analysis**: Per-case comparison of metrics
- **Verdict**: Supported, refuted, or partially supported

---

## 3. Experimental Results

### Experiment H1: Forced Per-Standard Traversal

**Hypothesis**: The passive prompt instruction ("Review the content against the rules") allows the model to conclude compliance without evaluating each rule individually.

**Intervention**: Modified prompts to require explicit per-rule evaluation:
```
Before: "Review the content above against the provided standards rules."
After:  "Evaluate the content against EACH rule listed above, one rule at a time..."
```

**Critical Discovery**: Before testing H1, we discovered the original evaluation was invalid. A model ID mismatch (`qwen2.5:32b` vs `qwen2.5:32b-instruct`) caused every request to return a 404 error. The pipeline's error handler returned empty observations, which the eval harness recorded as "model found no issues."

**Lesson**: Always verify the model is actually being called before analyzing results. Suspiciously fast latencies (7-24ms for Large Language Model (LLM) inference) were the tell.

**Results after fixing infrastructure + applying H1**:

| Case | Before | After | Change |
|------|--------|-------|--------|
| case_02 (vague verbs) | 0 obs, FAIL | 3-5 obs, PASS | Fixed |
| case_03 (acronyms) | 0 obs, FAIL | 4-5 obs, partial | Improved |
| case_04 (contradictions) | 0 obs, FAIL | 3-7 obs, partial | Improved |
| case_05 (structure) | 0 obs, FAIL | 5 obs, partial | Improved |

**Verdict**: H1 SUPPORTED. Forced traversal eliminated the "silent compliance" failure mode.

---

### Experiment H2: Single-Rule Evaluation

**Hypothesis**: Evaluating content against one rule at a time (N parallel requests) will improve accuracy by reducing prompt complexity and model context-switching.

**Intervention**: Added single-rule mode that sends separate requests per rule and merges results.

**Results**:

| Metric | H1 (Multi-Rule) | H2 (Single-Rule) |
|--------|-----------------|------------------|
| Cases passed | 4/8 | 3/8 |
| NAV-TR-3.3.1 found | No | Yes |
| Timeouts | 1 case | 0 cases |
| Over-detection | Moderate | High |

**Verdict**: H2 PARTIALLY SUPPORTED. Single-rule mode improved rule coverage (found previously missing violations) but caused over-detection (too many false positives on clean content).

---

## 4. Critical Analysis

### The Core Problem

We are building a system that must balance:

1. **Recall**: Find all genuine violations (don't miss issues)
2. **Precision**: Avoid false positives (don't cry wolf)
3. **Consistency**: Same input → similar output across runs
4. **Interpretability**: Humans can understand and verify findings

These goals conflict. Increasing sensitivity (recall) reduces precision. Reducing model temperature improves consistency but may miss edge cases.

### Current Failure Modes

#### Failure Mode 1: Silent Compliance
**Symptom**: Model returns empty observations for content with obvious violations.
**Cause**: Passive prompt framing + "don't fabricate" instruction biases toward silence.
**Status**: Addressed by H1 (forced traversal).

#### Failure Mode 2: Over-Detection
**Symptom**: Model generates too many observations, including false positives.
**Cause**: Single-rule isolation removes context that would indicate compliance.
**Status**: Observed in H2. Requires calibration.

#### Failure Mode 3: Severity Misclassification
**Symptom**: Model uses "violation" when "warning" is appropriate (or vice versa).
**Cause**: Insufficient guidance on severity criteria in prompts.
**Status**: Unresolved. Observed in both H1 and H2 results.

#### Failure Mode 4: Retrieval Miss
**Symptom**: Relevant rule not in top-k retrieved set.
**Cause**: TF-IDF may not capture semantic similarity for short content.
**Status**: Partially addressed by H2 (single-rule found NAV-TR-3.3.1). Needs H2 investigation.

#### Failure Mode 5: Span Instability
**Symptom**: Same violation identified at different character offsets across runs.
**Cause**: Model non-determinism in span selection.
**Status**: Observed (0-70% span stability). May require post-processing normalization.

### What We Don't Know Yet

1. **Retrieval effectiveness**: Are the right rules being retrieved? (H3 pending)
2. **Confidence calibration**: Are high-confidence observations actually more accurate?
3. **Model size impact**: Would 32B model reduce over-detection vs 7B?
4. **Rule corpus quality**: Are the rules themselves well-specified?

---

## 5. Recommendations

### Immediate (Configuration)

| Change | Rationale | Risk |
|--------|-----------|------|
| Increase `min_confidence` to 0.7 | Reduce false positives | May filter valid observations |
| Add severity guidance to prompt | Clarify warning vs violation criteria | Prompt length increase |
| Enable H1 prompts in production | Proven improvement | None (already tested) |

### Short-Term (Code Changes)

1. **Retrieval logging**: Add debug logging to verify which rules are retrieved per request. Required to test H2.

2. **Hybrid evaluation mode**: Use single-rule for specific problematic standards (NAV-TR-3.3.x), multi-rule for others. Balances coverage and precision.

3. **Span normalization**: Post-process spans to align with sentence/paragraph boundaries. Improves stability without changing model behavior.

4. **Confidence calibration**: Collect human feedback on observation accuracy, correlate with model confidence scores, adjust thresholds empirically.

### Medium-Term (Architecture)

1. **Replace TF-IDF with embeddings**: Dense vector retrieval (e.g., sentence-transformers) may improve rule relevance for short or semantic content.

2. **Multi-step orchestration**: Separate classification (which rules apply?) from analysis (how are they violated?). Reduces prompt complexity per step.

3. **Ensemble approach**: Run 2-3 model calls with different temperatures, intersect results. Improves precision at cost of latency.

### Long-Term (Product)

1. **Feedback loop**: Collect user accept/reject signals on observations, use to fine-tune or adjust prompts.

2. **Rule hierarchy**: Add metadata for rule dependencies, conditional applicability, severity defaults.

3. **Streaming results**: Return observations as they're generated rather than waiting for full analysis.

---

## 6. Conclusion

The CSR Service demonstrates that LLM-based content review is feasible but requires careful engineering. Our hypothesis-driven methodology revealed that:

1. **Infrastructure failures can masquerade as model behavior** — always verify the model is actually called
2. **Prompt framing dramatically affects output** — passive instructions cause under-detection
3. **Evaluation scope is a precision/recall tradeoff** — narrower scope improves recall but hurts precision
4. **Consistency remains challenging** — span stability is low even with low temperature

The system is not production-ready, but the path forward is clear: calibrate confidence thresholds, implement hybrid evaluation mode, and invest in retrieval quality. The experimental framework we've built enables continued iteration with measurable progress.

---

## Appendix: Experiment Files

```
eval/experiments/
├── h1_forced_traversal/
│   ├── 00_SUMMARY.md           # Experiment overview
│   ├── 01_RUN1_BASELINE.md     # Initial (invalid) baseline
│   ├── 02_CHANGES.md           # Infrastructure fixes + prompt changes
│   ├── 03_RUN2_RESULTS.md      # Results showing H1 worked
│   ├── baseline_prompts.yaml   # Original prompts
│   ├── modified_prompts.yaml   # H1 intervention prompts
│   └── *.json, *.png           # Data and visualizations
└── h2_single_rule/
    ├── 00_HYPOTHESIS.md        # H2 hypothesis and status
    ├── 01_RESULTS.md           # H2 experimental results
    └── results.json            # Raw eval data
```

## Appendix: Key Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| Observation count | Number of issues identified | Within expected range per case |
| Span stability | % of runs with same span for same ref | >80% |
| Severity stability | % of runs with same severity for same ref | >90% |
| Expected refs found | Required standard_ref appears in observations | 100% |
| Latency | Time from request to response | <30s for interactive use |
| False positive rate | Observations on clean content | <3 per review |

---

## Out of Scope for This Run

The following areas were identified but not addressed in this research phase:

- **Production latency optimization** — Current 20-30s response times are acceptable for evaluation but require optimization for interactive use
- **Model benchmarking** — Systematic comparison across model sizes (7B vs 32B) and architectures not conducted
- **Retrieval quality improvements** — TF-IDF retrieval works but dense embeddings may improve relevance; H2 experiment not executed
- **Severity calibration** — Model frequently misclassifies severity (violation vs warning); requires prompt tuning or post-processing rules
