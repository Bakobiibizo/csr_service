## AI Content Standards Review Service (CSRS) Demo Spec v0.1

### Goal

Deliver a production-grade API that reviews instructional content against a selected standards set and returns **structured, UI-ready observations** with **traceable citations** and a **stable schema**.

## 1) Core Requirements

### R1. API-first, contract-stable

* Request/response schemas are versioned and enforced with Pydantic.
* Output must always validate, even on model failure.

### R2. Standards grounded + traceable

Each observation references a standard via:

* `standard_ref` (stable ID, ex: `NAV-TR-3.2.1`)
* optional `standard_excerpt`
* optional `standard_url` or `standard_location`

### R3. UI-ready spans

* Observations include `span: [start, end]` character offsets into `content`.
* If span cannot be determined, set it to `null` (never omit).

### R4. Configurable policy

* Strictness modifies thresholds and severity behavior.
* Policy is separate from prompting, implemented in code.

### R5. Determinism containment

* Schema is deterministic.
* Severity and span should be stable across repeated runs for the same input (within defined tolerances).
* Natural language phrasing may vary.

### R6. Latency + instrumentation

* Return `meta.latency_ms`.
* Log request id, standards set, strictness, and token usage when available.

---

## 2) Service Interface

### Endpoint: `POST /v1/review`

#### Request schema

```json
{
  "request_id": "string",
  "content": "string",
  "standards_set": "string",
  "strictness": "low|medium|high",
  "options": {
    "return_rationale": true,
    "return_excerpts": true,
    "max_observations": 25,
    "min_confidence": 0.55
  }
}
```

#### Response schema

```json
{
  "observations": [
    {
      "id": "string",
      "span": [123, 156],
      "severity": "info|warning|violation",
      "category": "clarity|accuracy|structure|accessibility|pedagogy|compliance|other",
      "standard_ref": "string",
      "message": "string",
      "suggested_fix": "string|null",
      "rationale": "string|null",
      "standard_excerpt": "string|null",
      "confidence": 0.0
    }
  ],
  "meta": {
    "request_id": "string",
    "standards_set": "string",
    "strictness": "low|medium|high",
    "policy_version": "string",
    "model_id": "string",
    "latency_ms": 0,
    "usage": {
      "input_tokens": 0,
      "output_tokens": 0
    }
  },
  "errors": [
    {
      "code": "string",
      "message": "string",
      "details": "object|null"
    }
  ]
}
```

**Invariants**

* `observations` always present.
* `errors` always present.
* Every observation has `id`, `severity`, `category`, `standard_ref`, `message`, `confidence`.
* `span` is either `[start,end]` with `0 <= start < end <= len(content)` or `null`.
* `confidence` is `0.0..1.0`.

### Endpoint: `GET /v1/standards`

Returns available standards sets:

```json
{
  "standards_sets": [
    { "id": "naval_v3", "name": "Naval Training Standards v3", "version": "3.0" }
  ]
}
```

### Endpoint: `GET /health`

Returns:

* service status
* loaded standards count
* model backend status

---

## 3) Standards Layer

### Data model

A standards set is a collection of atomic rules:

```json
{
  "standards_set": "naval_v3",
  "rules": [
    {
      "standard_ref": "NAV-TR-3.2.1",
      "title": "Learning objectives must be measurable",
      "body": "Objectives must use observable verbs...",
      "tags": ["objectives", "measurable"],
      "severity_default": "warning"
    }
  ]
}
```

### Retrieval behavior

Given `content`, retrieve top-k relevant rules:

* k defaults: low=6, medium=10, high=14
* retrieval may use keyword/BM25 or embeddings
* return ordering remains stable when inputs do not change

---

## 4) Review Engine

### Pipeline

1. Validate request
2. Load standards set
3. Retrieve candidate rules (top-k)
4. Build model input (content + rule summaries)
5. Call model for structured output
6. Validate model output against schema
7. Apply policy adjustments (confidence thresholds, severity downgrades, max observations)
8. Return response with meta + metrics

### Model output format (internal)

The model returns machine-parsable JSON matching:

```json
{
  "observations": [
    {
      "span": [start,end] | null,
      "severity": "...",
      "category": "...",
      "standard_ref": "...",
      "message": "...",
      "suggested_fix": null|string,
      "rationale": null|string,
      "standard_excerpt": null|string,
      "confidence": 0.0..1.0
    }
  ]
}
```

If the model fails:

* return `observations=[]`
* populate `errors` with `MODEL_FAILURE` and details

---

## 5) Policy Layer

### Inputs

* strictness
* min_confidence
* max_observations

### Behavior

* **Confidence gating**

  * if confidence < `min_confidence`: downgrade severity by 1 level (violation->warning->info) or drop (consistent policy)
* **Strictness severity bias**

  * low: prefer info/warning; do not emit violation unless confidence >= 0.85
  * medium: standard thresholds
  * high: allow violation at confidence >= 0.70
* **Deduplication**

  * merge observations with the same `span` + `standard_ref`, keeping highest confidence
* **Sorting**

  * violation first, then warning, then info
  * within each category, sort by confidence desc

Policy version string must be emitted.

---

## 6) Evaluation Harness

### Command

`python -m eval.runner --cases eval/cases --backend <name>`

### Required outputs

* schema validation pass/fail
* repeatability check (run same case N=5)

  * % stable spans
  * % stable severities
* latency stats (mean/p95)
* observation count stats

### Golden cases (minimum 8)

* clean content, should return 0–2 infos
* missing measurable verbs in objectives
* accessibility issue (reading level, jargon)
* conflicting statements (internal inconsistency)
* overly long paragraph structure issue
* ambiguous standard match case
* malformed input (too long, empty)
* missing standards set

---

## 7) Implementation Constraints

### Runtime

* FastAPI, single service
* sync or async is fine, but be consistent
* no database required
* standards stored on disk as JSON (demo), loaded at startup

### Logging

* structured logs with request_id
* log: standards_set, strictness, latency_ms, error codes

### Security (demo)

* include a dummy auth header check:

  * `Authorization: Bearer demo-token`
* reject missing/invalid with structured error

---

## 8) Demo-Ready Deliverables

Completion criteria:

1. `GET /v1/standards` returns sets
2. `POST /v1/review` returns valid structured observations in <1s for a 300-word input
3. strictness changes output behavior
4. evaluation harness runs and prints repeatability + latency

---

## 9) Suggested 48-hour build order

1. Pydantic schemas + API skeleton
2. Standards loader + retrieval (simple first)
3. Model call + strict JSON parsing
4. Policy layer + invariants
5. Eval harness + 8 cases
6. Tune retrieval/prompt for stability
7. Add 1 failure-mode demo case
8. README + diagram

---

## 10) Anticipated stakeholder questions

* “What happens when the model times out?”
* “Can we swap models without breaking integrations?”
* “How do you regression test behavior?”
* “How do you keep outputs stable enough for UI?”
* “How do you deploy this on-prem?”
