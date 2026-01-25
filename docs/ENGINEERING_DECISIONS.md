# Engineering Decisions

## Design-first approach

All external behavior (API contracts, response invariants, error semantics) was specified before implementation. The spec (`docs/CSR_SPEC.md`) defines what the system must do; the code implements it. Model behavior is treated as untrusted input and normalized post-hoc through parsing and policy.

## Model containment

LLMs are isolated behind a narrow interface (`engine/model_client.py`). They are not allowed to:

- Define API shape (schemas are code-defined, not model-generated)
- Emit unvalidated output (parser validates each observation independently)
- Bypass policy logic (confidence gating, severity bias, dedup are pure code)

The model is a tool, not an authority. If it produces garbage, the system degrades gracefully with empty observations and a structured error.

## Determinism strategy

We do not attempt full determinism from the model. Instead:

- Schemas are deterministic (Pydantic-enforced, always valid)
- Severity and span are stabilized (policy layer normalizes model variance)
- Language variation in `message`/`rationale` is allowed (natural and expected)
- Retrieval ordering is deterministic for a given sklearn version and standards set

The eval harness measures what matters: span stability and severity stability across repeated runs.

## Policy as code, not prompting

Strictness is not a prompt modifier alone. It controls:

- Retrieval depth (how many rules the model sees)
- Confidence thresholds (what survives filtering)
- Severity caps (when violations are downgraded)

This means policy behavior is testable, debuggable, and independent of model choice.

## How this scales to teams

This structure allows junior engineers to work safely inside contracts (add rules, adjust thresholds), while senior engineers own policy, evaluation, and interfaces. Swapping models requires changing one environment variable. Adding standards sets requires dropping a JSON file.

Extensible and modular design enables fast iteration required for rapid refinement of prompts and rules while providing enough structure for development of reliable non-deterministic model outputs.