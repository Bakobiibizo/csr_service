class TestAuth:
    def test_no_auth_rejected(self, client):
        resp = client.post(
            "/v1/review",
            json={
                "content": "Test content.",
                "standards_set": "test_v1",
            },
        )
        assert resp.status_code == 401

    def test_wrong_token_rejected(self, client):
        resp = client.post(
            "/v1/review",
            json={
                "content": "Test content.",
                "standards_set": "test_v1",
            },
            headers={"Authorization": "Bearer wrong-token"},
        )
        assert resp.status_code == 401

    def test_valid_token_accepted(self, client):
        resp = client.post(
            "/v1/review",
            json={
                "content": "Test content here.",
                "standards_set": "test_v1",
            },
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200

    def test_health_no_auth_required(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_standards_no_auth_required(self, client):
        resp = client.get("/v1/standards")
        assert resp.status_code == 200
