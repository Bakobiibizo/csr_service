from unittest.mock import AsyncMock

import pytest

from src.csr_service.config import settings
from src.csr_service.engine.pipeline import run_review
from src.csr_service.schemas.request import ReviewOptions, ReviewRequest
from src.csr_service.schemas.response import Usage
from src.csr_service.schemas.standards import StandardRule, StandardsSet
from src.csr_service.standards.retriever import StandardsRetriever


@pytest.fixture
def standards_set():
    return StandardsSet(
        standards_set="test_v1",
        name="Test",
        version="1.0",
        rules=[
            StandardRule(
                standard_ref="T-1",
                title="Use measurable verbs",
                body="Objectives must use observable verbs.",
                tags=["objectives"],
            ),
            StandardRule(
                standard_ref="T-2",
                title="Define acronyms",
                body="Acronyms must be defined on first use.",
                tags=["acronyms"],
            ),
        ],
    )


@pytest.fixture
def retriever(standards_set):
    return StandardsRetriever(standards_set)


@pytest.fixture(autouse=True)
def force_multi_rule_mode():
    # Ensure tests run with multi-rule mode expectations
    original = settings.single_rule_mode
    settings.single_rule_mode = False
    yield
    settings.single_rule_mode = original


@pytest.fixture
def mock_model_client():
    client = AsyncMock()
    client.generate.return_value = (
        '{"observations": [{"span": [0, 20], "severity": "warning", "category": "pedagogy", "standard_ref": "T-1", "message": "Uses vague verb understand", "suggested_fix": "Use identify instead", "rationale": "Bloom taxonomy", "standard_excerpt": "Must use observable verbs", "confidence": 0.85}]}',
        Usage(input_tokens=200, output_tokens=80),
    )
    return client


class TestRunReview:
    async def test_successful_review(self, standards_set, retriever, mock_model_client):
        request = ReviewRequest(
            content="The student will understand navigation.",
            standards_set="test_v1",
            strictness="medium",
        )
        response = await run_review(request, standards_set, retriever, mock_model_client)

        assert len(response.observations) == 1
        assert response.observations[0].severity == "warning"
        assert response.observations[0].standard_ref == "T-1"
        assert response.meta.standards_set == "test_v1"
        assert response.meta.strictness == "medium"
        assert response.meta.latency_ms >= 0
        assert response.errors == []

    async def test_model_failure_returns_error(self, standards_set, retriever):
        client = AsyncMock()
        client.generate.side_effect = Exception("Model timeout")

        request = ReviewRequest(
            content="Some content.",
            standards_set="test_v1",
        )
        response = await run_review(request, standards_set, retriever, client)

        assert response.observations == []
        assert len(response.errors) == 1
        assert response.errors[0].code == "MODEL_FAILURE"
        assert "timeout" in response.errors[0].message.lower()

    async def test_parse_failure_returns_error(self, standards_set, retriever):
        client = AsyncMock()
        client.generate.return_value = (
            "This is not JSON at all, just prose.",
            Usage(input_tokens=100, output_tokens=30),
        )

        request = ReviewRequest(
            content="Some content here.",
            standards_set="test_v1",
        )
        response = await run_review(request, standards_set, retriever, client)

        assert response.observations == []
        assert len(response.errors) == 1
        assert response.errors[0].code == "MODEL_PARSE_FAILURE"

    async def test_empty_observations_no_error(self, standards_set, retriever):
        client = AsyncMock()
        client.generate.return_value = (
            '{"observations": []}',
            Usage(input_tokens=100, output_tokens=10),
        )

        request = ReviewRequest(
            content="Perfect content.",
            standards_set="test_v1",
        )
        response = await run_review(request, standards_set, retriever, client)

        assert response.observations == []
        assert response.errors == []

    async def test_strips_rationale_when_not_requested(
        self, standards_set, retriever, mock_model_client
    ):
        request = ReviewRequest(
            content="The student will understand navigation.",
            standards_set="test_v1",
            options=ReviewOptions(return_rationale=False),
        )
        response = await run_review(request, standards_set, retriever, mock_model_client)

        assert len(response.observations) == 1
        assert response.observations[0].rationale is None

    async def test_strips_excerpts_when_not_requested(
        self, standards_set, retriever, mock_model_client
    ):
        request = ReviewRequest(
            content="The student will understand navigation.",
            standards_set="test_v1",
            options=ReviewOptions(return_excerpts=False),
        )
        response = await run_review(request, standards_set, retriever, mock_model_client)

        assert len(response.observations) == 1
        assert response.observations[0].standard_excerpt is None

    async def test_keeps_rationale_when_requested(
        self, standards_set, retriever, mock_model_client
    ):
        request = ReviewRequest(
            content="The student will understand navigation.",
            standards_set="test_v1",
            options=ReviewOptions(return_rationale=True),
        )
        response = await run_review(request, standards_set, retriever, mock_model_client)

        assert response.observations[0].rationale == "Bloom taxonomy"

    async def test_usage_passed_through(self, standards_set, retriever, mock_model_client):
        request = ReviewRequest(
            content="Some content.",
            standards_set="test_v1",
        )
        response = await run_review(request, standards_set, retriever, mock_model_client)

        assert response.meta.usage.input_tokens == 200
        assert response.meta.usage.output_tokens == 80

    async def test_request_id_preserved(self, standards_set, retriever, mock_model_client):
        request = ReviewRequest(
            content="Content.",
            standards_set="test_v1",
            request_id="my-request-123",
        )
        response = await run_review(request, standards_set, retriever, mock_model_client)

        assert response.meta.request_id == "my-request-123"

    async def test_partial_observation_salvage(self, standards_set, retriever):
        client = AsyncMock()
        # One valid, one with unknown ref
        client.generate.return_value = (
            '{"observations": [{"span": [0, 5], "severity": "warning", "category": "clarity", "standard_ref": "T-1", "message": "Valid issue", "confidence": 0.8}, {"span": [0, 5], "severity": "info", "category": "other", "standard_ref": "UNKNOWN", "message": "Bad ref", "confidence": 0.7}]}',
            Usage(),
        )

        request = ReviewRequest(content="Hello", standards_set="test_v1")
        response = await run_review(request, standards_set, retriever, client)

        assert len(response.observations) == 1
        assert response.observations[0].standard_ref == "T-1"
        assert response.errors == []

    async def test_policy_applies_max_observations(self, standards_set, retriever):
        client = AsyncMock()
        # Return many observations
        obs_list = [
            f'{{"span": null, "severity": "info", "category": "other", "standard_ref": "T-1", "message": "Issue {i}", "confidence": 0.8}}'
            for i in range(20)
        ]
        client.generate.return_value = (
            '{"observations": [' + ",".join(obs_list) + "]}",
            Usage(),
        )

        request = ReviewRequest(
            content="Content.",
            standards_set="test_v1",
            options=ReviewOptions(max_observations=3),
        )
        response = await run_review(request, standards_set, retriever, client)

        assert len(response.observations) <= 3

    async def test_strictness_in_meta(self, standards_set, retriever, mock_model_client):
        request = ReviewRequest(
            content="Content.",
            standards_set="test_v1",
            strictness="high",
        )
        response = await run_review(request, standards_set, retriever, mock_model_client)

        assert response.meta.strictness == "high"
