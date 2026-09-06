"""Tests for POST /api/advice endpoint (Groq mocked)."""

from types import SimpleNamespace
from unittest.mock import patch, MagicMock

import httpx
import pytest
from groq import APIConnectionError, APIStatusError

import app.services.ai_advisor as ai_mod
from app.config import get_settings
from app.services.ai_advisor import (
    _format_history_lines,
    _get_client,
    generate_advice,
)

URL = "/api/advice"

VALID_BODY = {
    "temperature": 33,
    "rainfall": 0.5,
    "humidity": 65,
    "last_price": 246,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_groq_response(advice_text="Bhai, aaj bech do, rate theek hai."):
    """Build a fake Groq chat completion response."""
    msg = MagicMock()
    msg.content = advice_text
    choice = MagicMock()
    choice.message = msg
    completion = MagicMock()
    completion.choices = [choice]
    return completion


# ---------------------------------------------------------------------------
# Happy path (Groq mocked)
# ---------------------------------------------------------------------------
class TestAdviceHappyPath:
    @patch("app.services.ai_advisor._get_client")
    def test_returns_full_response(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_groq_response()
        mock_get_client.return_value = mock_client

        resp = client.post(URL, json=VALID_BODY)
        assert resp.status_code == 200

        body = resp.json()
        assert "predicted_price" in body
        assert "delta_pct" in body
        assert "retrieved_history" in body
        assert isinstance(body["retrieved_history"], list)
        assert "advice" in body
        assert body["advice"] == "Bhai, aaj bech do, rate theek hai."

    @patch("app.services.ai_advisor._get_client")
    def test_advice_text_is_stripped(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_groq_response(
            "  advice with spaces  "
        )
        mock_get_client.return_value = mock_client

        resp = client.post(URL, json=VALID_BODY)
        assert resp.status_code == 200
        assert resp.json()["advice"] == "advice with spaces"

    @patch("app.services.ai_advisor._get_client")
    def test_groq_called_with_correct_model(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_groq_response()
        mock_get_client.return_value = mock_client

        client.post(URL, json=VALID_BODY)

        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "qwen/qwen3.6-27b"
        assert call_kwargs["reasoning_format"] == "hidden"
        assert call_kwargs["reasoning_effort"] == "none"

    @patch("app.services.ai_advisor._get_client")
    def test_think_tags_stripped_from_response(self, mock_get_client, client):
        """Model may still leak <think> tags — regex safety net must remove them."""
        mock_client = MagicMock()
        raw = (
            "<think>\n"
            "Let me reason about this step by step...\n"
            "The farmer should sell now.\n"
            "</think>\n\n"
            "Bhai, aaj bech do, rate theek hai."
        )
        mock_client.chat.completions.create.return_value = _mock_groq_response(raw)
        mock_get_client.return_value = mock_client

        resp = client.post(URL, json=VALID_BODY)
        assert resp.status_code == 200
        advice = resp.json()["advice"]
        assert "<think>" not in advice
        assert "reason about this" not in advice
        assert advice == "Bhai, aaj bech do, rate theek hai."


# ---------------------------------------------------------------------------
# Groq 429 rate limit → RuntimeError
# ---------------------------------------------------------------------------
class TestAdviceGroqRateLimit:
    @patch("app.services.ai_advisor._get_client")
    def test_groq_rate_limit_returns_429(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError(
            "Thodi der baad try karein - free tier limit lag gayi"
        )
        mock_get_client.return_value = mock_client

        resp = client.post(URL, json=VALID_BODY)
        assert resp.status_code == 429
        body = resp.json()
        assert "advice" in body
        assert "free tier limit" in body["advice"]
        # Prediction + history should still be present
        assert "predicted_price" in body
        assert "retrieved_history" in body


# ---------------------------------------------------------------------------
# Validation errors (422)
# ---------------------------------------------------------------------------
class TestAdviceValidation:
    def test_missing_body(self, client):
        resp = client.post(URL)
        assert resp.status_code == 422

    def test_empty_body(self, client):
        resp = client.post(URL, json={})
        assert resp.status_code == 422

    def test_invalid_temperature(self, client):
        body = {**VALID_BODY, "temperature": 100}
        resp = client.post(URL, json=body)
        assert resp.status_code == 422

    def test_negative_rainfall(self, client):
        body = {**VALID_BODY, "rainfall": -5}
        resp = client.post(URL, json=body)
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestAdviceEdgeCases:
    @patch("app.services.ai_advisor._get_client")
    def test_empty_db_returns_empty_history(self, mock_get_client, client):
        """No rows in DB → retrieved_history is empty list."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_groq_response(
            "Koi data nahi hai bhai."
        )
        mock_get_client.return_value = mock_client

        resp = client.post(URL, json=VALID_BODY)
        assert resp.status_code == 200
        assert resp.json()["retrieved_history"] == []

    @patch("app.services.ai_advisor._get_client")
    def test_zero_last_price(self, mock_get_client, client):
        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = _mock_groq_response()
        mock_get_client.return_value = mock_client

        body = {**VALID_BODY, "last_price": 0}
        resp = client.post(URL, json=body)
        assert resp.status_code == 200
        assert resp.json()["delta_pct"] == 0.0


# ---------------------------------------------------------------------------
# _get_client() lazy init (lines 29-31)
# ---------------------------------------------------------------------------
class TestGetClient:
    def test_creates_client_when_none(self):
        """First call must instantiate a Groq client."""
        old = ai_mod._client
        try:
            ai_mod._client = None
            with patch("app.services.ai_advisor.Groq") as MockGroq:
                sentinel = MagicMock()
                MockGroq.return_value = sentinel
                result = _get_client()
                MockGroq.assert_called_once()
                assert result is sentinel
        finally:
            ai_mod._client = old

    def test_reuses_existing_client(self):
        """Second call must NOT re-create the Groq instance."""
        old = ai_mod._client
        try:
            sentinel = MagicMock()
            ai_mod._client = sentinel
            with patch("app.services.ai_advisor.Groq") as MockGroq:
                result = _get_client()
                MockGroq.assert_not_called()
                assert result is sentinel
        finally:
            ai_mod._client = old

    def test_client_created_with_timeout(self):
        """Groq client must use the configured timeout (not the ~10 min SDK default)."""
        old = ai_mod._client
        try:
            ai_mod._client = None
            with patch("app.services.ai_advisor.Groq") as MockGroq:
                _get_client()
                kwargs = MockGroq.call_args.kwargs
                assert kwargs["timeout"] == get_settings().groq_timeout_seconds
        finally:
            ai_mod._client = old


# ---------------------------------------------------------------------------
# _format_history_lines() with dataclass-like objects (lines 64-70)
# ---------------------------------------------------------------------------
class TestFormatHistoryLines:
    def test_dataclass_objects(self):
        """Objects with .date attribute use the hasattr branch."""
        days = [
            SimpleNamespace(
                date="2025-07-01",
                temperature=35.0,
                rainfall=2.0,
                humidity=70.0,
                price=500.0,
            ),
            SimpleNamespace(
                date="2025-07-08",
                temperature=30.0,
                rainfall=0.0,
                humidity=55.0,
                price=420.0,
            ),
        ]
        result = _format_history_lines(days)
        assert "2025-07-01" in result
        assert "35.0C" in result
        assert "500.0/kg" in result
        assert "2025-07-08" in result

    def test_dict_objects(self):
        """Plain dicts use the isinstance(day, dict) branch."""
        days = [
            {
                "date": "2025-08-01",
                "temperature": 28.0,
                "rainfall": 5.0,
                "humidity": 80.0,
                "price": 600.0,
            }
        ]
        result = _format_history_lines(days)
        assert "2025-08-01" in result
        assert "28.0C" in result

    def test_empty_returns_fallback(self):
        result = _format_history_lines([])
        assert result == "(koi historical data available nahi)"


# ---------------------------------------------------------------------------
# generate_advice() model fallback chain (lines 170-193)
# ---------------------------------------------------------------------------
def _make_api_status_error(status_code: int, message: str = "err"):
    """Build a real APIStatusError with the given status_code."""
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(status_code, request=request)
    return APIStatusError(message=message, response=response, body=None)


def _make_connection_error(message: str = "Connection error.") -> APIConnectionError:
    """Build a real APIConnectionError (network failure / timeout)."""
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    return APIConnectionError(message=message, request=request)


# ---------------------------------------------------------------------------
# Network failures to Groq (timeout / DNS / connection refused)
# ---------------------------------------------------------------------------
class TestConnectionError:
    @patch("app.services.ai_advisor._get_client")
    def test_connection_error_raises_unavailable(self, mock_get_client):
        """Network failure → RuntimeError (router maps to 503, not a 500 crash)."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = _make_connection_error(
            "Connection timed out."
        )
        mock_get_client.return_value = mock_client

        with pytest.raises(RuntimeError, match="temporarily unavailable"):
            generate_advice(500, 246, 33, 0.5, 65, [])

    @patch("app.services.ai_advisor._get_client")
    def test_connection_error_returns_503(self, mock_get_client, client):
        """Router must translate connection errors into a clean 503."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = _make_connection_error()
        mock_get_client.return_value = mock_client

        resp = client.post(URL, json=VALID_BODY)
        assert resp.status_code == 503
        body = resp.json()
        assert "temporarily unavailable" in body["advice"]
        # Prediction data should still be present in the degraded response
        assert "predicted_price" in body


class TestModelFallback:
    @patch("app.services.ai_advisor._get_client")
    def test_429_raises_rate_limit_runtime_error(self, mock_get_client):
        """Groq 429 → RuntimeError with rate-limit message (not re-raised as APIStatusError)."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = _make_api_status_error(
            429, "rate_limited"
        )
        mock_get_client.return_value = mock_client

        import pytest
        with pytest.raises(RuntimeError, match="free tier limit"):
            generate_advice(500, 246, 33, 0.5, 65, [])

    @patch("app.services.ai_advisor._get_client")
    def test_primary_404_fallback_succeeds(self, mock_get_client):
        """Primary model 404 → fallback succeeds with advice."""
        mock_client = MagicMock()
        create_fn = mock_client.chat.completions.create
        create_fn.side_effect = [
            _make_api_status_error(404, "model_not_found"),
            _mock_groq_response("Fallback advice: bech do."),
        ]
        mock_get_client.return_value = mock_client

        result = generate_advice(500, 246, 33, 0.5, 65, [])
        assert result == "Fallback advice: bech do."
        assert create_fn.call_count == 2
        # First call used primary model
        assert create_fn.call_args_list[0].kwargs["model"] == "qwen/qwen3.6-27b"
        # Second call used fallback model
        assert create_fn.call_args_list[1].kwargs["model"] == "openai/gpt-oss-20b"

    @patch("app.services.ai_advisor._get_client")
    def test_both_models_404_raises_unavailable(self, mock_get_client):
        """Both models return 404 → 'temporarily unavailable' RuntimeError."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = [
            _make_api_status_error(404, "not_found"),
            _make_api_status_error(404, "not_found"),
        ]
        mock_get_client.return_value = mock_client

        import pytest
        with pytest.raises(RuntimeError, match="temporarily unavailable"):
            generate_advice(500, 246, 33, 0.5, 65, [])

    @patch("app.services.ai_advisor._get_client")
    def test_generic_api_error_reraises(self, mock_get_client):
        """Non-429/404 error (e.g. 500) is re-raised immediately."""
        mock_client = MagicMock()
        err = _make_api_status_error(500, "internal_error")
        mock_client.chat.completions.create.side_effect = err
        mock_get_client.return_value = mock_client

        import pytest
        with pytest.raises(APIStatusError) as exc_info:
            generate_advice(500, 246, 33, 0.5, 65, [])
        assert exc_info.value.status_code == 500


# ---------------------------------------------------------------------------
# Service unavailable via router → 503
# ---------------------------------------------------------------------------
class TestServiceUnavailable:
    @patch("app.services.ai_advisor._get_client")
    def test_both_models_down_returns_503(self, mock_get_client, client):
        """RuntimeError('temporarily unavailable') → router returns 503."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError(
            "AI advice service temporarily unavailable. Try again later."
        )
        mock_get_client.return_value = mock_client

        resp = client.post(URL, json=VALID_BODY)
        assert resp.status_code == 503
        body = resp.json()
        assert "temporarily unavailable" in body["advice"]
        assert "predicted_price" in body
