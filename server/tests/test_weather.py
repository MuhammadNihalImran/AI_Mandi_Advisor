"""Tests for GET /api/weather/live endpoint (Open-Meteo mocked)."""

from unittest.mock import patch, AsyncMock, MagicMock

import httpx

URL = "/api/weather/live"

# Realistic Open-Meteo response shape
MOCK_API_RESPONSE = {
    "latitude": 31.42,
    "longitude": 73.08,
    "current": {
        "temperature_2m": 34.5,
        "precipitation": 0.2,
        "relative_humidity_2m": 62,
        "time": "2026-08-28T14:00",
    },
}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
class TestWeatherHappyPath:
    @patch("app.services.weather_service.httpx.AsyncClient")
    def test_returns_live_weather(self, mock_client_cls, client):
        # Build a mock async context manager for httpx.AsyncClient
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_API_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = client.get(URL)
        assert resp.status_code == 200

        body = resp.json()
        assert body["temperature"] == 34.5
        assert body["rainfall"] == 0.2
        assert body["humidity"] == 62
        assert "fetched_at" in body

    @patch("app.services.weather_service.httpx.AsyncClient")
    def test_response_schema_matches(self, mock_client_cls, client):
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_API_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = client.get(URL)
        body = resp.json()
        expected_keys = {"temperature", "rainfall", "humidity", "fetched_at"}
        assert expected_keys == set(body.keys())


# ---------------------------------------------------------------------------
# API failure → 502
# ---------------------------------------------------------------------------
class TestWeatherFailure:
    @patch("app.services.weather_service.httpx.AsyncClient")
    def test_api_error_returns_502(self, mock_client_cls, client):
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = client.get(URL)
        assert resp.status_code == 502
        body = resp.json()
        assert body["error"] == "weather_fetch_failed"

    @patch("app.services.weather_service.httpx.AsyncClient")
    def test_timeout_returns_502(self, mock_client_cls, client):
        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ReadTimeout("timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = client.get(URL)
        assert resp.status_code == 502


# ---------------------------------------------------------------------------
# Cache behaviour
# ---------------------------------------------------------------------------
class TestWeatherCache:
    @patch("app.services.weather_service.httpx.AsyncClient")
    def test_second_call_uses_cache(self, mock_client_cls, client):
        """Second request within TTL should not hit the API again."""
        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_API_RESPONSE
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        # First call – hits API
        resp1 = client.get(URL)
        assert resp1.status_code == 200

        # Second call – should use cache
        resp2 = client.get(URL)
        assert resp2.status_code == 200

        # httpx.AsyncClient should have been instantiated only once
        assert mock_client_cls.call_count == 1


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestWeatherEdgeCases:
    @patch("app.services.weather_service.httpx.AsyncClient")
    def test_zero_values(self, mock_client_cls, client):
        zero_response = {
            "current": {
                "temperature_2m": 0.0,
                "precipitation": 0.0,
                "relative_humidity_2m": 0,
            },
        }
        mock_response = MagicMock()
        mock_response.json.return_value = zero_response
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_client

        resp = client.get(URL)
        assert resp.status_code == 200
        assert resp.json()["temperature"] == 0.0
        assert resp.json()["rainfall"] == 0.0
