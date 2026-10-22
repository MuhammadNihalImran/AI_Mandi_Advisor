"""
Feedback validation helpers – plausible-range derivation and note
sanitization for POST /api/feedback.

The plausible price range is derived from the historical ``mandi_prices``
table so extreme outlier reports (typos, junk) are rejected before they
are stored.  Nothing here retrains or mutates the Ridge model; it only
guards the incoming farmer report.
"""

import logging
import re
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import MandiPrice

logger = logging.getLogger(__name__)

# Round stored/computed prices to 2 decimal places (matches price_predictor)
_TWO_PLACES = Decimal("0.01")

# ---------------------------------------------------------------------------
# Fallback band used when the history table is empty (e.g. fresh DB, tests).
# Tomato PKR/kg realistically sits in this window; anything far outside is
# treated as an obvious typo/junk.
# ---------------------------------------------------------------------------
_DEFAULT_LOW = Decimal("10")
_DEFAULT_HIGH = Decimal("2000")

# Width multipliers applied to the observed historical min/max.
_LOW_FACTOR = Decimal("0.5")
_HIGH_FACTOR = Decimal("2.0")

# C0/C1 control characters (except the whitespace we keep: \t \n \r).
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def strip_control_chars(text: str | None) -> str | None:
    """
    Remove non-printable control characters from a farmer note.

    Keeps normal whitespace (space, tab, newline, carriage return) but drops
    the remaining C0/C1 controls that could be used to smuggle escape
    sequences into stored text. Returns None for empty input.
    """
    if text is None:
        return None
    cleaned = _CONTROL_CHARS.sub("", text)
    return cleaned or None


def compute_plausible_range(db: Session) -> tuple[Decimal, Decimal]:
    """
    Return an inclusive (low, high) PKR/kg band derived from historical data.

    low  = historical_min * 0.5  (floor of 5)
    high = historical_max * 2.0

    Falls back to (10, 2000) when the table is empty, and widens the band
    when min == max so a single historical value doesn't reject all reports.
    """
    pmin, pmax = (
        db.query(
            func.min(MandiPrice.price), func.max(MandiPrice.price)
        )
        .first()
    )

    if pmin is None or pmax is None:
        logger.info("feedback_plausible_range_defaulted")
        return _DEFAULT_LOW, _DEFAULT_HIGH

    # Convert stored floats to Decimal via str to avoid binary float noise.
    low = Decimal(str(pmin)) * _LOW_FACTOR
    high = Decimal(str(pmax)) * _HIGH_FACTOR

    # Absolute floor so a near-zero historical low doesn't allow junk reports.
    low = max(low, Decimal("5"))

    # Degenerate band (single/flat historical value) – widen upward.
    if high <= low:
        high = low * Decimal("3") + Decimal("50")

    return (
        low.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP),
        high.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP),
    )


def is_plausible(reported: Decimal, low: Decimal, high: Decimal) -> bool:
    """True when ``low <= reported <= high``."""
    return low <= reported <= high
