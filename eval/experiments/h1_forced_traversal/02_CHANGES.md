# Changes Between Run 1 and Run 2

**Notes**:
- Run 2 prioritizes behavioral validation over output quality; model size and latency characteristics are not representative of a production configuration.
- No changes were made to retrieval, policy thresholds, confidence gating, or severity logic in this intervention.

## Infrastructure Fixes

### Fix 1: Model Size

***Problem**: Originally fixed to `qwen2.5:32b-instruct`. While my machine (GX10: 128GB VRAM) can handle loading a 32B model, there is a limited amount of throughput available which caused a 5-10 minute round trip delay per request. In production I would recommend using an A6000 GPU or better. 

**Solution**: Switched to 7B model with known reductions in semantic fidelity, acceptable for diagnosing pipeline behavior but not for final quality evaluation. 

```diff
# .env
- CSR_MODEL_ID=qwen2.5:32b-instruct
+ CSR_MODEL_ID=qwen2.5:7b-instruct
```

This reduced round trip time to ~30 seconds per request at the cost of model accuracy.

**Note**: Bench marking model performance and doing a cost analysis will be required when selecting hardware for the project. 

### Fix 2: GPU memory exhaustion

**Problem**: After fixing model ID, Ollama couldn't load the 18GB model. 

**Solution**: Killed external processes that were consuming GPU memory.

## H1 Intervention: Forced Per-Standard Traversal

### Hypothesis

The passive prompt instruction ("Review the content above against the provided standards rules") allows the model to conclude compliance without checking each rule individually.

### System prompt changes

```diff
# config/prompts.yaml (system prompt)
  Rules for observations:
  - span must be [start, end] character offsets...
  - severity: "violation" for clear breaches...
  - confidence: how certain you are...
  - standard_ref must exactly match...
- - Only report genuine issues. Do not fabricate problems.
- - If the content fully complies with all provided rules, return {"observations": []}
+ - Do not invent issues that are not evidenced in the text. Every observation must cite specific content that triggers the rule.
+ - You MUST evaluate each provided rule against the content individually. Do not skip rules.
+ - An empty observations list is only appropriate when you have checked every provided rule and none are violated.
```

### User prompt changes

```diff
# config/prompts.yaml (user prompt)
  ## Instructions

- Review the content above against the provided standards rules. Return your observations as JSON.
+ Evaluate the content against EACH rule listed above, one rule at a time:
+
+ 1. For each rule, identify whether the content violates that specific rule.
+ 2. If violated, locate the specific text span that triggers the violation and report it as an observation.
+ 3. If a rule is satisfied by the content, move to the next rule without reporting it.
+
+ You must check every rule. Do not stop after finding the first issue or conclude "no problems" without testing each rule individually.
+
+ Return your observations as JSON.
```

### Notes

- This change enforces traversal without encouraging issue fabrication. 
- The model is still explicitly prohibited from inventing violations
- The only added constraint is that each rule must be evaluated before an empty result is returned.

## Summary of changes

| Component | Before | After |
|-----------|--------|-------|
| Model ID | `qwen2.5:32b-instruct` (404) | `qwen2.5:7b-instruct` |
| GPU memory | exhausted | freed 31GB |
| System prompt | permits empty default | requires per-rule check |
| User prompt | passive "review" | explicit per-rule traversal |

## Files

- Original prompts: `baseline_prompts.yaml`
- Modified prompts: `modified_prompts.yaml`
- Diff: `diff baseline_prompts.yaml modified_prompts.yaml`
