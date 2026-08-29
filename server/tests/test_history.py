"""Tests for GET /api/history endpoint."""

from datetime import date

from app.db.models import MandiPrice

URL = "/api/history"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _seed_rows(db, n=5):
    """Insert n sample MandiPrice rows into the test DB."""
    rows = []
    for i in range(n):
        rows.append(MandiPrice(
            date=date(2025, 1, i + 1),
            city="Faisalabad",
            crop="Tomato",
            temperature=20.0 + i,
            rainfall=float(i),
            humidity=50.0 + i,
            price=100.0 + i * 10,
        ))
    db.add_all(rows)
    db.flush()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------
class TestHistoryHappyPath:
    def test_returns_records(self, client, db):
        _seed_rows(db, 3)
        resp = client.get(URL)
        assert resp.status_code == 200

        body = resp.json()
        assert body["total"] == 3
        assert body["limit"] == 50  # default
        assert len(body["records"]) == 3

    def test_records_sorted_by_date_desc(self, client, db):
        _seed_rows(db, 5)
        resp = client.get(URL)
        records = resp.json()["records"]

        dates = [r["date"] for r in records]
        assert dates == sorted(dates, reverse=True)

    def test_limit_parameter(self, client, db):
        _seed_rows(db, 10)
        resp = client.get(URL, params={"limit": 3})
        assert resp.status_code == 200
        assert len(resp.json()["records"]) == 3
        assert resp.json()["total"] == 10

    def test_record_schema(self, client, db):
        _seed_rows(db, 1)
        resp = client.get(URL)
        record = resp.json()["records"][0]

        expected_keys = {
            "id", "date", "city", "crop",
            "temperature", "rainfall", "humidity",
            "price", "min_price", "max_price", "price_spread",
            "unit", "n_reports", "data_type", "source",
            "latitude", "longitude", "weather_source",
        }
        assert expected_keys.issubset(record.keys())


# ---------------------------------------------------------------------------
# Empty database
# ---------------------------------------------------------------------------
class TestHistoryEmpty:
    def test_empty_db(self, client):
        resp = client.get(URL)
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 0
        assert body["records"] == []


# ---------------------------------------------------------------------------
# Validation errors (422)
# ---------------------------------------------------------------------------
class TestHistoryValidation:
    def test_limit_zero(self, client):
        resp = client.get(URL, params={"limit": 0})
        assert resp.status_code == 422

    def test_limit_negative(self, client):
        resp = client.get(URL, params={"limit": -5})
        assert resp.status_code == 422

    def test_limit_above_max(self, client):
        resp = client.get(URL, params={"limit": 999})
        assert resp.status_code == 422

    def test_limit_non_integer(self, client):
        resp = client.get(URL, params={"limit": "abc"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
class TestHistoryEdgeCases:
    def test_limit_equals_row_count(self, client, db):
        _seed_rows(db, 5)
        resp = client.get(URL, params={"limit": 5})
        assert resp.status_code == 200
        assert len(resp.json()["records"]) == 5

    def test_limit_one(self, client, db):
        _seed_rows(db, 10)
        resp = client.get(URL, params={"limit": 1})
        assert resp.status_code == 200
        assert len(resp.json()["records"]) == 1
