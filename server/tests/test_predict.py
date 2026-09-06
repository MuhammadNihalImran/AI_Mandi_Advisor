"""Tests for POST /api/predict endpoint and the Decimal-based
predict_price service (ROUND_HALF_UP, 2 decimal places)."""

from decimal import Decimal

from app.services.price_predictor import predict_price

URL = "/api/predict"

# Expected values assume coefficients loaded from
# reference/metrics_real_weekly.json (see price_predictor._METRICS_PATH).


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
        # Decimal math: raw pred 219.1978517656932 → 219.20 (ROUND_HALF_UP)
        assert body["predicted_price"] == 219.2
        assert body["delta_pct"] == -10.89

    def test_price_floor(self, client):
        """Predicted price should never drop below 10 PKR."""
        resp = client.post(URL, json={
            "temperature": 0, "rainfall": 500,
            "humidity": 0, "last_price": 0,
        })
        assert resp.status_code == 200
        assert resp.json()["predicted_price"] == 10.0

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
        assert resp.json()["predicted_price"] == 3065.72

    def test_delta_pct_round_half_up(self, client):
        """
        (10.00 - 2.56) / 2.56 * 100 = 290.625 exactly.

        ROUND_HALF_UP must give 290.63; float round() (banker's
        rounding) would give 290.62.
        """
        resp = client.post(URL, json={
            "temperature": 0, "rainfall": 0,
            "humidity": 0, "last_price": 2.56,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["predicted_price"] == 10.0  # floored at 10
        assert body["delta_pct"] == 290.63


# ---------------------------------------------------------------------------
# Decimal-based predict_price service (direct unit tests)
# ---------------------------------------------------------------------------
class TestPredictPriceDecimal:
    """predict_price must do all math in Decimal, quantized to 2 decimal
    places with ROUND_HALF_UP."""

    def test_returns_decimal_instances(self):
        pred, delta = predict_price(33, 0.5, 65, 246)
        assert isinstance(pred, Decimal)
        assert isinstance(delta, Decimal)

    def test_predicted_price_has_exactly_two_decimal_places(self):
        pred, delta = predict_price(33, 0.5, 65, 246)
        assert pred == Decimal("219.20")
        assert pred.as_tuple().exponent == -2  # exactly 2 decimal places
        assert delta == Decimal("-10.89")

    def test_round_half_up_not_bankers_rounding(self):
        """
        (10.00 - 2.56) / 2.56 * 100 = 290.625 exactly.

        Decimal + ROUND_HALF_UP → 290.63; Python's default banker's
        rounding (float round()) would give 290.62.
        """
        pred, delta = predict_price(0, 0, 0, 2.56)
        assert pred == Decimal("10.00")  # floored at 10
        assert delta == Decimal("290.63")

    def test_price_floor_is_decimal_10(self):
        pred, delta = predict_price(0, 500, 0, 0)
        assert pred == Decimal("10.00")
        assert delta == Decimal("0.00")

    def test_accepts_decimal_inputs(self):
        """Inputs may arrive as Decimal – must pass through unchanged."""
        pred, delta = predict_price(
            Decimal("33"), Decimal("0.5"), Decimal("65"), Decimal("246")
        )
        assert pred == Decimal("219.20")
        assert delta == Decimal("-10.89")
