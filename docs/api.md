# API Reference

Base URL: `http://localhost:9020`

## Authentication

All `/v1/review` requests require a bearer token:

```
Authorization: Bearer <token>
```

The token is configured via `CSR_AUTH_TOKEN` (default: `demo-token`). Health and standards endpoints do not require authentication.

---

## GET /health

Liveness and readiness probe.

**Response:**
```json
{
  "status": "ok",
  "standards_loaded": 1,
  "model_backend": "connected"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `status` | string | Always `"ok"` if service is running |
| `standards_loaded` | int | Number of standards sets loaded |
| `model_backend` | string | `"connected"` or `"unavailable"` |

---

## GET /v1/standards

Lists all available standards sets loaded at startup.

**Response:**
```json
{
  "standards_sets": [
    {
      "id": "naval_v3",
      "name": "Naval Training Standards v3",
      "version": "3.0"
    }
  ]
}
```

---

## POST /v1/review

Submit content for review against a standards set.

### Request

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `content` | string | yes | - | Instructional content to review |
| `standards_set` | string | yes | - | ID of standards set to use |
| `strictness` | enum | no | `"medium"` | `"low"`, `"medium"`, or `"high"` |
| `request_id` | string | no | auto-generated | Tracking ID for logs |
| `options` | object | no | defaults | Review options (see below) |

**Options:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `return_rationale` | bool | `true` | Include rationale in observations |
| `return_excerpts` | bool | `true` | Include standard_excerpt in observations |
| `max_observations` | int | `25` | Maximum observations to return (1-100) |
| `min_confidence` | float | `0.55` | Minimum confidence threshold (0.0-1.0) |

### Response

```json
{
  "observations": [...],
  "meta": {...},
  "errors": [...]
}
```

**Invariants:**
- `observations` is always present (may be empty)
- `errors` is always present (may be empty)
- Response always validates against the schema, even on model failure

### Observation Object

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Unique observation ID |
| `span` | `[int, int]` or `null` | Character offsets `[start, end)` into content |
| `severity` | enum | `"info"`, `"warning"`, or `"violation"` |
| `category` | enum | See categories below |
| `standard_ref` | string | References a rule in the standards set |
| `message` | string | Human-readable description of the issue |
| `suggested_fix` | string or null | How to resolve the issue |
| `rationale` | string or null | Why this is an issue per the standard |
| `standard_excerpt` | string or null | Relevant quote from the standard |
| `confidence` | float | Model's confidence in this observation (0.0-1.0) |

**Categories:** `clarity`, `accuracy`, `structure`, `accessibility`, `pedagogy`, `compliance`, `other`

**Span rules:**
- `0 <= start < end <= len(content)` or `null`
- Never omitted, always explicitly set

### Meta Object

| Field | Type | Description |
|-------|------|-------------|
| `request_id` | string | Tracking ID |
| `standards_set` | string | Standards set used |
| `strictness` | string | Strictness level applied |
| `policy_version` | string | Policy version applied |
| `model_id` | string | Model used for inference |
| `latency_ms` | int | Total processing time |
| `usage.input_tokens` | int | Tokens sent to model |
| `usage.output_tokens` | int | Tokens received from model |

### Error Object

| Field | Type | Description |
|-------|------|-------------|
| `code` | string | Machine-readable error code |
| `message` | string | Human-readable description |
| `details` | any or null | Additional context |

**Error codes:**

| Code | Description |
|------|-------------|
| `MODEL_FAILURE` | Model unreachable or returned an error |
| `MODEL_PARSE_FAILURE` | Model output could not be parsed into valid observations |

### HTTP Error Responses

| Status | Code | When |
|--------|------|------|
| 401 | `AUTH_FAILED` | Missing or invalid bearer token |
| 422 | `EMPTY_CONTENT` | Content is empty or whitespace-only |
| 422 | `CONTENT_TOO_LONG` | Content exceeds `CSR_MAX_CONTENT_LENGTH` |
| 422 | `STANDARDS_NOT_FOUND` | Requested standards set not loaded |
| 503 | `MODEL_UNAVAILABLE` | Model client not initialized |

---

## Strictness Behavior

Strictness affects both retrieval (how many rules to consider) and policy (how observations are filtered):

| Level | Rules Retrieved | Violation Threshold | Behavior |
|-------|----------------|---------------------|----------|
| `low` | 6 | confidence >= 0.85 | Lenient. Only clear issues. |
| `medium` | 10 | confidence >= 0.75 | Standard thresholds. |
| `high` | 14 | confidence >= 0.70 | Thorough. Flags minor issues. |

---

## Examples

### Minimal request

```bash
curl -X POST http://localhost:9020/v1/review \
  -H "Authorization: Bearer demo-token" \
  -H "Content-Type: application/json" \
  -d '{"content":"Test content.","standards_set":"naval_v3"}'
```

### Full request with options

```bash
curl -X POST http://localhost:9020/v1/review \
  -H "Authorization: Bearer demo-token" \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "review-001",
    "content": "The student will understand basic navigation principles and be familiar with chart reading.",
    "standards_set": "naval_v3",
    "strictness": "high",
    "options": {
      "return_rationale": true,
      "return_excerpts": true,
      "max_observations": 10,
      "min_confidence": 0.6
    }
  }'
```

### Strictness comparison

```bash
# Same content, different strictness levels:
for level in low medium high; do
  echo "=== $level ==="
  curl -s -X POST http://localhost:9020/v1/review \
    -H "Authorization: Bearer demo-token" \
    -H "Content-Type: application/json" \
    -d "{\"content\":\"The student will understand navigation.\",\"standards_set\":\"naval_v3\",\"strictness\":\"$level\"}" \
    | python3 -c "import sys,json; d=json.load(sys.stdin); print(f'Observations: {len(d[\"observations\"])}')"
done
```
