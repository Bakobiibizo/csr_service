# Rule and evidence contracts

Each standards file is startup-validated. Rule identifiers must be unique and every rule must contain a non-empty identifier, title, and normative body. A rule may declare `evidence` requirements:

```json
{"kind":"content_span","description":"Quote the text that violates the rule","required":true}
```

Kinds are `content_span`, `document`, and `metadata`. Existing standards default to one required content-span requirement, preserving backward compatibility.

Observations expose an `evidence` array with a kind, stable reference, optional character span, and optional excerpt. Model-produced observations remain untrusted until parser validation and deterministic policy processing. The current parser verifies span bounds and rule references; clients must treat missing evidence as reduced traceability, not as proof of compliance.

Provider calls are isolated behind `ModelClient.generate`. Evaluation selection, confidence gating, severity bias, deduplication, ordering, and truncation are deterministic. Provider temperature defaults to 0.1 and can be set to zero for stricter repeatability.

## Privacy boundary

The service sends content to the configured OpenAI-compatible provider. Deployers are responsible for that provider's retention policy and network boundary. The CSR service does not persist raw content. Its optional audit record contains timestamp, request ID, standards ID, content length, status, and a SHA-256 fingerprint only.
