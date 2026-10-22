from pydantic import BaseModel, Field, field_validator
from datetime import date
from typing import Optional


class MandiPriceResponse(BaseModel):
    """Pydantic schema for /api/history response items."""

    id: int
    date: date
    city: str
    crop: str

    # Weather
    temperature: Optional[float] = None
    rainfall: Optional[float] = None
    humidity: Optional[float] = None

    # Prices
    price: Optional[float] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    price_spread: Optional[float] = None

    # Meta
    unit: Optional[str] = None
    n_reports: Optional[int] = None
    data_type: Optional[str] = None
    source: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    weather_source: Optional[str] = None

    model_config = {"from_attributes": True}


class HistoryResponse(BaseModel):
    """Wrapper for the paginated history response."""

    total: int
    limit: int
    records: list[MandiPriceResponse]


# ---------------------------------------------------------------------------
# Prediction schemas
# ---------------------------------------------------------------------------

class PredictRequest(BaseModel):
    """Input for POST /api/predict."""

    temperature: float = Field(
        ..., ge=-10, le=55, description="Temperature in °C"
    )
    rainfall: float = Field(
        ..., ge=0, le=500, description="Rainfall in mm"
    )
    humidity: float = Field(
        ..., ge=0, le=100, description="Relative humidity %"
    )
    last_price: float = Field(
        ..., ge=0, description="Last known mandi price (PKR/kg)"
    )


class PredictResponse(BaseModel):
    """Output for POST /api/predict."""

    predicted_price: float
    delta_pct: float


# ---------------------------------------------------------------------------
# Advice schemas
# ---------------------------------------------------------------------------

class SimilarDayResponse(BaseModel):
    """One retrieved similar historical day."""

    date: date
    temperature: float
    rainfall: float
    humidity: float
    price: float
    distance: float


class AdviceRequest(PredictRequest):
    """Input for POST /api/advice (same fields as PredictRequest)."""
    pass


class AdviceResponse(BaseModel):
    """Combined output: prediction + RAG history + AI advice."""

    predicted_price: float
    delta_pct: float
    retrieved_history: list[SimilarDayResponse]
    advice: str


# ---------------------------------------------------------------------------
# Weather schemas
# ---------------------------------------------------------------------------

class WeatherResponse(BaseModel):
    """Output for GET /api/weather/live."""

    temperature: float
    rainfall: float
    humidity: float
    fetched_at: str


# ---------------------------------------------------------------------------
# Feedback (price-correction reports) schemas
# ---------------------------------------------------------------------------

class FeedbackRequest(PredictRequest):
    """Input for POST /api/feedback (weather fields inherited)."""

    predicted_price: float = Field(
        ..., ge=0, description="Ridge model's predicted rate (PKR/kg)"
    )
    reported_price: float = Field(
        ..., gt=0, description="Farmer-reported actual rate (PKR/kg)"
    )
    note: Optional[str] = Field(
        default=None,
        max_length=300,
        description="Optional farmer note (max 300 chars, untrusted text)",
    )
    regenerate: bool = Field(
        default=False,
        description="If true, regenerate advice via Groq using the report "
                    "(treated as untrusted context). Ridge prediction is "
                    "never changed.",
    )

    @field_validator("note")
    @classmethod
    def _normalize_note(cls, v: Optional[str]) -> Optional[str]:
        """Trim surrounding whitespace; blank notes become None."""
        if v is None:
            return None
        v = v.strip()
        return v or None


class FeedbackResponse(BaseModel):
    """Output for POST /api/feedback."""

    feedback_id: int
    stored: bool
    verified: bool
    predicted_price: float
    reported_price: float
    regenerated: bool
    advice: str = ""


class FeedbackSummaryResponse(BaseModel):
    """Output for GET /api/feedback/summary (read-only team review)."""

    count: int
    verified_count: int
    unverified_count: int
    avg_absolute_error: Optional[float] = None
    avg_signed_error: Optional[float] = None
    max_absolute_error: Optional[float] = None
    plausible_low: Optional[float] = None
    plausible_high: Optional[float] = None
