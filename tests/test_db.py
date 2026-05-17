from __future__ import annotations

from datetime import date

import pytest
import pandas as pd
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.data.cache_manager import CacheManager
from backend.db import (
    ALL_MODELS,
    DailyKline,
    ManualPosition,
    SystemMeta,
    get_session,
    get_system_meta,
    table_counts,
)


EXPECTED_TABLES = {
    "daily_kline",
    "index_kline",
    "daily_basic",
    "limit_up_records",
    "lianban_records",
    "sector_mapping",
    "sector_daily",
    "moneyflow",
    "auction_snapshot",
    "intraday_snapshot",
    "mainline_history",
    "role_assignment",
    "evaluation_results",
    "strategy_signals",
    "stage_analysis",
    "mainline_radar",
    "leader_radar",
    "manual_positions",
    "trade_history",
    "stop_loss_levels",
    "system_meta",
}


def test_init_db_creates_all_tables(db_engine) -> None:
    inspector = inspect(db_engine)
    assert set(inspector.get_table_names()) == EXPECTED_TABLES


def test_daily_kline_unique_constraint(db_session: Session) -> None:
    first_row = DailyKline(
        symbol="002415.SZ",
        date=date(2026, 5, 15),
        open=10.0,
        high=11.0,
        low=9.8,
        close=10.8,
        volume=1000000,
        amount=10800000,
        turnover_rate=2.5,
    )
    duplicate_row = DailyKline(
        symbol="002415.SZ",
        date=date(2026, 5, 15),
        open=10.1,
        high=11.2,
        low=9.9,
        close=10.9,
        volume=1000001,
        amount=10900000,
        turnover_rate=2.6,
    )
    db_session.add(first_row)
    db_session.commit()
    db_session.add(duplicate_row)

    with pytest.raises(IntegrityError):
        db_session.commit()


def test_insert_manual_positions(db_session: Session) -> None:
    position = ManualPosition(
        symbol="600886.SH",
        name="国投电力",
        entry_price=12.3,
        entry_date=date(2026, 5, 15),
        quantity=1000,
        stop_loss=11.6,
        notes="manual input only",
    )
    db_session.add(position)
    db_session.commit()

    stored = db_session.query(ManualPosition).filter_by(symbol="600886.SH").one()
    assert stored.name == "国投电力"
    assert stored.quantity == 1000


def test_system_meta_read_write(db_session: Session) -> None:
    db_session.add(SystemMeta(key="last_daily_update", value="2026-05-15"))
    db_session.add(SystemMeta(key="data_source_status", value="full"))
    db_session.commit()

    meta = get_system_meta(db_session)
    assert meta["last_daily_update"] == "2026-05-15"
    assert meta["data_source_status"] == "full"


def test_all_tables_are_queryable(db_session: Session) -> None:
    counts = table_counts(db_session)
    expected_model_tables = {model.__tablename__ for model in ALL_MODELS}

    assert set(counts) == expected_model_tables
    assert all(count == 0 for count in counts.values())


def test_cache_manager_daily_read_write_and_upsert(db_engine) -> None:
    cache = CacheManager(session_factory=lambda: get_session(db_engine))
    first = pd.DataFrame(
        [
            {
                "symbol": "002415.SZ",
                "date": "2026-05-15",
                "open": 10.0,
                "high": 11.0,
                "low": 9.8,
                "close": 10.8,
                "volume": 1000000,
                "amount": 10800000,
                "turnover_rate": 2.5,
            }
        ]
    )
    second = first.copy()
    second.loc[0, "close"] = 10.9

    cache.write_daily("002415.SZ", first)
    cache.write_daily("002415.SZ", second)
    cached = cache.read_daily("002415.SZ", "20260515", "20260515")

    assert cached is not None
    assert len(cached) == 1
    assert cached.iloc[0]["close"] == 10.9
