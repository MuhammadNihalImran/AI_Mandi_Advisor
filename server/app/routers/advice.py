import logging
from dataclasses import asdict

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.rate_limiter import limiter
from app.db.database import get_db
from app.models.schemas import AdviceRequest, AdviceResponse, SimilarDayResponse
from app.services.price_predictor import predict_price
from app.services.rag_retrieval import retrieve_similar_days
from app.services.ai_advisor import generate_advice

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["advice"])


@router.post("/advice", response_model=AdviceResponse)
@limiter.limit("20/15minutes")
async def get_advice(
    request: Request,
    body: AdviceRequest,
    db: Session = Depends(get_db),
):
    """
    Full advisory pipeline:
    1. Ridge regression se price predict karo
    2. RAG se similar historical days retrieve karo
    3. Groq LLM se farmer advice generate karo
    4. Sab kuch ek combined response mein return karo

    Rate-limited: 20 requests per 15 minutes per IP (Groq quota control).
    """
    # Step 1 – ML prediction
    predicted_price, delta_pct = predict_price(
        temperature=body.temperature,
        rainfall=body.rainfall,
        humidity=body.humidity,
        last_price=body.last_price,
    )

    # Step 2 – RAG retrieval
    similar_days = retrieve_similar_days(
        temperature=body.temperature,
        rainfall=body.rainfall,
        humidity=body.humidity,
        k=3,
        db=db,
    )

    # Convert SimilarDay dataclasses → Pydantic models for response
    history_response = [
        SimilarDayResponse(**asdict(d)) for d in similar_days
    ]

    # Step 3 – AI advice (Groq LLM)
    try:
        advice = generate_advice(
            predicted_price=predicted_price,
            last_price=body.last_price,
            temperature=body.temperature,
            rainfall=body.rainfall,
            humidity=body.humidity,
            retrieved_history=similar_days,
        )
    except RuntimeError as exc:
        msg = str(exc)
        if "rate limit" in msg.lower() or "free tier" in msg.lower():
            # Groq 429 – return friendly error with prediction data
            return JSONResponse(
                status_code=429,
                content={
                    "predicted_price": predicted_price,
                    "delta_pct": delta_pct,
                    "retrieved_history": [h.model_dump() for h in history_response],
                    "advice": msg,
                },
            )
        # Service unavailable (all models down) – return 503 with prediction data
        return JSONResponse(
            status_code=503,
            content={
                "predicted_price": predicted_price,
                "delta_pct": delta_pct,
                "retrieved_history": [h.model_dump() for h in history_response],
                "advice": msg,
            },
        )

    # Step 4 – Combined response
    return AdviceResponse(
        predicted_price=predicted_price,
        delta_pct=delta_pct,
        retrieved_history=history_response,
        advice=advice,
    )
