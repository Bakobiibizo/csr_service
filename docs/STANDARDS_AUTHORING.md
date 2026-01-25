# Standards Authoring Guide

This guide explains how to create and add custom standards sets to the Content Search and Review (CSR) Service.

## File Format

Standards are JavaScript Object Notation (JSON) files placed in the `standards/` directory. Each file defines one standards set containing multiple rules.

```json
{
  "standards_set": "my_standards_v1",
  "name": "My Standards Set",
  "version": "1.0",
  "rules": [...]
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `standards_set` | string | yes | Unique identifier (used in API requests) |
| `name` | string | no | Human-readable name |
| `version` | string | no | Version string (default: `"1.0"`) |
| `rules` | array | yes | List of rule objects |

## Rule Format

```json
{
  "standard_ref": "MY-STD-1.2.3",
  "title": "Short descriptive title",
  "body": "Detailed explanation of what this rule requires...",
  "tags": ["keyword1", "keyword2"],
  "severity_default": "warning"
}
```

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `standard_ref` | string | yes | Stable reference ID (returned in observations) |
| `title` | string | yes | Concise rule name |
| `body` | string | yes | Full rule description the model uses for evaluation |
| `tags` | array | no | Keywords for TF-IDF retrieval boosting |
| `severity_default` | enum | no | `"info"`, `"warning"`, or `"violation"` (default: `"warning"`) |

## Writing Effective Rules

### Title

Keep it concise and action-oriented. The title appears in retrieval results alongside the body.

- Good: "Learning objectives must be measurable"
- Bad: "Rule about objectives"

### Body

The body is the primary text the model uses to evaluate content. Write it as a clear requirement statement:

- State what is required or prohibited
- Include specific examples of compliance/non-compliance where helpful
- Use concrete language (avoid vague qualifiers)
- Keep under ~200 words for best retrieval performance

### Tags

Tags improve Term Frequency-Inverse Document Frequency (TF-IDF) retrieval. Include:
- Topic keywords (`objectives`, `safety`, `procedures`)
- Synonyms for key concepts
- Related domain terms

The retriever builds its index from `title + body + tags`, so tags help surface rules for content that uses different terminology than the rule body.

### Severity Default

This is a hint to the model about the rule's importance:

- `violation` - Critical requirements; non-compliance is a clear failure
- `warning` - Important best practices; non-compliance should be flagged
- `info` - Suggestions and recommendations; nice to have

The model may override this based on context, and the policy layer further adjusts severity based on confidence and strictness.

## Retrieval Behavior

The TF-IDF retriever selects rules based on term overlap between the content and rule text. Rules are ranked by cosine similarity, and the top-k are sent to the model:

- **low strictness**: top 6 rules
- **medium strictness**: top 10 rules
- **high strictness**: top 14 rules

If your standards set has fewer rules than k, all rules are always sent.

### Tips for retrieval

- Use the same terminology in rule bodies that authors typically use in content
- If a rule should trigger on specific keywords, include those keywords in the body or tags
- Broad rules (e.g., "paragraphs must be under 150 words") will match most content; narrow rules (e.g., "safety warnings must precede hazardous steps") only match relevant content

## Example: Complete Standards Set

```json
{
  "standards_set": "writing_v1",
  "name": "Technical Writing Standards",
  "version": "1.0",
  "rules": [
    {
      "standard_ref": "WRT-1.1",
      "title": "Use active voice",
      "body": "Sentences should use active voice. Passive voice obscures the actor and makes instructions unclear. Exception: when the actor is unknown or unimportant.",
      "tags": ["voice", "active", "passive", "clarity"],
      "severity_default": "info"
    },
    {
      "standard_ref": "WRT-1.2",
      "title": "Define acronyms on first use",
      "body": "All acronyms must be spelled out in full on first occurrence, with the acronym in parentheses. Subsequent uses may use the acronym alone.",
      "tags": ["acronyms", "abbreviations", "definitions"],
      "severity_default": "warning"
    },
    {
      "standard_ref": "WRT-2.1",
      "title": "One instruction per step",
      "body": "Each numbered step in a procedure must contain exactly one action. Do not combine multiple actions into a single step. If actions must occur simultaneously, state this explicitly.",
      "tags": ["procedures", "steps", "instructions"],
      "severity_default": "warning"
    }
  ]
}
```

## Deploying

1. Create your JSON file in `standards/`
2. Restart the service (standards are loaded at startup)
3. Verify with `GET /v1/standards` - your set should appear in the list
4. Test with a review request using your `standards_set` ID
