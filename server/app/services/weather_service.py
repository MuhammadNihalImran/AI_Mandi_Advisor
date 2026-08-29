"""
Live weather service – Open-Meteo forecast API for Faisalabad.

Uses httpx for async HTTP calls and cachetools.TTLCache (15 min) so we
don't hammer the external API on every request.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

import httpx
from cachetools import TTLCache

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Faisalabad coordinates
# ---------------------------------------------------------------------------
LATITUDE = 31.42
LONGITUDE = 73.08

# ---------------------------------------------------------------------------
# Open-Meteo forecast endpoint (free, no API key needed)
# ---------------------------------------------------------------------------
_API_URL = "https://api.open-meteo.com/v1/forecast"
_PARAMS = {
    "latitude": LATITUDE,
    "longitude": LONGITUDE,
    "current": "temperature_2m,precipitation,relative_humidity_2m",
    "timezone": "Asia/Karachi",
}

# ---------------------------------------------------------------------------
# In-memory cache: 1 slot, 15 minute TTL
# ---------------------------------------------------------------------------
_CACHE_TTL_SECONDS = 15 * 60  # 900 seconds
_cache: TTLCache = TTLCache(maxsize=1, ttl=_CACHE_TTL_SECONDS)
_CACHE_KEY = "faisalabad_current"

# ---------------------------------------------------------------------------
# HTTP client (shared, connection-pooled)
# ---------------------------------------------------------------------------
_HTTP_TIMEOUT = 10.0  # seconds


@dataclass
class CurrentWeather:
    """Parsed current weather reading."""

    temperature: float      # °C
    rainfall: float         # mm
    humidity: float         # %
    fetched_at: str         # ISO timestamp


async def fetch_live_weather() -> CurrentWeather:
    """
    Fetch current Faisalabad weather from Open-Meteo.

    Returns cached result if < 15 min old; otherwise hits the API.

    Raises:
        httpx.HTTPStatusError: If Open-Meteo returns a non-2xx status.
        httpx.RequestError:    Network / DNS / timeout errors.
    """
    # --- Check cache first ------------------------------------------------
    cached = _cache.get(_CACHE_KEY)
    if cached is not None:
        logger.debug("Weather cache hit")
        return cached

    # --- API call ----------------------------------------------------------
    logger.info("Fetching live weather from Open-Meteo")
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
        response = await client.get(_API_URL, params=_PARAMS)
        response.raise_for_status()

    data = response.json()
    current = data["current"]

    weather = CurrentWeather(
        temperature=current["temperature_2m"],
        rainfall=current["precipitation"],
        humidity=current["relative_humidity_2m"],
        fetched_at=datetime.now().isoformat(),
    )

    # --- Store in cache ----------------------------------------------------
    _cache[_CACHE_KEY] = weather
    return weather
