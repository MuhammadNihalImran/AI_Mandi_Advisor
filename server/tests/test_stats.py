"""
Tests for GET /api/stats – in-memory request statistics.
"""

import pytest

URL = "/api/stats"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
class TestStatsHappyPath:

    def test_returns_200(self, client):
        r = client.get(URL)
        assert r.status_code == 200

    def test_schema_keys(self, client):
        r = client.get(URL)
        data = r.json()
        expected = {
            "total_requests",
            "total_errors",
            "error_rate_pct",
            "avg_response_time_ms",
            "min_response_time_ms",
            "max_response_time_ms",
        }
        assert set(data.keys()) == expected

    def test_zero_initially(self, client):
        """Stats are reset to zero before each test (conftest)."""
        r = client.get(URL)
        data = r.json()
        assert data["total_requests"] == 0
        assert data["total_errors"] == 0
        assert data["avg_response_time_ms"] == 0.0

    def test_counts_requests(self, client):
        """Making requests should increment total_requests."""
        # Make a few requests first
        client.get("/api/health")
        client.get("/api/health")
        client.get("/")

        r = client.get(URL)
        data = r.json()
        # 3 requests above + this stats request itself = at least 4
        assert data["total_requests"] >= 3

    def test_counts_errors(self, client):
        """4xx/5xx responses should increment total_errors."""
        # Trigger a validation error (422)
        client.post("/api/predict", json={"temperature": "bad"})

        r = client.get(URL)
        data = r.json()
        assert data["total_errors"] >= 1

    def test_response_time_tracked(self, client):
        """avg_response_time_ms should be > 0 after requests."""
        client.get("/api/health")
        client.get("/api/health")

        r = client.get(URL)
        data = r.json()
        assert data["avg_response_time_ms"] > 0
        assert data["min_response_time_ms"] > 0
        assert data["max_response_time_ms"] >= data["min_response_time_ms"]

    def test_error_rate_calculation(self, client):
        """error_rate_pct should reflect ratio of errors to total."""
        # 2 good requests
        client.get("/api/health")
        client.get("/api/health")
        # 1 bad request (422)
        client.post("/api/predict", json={"temperature": "bad"})

        r = client.get(URL)
        data = r.json()
        # At this point we have 3+ requests, at least 1 error
        assert data["error_rate_pct"] > 0
        assert data["error_rate_pct"] <= 100


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestStatsEdgeCases:

    def test_security_headers_present(self, client):
        r = client.get(URL)
        assert r.headers.get("x-content-type-options") == "nosniff"
        assert r.headers.get("x-frame-options") == "DENY"

    def test_multiple_calls_accumulate(self, client):
        """Each call to /api/stats itself counts as a request."""
        r1 = client.get(URL)
        count1 = r1.json()["total_requests"]

        r2 = client.get(URL)
        count2 = r2.json()["total_requests"]

        # The second stats call should see at least 1 more request
        assert count2 > count1
