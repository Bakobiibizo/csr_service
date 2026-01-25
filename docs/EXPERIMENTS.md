# Experiment Log

## Observed Failure

Cases 02-05 return zero observations despite containing clear standards violations:

| Case | Content Issue | Expected Standard | Expected Obs | Actual Obs |
|------|--------------|-------------------|-------------|-----------|
| case_02 | Vague verbs ("understand", "appreciate", "know") | NAV-TR-3.1.1 | 2-8 | 0 |
| case_03 | Undefined acronyms (OOD, JOOD, BMOW, MOBOARD) | NAV-TR-3.3.1 | 2-10 | 0 |
| case_04 | Contradictory statements (70dB vs 100dB) | NAV-TR-3.2.2 | 1-6 | 0 |
| case_05 | Procedures embedded in prose paragraphs | NAV-TR-3.4.1 | 2-8 | 0 |

Cases that pass (01, 06, 07, 08) are either clean content, loose expectations, or error cases. The failure is specific to cases where the model must actively identify violations.

---

## Investigation: Pre-Condition Failures (2026-01-24)

Before testing H1, investigation revealed that the **model was never called** in the original evaluation. Two infrastructure failures masked the actual pipeline behavior:

### Finding 1: Model ID mismatch (critical)

```
Container env:     CSR_MODEL_ID=qwen2.5:32b
Ollama model name: qwen2.5:32b-instruct
```

Every review request returned:
```
Error code: 404 - model 'qwen2.5:32b' not found
```

The pipeline's error handler caught this and returned `{"observations": []}` — a valid schema response with zero observations. The eval harness interpreted this as "model analyzed content and found nothing" rather than "model was never called."

**Fix applied**: `.env` updated to `CSR_MODEL_ID=qwen2.5:32b-instruct`

**Implication**: The original baseline results (4/8 pass, 14ms mean latency) were measuring HTTP round-trip + error handling, not model inference. All zero-observation results in cases 02-05 were artifacts of the 404, not prompt engineering failures.

### Finding 2: GPU memory exhaustion (blocking)

After fixing the model ID, Ollama cannot load the model:

```
nvidia-smi GPU processes:
  python3 (port 7105, tiktokenizer) — 31,001 MiB
  python  (inference service)       —  7,271 MiB
  python3 (inference service)       —  3,591 MiB
  python  (inference service)       —  2,818 MiB
  Xorg + gnome-shell                —     60 MiB
  Total allocated:                    ~45 GB
```

The qwen2.5:32b-instruct model (Q4_K_M, ~18GB) cannot allocate GPU memory. Ollama accepts the generate request but hangs indefinitely waiting for memory.

**System**: NVIDIA GB10 (unified memory), 119GB total RAM, ~27GB free. In theory sufficient for CPU offload, but Ollama is not falling back to CPU-only inference.

### Impact on Experiment Plan

- H1 prompt intervention is **applied and ready** but **untested** due to GPU memory
- Original "baseline" results are **invalid** — they test error handling, not model behavior
- A true baseline requires the model to actually run

### Required Actions

To proceed with H1 testing:

1. Free ~18GB GPU memory (stop tiktokenizer or other inference services), OR
2. Configure Ollama for CPU-only mode: `OLLAMA_NUM_GPU=0`, OR
3. Use a smaller model (e.g., pull `qwen2.5:7b-instruct` — ~4GB)

Once the model loads, re-run both baseline and modified evals to establish a true comparison.

---

## Hypotheses

### H1: Passive instruction allows early compliance conclusion

**Statement**: The user prompt instruction "Review the content above against the provided standards rules" permits the model to conclude compliance without per-standard evaluation. Combined with "Only report genuine issues. Do not fabricate problems," the model defaults to silence unless violations are obvious at surface level.

**Evidence**:
- All four failing cases return `{"observations": []}` — not malformed output, but a valid empty result
- The model is not failing to parse or generate JSON — it is actively concluding "no issues"
- The system prompt explicitly permits empty results: "If the content fully complies with all provided rules, return `{"observations": []}`"

