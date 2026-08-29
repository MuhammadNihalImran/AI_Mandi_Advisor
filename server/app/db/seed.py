"""
One-time seed script – imports faisalabad_tomato_dataset.csv into mandi_prices.

Run from the server/ directory:
    python -m app.db.seed
"""

import csv
from datetime import datetime
from pathlib import Path

from app.db.database import engine, SessionLocal, Base
from app.db.models import MandiPrice

# CSV bundled inside the package: server/app/data/
CSV_PATH = Path(__file__).resolve().parent.parent / "data" / "faisalabad_tomato_dataset.csv"


def _safe_float(val: str) -> float | None:
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val: str) -> int | None:
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


def seed() -> None:
    # Create all tables
    Base.metadata.create_all(bind=engine)

    if not CSV_PATH.exists():
        raise FileNotFoundError(
            f"SEEDING FAILED — CSV not found at {CSV_PATH}\n"
            f"Expected file: {CSV_PATH}\n"
            f"Ensure server/app/data/faisalabad_tomato_dataset.csv exists."
        )

    db = SessionLocal()
    try:
        with open(CSV_PATH, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"Read {len(rows)} rows from {CSV_PATH.name}")

        records: list[MandiPrice] = []
        for row in rows:
            record = MandiPrice(
                date=datetime.strptime(row["date"], "%Y-%m-%d").date(),
                city=row["city"],
                crop=row["crop"],
                temperature=_safe_float(row["temperature_c"]),
                rainfall=_safe_float(row["rainfall_mm"]),
                humidity=_safe_float(row["humidity_percent"]),
                price=_safe_float(row["avg_price_pkr"]),
                min_price=_safe_float(row["min_price_pkr"]),
                max_price=_safe_float(row["max_price_pkr"]),
                price_spread=_safe_float(row["price_spread_pkr"]),
                unit=row.get("unit"),
                n_reports=_safe_int(row.get("n_price_reports", "")),
                data_type=row.get("data_type"),
                source=row.get("source_file"),
                latitude=_safe_float(row.get("latitude", "")),
                longitude=_safe_float(row.get("longitude", "")),
                weather_source=row.get("weather_source"),
            )
            records.append(record)

        db.bulk_save_objects(records)
        db.commit()
        print(f"Inserted {len(records)} records into mandi_prices table.")

    except Exception as exc:
        db.rollback()
        print(f"Seed failed: {exc}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
