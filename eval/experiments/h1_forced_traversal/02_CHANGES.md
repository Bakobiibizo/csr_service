# Changes Between Run 1 and Run 2

## Infrastructure Fixes

### Fix 1: Model ID mismatch

**Problem**: Service configured with wrong model name.

```diff
# .env
- CSR_MODEL_ID=qwen2.5:32b
+ CSR_MODEL_ID=qwen2.5:7b-instruct
```

Note: Originally fixed to `qwen2.5:32b-instruct`, but 32B model was too slow (2-15 min/request) for my infrastructure. Switched to 7B for practical iteration speed. A more powerful machine should have no problem handling 32B.

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

## Summary of changes

| Component | Before | After |
|-----------|--------|-------|
| Model ID | `qwen2.5:32b` (404) | `qwen2.5:7b-instruct` |
| GPU memory | exhausted | freed 31GB |
| System prompt | permits empty default | requires per-rule check |
| User prompt | passive "review" | explicit per-rule traversal |

## Files

- Original prompts: `baseline_prompts.yaml`
- Modified prompts: `modified_prompts.yaml`
- Diff: `diff baseline_prompts.yaml modified_prompts.yaml`