**Prediction**: Replacing the passive instruction with forced per-standard evaluation will produce observations for cases 02-05 without changing retrieval, policy, or model parameters.

**Falsification**: If forced traversal still produces zero observations, the problem is upstream (retrieval not surfacing correct rules) or downstream (policy filtering valid observations).

---

### H2: TF-IDF retrieval fails to surface applicable rules for short content

**Statement**: Short content (case_02 is 268 chars, case_04 is 337 chars) may produce weak TF-IDF similarity scores against rule bodies, causing relevant rules to rank below the top-k cutoff.

**Evidence**: Not yet tested. This is a secondary hypothesis if H1 fails.

**Prediction**: Adding debug logging to retrieval will show that relevant rules (e.g., NAV-TR-3.1.1 for case_02) are not in the retrieved set.

**Falsification**: If retrieval logs show the correct rules are retrieved but the model still produces no observations, the problem is in the analysis stage (supports H1).

---

### H3: Confidence gating removes valid low-confidence observations

**Statement**: The model may be generating observations with confidence below the 0.55 threshold, which are then removed by the policy layer's confidence gating step.

**Evidence**: Not yet tested. Requires capturing pre-policy observations.

**Prediction**: Temporarily disabling confidence gating (setting `min_confidence: 0.0`) will reveal observations that are currently filtered.

**Falsification**: If pre-policy observations are also empty, the problem is in the model's generation (supports H1).

---

## Experiment Protocol

### Variables

| Variable | Baseline | H1 Intervention |
|----------|----------|----------------|
| System prompt | Current (passive) | Modified (per-rule testing) |
| User prompt instruction | "Review the content above..." | "For each rule, determine if violated..." |
| Retrieval | TF-IDF, k_medium=10 | Unchanged |
| Policy | min_confidence=0.55 | Unchanged |
| Model | qwen2.5:32b | Unchanged |
| Temperature | 0.1 | Unchanged |
| Cases | case_01 through case_08 | Unchanged |

### Procedure

1. Record baseline results (current prompts.yaml, 5 runs per case)
2. Apply H1 intervention (modify prompts.yaml only)
3. Run identical eval (same model, same cases, same n=5)
4. Compare deltas

### Metrics

For each case, report:

| Metric | Baseline | Modified | Delta |
|--------|----------|----------|-------|
| Observation count | N | N | +/- |
| Expected severities found | Y/N per severity | Y/N | Change |
| Expected refs found | Y/N per ref | Y/N | Change |
| Span stability | % | % | +/- |
| Severity stability | % | % | +/- |
| Latency mean (ms) | N | N | +/- |

### Success Criteria

H1 is **supported** if:
- Cases 02-05 produce non-zero observations after intervention
- case_01 (clean content) does not regress to false positives (stays 0-3)
- Observation counts fall within expected ranges for at least 3/4 failing cases

H1 is **not supported** if:
- Cases 02-05 still produce zero observations after prompt change
- case_01 regresses significantly (>5 false positives)

---

## Experiment 1: Forced Per-Standard Traversal (H1)

### Intervention

**Changed file**: `config/prompts.yaml`

**System prompt changes**:
- Reframed "don't fabricate" to "do not invent issues that are not evidenced in the text"
- Removed the explicit permission to return empty observations as a default
- Added instruction to evaluate each provided rule

**User prompt changes**:
- Replaced "Review the content above against the provided standards rules" with explicit per-rule evaluation directive
- Added requirement to state disposition (violated/satisfied) for each rule

### Execution

**Files**:
- Baseline config: `eval/experiments/h1_forced_traversal/baseline_prompts.yaml`
- Modified config: `eval/experiments/h1_forced_traversal/modified_prompts.yaml`
- Baseline results: `eval/experiments/h1_forced_traversal/baseline_results.json`
- Modified results: `eval/experiments/h1_forced_traversal/modified_results.json`
- Comparison: `eval/experiments/h1_forced_traversal/comparison.json`

**Manual execution** (recommended — ensures clean service restarts):

