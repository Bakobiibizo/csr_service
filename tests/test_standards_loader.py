import json
import tempfile
from pathlib import Path

from src.csr_service.standards.loader import load_standards


def test_load_standards_from_dir():
    with tempfile.TemporaryDirectory() as tmpdir:
        data = {
            "standards_set": "test_set",
            "name": "Test",
            "version": "1.0",
            "rules": [
                {
                    "standard_ref": "T-1",
                    "title": "Rule 1",
                    "body": "Description of rule 1",
                    "tags": ["test"],
                }
            ],
        }
        Path(tmpdir, "test.json").write_text(json.dumps(data))

        result = load_standards(tmpdir)
        assert "test_set" in result
        assert len(result["test_set"].rules) == 1


def test_load_standards_missing_dir():
    result = load_standards("/nonexistent/path")
    assert result == {}


def test_load_standards_invalid_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        Path(tmpdir, "bad.json").write_text("not json")
        result = load_standards(tmpdir)
        assert result == {}
