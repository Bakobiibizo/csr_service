import pytest
from pydantic import ValidationError

from src.csr_service.schemas.request import ReviewOptions, ReviewRequest
from src.csr_service.schemas.response import Meta, Observation, ReviewResponse
from src.csr_service.schemas.standards import StandardRule, StandardsSet


class TestReviewRequest:
    def test_defaults(self):
        req = ReviewRequest(content="test", standards_set="naval_v3")
        assert req.strictness == "medium"
        assert req.options.max_observations == 25
        assert req.options.min_confidence == 0.55

    def test_invalid_strictness(self):
        with pytest.raises(ValidationError):
            ReviewRequest(content="test", standards_set="s", strictness="extreme")

    def test_options_bounds(self):
        with pytest.raises(ValidationError):
            ReviewOptions(min_confidence=1.5)
        with pytest.raises(ValidationError):
            ReviewOptions(max_observations=0)


class TestObservation:
    def test_valid(self):
        obs = Observation(
            id="abc123",
            span=[0, 10],
            severity="warning",
            category="clarity",
            standard_ref="REF-1",
            message="Issue found",
            confidence=0.8,
        )
        assert obs.span == [0, 10]

    def test_null_span(self):
        obs = Observation(
            id="abc123",
            span=None,
            severity="info",
            category="other",
            standard_ref="REF-1",
            message="General issue",
            confidence=0.5,
        )
        assert obs.span is None

    def test_invalid_confidence(self):
        with pytest.raises(ValidationError):
            Observation(
                id="x",
                severity="info",
                category="other",
                standard_ref="R",
                message="m",
                confidence=1.5,
            )


class TestReviewResponse:
    def test_empty_response(self):
        resp = ReviewResponse(
            observations=[],
            meta=Meta(
                request_id="r1",
                standards_set="s",
                strictness="medium",
                policy_version="1.0.0",
                model_id="llama3",
            ),
            errors=[],
        )
        assert resp.observations == []
        assert resp.errors == []


class TestStandardsSet:
    def test_valid(self):
        ss = StandardsSet(
            standards_set="test",
            rules=[
                StandardRule(
                    standard_ref="T-1",
                    title="Title",
                    body="Body text",
                    tags=["tag1"],
                )
            ],
        )
        assert len(ss.rules) == 1
        assert ss.rules[0].severity_default == "warning"
