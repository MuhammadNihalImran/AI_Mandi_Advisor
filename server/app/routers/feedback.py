"""
POST /api/feedback – farmer price-correction reports.

Lets a farmer confirm ("Sahi") or correct ("Galat") the rate shown by the
advisory.  Corrections are stored for offline team review – they NEVER
trigger a model retrain and NEVER alter the Ridge prediction.  On a Galat
report the endpoint can optionally regenerate the advisory *text* with Groq,
treating the farmer note strictly as untrusted context.

GET /api/feedback/summary – read-only average-error rollup for the team.
"""

import logging
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.rate_limiter import limiter
from app.db.database import get_db
from app.db.models import PriceFeedback
from app.models.schemas import (
    FeedbackRequest,
    FeedbackResponse,
    FeedbackSummaryResponse,
)
from app.services.ai_advisor import generate_correction_advice
from app.services.feedback_validation import (
    compute_plausible_range,
    is_plausible,
    strip_control_chars,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["feedback"])

# Shown when Groq can't regenerate the correction advice – the report is still
# saved, so a failure here must never lose the farmer's data or crash (500).
_ACKNOWLEDGEMENT = (
    "Shukriya! Aapki report record ho gayi aur team review ke liye save "
    "ho gayi hai. AI correction abhi generate nahi ho saka, hum is par "
    "ghour karenge."
)


# Sync on purpose: SQLAlchemy + Groq calls below are blocking; a sync
# endpoint runs in FastAPI's threadpool instead of stalling the event loop.
@router.post("/feedback", response_model=FeedbackResponse)
@limiter.limit("20/15minutes")
def submit_feedback(
    request: Request,
    body: FeedbackRequest,
    db: Session = Depends(get_db),
):
    """
    Store a price-correction report.

    Steps:
      1. Strip control characters from the note.
      2. Validate reported_price against a plausible range derived from the
         historical mandi data (reject extreme outliers with 422).
      3. Persist (verified=False).
      4. If ``regenerate`` (Galat path), produce corrected advisory text via
         Groq – the Ridge prediction is left untouched.  Any Groq failure
         falls back to a simple acknowledgement instead of a 500.
    """
    note = strip_control_chars(body.note)
    reported = Decimal(str(body.reported_price))
    predicted = Decimal(str(body.predicted_price))

    low, high = compute_plausible_range(db)
    if not is_plausible(reported, low, high):
        logger.warning(
            "feedback_outlier_rejected",
            extra={
                "reported_price": str(reported),
                "plausible_low": str(low),
                "plausible_high": str(high),
            },
        )
        raise HTTPException(
            status_code=422,
            detail=(
                f"Reported rate Rs {reported}/kg plausible range "
                f"(Rs {low}–{high}/kg) se bahar hai. Dobara check karke "
                f"lein."
            ),
        )

    fb = PriceFeedback(
        predicted_price=predicted,
        reported_price=reported,
        note=note,
        temperature=body.temperature,
        rainfall=body.rainfall,
        humidity=body.humidity,
        last_price=body.last_price,
        verified=False,
    )
    db.add(fb)
    db.commit()
    db.refresh(fb)

    logger.info(
        "feedback_stored",
        extra={
            "feedback_id": fb.id,
            "predicted": str(predicted),
            "reported": str(reported),
            "regenerate": body.regenerate,
            "has_note": note is not None,
        },
    )

    advice_text = ""
    regenerated = False
    if body.regenerate:
        try:
            advice_text = generate_correction_advice(
                predicted_price=predicted,
                reported_price=reported,
                temperature=body.temperature,
                rainfall=body.rainfall,
                humidity=body.humidity,
                note=note,
            )
            regenerated = True
        except Exception as exc:  # noqa: BLE001 – report is saved; degrade to ack
            # Groq rate-limit / unavailable / any API error: keep the stored
            # report and return a plain acknowledgement instead of failing.
            logger.warning(
                "feedback_correction_advice_failed",
                extra={"feedback_id": fb.id, "error_detail": str(exc)},
            )
            advice_text = _ACKNOWLEDGEMENT

    return FeedbackResponse(
        feedback_id=fb.id,
        stored=True,
        verified=bool(fb.verified),
        # JSON boundary: Decimal -> float
        predicted_price=float(fb.predicted_price),
        reported_price=float(fb.reported_price),
        regenerated=regenerated,
        advice=advice_text,
    )


# Sync on purpose: the aggregation below is blocking SQLAlchemy work.
@router.get("/feedback/summary", response_model=FeedbackSummaryResponse)
def feedback_summary(db: Session = Depends(get_db)):
    """
    Read-only rollup of stored correction reports for team review.

    Returns count, verified/unverified split, and the average (signed +
    absolute) error between predicted and reported prices.  Never modifies
    anything.
    """
    rows = db.query(
        PriceFeedback.predicted_price, PriceFeedback.reported_price
    ).all()
    verified_count = (
        db.query(PriceFeedback).filter(PriceFeedback.verified.is_(True)).count()
    )

    count = len(rows)
    avg_absolute = avg_signed = max_absolute = None
    if count:
        errors = [
            (predicted or Decimal("0")) - (reported or Decimal("0"))
            for predicted, reported in rows
        ]
        abs_errors = [abs(e) for e in errors]
        avg_signed = float(
            (sum(errors, Decimal("0")) / Decimal(count)).quantize(Decimal("0.01"))
        )
        avg_absolute = float(
            (sum(abs_errors, Decimal("0")) / Decimal(count)).quantize(Decimal("0.01"))
        )
        max_absolute = float(max(abs_errors).quantize(Decimal("0.01")))

    low, high = compute_plausible_range(db)

    return FeedbackSummaryResponse(
        count=count,
        verified_count=verified_count,
        unverified_count=count - verified_count,
        avg_absolute_error=avg_absolute,
        avg_signed_error=avg_signed,
        max_absolute_error=max_absolute,
        plausible_low=float(low),
        plausible_high=float(high),
    )
