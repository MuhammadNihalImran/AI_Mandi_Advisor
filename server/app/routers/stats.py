"""
GET /api/stats – in-memory request statistics for judges / demo.
"""

from fastapi import APIRouter

from app.services.stats_collector import get_snapshot

router = APIRouter(prefix="/api", tags=["stats"])


@router.get("/stats")
async def stats():
    """
    Return in-memory counters showing how the server has been performing
    since the last restart.

    Useful for hackathon demos and quick health dashboards.
    """
    return get_snapshot()
