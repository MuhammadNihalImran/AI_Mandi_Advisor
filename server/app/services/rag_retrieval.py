"""
RAG Retrieval – find historically similar mandi days by weather.

Implements the same normalized-Euclidean-distance logic as
retrieveSimilarDays() in tomato_hybrid_advisor.html.
"""

import math
import logging
from dataclasses import dataclass
from datetime import date

from sqlalchemy.orm import Session

from app.db.models import MandiPrice

logger = logging.getLogger(__name__)


@dataclass
class SimilarDay:
    """One retrieved historical day with its distance score."""

    date: date
    temperature: float
    rainfall: float
    humidity: float
    price: float
    distance: float


def retrieve_similar_days(
    temperature: float,
    rainfall: float,
    humidity: float,
    k: int = 3,
    db: Session | None = None,
) -> list[SimilarDay]:
    """
    Retrieve the top-k most similar historical mandi days by weather.

    Distance metric (matches JS retrieveSimilarDays exactly):
        d = sqrt(((t - T) / range_T)² + ((r - R) / range_R)² + ((h - H) / range_H)²)

    Each feature is divided by its range (max − min) across all rows so
    that features with larger numeric scales don't dominate.  If a feature
    has zero range (constant column), the denominator defaults to 1.

    Args:
        temperature: Current temperature in °C.
        rainfall:    Current rainfall in mm.
        humidity:    Current relative humidity %.
        k:           Number of similar days to return (default 3).
        db:          SQLAlchemy session (required).

    Returns:
        Sorted list of SimilarDay (nearest first), up to k items.
    """
    if db is None:
        return []

    rows: list[MandiPrice] = db.query(MandiPrice).all()
    if not rows:
        return []

    # --- Ranges (|| 1 fallback matches JS: range(arr) || 1) -----------
    temps = [r.temperature or 0.0 for r in rows]
    rains = [r.rainfall or 0.0 for r in rows]
    hums = [r.humidity or 0.0 for r in rows]

    t_range = max(temps) - min(temps) or 1.0
    r_range = max(rains) - min(rains) or 1.0
    h_range = max(hums) - min(hums) or 1.0

    # --- Score every row -----------------------------------------------
    scored: list[SimilarDay] = []
    for row in rows:
        t = row.temperature or 0.0
        r = row.rainfall or 0.0
        h = row.humidity or 0.0

        dist = math.sqrt(
            ((t - temperature) / t_range) ** 2
            + ((r - rainfall) / r_range) ** 2
            + ((h - humidity) / h_range) ** 2
        )

        scored.append(
            SimilarDay(
                date=row.date,
                temperature=t,
                rainfall=r,
                humidity=h,
                price=row.price or 0.0,
                distance=round(dist, 6),
            )
        )

    scored.sort(key=lambda x: x.distance)
    return scored[:k]
