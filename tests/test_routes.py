from tests.conftest import AUTH_HEADER


class TestHealthRoute:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["standards_loaded"] == 1


class TestStandardsRoute:
    def test_list_standards(self, client):
        resp = client.get("/v1/standards")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["standards_sets"]) == 1
        assert data["standards_sets"][0]["id"] == "test_v1"


class TestReviewRoute:
    def test_review_success(self, client):
        resp = client.post(
            "/v1/review",
            json={
                "content": "The student will understand basic navigation principles.",
                "standards_set": "test_v1",
                "strictness": "medium",
            },
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "observations" in data
        assert "meta" in data
        assert "errors" in data
        assert data["meta"]["standards_set"] == "test_v1"

    def test_review_missing_standards(self, client):
        resp = client.post(
            "/v1/review",
            json={
                "content": "Some content here.",
                "standards_set": "nonexistent",
            },
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "STANDARDS_NOT_FOUND"

    def test_review_empty_content(self, client):
        resp = client.post(
            "/v1/review",
            json={
                "content": "   ",
                "standards_set": "test_v1",
            },
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "EMPTY_CONTENT"

    def test_review_content_too_long(self, client, monkeypatch):
        from src.csr_service.config import settings

        monkeypatch.setattr(settings, "max_content_length", 50)
        resp = client.post(
            "/v1/review",
            json={
                "content": "x" * 100,
                "standards_set": "test_v1",
            },
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 422
        assert resp.json()["detail"]["code"] == "CONTENT_TOO_LONG"

    def test_review_response_schema(self, client):
        resp = client.post(
            "/v1/review",
            json={
                "content": "The student will understand navigation.",
                "standards_set": "test_v1",
                "strictness": "high",
                "options": {"max_observations": 10},
            },
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["observations"], list)
        assert isinstance(data["errors"], list)
        assert "latency_ms" in data["meta"]
