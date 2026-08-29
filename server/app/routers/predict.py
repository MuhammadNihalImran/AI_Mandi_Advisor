from fastapi import APIRouter, Request

from app.rate_limiter import limiter
from app.models.schemas import PredictRequest, PredictResponse
from app.services.price_predictor import predict_price

router = APIRouter(prefix="/api", tags=["predict"])


@router.post("/predict", response_model=PredictResponse)
@limiter.limit("60/15minutes")
async def predict(request: Request, body: PredictRequest):
    """
    Predict next mandi price using Ridge regression.

    Accepts current weather + last known price, returns predicted price
    and percentage change (delta_pct).

    Rate-limited: 60 requests per 15 minutes per IP.
    """
    predicted_price, delta_pct = predict_price(
        temperature=body.temperature,
        rainfall=body.rainfall,
        humidity=body.humidity,
        last_price=body.last_price,
    )
    return PredictResponse(
        predicted_price=predicted_price,
        delta_pct=delta_pct,
    )
