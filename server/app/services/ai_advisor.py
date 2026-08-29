"""
AI Advisor – Groq LLM integration for farmer advice.

Follows the prompt-building logic from getFarmerAdvice() in
tomato_hybrid_advisor.html, but runs server-side with Groq's
available models (qwen/qwen3.6-27b primary, openai/gpt-oss-20b fallback).
"""

import logging
import re
import time
from typing import Any

from groq import Groq, APIStatusError

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ---------------------------------------------------------------------------
# Groq client (lazy-init, reused across calls)
# ---------------------------------------------------------------------------
_client: Groq | None = None


def _get_client() -> Groq:
    global _client
    if _client is None:
        _client = Groq(api_key=settings.groq_api_key)
    return _client


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
# Primary model (good multilingual support for Roman Urdu)
_MODEL = "qwen/qwen3.6-27b"
# Fallback model in case primary is unavailable
_FALLBACK_MODEL = "openai/gpt-oss-20b"

_SYSTEM_PROMPT = (
    "Tum ek Pakistani mandi price advisor ho jo Faisalabad ke tomato farmers "
    "ko roman Urdu mein seedha, practical advice dete ho. Kisi bhi tarah ki "
    "hedging ya lambi disclaimer mat likho."
)

_RATE_LIMIT_MESSAGE = (
    "Thodi der baad try karein - free tier limit lag gayi"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _format_history_lines(retrieved_history: list[Any]) -> str:
    """
    Convert retrieved SimilarDay objects (or dicts) into the prompt lines
    that the JS version builds as ragLines.
    """
    lines: list[str] = []
    for day in retrieved_history:
        # Support both dataclass (SimilarDay) and plain dict
        if hasattr(day, "date"):
            lines.append(
                f"{day.date} — temp {day.temperature}C, rain {day.rainfall}mm, "
                f"humidity {day.humidity}% → price Rs {day.price}/kg"
            )
        elif isinstance(day, dict):
            lines.append(
                f"{day.get('date', '?')} — temp {day.get('temperature', '?')}C, "
                f"rain {day.get('rainfall', '?')}mm, "
                f"humidity {day.get('humidity', '?')}% → "
                f"price Rs {day.get('price', '?')}/kg"
            )
    return "\n".join(lines) if lines else "(koi historical data available nahi)"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def generate_advice(
    predicted_price: float,
    last_price: float,
    temperature: float,
    rainfall: float,
    humidity: float,
    retrieved_history: list[Any],
) -> str:
    """
    Call Groq LLM to generate farmer-friendly advice in Roman Urdu.

    Args:
        predicted_price: ML model ka predicted rate (PKR/kg).
        last_price:      Pichla mandi rate (PKR/kg).
        temperature:     Current temperature (°C).
        rainfall:        Current rainfall (mm).
        humidity:        Current humidity (%).
        retrieved_history: List of SimilarDay (or dict) from RAG retrieval.

    Returns:
        Advice text string (Roman Urdu).

    Raises:
        RateLimitError: When Groq returns 429 – caller should translate
                        into a user-friendly message.
        Exception:      Any other API / network error.
    """
    rag_lines = _format_history_lines(retrieved_history)

    user_prompt = (
        "ML MODEL KA PREDICTION (chhote statistical model se, "
        "11 real mandi weeks pe train):\n"
        f"- Aaj: temperature {temperature}C, rainfall {rainfall}mm, "
        f"humidity {humidity}%\n"
        f"- Pichla mandi rate: Rs {last_price}/kg\n"
        f"- Model ka predicted agla rate: Rs {predicted_price}/kg\n"
        "\n"
        "RETRIEVED HISTORICAL CONTEXT (RAG - asal mandi records jo aaj "
        "jaise weather se sabse zyada milte julte hain):\n"
        f"{rag_lines}\n"
        "\n"
        "Farmer ko 4-5 sentence mein seedha jawab do (roman Urdu mein):\n"
        "1. Kya karna chahiye - abhi bechna behtar hai ya thoda rukna\n"
        "2. Weather ka is prediction pe kya asar hai (ek line mein)\n"
        '3. Retrieved historical days ka reference do agar relevant ho '
        '("pichli baar jab mausam aisa tha...")\n'
        "4. Ek honest caution ke saath ke yeh chhoti dataset se aya "
        "estimate hai, guaranteed nahi\n"
        "\n"
        "Tone: seedha, farmer-friendly, jaise koi mandi ka tajurbekar "
        "aadmi advice de raha ho."
    )

    client = _get_client()

    for model_id in (_MODEL, _FALLBACK_MODEL):
        try:
            t0 = time.perf_counter()
            response = client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=512,
                temperature=0.7,
                reasoning_format="hidden",
                reasoning_effort="none",
            )
            groq_ms = round((time.perf_counter() - t0) * 1000, 2)
            advice = response.choices[0].message.content or ""

            logger.info(
                "groq_api_success",
                extra={
                    "model": model_id,
                    "duration_ms": groq_ms,
                    "prompt_tokens": getattr(
                        response.usage, "prompt_tokens", None
                    ),
                    "completion_tokens": getattr(
                        response.usage, "completion_tokens", None
                    ),
                },
            )
            return _strip_thinking_tags(advice.strip())

        except APIStatusError as exc:
            if exc.status_code == 429:
                logger.warning(
                    "groq_rate_limit",
                    extra={"model": model_id, "status_code": 429},
                )
                raise RuntimeError(_RATE_LIMIT_MESSAGE) from exc
            if exc.status_code == 404:
                logger.warning(
                    "groq_model_not_found",
                    extra={"model": model_id, "status_code": 404},
                )
                continue
            logger.error(
                "groq_api_error",
                extra={
                    "model": model_id,
                    "status_code": exc.status_code,
                    "error_detail": exc.message,
                },
            )
            raise

    # Both models failed
    raise RuntimeError("AI advice service temporarily unavailable. Try again later.")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _strip_thinking_tags(text: str) -> str:
    """
    Strip <think>...</think> tags from model output (e.g. Qwen chain-of-thought).
    Returns only the final response content.
    Uses re.DOTALL so multiline <think> blocks are also removed.
    """
    cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL)
    return cleaned.strip()
