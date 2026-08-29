import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.models.schemas import WeatherResponse
from app.services.weather_service import fetch_live_weather

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/weather", tags=["weather"])


@router.get("/live", response_model=WeatherResponse)
async def get_live_weather():
    """
    Fetch current Faisalabad weather from Open-Meteo API.

    Returns temperature (°C), rainfall (mm), humidity (%), and the
    timestamp when the data was fetched.  Results are cached in-memory
    for 15 minutes to avoid hitting the external API too often.
    """
    try:
        weather = await fetch_live_weather()
    except Exception as exc:
        logger.error("Failed to fetch live weather: %s", exc)
        return JSONResponse(
            status_code=502,
            content={
                "error": "weather_fetch_failed",
                "detail": "Open-Meteo API se weather data nahi mil saka. "
                          "Manual values use karein.",
            },
        )

    return WeatherResponse(
        temperature=weather.temperature,
        rainfall=weather.rainfall,
        humidity=weather.humidity,
        fetched_at=weather.fetched_at,
    )
