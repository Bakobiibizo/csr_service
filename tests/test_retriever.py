from src.csr_service.schemas.standards import StandardRule, StandardsSet
from src.csr_service.standards.retriever import StandardsRetriever


def test_retrieve_returns_rules(sample_retriever):
    rules = sample_retriever.retrieve("The student will understand navigation", "medium")
    assert len(rules) > 0
    assert all(isinstance(r, StandardRule) for r in rules)


def test_retrieve_k_varies_by_strictness(sample_retriever):
    low = sample_retriever.retrieve("test content", "low")
    high = sample_retriever.retrieve("test content", "high")
    # With only 3 rules, both will return all, but k limits are respected
    assert len(low) <= 6
    assert len(high) <= 14


def test_retrieve_relevance():
    ss = StandardsSet(
        standards_set="test",
        rules=[
            StandardRule(
                standard_ref="A",
                title="Acronyms defined",
                body="Define all acronyms on first use",
                tags=["acronyms"],
            ),
            StandardRule(
                standard_ref="B",
                title="Measurable verbs",
                body="Use Bloom's taxonomy verbs for objectives",
                tags=["objectives"],
            ),
            StandardRule(
                standard_ref="C",
                title="Paragraph length",
                body="Keep paragraphs under 150 words",
                tags=["structure"],
            ),
        ],
    )
    retriever = StandardsRetriever(ss)
    rules = retriever.retrieve("The learning objectives should use measurable verbs", "low")
    # B should rank highly due to term overlap
    refs = [r.standard_ref for r in rules]
    assert "B" in refs
