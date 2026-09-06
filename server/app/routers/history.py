from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import MandiPrice
from app.models.schemas import MandiPriceResponse, HistoryResponse

router = APIRouter(prefix="/api", tags=["history"])


# Sync on purpose: the SQLAlchemy queries below are blocking; a sync
# endpoint runs in FastAPI's threadpool instead of stalling the event loop.
@router.get("/history", response_model=HistoryResponse)
def get_history(
    limit: int = Query(default=50, ge=1, le=500, description="Max records to return"),
    db: Session = Depends(get_db),
):
    """Return the latest mandi price records from the database."""
    total = db.query(MandiPrice).count()
    records = (
        db.query(MandiPrice)
        .order_by(MandiPrice.date.desc())
        .limit(limit)
        .all()
    )
    return HistoryResponse(
        total=total,
        limit=limit,
        records=records,
    )
