import pytest
from fastapi.testclient import TestClient

from src.csr_service.config import settings
from src.csr_service.main import app
from src.csr_service.schemas.standards import StandardRule, StandardsSet
from src.csr_service.standards.retriever import StandardsRetriever


@pytest.fixture
def sample_rules() -> list[StandardRule]:
    return [
        StandardRule(
            standard_ref="TEST-1.1",
            title="Use measurable verbs",
            body="Objectives must use observable verbs like identify, demonstrate.",
            tags=["objectives", "measurable"],
            severity_default="violation",
        ),
        StandardRule(
            standard_ref="TEST-1.2",
            title="Define acronyms",
            body="All acronyms must be defined on first use.",
            tags=["acronyms", "accessibility"],
            severity_default="warning",
        ),
        StandardRule(
            standard_ref="TEST-1.3",
            title="Paragraph length",
            body="Paragraphs must not exceed 150 words.",
            tags=["structure", "length"],
            severity_default="info",
        ),
    ]


@pytest.fixture
def sample_standards_set(sample_rules) -> StandardsSet:
    return StandardsSet(
        standards_set="test_v1",
        name="Test Standards",
        version="1.0",
        rules=sample_rules,
    )


@pytest.fixture
def sample_retriever(sample_standards_set) -> StandardsRetriever:
    return StandardsRetriever(sample_standards_set)


@pytest.fixture
def mock_model_response():
    return '{"observations": [{"span": [0, 30], "severity": "warning", "category": "pedagogy", "standard_ref": "TEST-1.1", "message": "Uses vague verb understand", "suggested_fix": "Replace with identify or demonstrate", "rationale": "Bloom taxonomy requires measurable verbs", "standard_excerpt": null, "confidence": 0.82}]}'


@pytest.fixture
def client(monkeypatch, sample_standards_set, sample_retriever):
    # Patch settings for test
    monkeypatch.setattr(settings, "auth_token", "test-token")

    # Mock model client
    class MockModelClient:
        async def generate(self, system_prompt, user_prompt):
            from src.csr_service.schemas.response import Usage

            return (
                '{"observations": [{"span": [0, 30], "severity": "warning", "category": "pedagogy", "standard_ref": "TEST-1.1", "message": "Uses vague verb", "confidence": 0.82}]}',
                Usage(input_tokens=100, output_tokens=50),
            )

    app.state.standards_sets = {"test_v1": sample_standards_set}
    app.state.retrievers = {"test_v1": sample_retriever}
    app.state.model_client = MockModelClient()

    return TestClient(app)


AUTH_HEADER = {"Authorization": "Bearer test-token"}