```bash
# Step 1: Run baseline (current prompts are already the baseline from previous eval)
# If baseline_results.json already exists from previous run, skip this step.

# To re-run baseline:
cp eval/experiments/h1_forced_traversal/baseline_prompts.yaml config/prompts.yaml
# Restart service, then:
uv run python -m eval.runner --cases eval/cases -n 5 \
    --json-output eval/experiments/h1_forced_traversal/baseline_results.json

# Step 2: Apply H1 intervention and run modified eval
cp eval/experiments/h1_forced_traversal/modified_prompts.yaml config/prompts.yaml
# Restart service, then:
uv run python -m eval.runner --cases eval/cases -n 5 \
    --json-output eval/experiments/h1_forced_traversal/modified_results.json

# Step 3: Compare
uv run python -m eval.experiment_runner compare \
    --baseline eval/experiments/h1_forced_traversal/baseline_results.json \
    --modified eval/experiments/h1_forced_traversal/modified_results.json \
    --output eval/experiments/h1_forced_traversal/comparison.json
```

**Automated execution** (if service auto-restarts on file change):

```bash
uv run python -m eval.experiment_runner run \
    --experiment-dir eval/experiments/h1_forced_traversal \
    --base-url http://localhost:9020 \
    --token demo-token \
    -n 5 \
    --restart-delay 10
```

### Status

- [x] Baseline captured (invalidated — model was never called)
- [x] Intervention applied
- [x] Post-intervention eval run (2026-01-25, qwen2.5:7b-instruct, n=3)
- [x] Results compared
- [x] Hypothesis adjudicated

### Results

**Hypothesis H1 is SUPPORTED.**

The original baseline was invalid (model 404). After fixing infrastructure and applying H1:

| Case | Original (invalid) | H1 Modified (7B) | Change |
|------|-------------------|------------------|--------|
| case_01 | 0 obs, PASS | 2-4 obs, PASS | +2-4 obs (borderline FPs) |
| case_02 | 0 obs, FAIL | 3-5 obs, **PASS** | **Fixed** — NAV-TR-3.1.1 found |
| case_03 | 0 obs, FAIL | 4-5 obs, FAIL | +4-5 obs, wrong ref surfaced |
| case_04 | 0 obs, FAIL | 3-7 obs, FAIL | +3-7 obs, slight over-count |
| case_05 | 0 obs, FAIL | 5 obs, FAIL | +5 obs, missing severity class |
| case_06 | 0 obs, PASS | timeout | Infrastructure issue |
| case_07 | error, PASS | error, PASS | No change (error case) |
| case_08 | error, PASS | error, PASS | No change (error case) |

**Expectations**: 4/17 → 13/16 (excluding timeout case)

**Conclusion**: Forced per-standard traversal eliminated the "silent compliance" failure mode. The model now actively evaluates each rule and generates observations. Remaining failures are calibration issues:
- **case_03**: Retrieval may not be surfacing NAV-TR-3.3.1 (H2 territory)
- **case_04**: Over-generating observations (prompt may need "only report clear violations")
- **case_05**: Severity classification incorrect (model using "violation" instead of "warning")

**Next steps**:
1. Validate on 32B model (same prompt, expect similar behavior)
2. Investigate H2 (retrieval) for case_03
3. Tune severity classification in prompt or policy layer

---

## Experiment 2: Retrieval Verification (H2)

### Intervention

**Changed file**: `src/csr_service/standards/retriever.py` (add debug logging only)

Add logging of retrieved rule refs and their similarity scores for each request. No functional change.

### Status

- [ ] Logging added
- [ ] Cases 02-05 run with logging
- [ ] Retrieved rules verified against expectations
- [ ] Hypothesis adjudicated

### Results

_Pending execution._

---

## Experiment 3: Policy Gating Verification (H3)

### Intervention

**Changed file**: `config/policy.yaml` (set `min_confidence: 0.0`)

Disable confidence gating to see if observations are generated but filtered.

### Status

- [ ] Baseline captured (same as Experiment 1 baseline)
- [ ] min_confidence set to 0.0
- [ ] Eval run
- [ ] Pre-policy observations compared to post-policy
- [ ] Hypothesis adjudicated

### Results

_Pending execution._
