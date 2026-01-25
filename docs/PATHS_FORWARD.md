# Paths Forward

Practical improvements to the Content Standards Review (CSR) service, ordered by effort and impact. This document outlines pragmatic extensions to the existing architecture based on prior experience operating similar systems.

---

## Quick Wins (config/infra only)

### Response Caching Layer

**Problem**: Identical content + rules + strictness produces the same review every time, but still burns a full model call (~18s for 27B models).

**Solution**: Hash-based cache keyed on `(content_hash, standards_set, strictness, model_id, policy_version)`.

```
Request → hash(content + rules + strictness, model_id, prompt_version, policy_version) → cache lookup
  ├─ HIT  → return cached ReviewResponse (latency: <5ms)
  └─ MISS → run pipeline → store result → return
```

**Implementation options**:

| Option | Persistence | Latency | Dependencies |
|--------|-------------|---------|--------------|
| In-memory Least Recently Used (LRU) cache (`functools.lru_cache` or `cachetools.TTLCache`) | Process lifetime | ~0ms | None |
| Redis | Across restarts | ~1ms | Redis server |
| SQLite | Disk-persistent | ~2ms | None (stdlib) |

**Cache invalidation triggers**:
- `policy_version` bump (config change)
- Standards file modification (file watcher or manual flush)
- Time-to-Live (TTL) expiry (configurable, e.g. 24h)

**Where it goes**: New module `src/csr_service/engine/cache.py`, called at the top of `pipeline.py:run_review()` before retrieval.

**Estimated impact**: Eliminates model latency for repeated reviews. Common in editorial workflows where the same content is re-checked during revision cycles.

---

### Request Batching

**Problem**: Each review request waits for its own model call. Multiple concurrent requests queue sequentially at the model.

**Solution**: Collect requests arriving within a short window (50-100ms), batch them into a single model call with multiple content blocks, then fan out responses.

**Where it goes**: Wrap `model_client.py:generate()` with an async batcher (e.g. `asyncio.Queue` + periodic flush).

**Tradeoff**: Adds latency for the first request in a batch window. Only worthwhile under concurrent load.

---

## Medium Effort (new modules, same architecture)

### Vector Embedding Retrieval

**Problem**: TF-IDF matches on lexical overlap. Rules about "learner engagement" won't retrieve for content about "student motivation" because the words differ. Retrieval quality degrades with abstract/conceptual rules.

**Solution**: Augment or replace TF-IDF with dense vector embeddings. Encode rules and queries into the same embedding space, retrieve by cosine similarity on dense vectors.

```
Current:  content → TF-IDF vectorize → cosine_similarity(sparse, sparse) → top-k rules
Proposed: content → embed(content) → cosine_similarity(dense, dense) → top-k rules
```

**Architecture**:

```
┌─────────────────────────────────────────────────┐
│  EmbeddingRetriever                             │
│                                                 │
│  init:                                          │
│    rules[] → embed_batch(rule_texts) → matrix   │
│                                                 │
│  retrieve(content, strictness):                 │
│    query_vec = embed(content)                   │
│    scores = cosine_sim(query_vec, matrix)       │
│    return top_k(scores, k_by_strictness)        │
└─────────────────────────────────────────────────┘
```

**Embedding options**:

| Option | Dim | Speed | Quality | Dependencies |
|--------|-----|-------|---------|--------------|
| Ollama embeddings (`nomic-embed-text`) | 768 | ~50ms | Good | Already have Ollama |
| `sentence-transformers` (local) | 384-1024 | ~20ms | Very good | ~500MB model download |
| OpenAI `text-embedding-3-small` | 1536 | ~100ms | Excellent | API key + network |

**Recommended approach**: Use Ollama's `/api/embeddings` endpoint for local embedding since the infrastructure already exists. 
When moving to production I recommend upgrading to `sentence-transformers` for better quality.
Store the embedding matrix in memory (same as current TF-IDF matrix). For larger rule sets (>500 rules), persist to a vector store like `ChromaDB` or `Qdrant`.

**Vector storage for scale**:

| Store | Use case | Overhead |
|-------|----------|----------|
| NumPy matrix in memory | <500 rules | None |
| ChromaDB (embedded) | 500-10K rules, persistence needed | `pip install chromadb` |
| Qdrant (server) | >10K rules, multi-tenant | Container deployment |
| pgvector (Postgres) | Already using Postgres | Extension install |

