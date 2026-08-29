"""Tests for POST /api/predict endpoint."""

URL = "/api/predict"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
class TestPredictHappyPath:
    def test_returns_prediction(self, client):
        resp = client.post(URL, json={
            "temperature": 33, "rainfall": 0.5,
            "humidity": 65, "last_price": 246,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert "predicted_price" in body
        assert "delta_pct" in body
        assert isinstance(body["predicted_price"], (int, float))
        assert isinstance(body["delta_pct"], (int, float))

    def test_price_floor(self, client):
        """Predicted price should never drop below 10 PKR."""
        resp = client.post(URL, json={
            "temperature": 0, "rainfall": 500,
            "humidity": 0, "last_price": 0,
        })
        assert resp.status_code == 200
        assert resp.json()["predicted_price"] >= 10

    def test_security_headers_present(self, client):
        resp = client.post(URL, json={
            "temperature": 25, "rainfall": 1,
            "humidity": 50, "last_price": 100,
        })
        assert resp.headers.get("X-Content-Type-Options") == "nosniff"
        assert resp.headers.get("X-Frame-Options") == "DENY"


# ---------------------------------------------------------------------------
# Validation errors (422)
# ---------------------------------------------------------------------------
class TestPredictValidation:
    def test_missing_fields(self, client):
        resp = client.post(URL, json={"temperature": 30})
        assert resp.status_code == 422

    def test_temperature_below_min(self, client):
        resp = client.post(URL, json={
            "temperature": -20, "rainfall": 0,
            "humidity": 50, "last_price": 100,
        })
        assert resp.status_code == 422

    def test_temperature_above_max(self, client):
        resp = client.post(URL, json={
            "temperature": 60, "rainfall": 0,
            "humidity": 50, "last_price": 100,
        })
        assert resp.status_code == 422

    def test_rainfall_negative(self, client):
        resp = client.post(URL, json={
            "temperature": 25, "rainfall": -1,
            "humidity": 50, "last_price": 100,
        })
        assert resp.status_code == 422

    def test_rainfall_above_max(self, client):
        resp = client.post(URL, json={
            "temperature": 25, "rainfall": 600,
            "humidity": 50, "last_price": 100,
        })
        assert resp.status_code == 422

    def test_humidity_above_100(self, client):
        resp = client.post(URL, json={
            "temperature": 25, "rainfall": 0,
            "humidity": 150, "last_price": 100,
        })
        assert resp.status_code == 422

    def test_last_price_negative(self, client):
        resp = client.post(URL, json={
            "temperature": 25, "rainfall": 0,
            "humidity": 50, "last_price": -10,
        })
        assert resp.status_code == 422

    def test_invalid_json_body(self, client):
        resp = client.post(URL, content="not json",
                           headers={"Content-Type": "application/json"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestPredictEdgeCases:
    def test_zero_last_price(self, client):
        resp = client.post(URL, json={
            "temperature": 25, "rainfall": 0,
            "humidity": 50, "last_price": 0,
        })
        assert resp.status_code == 200
        assert resp.json()["delta_pct"] == 0.0

    def test_boundary_values(self, client):
        """All fields at their boundary limits."""
        resp = client.post(URL, json={
            "temperature": -10, "rainfall": 0,
            "humidity": 0, "last_price": 0,
        })
        assert resp.status_code == 200

    def test_boundary_values_max(self, client):
        resp = client.post(URL, json={
            "temperature": 55, "rainfall": 500,
            "humidity": 100, "last_price": 9999,
        })
        assert resp.status_code == 200
