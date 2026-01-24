"""Prompt construction for the review model.

Defines the system prompt (enforces JSON output schema and observation rules)
and builds the user prompt with formatted rules, strictness instructions,
and the content to review.
"""

from ..schemas.standards import StandardRule

SYSTEM_PROMPT = """You are a content standards reviewer. You analyze instructional content against provided standards rules and return structured observations.

You MUST respond with raw JSON only. No markdown, no code fences, no explanation text.

Your response must match this exact schema:
{
  "observations": [
    {
      "span": [start_char, end_char] or null,
      "severity": "info" | "warning" | "violation",
      "category": "clarity" | "accuracy" | "structure" | "accessibility" | "pedagogy" | "compliance" | "other",
      "standard_ref": "the rule's standard_ref",
      "message": "clear description of the issue",
      "suggested_fix": "how to fix it" or null,
      "rationale": "why this is an issue per the standard" or null,
      "standard_excerpt": "relevant quote from the standard" or null,
      "confidence": 0.0 to 1.0
    }
  ]
}

Rules for observations:
- span must be [start, end] character offsets into the content where 0 <= start < end <= content_length, or null if not locatable
- severity: "violation" for clear breaches, "warning" for likely issues, "info" for suggestions
- confidence: how certain you are this is a real issue (0.0-1.0)
- standard_ref must exactly match one of the provided rules' standard_ref values
- Only report genuine issues. Do not fabricate problems.
- If the content fully complies with all provided rules, return {"observations": []}
"""


def build_user_prompt(
    content: str,
    rules: list[StandardRule],
    strictness: str,
) -> str:
    rules_text = "\n".join(f"- [{r.standard_ref}] {r.title}: {r.body}" for r in rules)

    strictness_instruction = {
        "low": "Be lenient. Only flag clear, unambiguous issues.",
        "medium": "Apply standard review criteria.",
        "high": "Be thorough and strict. Flag any potential issue, even minor ones.",
    }.get(strictness, "Apply standard review criteria.")

    return f"""## Standards Rules

{rules_text}

## Strictness

{strictness_instruction}

## Content to Review (length: {len(content)} characters)

{content}

## Instructions

Review the content above against the provided standards rules. Return your observations as JSON."""