**Interface change**: None. `StandardsRetriever` already returns `list[StandardRule]`. Swap the implementation, keep the interface.

**Where it goes**: New class `EmbeddingRetriever` in `src/csr_service/standards/retriever.py` (or a new file), selected by config flag. Keep TF-IDF as fallback for zero-dependency deployments.

---

### Multi-Step Orchestrator

**Problem**: Single model call does retrieval-augmented analysis in one shot. Complex rules requiring reasoning chains (cross-reference validation, structural analysis, multi-paragraph coherence) produce low-quality observations because the model can't "think" step by step.

**Solution**: Break the review into discrete reasoning stages with intermediate validation.

**Proposed pipeline**:

```
Step 1: CLASSIFY
  Input:  content + rule summaries
  Output: { relevant_rules: [refs], content_type: str, complexity: low|medium|high }
  Purpose: Pre-filter rules, determine pipeline depth

Step 2: ANALYZE (per-rule or batched)
  Input:  content + single rule (or small rule group)
  Output: { findings: [{ span, issue, severity, confidence }] }
  Purpose: Deep analysis with full rule context, no schema pressure

Step 3: STRUCTURE
  Input:  raw findings from step 2
  Output: { observations: [...] } (final schema)
  Purpose: Deduplicate, assign categories, format for API response
```

**Benefits**:
- Each step has a simpler task → higher quality per step
- Step 1 reduces wasted compute (skip irrelevant rules)
- Step 2 can run in parallel across rule groups
- Step 3 handles schema compliance separately from analysis

**Latency tradeoff**:

| Mode | Calls | Latency (27B) | Quality |
|------|-------|---------------|---------|
| Current single-shot | 1 | ~18s | Baseline |
| 3-step sequential | 3 | ~45s | Higher |
| 3-step with parallel step 2 | 1 + N + 1 | ~25s | Higher |
| 2-step (analyze + structure) | 2 | ~30s | Moderate improvement |

**Where it goes**: New orchestrator in `src/csr_service/engine/pipeline.py` (or `orchestrator.py`), selectable by request option or config flag. Keep single-shot as the default for latency-sensitive use.

**Config addition** (`config/policy.yaml`):
```yaml
pipeline:
  mode: single_shot  # single_shot | two_step | multi_step
  parallel_analysis: true
  max_parallel_rules: 5
```

---

### Streaming Response

**Problem**: The current synchronous Application Programming Interface (API) produces 18–45 seconds of silence before the client receives any data. This creates poor User Experience (UX) for interactive workflows and provides no visibility into system progress during long-running reviews.

**Solution**: Introduce a streaming endpoint using Server-Sent Events (SSE) that emits progress and observations incrementally as the pipeline advances.

```
POST /v1/review/stream
→ event: progress   data: {"stage": "retrieving", "rules_matched": 12}
→ event: progress   data: {"stage": "analyzing", "rules_processed": 4, "total": 12}
→ event: observation data: {"id": "abc", "severity": "violation", ...}
→ event: observation data: {"id": "def", "severity": "warning", ...}
→ event: complete   data: {"meta": {...}, "total_observations": 5}
```
This allows clients to render partial results, show live progress, and fail fast if needed, without waiting for full pipeline completion.

**Implementation notes**: The streaming route would live alongside the existing synchronous endpoint (e.g. POST /v1/review/stream) and be implemented via FastAPI’s StreamingResponse. The architecture already lends itself to this model, as the review pipeline is explicitly staged (retrieval → analysis → parsing → policy), making it straightforward to emit events at step boundaries.

**Where it goes**: New route `routes/review.py` with `StreamingResponse`. Pairs naturally with the multi-step orchestrator (stream after each step 2 completion).

**Recommendation**: Although streaming is often deferred in early API designs, I recommend implementing this early rather than retrofitting it later. Streaming has a significant impact on API surface area, response schemas, client expectations, and internal orchestration boundaries. I have previously implemented this change, and the backend changes were conceptually straightforward but required touching many parts of the codebase once the synchronous contract had already solidified.

