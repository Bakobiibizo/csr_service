from src.csr_service.engine.parser import extract_json, parse_model_output, validate_observation


class TestExtractJson:
    def test_direct_json(self):
        result = extract_json('{"observations": []}')
        assert result == {"observations": []}

    def test_code_fence(self):
        raw = '```json\n{"observations": []}\n```'
        result = extract_json(raw)
        assert result == {"observations": []}

    def test_brace_extraction(self):
        raw = 'Here is the result: {"observations": []} hope this helps'
        result = extract_json(raw)
        assert result == {"observations": []}

    def test_invalid_returns_none(self):
        assert extract_json("no json here") is None


class TestValidateObservation:
    def test_valid_observation(self):
        data = {
            "span": [0, 10],
            "severity": "warning",
            "category": "clarity",
            "standard_ref": "R-1",
            "message": "Issue found",
            "confidence": 0.8,
        }
        obs = validate_observation(data, 100, {"R-1"})
        assert obs is not None
        assert obs.standard_ref == "R-1"

    def test_unknown_ref_rejected(self):
        data = {
            "span": [0, 10],
            "severity": "warning",
            "category": "clarity",
            "standard_ref": "UNKNOWN",
            "message": "Issue",
            "confidence": 0.8,
        }
        obs = validate_observation(data, 100, {"R-1"})
        assert obs is None

    def test_invalid_span_nullified(self):
        data = {
            "span": [50, 200],
            "severity": "info",
            "category": "other",
            "standard_ref": "R-1",
            "message": "Issue",
            "confidence": 0.7,
        }
        obs = validate_observation(data, 100, {"R-1"})
        assert obs is not None
        assert obs.span is None

    def test_confidence_clamped(self):
        data = {
            "span": None,
            "severity": "info",
            "category": "other",
            "standard_ref": "R-1",
            "message": "Issue",
            "confidence": 1.5,
        }
        obs = validate_observation(data, 100, {"R-1"})
        assert obs is not None
        assert obs.confidence == 1.0

    def test_missing_message_rejected(self):
        data = {
            "severity": "info",
            "category": "other",
            "standard_ref": "R-1",
            "message": "",
            "confidence": 0.8,
        }
        obs = validate_observation(data, 100, {"R-1"})
        assert obs is None


class TestParseModelOutput:
    def test_valid_output(self):
        raw = '{"observations": [{"span": [0, 5], "severity": "warning", "category": "clarity", "standard_ref": "R-1", "message": "Test issue", "confidence": 0.8}]}'
        result = parse_model_output(raw, 100, {"R-1"})
        assert len(result) == 1

    def test_empty_observations(self):
        raw = '{"observations": []}'
        result = parse_model_output(raw, 100, {"R-1"})
        assert result == []

    def test_invalid_json(self):
        result = parse_model_output("not json", 100, {"R-1"})
        assert result == []

    def test_partial_salvage(self):
        raw = '{"observations": [{"span": [0, 5], "severity": "warning", "category": "clarity", "standard_ref": "R-1", "message": "Valid", "confidence": 0.8}, {"standard_ref": "BAD", "message": "Invalid", "severity": "info", "category": "other", "confidence": 0.5}]}'
        result = parse_model_output(raw, 100, {"R-1"})
        assert len(result) == 1
