"""
Tests for app.services.rag_retrieval.retrieve_similar_days
"""

import pytest
from datetime import date

from app.db.models import MandiPrice
from app.services.rag_retrieval import retrieve_similar_days


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_row(**kwargs) -> MandiPrice:
    """Create a MandiPrice with sensible defaults, overridden by kwargs."""
    defaults = dict(
        date=date(2025, 6, 1),
        city="Faisalabad",
        crop="Tomato",
        temperature=25.0,
        rainfall=0.0,
        humidity=50.0,
        price=100.0,
    )
    defaults.update(kwargs)
    return MandiPrice(**defaults)


def _seed(db, rows: list[MandiPrice]):
    db.add_all(rows)
    db.flush()


# ---------------------------------------------------------------------------
# Test 1 – Exact match: query matches a DB row exactly → distance = 0
# ---------------------------------------------------------------------------

class TestExactMatch:
    def test_exact_match_returns_zero_distance(self, db):
        rows = [
            _make_row(date=date(2025, 1, 1), temperature=30.0, rainfall=5.0, humidity=60.0, price=120.0),
            _make_row(date=date(2025, 2, 1), temperature=20.0, rainfall=0.0, humidity=40.0, price=80.0),
            _make_row(date=date(2025, 3, 1), temperature=35.0, rainfall=10.0, humidity=80.0, price=150.0),
        ]
        _seed(db, rows)

        results = retrieve_similar_days(
            temperature=30.0, rainfall=5.0, humidity=60.0, k=3, db=db
        )

        assert len(results) == 3
        assert results[0].distance == 0.0
        assert results[0].price == 120.0
        assert results[0].date == date(2025, 1, 1)

    def test_exact_match_ranked_first(self, db):
        """Even among many rows, the exact match must come first."""
        rows = [
            _make_row(date=date(2025, i, 15), temperature=10.0 + i * 3, rainfall=i * 0.5, humidity=30.0 + i * 2, price=90.0 + i)
            for i in range(1, 10)
        ]
        _seed(db, rows)

        # Query for the 5th row's exact values
        target_temp = 10.0 + 5 * 3   # 25.0
        target_rain = 5 * 0.5        # 2.5
        target_hum = 30.0 + 5 * 2    # 40.0

        results = retrieve_similar_days(
            temperature=target_temp, rainfall=target_rain, humidity=target_hum, k=3, db=db
        )

        assert results[0].distance == 0.0
        assert results[0].temperature == target_temp


# ---------------------------------------------------------------------------
# Test 2 – Empty database → empty list
# ---------------------------------------------------------------------------

class TestEmptyDatabase:
    def test_returns_empty_list(self, db):
        # No rows inserted
        results = retrieve_similar_days(
            temperature=30.0, rainfall=5.0, humidity=60.0, k=3, db=db
        )
        assert results == []

    def test_returns_empty_when_db_is_none(self):
        results = retrieve_similar_days(
            temperature=30.0, rainfall=5.0, humidity=60.0, k=3, db=None
        )
        assert results == []


# ---------------------------------------------------------------------------
# Test 3 – Extreme values
# ---------------------------------------------------------------------------

class TestExtremeValues:
    def test_zero_values_still_work(self, db):
        """All-zero query should not crash and should rank closest row first."""
        rows = [
            _make_row(date=date(2025, 4, 1), temperature=0.0, rainfall=0.0, humidity=0.0, price=50.0),
            _make_row(date=date(2025, 4, 2), temperature=40.0, rainfall=20.0, humidity=90.0, price=200.0),
        ]
        _seed(db, rows)

        results = retrieve_similar_days(
            temperature=0.0, rainfall=0.0, humidity=0.0, k=2, db=db
        )

        assert len(results) == 2
        assert results[0].distance == 0.0
        assert results[0].price == 50.0

    def test_very_high_values(self, db):
        """Query far beyond data range – nearest row still returned first."""
        rows = [
            _make_row(date=date(2025, 5, 1), temperature=15.0, rainfall=1.0, humidity=40.0, price=80.0),
            _make_row(date=date(2025, 5, 2), temperature=35.0, rainfall=5.0, humidity=70.0, price=140.0),
        ]
        _seed(db, rows)

        results = retrieve_similar_days(
            temperature=999.0, rainfall=999.0, humidity=999.0, k=2, db=db
        )

        assert len(results) == 2
        # Both should have large distances, but the higher-value row is closer
        assert results[0].price == 140.0
        assert results[0].distance < results[1].distance

    def test_constant_column_zero_range(self, db):
        """When all rows have the same temp, range defaults to 1 (no ZeroDivisionError)."""
        rows = [
            _make_row(date=date(2025, 6, 1), temperature=25.0, rainfall=0.0, humidity=50.0, price=100.0),
            _make_row(date=date(2025, 6, 2), temperature=25.0, rainfall=5.0, humidity=60.0, price=120.0),
            _make_row(date=date(2025, 6, 3), temperature=25.0, rainfall=10.0, humidity=70.0, price=140.0),
        ]
        _seed(db, rows)

        # Should not raise ZeroDivisionError even though temp range = 0
        results = retrieve_similar_days(
            temperature=25.0, rainfall=5.0, humidity=60.0, k=2, db=db
        )

        assert len(results) == 2
        assert results[0].distance == 0.0


# ---------------------------------------------------------------------------
# Test 4 – k limiting and ordering
# ---------------------------------------------------------------------------

class TestKLimitAndOrdering:
    def test_k_limits_results(self, db):
        rows = [
            _make_row(date=date(2025, 7, i), temperature=20.0 + i, rainfall=i * 0.5, humidity=50.0, price=100.0)
            for i in range(1, 8)  # 7 rows
        ]
        _seed(db, rows)

        results = retrieve_similar_days(
            temperature=22.0, rainfall=1.0, humidity=50.0, k=2, db=db
        )

        assert len(results) == 2

    def test_results_sorted_by_distance(self, db):
        rows = [
            _make_row(date=date(2025, 8, 1), temperature=10.0, rainfall=0.0, humidity=30.0, price=80.0),
            _make_row(date=date(2025, 8, 2), temperature=30.0, rainfall=5.0, humidity=60.0, price=130.0),
            _make_row(date=date(2025, 8, 3), temperature=50.0, rainfall=10.0, humidity=90.0, price=180.0),
        ]
        _seed(db, rows)

        results = retrieve_similar_days(
            temperature=28.0, rainfall=4.0, humidity=55.0, k=3, db=db
        )

        distances = [r.distance for r in results]
        assert distances == sorted(distances)

    def test_k_larger_than_row_count(self, db):
        rows = [
            _make_row(date=date(2025, 9, 1), temperature=20.0, rainfall=1.0, humidity=50.0, price=100.0),
        ]
        _seed(db, rows)

        results = retrieve_similar_days(
            temperature=20.0, rainfall=1.0, humidity=50.0, k=10, db=db
        )

        assert len(results) == 1