Designing for streaming from the outset avoids backfilling these assumptions later and results in a cleaner, more adaptable API overall.
---

### Document Ingestion

**Problem**: Currently, the system only accepts raw text input. For production use, we need to support structured document formats (PDF, DOCX, etc.) and extract text content reliably.

**Solution**: Implement a document ingestion pipeline that:
- Supports multiple document formats (PDF, DOCX, etc.)
- Extracts text content with proper formatting preservation
- Handles images, tables, and other rich content
- Provides fallback mechanisms for complex documents
- Maintains document structure and metadata
- Has a low failure rate for common document types

**Implementation notes**: This would involve adding document processing libraries (e.g., PyPDF2, python-docx) and ideally integrating with Object Classification and Recognition (OCR) for scanned documents and images. The extracted content would then be processed through the existing review pipeline.

**Where it goes**: New module `src/csr_service/document_ingestion/` with format-specific processors and a unified ingestion interface.

## Higher Effort (architectural changes)

### Rule Hierarchy and Conditional Applicability

**Problem**: Flat `StandardRule` list can't express "rule A only applies to procedural content" or "rule B supersedes rule C when both match."

**Solution**: Extend the standards schema:

```json
{
  "standard_ref": "NAV-301",
  "title": "...",
  "body": "...",
  "applies_to": ["procedural", "assessment"],
  "requires": ["NAV-101"],
  "supersedes": ["NAV-300"],
  "parent_ref": "NAV-3XX",
  "weight": 1.5
}
```

**Impact**: Changes standards schema, retriever (filter by applicability), prompt construction (include dependency context), and policy (handle supersedes/weight).

---

### Structured Content Addressing

**Problem**: `span: [start, end]` assumes flat text. Real content has structure (headings, lists, tables, embedded media).

**Solution**: Replace character spans with structural addresses:

```json
{
  "location": {
    "type": "paragraph",
    "index": 3,
    "char_range": [12, 45]
  }
}
```

Or for multi-field documents:
```json
{
  "location": {
    "field": "body",
    "paragraph": 3,
    "sentence": 2
  }
}
```

**Impact**: Request schema (accept structured input), response schema (new location model), prompt (teach model the addressing scheme), parser (validate new structure), frontend rendering.

---

### Multi-Model Ensemble

**Problem**: Single model has blind spots. Different models catch different issues.

**Solution**: Run 2-3 models in parallel, merge observations with confidence boosting for agreement.

```
content → ┬─ Model A (large, slow) ─────┐
           ├─ Model B (fast, specialized) ─┤─ merge + boost → final observations
           └─ Model C (different family) ──┘
```

**Merge strategy**:
- Same span + same rule → boost confidence by 0.15 per agreeing model
- Unique findings → keep at original confidence
- Conflicting severity → use highest-confidence model's judgment

**Where it goes**: New `ensemble.py` module. Config selects models and merge strategy.

---

### Feedback Loop and Active Learning

**Problem**: No mechanism to improve over time. Model makes the same mistakes repeatedly.

**Solution**: Collect user feedback (accept/reject/edit observations), use it to:
1. Build few-shot examples per rule and explicitly include error cases in prompts
2. Fine-tune severity/confidence calibration in policy layer
3. Track responses and identify patterns in low-quality and high-quality observations

**Storage**: Lightweight SQLite or Postgres table:
```sql
CREATE TABLE feedback (
    observation_id TEXT,
    standard_ref TEXT,
    user_action TEXT,  -- accept, reject, edit
    corrected_severity TEXT,
    timestamp DATETIME
);
```

**Where it goes**: New route `POST /v1/feedback`, new module `src/csr_service/feedback/`, prompt builder reads top-N examples per rule.

---

## Recommended Priority

For immediate impact with minimal risk:

1. **Response caching** — eliminates redundant model calls, near-zero implementation risk
2. **Vector embeddings** — direct quality improvement for retrieval, drop-in interface replacement
3. **Two-step pipeline** (analyze → structure) — meaningful quality gain without full multi-step complexity
4. **Streaming** — UX improvement, pairs with step 3

For longer-term investment:

5. **Rule hierarchy** — enables complex standards modeling
6. **Feedback loop** — enables continuous improvement
7. **Multi-model ensemble** — diminishing returns unless models are significantly different
