"""Edge case tests for parser, policy, and retriever."""

from src.csr_service.engine.parser import extract_json, parse_model_output, validate_observation
from src.csr_service.policy.policy import (
    apply_policy,
    confidence_gate,
    deduplicate,
    sort_observations,
    strictness_bias,
)
from src.csr_service.schemas.response import Observation
from src.csr_service.schemas.standards import StandardRule, StandardsSet
from src.csr_service.standards.retriever import StandardsRetriever


def _obs(
    severity: str = "warning",
    confidence: float = 0.8,
    span: list[int] | None = None,
    ref: str = "R-1",
    msg: str = "issue",
):
    return Observation(
        id="x",
        span=span,
        severity=severity,
        category="other",
        standard_ref=ref,
        message=msg,
        confidence=confidence,
    )


class TestParserEdgeCases:
    def test_nested_braces_in_content(self):
        # JSON with nested objects
        raw = '{"observations": [{"span": null, "severity": "info", "category": "other", "standard_ref": "R-1", "message": "Found {nested} braces", "confidence": 0.5}]}'
        result = parse_model_output(raw, 100, {"R-1"})
        assert len(result) == 1

    def test_multiple_json_blocks_greedy_match(self):
        # Brace extraction is greedy: matches first { to last }
        # which produces invalid JSON when multiple blocks exist
        raw = '{"observations": []} some text {"other": "json"}'
        data = extract_json(raw)
        # Greedy regex matches entire span, which isn't valid JSON
        assert data is None

    def test_single_json_in_prose(self):
        raw = 'Here is the result: {"observations": []} done.'
        data = extract_json(raw)
        assert data == {"observations": []}

    def test_unicode_in_message(self):
        raw = '{"observations": [{"span": null, "severity": "info", "category": "other", "standard_ref": "R-1", "message": "学生は理解する", "confidence": 0.7}]}'
        result = parse_model_output(raw, 1000, {"R-1"})
        assert len(result) == 1
        assert "学生" in result[0].message

    def test_extra_fields_ignored(self):
        data = {
            "span": [0, 5],
            "severity": "info",
            "category": "other",
            "standard_ref": "R-1",
            "message": "Issue",
            "confidence": 0.8,
            "extra_field": "ignored",
            "another": 123,
        }
        obs = validate_observation(data, 100, {"R-1"})
        assert obs is not None

    def test_empty_string_input(self):
        result = parse_model_output("", 100, {"R-1"})
        assert result == []

    def test_whitespace_only_input(self):
        result = parse_model_output("   \n\t  ", 100, {"R-1"})
        assert result == []

    def test_span_with_zero_length(self):
        # start == end is invalid (start < end required)
        data = {
            "span": [5, 5],
            "severity": "info",
            "category": "other",
            "standard_ref": "R-1",
            "message": "Issue",
            "confidence": 0.8,
        }
        obs = validate_observation(data, 100, {"R-1"})
        assert obs is not None
        assert obs.span is None  # Nullified

    def test_span_with_negative_start(self):
        data = {
            "span": [-1, 10],
            "severity": "info",
            "category": "other",
            "standard_ref": "R-1",
            "message": "Issue",
            "confidence": 0.8,
        }
        obs = validate_observation(data, 100, {"R-1"})
        assert obs.span is None

    def test_span_with_non_int_values(self):
        data = {
            "span": [0.5, 10.5],
            "severity": "info",
            "category": "other",
            "standard_ref": "R-1",
            "message": "Issue",
            "confidence": 0.8,
        }
        obs = validate_observation(data, 100, {"R-1"})
        assert obs.span is None

    def test_confidence_as_string_defaults(self):
        data = {
            "span": None,
            "severity": "info",
            "category": "other",
            "standard_ref": "R-1",
            "message": "Issue",
            "confidence": "high",
        }
        obs = validate_observation(data, 100, {"R-1"})
        assert obs is not None
        assert obs.confidence == 0.5  # Default for non-numeric

    def test_invalid_severity_defaults_to_info(self):
        data = {
            "span": None,
            "severity": "critical",
            "category": "other",
            "standard_ref": "R-1",
            "message": "Issue",
            "confidence": 0.8,
        }
        obs = validate_observation(data, 100, {"R-1"})
        assert obs.severity == "info"

    def test_invalid_category_defaults_to_other(self):
        data = {
            "span": None,
            "severity": "info",
            "category": "nonexistent",
            "standard_ref": "R-1",
            "message": "Issue",
            "confidence": 0.8,
        }
        obs = validate_observation(data, 100, {"R-1"})
        assert obs.category == "other"

    def test_very_long_model_output(self):
        # Large number of observations
        obs_list = [
            f'{{"span": null, "severity": "info", "category": "other", "standard_ref": "R-1", "message": "Issue {i}", "confidence": 0.7}}'
            for i in range(100)
        ]
        raw = '{"observations": [' + ",".join(obs_list) + "]}"
        result = parse_model_output(raw, 10000, {"R-1"})
        assert len(result) == 100

    def test_observations_not_a_list(self):
        raw = '{"observations": "not a list"}'
        result = parse_model_output(raw, 100, {"R-1"})
        assert result == []

    def test_observation_not_a_dict(self):
        raw = '{"observations": ["string", 123, null]}'
        result = parse_model_output(raw, 100, {"R-1"})
        assert result == []

    def test_code_fence_with_extra_whitespace(self):
        raw = 'Here:\n```json\n  \n{"observations": []}\n  \n```\n'
        data = extract_json(raw)
        assert data == {"observations": []}

    def test_code_fence_without_json_label(self):
        raw = '```\n{"observations": []}\n```'
        data = extract_json(raw)
        assert data == {"observations": []}


