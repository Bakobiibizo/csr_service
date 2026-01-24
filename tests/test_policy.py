from src.csr_service.policy.policy import (
    apply_policy,
    confidence_gate,
    deduplicate,
    sort_observations,
    strictness_bias,
)
from src.csr_service.schemas.response import Observation


def _obs(severity="warning", confidence=0.8, span=None, ref="R-1", msg="issue"):
    return Observation(
        id="x",
        span=span,
        severity=severity,
        category="other",
        standard_ref=ref,
        message=msg,
        confidence=confidence,
    )


class TestConfidenceGate:
    def test_above_threshold_kept(self):
        obs = [_obs(confidence=0.9)]
        result = confidence_gate(obs, 0.55)
        assert len(result) == 1
        assert result[0].severity == "warning"

    def test_below_threshold_downgraded(self):
        obs = [_obs(severity="violation", confidence=0.4)]
        result = confidence_gate(obs, 0.55)
        assert len(result) == 1
        assert result[0].severity == "warning"

    def test_info_below_threshold_dropped(self):
        obs = [_obs(severity="info", confidence=0.3)]
        result = confidence_gate(obs, 0.55)
        assert len(result) == 0


class TestStrictnessBias:
    def test_low_blocks_low_confidence_violation(self):
        obs = [_obs(severity="violation", confidence=0.75)]
        result = strictness_bias(obs, "low")
        assert result[0].severity == "warning"

    def test_high_allows_lower_confidence_violation(self):
        obs = [_obs(severity="violation", confidence=0.72)]
        result = strictness_bias(obs, "high")
        assert result[0].severity == "violation"


class TestDeduplicate:
    def test_same_span_and_ref_keeps_highest(self):
        obs = [
            _obs(confidence=0.7, span=[0, 10], ref="R-1"),
            _obs(confidence=0.9, span=[0, 10], ref="R-1"),
        ]
        result = deduplicate(obs)
        assert len(result) == 1
        assert result[0].confidence == 0.9

    def test_different_refs_kept(self):
        obs = [
            _obs(confidence=0.7, span=[0, 10], ref="R-1"),
            _obs(confidence=0.9, span=[0, 10], ref="R-2"),
        ]
        result = deduplicate(obs)
        assert len(result) == 2


class TestSortObservations:
    def test_severity_order(self):
        obs = [
            _obs(severity="info", confidence=0.9),
            _obs(severity="violation", confidence=0.8),
            _obs(severity="warning", confidence=0.85),
        ]
        result = sort_observations(obs)
        assert [o.severity for o in result] == ["violation", "warning", "info"]

    def test_confidence_within_severity(self):
        obs = [
            _obs(severity="warning", confidence=0.7),
            _obs(severity="warning", confidence=0.9),
        ]
        result = sort_observations(obs)
        assert result[0].confidence == 0.9


class TestApplyPolicy:
    def test_truncates_to_max(self):
        obs = [_obs(confidence=0.8, ref=f"R-{i}") for i in range(30)]
        result = apply_policy(obs, max_observations=5)
        assert len(result) == 5
