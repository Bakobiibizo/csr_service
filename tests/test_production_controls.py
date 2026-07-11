import json

import pytest
from pydantic import ValidationError

from src.csr_service.auth import require_auth
from src.csr_service.config import settings
from src.csr_service.schemas.standards import StandardRule, StandardsSet


def test_duplicate_rule_references_are_rejected():
    rule = StandardRule(standard_ref="X-1", title="Rule", body="Do the thing")
    with pytest.raises(ValidationError):
        StandardsSet(standards_set="x", rules=[rule, rule])


@pytest.mark.asyncio
async def test_rotating_auth_tokens(monkeypatch):
    from fastapi.security import HTTPAuthorizationCredentials

    monkeypatch.setattr(settings, "auth_tokens", "old-token,new-token")
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="new-token")
    assert await require_auth(credentials) == "new-token"


def test_audit_does_not_persist_content(tmp_path, monkeypatch):
    from src.csr_service.routes.review import _audit
    from src.csr_service.schemas.request import ReviewRequest

    path = tmp_path / "audit.jsonl"
    monkeypatch.setattr(settings, "audit_log_path", str(path))
    body = ReviewRequest(content="private lesson", standards_set="naval_v3")
    _audit("request-1", body, "completed")
    raw = path.read_text()
    record = json.loads(raw)
    assert "private lesson" not in raw
    assert record["content_length"] == 14
    assert len(record["content_sha256"]) == 64
