"""
Shared pytest fixtures for the test suite.

Uses an in-memory SQLite database so tests never touch the real mandi.db.
The FastAPI dependency ``get_db`` is overridden so all routers use the
test session.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.db.database import Base, get_db
from app.db.models import MandiPrice  # noqa: F401 – registers model with Base
from app.main import app
from app.services import weather_service
from app.services.stats_collector import reset as reset_stats


# ---------------------------------------------------------------------------
# Database fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def engine():
    """One in-memory SQLite engine for the entire test session."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=eng)
    yield eng
    Base.metadata.drop_all(bind=eng)


@pytest.fixture()
def db(engine):
    """
    Per-test session with automatic rollback.

    Every test gets a fresh transaction that is rolled back afterwards,
    so tests are isolated from each other.
    """
    connection = engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ---------------------------------------------------------------------------
# FastAPI TestClient
# ---------------------------------------------------------------------------

@pytest.fixture()
def client(db):
    """
    httpx-backed TestClient with ``get_db`` overridden to use the test
    database session.  Weather cache is cleared before each test.
    """
    # Override the DB dependency
    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db

    # Clear weather cache so tests don't leak cached responses
    weather_service._cache.clear()

    # Reset in-memory stats so each test starts fresh
    reset_stats()

    with TestClient(app, raise_server_exceptions=False) as c:
        yield c

    app.dependency_overrides.clear()
