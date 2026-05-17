from __future__ import annotations

from collections.abc import Iterator

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from backend.db import create_db_engine, init_db


@pytest.fixture()
def db_engine() -> Engine:
    """Create an isolated in-memory SQLite database for each test."""
    engine = create_db_engine(":memory:")
    init_db(engine=engine)
    return engine


@pytest.fixture()
def db_session(db_engine: Engine) -> Iterator[Session]:
    """Yield a database session bound to the test engine."""
    factory = sessionmaker(bind=db_engine, expire_on_commit=False)
    session = factory()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture()
def mock_config() -> dict[str, object]:
    """Return a compact config fixture for future tests."""
    return {
        "system": {"db_path": ":memory:", "log_level": "INFO"},
        "data_source": {"daily": {"chain": ["mock"]}},
        "stock_pool": {"max_observation_pool": 50, "max_focus_pool": 10},
    }