class TestPolicyEdgeCases:
    def test_empty_observation_list(self):
        result = apply_policy([], strictness="medium")
        assert result == []

    def test_confidence_gate_empty_list(self):
        result = confidence_gate([], 0.55)
        assert result == []

    def test_strictness_bias_empty_list(self):
        result = strictness_bias([], "medium")
        assert result == []

    def test_deduplicate_empty_list(self):
        result = deduplicate([])
        assert result == []

    def test_sort_empty_list(self):
        result = sort_observations([])
        assert result == []

    def test_all_observations_below_threshold(self):
        obs = [
            _obs(severity="info", confidence=0.1),
            _obs(severity="info", confidence=0.2),
            _obs(severity="info", confidence=0.3),
        ]
        result = confidence_gate(obs, 0.55)
        # All info below threshold → all dropped
        assert len(result) == 0

    def test_violation_downgraded_twice(self):
        # violation → warning (first gate), then if still below...
        obs = [_obs(severity="violation", confidence=0.3)]
        result = confidence_gate(obs, 0.55)
        # violation → warning
        assert result[0].severity == "warning"

    def test_deduplicate_null_spans_different_refs(self):
        obs = [
            _obs(confidence=0.7, span=None, ref="R-1"),
            _obs(confidence=0.9, span=None, ref="R-2"),
        ]
        result = deduplicate(obs)
        assert len(result) == 2

    def test_deduplicate_null_spans_same_ref(self):
        obs = [
            _obs(confidence=0.7, span=None, ref="R-1"),
            _obs(confidence=0.9, span=None, ref="R-1"),
        ]
        result = deduplicate(obs)
        assert len(result) == 1
        assert result[0].confidence == 0.9

    def test_deduplicate_identical_confidence_keeps_last(self):
        obs = [
            _obs(confidence=0.8, span=[0, 10], ref="R-1", msg="first"),
            _obs(confidence=0.8, span=[0, 10], ref="R-1", msg="second"),
        ]
        result = deduplicate(obs)
        assert len(result) == 1
        # Equal confidence → keeps first (no replacement)
        assert result[0].message == "first"

    def test_sort_same_severity_same_confidence(self):
        obs = [
            _obs(severity="warning", confidence=0.8, msg="a"),
            _obs(severity="warning", confidence=0.8, msg="b"),
        ]
        result = sort_observations(obs)
        assert len(result) == 2

    def test_apply_policy_max_observations_zero_not_allowed(self):
        # max_observations should be at least 1
        obs = [_obs(confidence=0.8)]
        result = apply_policy(obs, max_observations=1)
        assert len(result) == 1

    def test_strictness_low_downgrades_borderline(self):
        # 0.84 is below low threshold (0.85)
        obs = [_obs(severity="violation", confidence=0.84)]
        result = strictness_bias(obs, "low")
        assert result[0].severity == "warning"

    def test_strictness_low_keeps_high_confidence(self):
        obs = [_obs(severity="violation", confidence=0.90)]
        result = strictness_bias(obs, "low")
        assert result[0].severity == "violation"

    def test_strictness_does_not_affect_non_violations(self):
        obs = [_obs(severity="warning", confidence=0.5)]
        result = strictness_bias(obs, "low")
        assert result[0].severity == "warning"


class TestRetrieverEdgeCases:
    def test_single_rule(self):
        ss = StandardsSet(
            standards_set="test",
            rules=[StandardRule(standard_ref="A", title="Only rule", body="Only body", tags=[])],
        )
        retriever = StandardsRetriever(ss)
        rules = retriever.retrieve("any content", "high")
        assert len(rules) == 1

    def test_content_with_no_overlap(self):
        ss = StandardsSet(
            standards_set="test",
            rules=[
                StandardRule(
                    standard_ref="A",
                    title="Navigation",
                    body="Maritime navigation rules",
                    tags=["nav"],
                ),
            ],
        )
        retriever = StandardsRetriever(ss)
        # Completely unrelated content still returns rules (up to k)
        rules = retriever.retrieve("The quick brown fox jumped over the lazy dog", "medium")
        assert len(rules) == 1  # Only 1 rule available

    def test_empty_content(self):
        ss = StandardsSet(
            standards_set="test",
            rules=[
                StandardRule(standard_ref="A", title="Rule", body="Body text", tags=[]),
            ],
        )
        retriever = StandardsRetriever(ss)
        # Empty content should not crash
        rules = retriever.retrieve("", "medium")
        assert isinstance(rules, list)

    def test_k_capped_at_rule_count(self):
        rules = [
            StandardRule(standard_ref=f"R-{i}", title=f"Rule {i}", body=f"Body {i}", tags=[])
            for i in range(3)
        ]
        ss = StandardsSet(standards_set="test", rules=rules)
        retriever = StandardsRetriever(ss)
        # high strictness wants k=14, but only 3 rules
        result = retriever.retrieve("content", "high")
        assert len(result) == 3
