"""
Read-only team review of farmer price-correction reports.

Prints the average error (predicted vs reported) stored in the
``price_feedback`` table.  This is a report only – it never verifies rows,
never mutates data, and never retrains the Ridge model.

Run from the server/ directory:
    python -m scripts.feedback_report
"""

from decimal import Decimal

from app.db.database import SessionLocal
from app.db.models import PriceFeedback
from app.services.feedback_validation import compute_plausible_range


def main() -> None:
    db = SessionLocal()
    try:
        rows = db.query(
            PriceFeedback.predicted_price, PriceFeedback.reported_price
        ).all()
        verified = (
            db.query(PriceFeedback)
            .filter(PriceFeedback.verified.is_(True))
            .count()
        )
        low, high = compute_plausible_range(db)

        count = len(rows)
        print("=== Farmer price-correction report summary ===")
        print(f"Total reports    : {count}")
        print(f"Verified         : {verified}")
        print(f"Unverified       : {count - verified}")
        print(f"Plausible range  : Rs {low} - {high} /kg")

        if not count:
            print("No feedback recorded yet.")
            return

        errors = [
            (p or Decimal("0")) - (r or Decimal("0")) for p, r in rows
        ]
        abs_errors = [abs(e) for e in errors]
        avg_signed = (sum(errors, Decimal("0")) / Decimal(count)).quantize(Decimal("0.01"))
        avg_abs = (sum(abs_errors, Decimal("0")) / Decimal(count)).quantize(Decimal("0.01"))
        max_abs = max(abs_errors).quantize(Decimal("0.01"))

        print(f"Avg signed error : Rs {avg_signed}/kg (predicted - reported)")
        print(f"Avg abs error    : Rs {avg_abs}/kg")
        print(f"Max abs error    : Rs {max_abs}/kg")
    finally:
        db.close()


if __name__ == "__main__":
    main()
