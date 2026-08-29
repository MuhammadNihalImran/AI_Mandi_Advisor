"""
Ridge regression price predictor.

Mirrors the predictPrice() JS function from tomato_hybrid_advisor.html.
Coefficients are loaded from reference/metrics_real_weekly.json at import
time; if the file is unavailable, hardcoded fallback values are used.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hardcoded fallback coefficients (from trained Ridge model)
# ---------------------------------------------------------------------------
_COEF_FALLBACK = {
    "temp": 7.0656269,
    "rain": -0.26778793,
    "hum": 3.71686402,
    "lag1": 0.34666444,
    "roll3": -0.07041521,
}
_INTERCEPT_FALLBACK = -323.4013482343068

# ---------------------------------------------------------------------------
# Try loading from metrics_real_weekly.json
# ---------------------------------------------------------------------------
_METRICS_PATH = Path(__file__).resolve().parents[3] / "reference" / "metrics_real_weekly.json"


def _load_coefficients() -> tuple[dict[str, float], float]:
    """
    Attempt to read feature_importance from metrics_real_weekly.json.
    Returns (coefficients_dict, intercept).

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

        coefs: dict[str, float] = {}
        for json_key, (name, sign) in sign_map.items():
            if json_key in importance:
                coefs[name] = sign * abs(importance[json_key])
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

_MIN_PRICE = 10.0  # price floor, same as JS: Math.max(pred, 10)


def predict_price(
    temperature: float,
    rainfall: float,
    humidity: float,
    last_price: float,
) -> tuple[float, float]:
    """
    Predict next mandi price using Ridge regression.

    Parameters match the JS predictPrice() function:
        pred = INTERCEPT + temp*COEF + rain*COEF + hum*COEF + lag1*COEF + roll3*COEF
    where roll3 ≈ last_price (simplification from the JS widget).

    Returns:
        (predicted_price, delta_pct)
        predicted_price: rounded to nearest integer, floored at 10 PKR
        delta_pct: percentage change from last_price
    """
    roll3 = last_price  # same simplification as JS widget

    pred = (
        INTERCEPT
        + COEF["temp"] * temperature
        + COEF["rain"] * rainfall
        + COEF["hum"] * humidity
        + COEF["lag1"] * last_price
        + COEF["roll3"] * roll3
    )

    # Price floor sanity check (mirrors JS: Math.max(pred, 10))
    pred = max(pred, _MIN_PRICE)
    pred = round(pred)

    # Delta percentage
    if last_price != 0:
        delta_pct = round((pred - last_price) / last_price * 100, 2)
    else:
        delta_pct = 0.0

    return pred, delta_pct
