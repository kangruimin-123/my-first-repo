from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
from sqlalchemy import func
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from backend.db import DailyKline, get_session


logger = logging.getLogger(__name__)
SessionContextFactory = Callable[[], AbstractContextManager[Session]]


class CacheManager:
    """Read and write provider data through SQLite cache tables."""

    def __init__(self, session_factory: SessionContextFactory | None = None) -> None:
        self.session_factory = session_factory or get_session

    def read_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame | None:
        """Read daily kline rows for a symbol/date range."""
        start_date = self._parse_compact_date(start)
        end_date = self._parse_compact_date(end)
        with self.session_factory() as session:
            rows = (
                session.query(DailyKline)
                .filter(DailyKline.symbol == symbol, DailyKline.date >= start_date, DailyKline.date <= end_date)
                .order_by(DailyKline.date)
                .all()
            )
        if not rows:
            return None
        return pd.DataFrame(
            [
                {
                    "symbol": row.symbol,
                    "date": row.date.strftime("%Y-%m-%d"),
                    "open": row.open,
                    "high": row.high,
                    "low": row.low,
                    "close": row.close,
                    "volume": row.volume,
                    "amount": row.amount,
                    "turnover_rate": row.turnover_rate,
                }
                for row in rows
            ]
        )

    def write_daily(self, symbol: str, df: pd.DataFrame) -> None:
        """Upsert daily kline rows using the symbol/date unique constraint."""
        logger.info("cache_manager.write_daily symbol=%s rows=%s", symbol, len(df))
        if df.empty:
            return
        rows = []
        for record in df.to_dict("records"):
            row_symbol = str(record.get("symbol") or symbol)
            row_date = self._parse_any_date(record["date"])
            rows.append(
                {
                    "symbol": row_symbol,
                    "date": row_date,
                    "open": float(record["open"]),
                    "high": float(record["high"]),
                    "low": float(record["low"]),
                    "close": float(record["close"]),
                    "volume": float(record["volume"]),
                    "amount": float(record["amount"]),
                    "turnover_rate": self._optional_float(record.get("turnover_rate")),
                    "updated_at": datetime.now(UTC).replace(tzinfo=None),
                }
            )
        with self.session_factory() as session:
            statement = insert(DailyKline).values(rows)
            update_columns = {
                column: getattr(statement.excluded, column)
                for column in ("open", "high", "low", "close", "volume", "amount", "turnover_rate", "updated_at")
            }
            session.execute(statement.on_conflict_do_update(index_elements=["symbol", "date"], set_=update_columns))

    def get_missing_dates(self, symbol: str, start: str, end: str) -> list[str]:
        """Return business dates missing from the daily cache."""
        expected_dates = pd.bdate_range(start=self._parse_compact_date(start), end=self._parse_compact_date(end))
        cached = self.read_daily(symbol, start, end)
        if cached is None:
            return [item.strftime("%Y%m%d") for item in expected_dates]
        present = {self._parse_any_date(value) for value in cached["date"].tolist()}
        return [item.strftime("%Y%m%d") for item in expected_dates if item.date() not in present]

    def is_fresh(self, table: str, max_age_hours: int) -> bool:
        """Return whether the newest updated_at in a table is inside the allowed age."""
        model_by_table = {"daily_kline": DailyKline}
        model = model_by_table.get(table)
        if model is None:
            return False
        with self.session_factory() as session:
            latest = session.query(func.max(model.updated_at)).scalar()
        if latest is None:
            return False
        age_seconds = (datetime.now(UTC).replace(tzinfo=None) - latest).total_seconds()
        return age_seconds <= max_age_hours * 3600

    def _parse_compact_date(self, value: str) -> date:
        return datetime.strptime(value, "%Y%m%d").date()

    def _parse_any_date(self, value: Any) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        if isinstance(value, datetime):
            return value.date()
        text = str(value)
        if "-" in text:
            return datetime.strptime(text, "%Y-%m-%d").date()
        return self._parse_compact_date(text)

    def _optional_float(self, value: Any) -> float | None:
        if value is None or pd.isna(value):
            return None
        return float(value)
