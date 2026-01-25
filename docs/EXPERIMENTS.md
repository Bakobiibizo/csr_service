# Experiments Index

This document provides an overview of hypothesis-driven experiments conducted on the CSR Service pipeline.

For methodology and comprehensive analysis, see **[RESEARCH_OVERVIEW.md](RESEARCH_OVERVIEW.md)**.

---

## Completed Experiments

### H1: Forced Per-Standard Traversal

**Hypothesis**: Passive prompt instructions allow the model to conclude compliance without evaluating each rule individually.

**Result**: **SUPPORTED** — Changing prompts to require explicit per-rule evaluation fixed the "silent compliance" failure mode.

**Documentation**: [eval/experiments/h1_forced_traversal/](../eval/experiments/h1_forced_traversal/)
- [00_SUMMARY.md](../eval/experiments/h1_forced_traversal/00_SUMMARY.md) — Overview and verdict
- [01_RUN1_BASELINE.md](../eval/experiments/h1_forced_traversal/01_RUN1_BASELINE.md) — Initial (invalid) baseline
- [02_CHANGES.md](../eval/experiments/h1_forced_traversal/02_CHANGES.md) — Infrastructure fixes + prompt changes
- [03_RUN2_RESULTS.md](../eval/experiments/h1_forced_traversal/03_RUN2_RESULTS.md) — Results after H1

---

### H4: Single-Rule Evaluation

**Hypothesis**: Evaluating content against one rule at a time improves accuracy by reducing prompt complexity.

**Result**: **PARTIALLY SUPPORTED** — Improved rule coverage (found previously missing violations) but caused over-detection (too many false positives).

**Documentation**: [eval/experiments/h4_single_rule/](../eval/experiments/h4_single_rule/)
- [00_HYPOTHESIS.md](../eval/experiments/h4_single_rule/00_HYPOTHESIS.md) — Hypothesis and status
- [01_RESULTS.md](../eval/experiments/h4_single_rule/01_RESULTS.md) — Experimental results

---

## Pending Experiments

### H2: Retrieval Verification

**Hypothesis**: TF-IDF retrieval may fail to surface applicable rules for short content.

**Status**: Not started. Requires adding debug logging to retrieval.

### H3: Confidence Gating Verification

**Hypothesis**: The confidence threshold (0.55) may be filtering valid observations.

**Status**: Not started. Requires running eval with `min_confidence: 0.0`.

---

## Experiment Methodology

Each experiment follows this structure:

1. **Observe failure** — Identify specific cases that fail expectations
2. **Form hypothesis** — Propose a falsifiable explanation
3. **Design intervention** — Change exactly one variable
4. **Run controlled experiment** — Same cases, same model, before/after
5. **Measure deltas** — Quantify the change per case
6. **Adjudicate** — Determine if hypothesis is supported, refuted, or inconclusive

See [RESEARCH_OVERVIEW.md](RESEARCH_OVERVIEW.md) for detailed methodology explanation.

---

## Quick Reference

| Experiment | Status | Pass Rate | Key Finding |
|------------|--------|-----------|-------------|
| H1 | Complete | 4/8, 13/16 exp | Fixed silent compliance |
| H4 | Complete | 3/8, 11/17 exp | Better coverage, over-detection |
| H2 | Pending | - | Retrieval verification needed |
| H3 | Pending | - | Confidence gating verification needed |
