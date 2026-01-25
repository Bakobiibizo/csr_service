# Next Experiment: Single-Rule Evaluation

## Hypothesis H4: Narrowing scope improves performance

**Statement**: Evaluating content against one rule at a time (N requests for N rules) will produce more accurate observations with lower latency than evaluating against all rules in a single request.

**Rationale**:
- Current approach sends 10 rules + content in one prompt
- Model must context-switch between rules while maintaining analysis state
- Prompt length increases token count, slowing inference
- Multi-rule prompts may cause rule confusion or missed violations

**Proposed change**:
```
Current:  1 request × 10 rules → model evaluates all rules at once
Proposed: 10 requests × 1 rule → model evaluates one rule per request
```

## Expected benefits

| Metric | Current (multi-rule) | Expected (single-rule) |
|--------|---------------------|------------------------|
| Latency per rule | ~3s (amortized) | ~2-5s |
| Total latency | ~20-30s | ~20-50s (serial) or ~5s (parallel) |
| Accuracy | rule confusion possible | focused evaluation |
| Parallelization | not possible | trivially parallel |

## Implementation approach

1. **Retrieval**: unchanged — still retrieve top-k rules via TF-IDF
2. **Prompt**: simplified — single rule + content per request
3. **Orchestration**: new — fan-out to N parallel model calls, merge results
4. **Policy**: unchanged — apply confidence gating, dedup, sort on merged observations

```python
# Pseudocode
async def review_single_rule(content: str, rule: StandardRule) -> list[Observation]:
    prompt = f"Evaluate if this content violates: [{rule.ref}] {rule.title}: {rule.body}\n\n{content}"
    return await model.generate(prompt)

async def review_content(content: str, rules: list[StandardRule]) -> list[Observation]:
    tasks = [review_single_rule(content, rule) for rule in rules]
    results = await asyncio.gather(*tasks)
    return merge_and_dedupe(flatten(results))
```

## Trade-offs

**Pros**:
- Simpler prompts → better model comprehension
- Parallel execution → lower wall-clock time
- Easier debugging → one rule per response
- More predictable output → constrained task

**Cons**:
- More API calls → higher total token usage
- Coordination overhead → merge logic needed
- Potential duplicate observations → requires dedup
- Cold-start penalty if model unloads between calls

## Validation plan

1. Implement single-rule evaluation mode (feature flag)
2. Run eval with same cases, same rules, n=3
3. Compare:
   - Observation accuracy (correct refs found)
   - Latency (serial vs parallel)
   - Token usage (total input + output tokens)
   - Stability (span/severity consistency)

## Files to modify

- `src/csr_service/engine/pipeline.py` — add single-rule orchestration
- `src/csr_service/engine/prompt.py` — add single-rule prompt template
- `config/prompts.yaml` — add `single_rule_prompt_template`
- `.env` — add `CSR_SINGLE_RULE_MODE=true` flag

## Status

- [x] Implementation
- [x] Eval run
- [x] Comparison to H1 results
- [x] Hypothesis adjudicated

## Verdict

**PARTIALLY SUPPORTED** — See [01_RESULTS.md](01_RESULTS.md) for full analysis.

Single-rule evaluation improved rule coverage (found NAV-TR-3.3.1, fixed timeouts) but caused over-detection. The model finds more issues per rule when evaluated in isolation, leading to false positives on clean content.
