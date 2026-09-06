"""
Ridge regression price predictor.

Mirrors the predictPrice() JS function from tomato_hybrid_advisor.html.
Coefficients are loaded from reference/metrics_real_weekly.json at import
time; if the file is unavailable, hardcoded fallback values are used.

All price math uses ``decimal.Decimal`` (exact decimal arithmetic, no
binary float), and final values are rounded to 2 decimal places using
ROUND_HALF_UP (banking-standard half-away-from-zero rounding).
"""

import json
import logging
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

logger = logging.getLogger(__name__)

# Rounding target: 2 decimal places
_TWO_PLACES = Decimal("0.01")

# ---------------------------------------------------------------------------
# Hardcoded fallback coefficients (from trained Ridge model)
# ---------------------------------------------------------------------------
_COEF_FALLBACK = {
    "temp": Decimal("7.0656269"),
    "rain": Decimal("-0.26778793"),
    "hum": Decimal("3.71686402"),
    "lag1": Decimal("0.34666444"),
    "roll3": Decimal("-0.07041521"),
}
_INTERCEPT_FALLBACK = Decimal("-323.4013482343068")

# ---------------------------------------------------------------------------
# Try loading from metrics_real_weekly.json
# ---------------------------------------------------------------------------
_METRICS_PATH = Path(__file__).resolve().parents[3] / "reference" / "metrics_real_weekly.json"


def _load_coefficients() -> tuple[dict[str, Decimal], Decimal]:
    """
    Attempt to read feature_importance from metrics_real_weekly.json.
    Returns (coefficients_dict, intercept) as Decimals.

    The JSON stores absolute importance values without signs, so we merge
    the signs from the known fallback and override magnitudes when available.
    """
    try:
        with open(_METRICS_PATH, encoding="utf-8") as f:
            metrics = json.load(f)

        importance = metrics.get("feature_importance", {})
        if not importance:
            raise KeyError("feature_importance key missing")

        # Map JSON keys → our coefficient names, preserving signs from fallback
        sign_map = {
            "temperature_c": ("temp", 1),
            "rainfall_mm": ("rain", -1),
            "humidity_percent": ("hum", 1),
            "price_lag1": ("lag1", 1),
            "price_roll_mean_3": ("roll3", -1),
        }

        coefs: dict[str, Decimal] = {}
        for json_key, (name, sign) in sign_map.items():
            if json_key in importance:
                # Convert via str() so the JSON number's decimal form is
                # kept exactly (no binary float artifacts).
                magnitude = Decimal(str(abs(importance[json_key])))
                coefs[name] = magnitude if sign == 1 else -magnitude
            else:
                coefs[name] = _COEF_FALLBACK[name]

        # Intercept is not in the metrics file – always use fallback
        logger.info("Loaded coefficients from %s", _METRICS_PATH.name)
        return coefs, _INTERCEPT_FALLBACK

    except Exception as exc:
        logger.warning("Could not load metrics (%s) – using hardcoded coefficients", exc)
        return _COEF_FALLBACK.copy(), _INTERCEPT_FALLBACK


COEF, INTERCEPT = _load_coefficients()

# ---------------------------------------------------------------------------
# Prediction (matches JS predictPrice logic exactly)
# ---------------------------------------------------------------------------

_MIN_PRICE = Decimal("10")  # price floor, same as JS: Math.max(pred, 10)


def _dec(value) -> Decimal:
    """
    Convert an incoming number (float/int/Decimal) to Decimal via its
    string form, so values like 0.1 stay exact instead of inheriting
    binary float representation errors.
    """
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def predict_price(
    temperature: float,
    rainfall: float,
    humidity: float,
    last_price: float,
) -> tuple[Decimal, Decimal]:
    """
    Predict next mandi price using Ridge regression.

    All arithmetic is done with ``decimal.Decimal``; the final price and
    delta percentage are rounded to 2 decimal places using ROUND_HALF_UP
    (banking-standard rounding).

    Parameters match the JS predictPrice() function:
        pred = INTERCEPT + temp*COEF + rain*COEF + hum*COEF + lag1*COEF + roll3*COEF
    where roll3 ≈ last_price (simplification from the JS widget).

    Returns:
        (predicted_price, delta_pct)
        predicted_price: Decimal rounded to 2 decimal places (ROUND_HALF_UP),
                         floored at 10 PKR
        delta_pct: Decimal percentage change from last_price,
                   2 decimal places (ROUND_HALF_UP)
    """
    temp = _dec(temperature)
    rain = _dec(rainfall)
    hum = _dec(humidity)
    lp = _dec(last_price)
    roll3 = lp  # same simplification as JS widget

    pred = (
        INTERCEPT
        + COEF["temp"] * temp
        + COEF["rain"] * rain
        + COEF["hum"] * hum
        + COEF["lag1"] * lp
        + COEF["roll3"] * roll3
    )

    # Price floor sanity check (mirrors JS: Math.max(pred, 10))
    pred = max(pred, _MIN_PRICE)
    pred = pred.quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)

    # Delta percentage
    if lp != 0:
        delta_pct = (
            (pred - lp) / lp * Decimal("100")
        ).quantize(_TWO_PLACES, rounding=ROUND_HALF_UP)
    else:
        delta_pct = Decimal("0.00")

    return pred, delta_pct
