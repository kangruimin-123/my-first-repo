from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from backend.config import load_config
from backend.data.akshare_provider import AkshareProvider
from backend.data.cache_manager import CacheManager
from backend.data.degradation import DegradationManager
from backend.data.mock_provider import MockProvider
from backend.data.provider_base import ConfigError, DataProvider, run_with_degradation
from backend.data.stock_pool_filter import StockPoolFilter
from backend.data.tushare_provider import TushareProvider
from backend.db import (
    DailyKline,
    LianbanRecord,
    LimitUpRecord,
    SectorDaily,
    SectorMapping,
    SystemMeta,
    get_session,
)


logger = logging.getLogger(__name__)
SessionContextFactory = Callable[[], AbstractContextManager[Session]]


@dataclass(frozen=True)
class SyncResult:
    success_count: int
    fail_count: int
    degradation_count: int
    skipped: bool

    def combine(self, other: SyncResult) -> SyncResult:
        """Combine result counters from multiple sync steps."""
        return SyncResult(
            success_count=self.success_count + other.success_count,
            fail_count=self.fail_count + other.fail_count,
            degradation_count=self.degradation_count + other.degradation_count,
            skipped=self.skipped and other.skipped,
        )


class DataSync:
    """Coordinate incremental provider sync into SQLite."""

    def __init__(
        self,
        config: dict[str, Any] | None = None,
        providers: dict[str, DataProvider] | None = None,
        session_factory: SessionContextFactory | None = None,
        force: bool = False,
    ) -> None:
        self.config = config or load_config()
        self.session_factory = session_factory or get_session
        self.force = force
        self.degradation_manager = DegradationManager(session_factory=self.session_factory)
        self.cache_manager = CacheManager(session_factory=self.session_factory)
        self.stock_pool_filter = StockPoolFilter(self.config)
        self.providers = providers or self._build_providers()

    def sync_daily(self, symbols: list[str]) -> SyncResult:
        """Incrementally sync daily kline data for selected symbols."""
        logger.info("data_sync.sync_daily started symbols=%s", len(symbols))
        end = self._today_compact()
        start = self._compact_days_ago(int(self.config["data_source"]["tushare"]["history_days"]))
        success_count = 0
        fail_count = 0
        degradation_count = 0
        for symbol in symbols:
            try:
                frame = run_with_degradation(self.providers, self._daily_chain(), "get_daily", self.degradation_manager, symbol, start, end)
                self.cache_manager.write_daily(symbol, frame)
                success_count += len(frame)
                if frame.attrs.get("data_quality") != "full":
                    degradation_count += 1
            except Exception as exc:
                logger.warning("sync_daily failed symbol=%s reason=%s", symbol, exc)
                fail_count += 1
        logger.info("data_sync.sync_daily finished success=%s fail=%s", success_count, fail_count)
        return SyncResult(success_count, fail_count, degradation_count, skipped=False)

    def sync_limit_up(self, date_text: str) -> SyncResult:
        """Sync limit-up records for one trade date."""
        logger.info("data_sync.sync_limit_up date=%s", date_text)
        try:
            frame = run_with_degradation(self.providers, self._event_chain(), "get_limit_up", self.degradation_manager, date_text)
            self._upsert_limit_up(frame)
            return SyncResult(len(frame), 0, 1 if frame.attrs.get("data_quality") != "full" else 0, skipped=False)
        except Exception as exc:
            logger.warning("sync_limit_up failed date=%s reason=%s", date_text, exc)
            return SyncResult(0, 1, 0, skipped=False)

    def sync_lianban(self, date_text: str) -> SyncResult:
        """Calculate simple lianban count from limit-up records."""
        logger.info("data_sync.sync_lianban date=%s", date_text)
        target_date = self._parse_compact_date(date_text)
        with self.session_factory() as session:
            records = session.query(LimitUpRecord).filter(LimitUpRecord.date == target_date).all()
            counts_by_symbol: dict[str, int] = {}
            for record in records:
                symbol = self._normalize_symbol(record.symbol)
                count = 1
                if record.limit_type and "连板" in record.limit_type:
                    count = 2
                if record.open_count:
                    count = max(count, int(record.open_count))
                counts_by_symbol[symbol] = max(counts_by_symbol.get(symbol, 0), count)
            rows = []
            for symbol, count in counts_by_symbol.items():
                rows.append({"symbol": symbol, "date": target_date, "lianban_count": count, "updated_at": self._now()})
            if rows:
                statement = insert(LianbanRecord).values(rows)
                session.execute(
                    statement.on_conflict_do_update(
                        index_elements=["symbol", "date"],
                        set_={"lianban_count": statement.excluded.lianban_count, "updated_at": statement.excluded.updated_at},
                    )
                )
        return SyncResult(len(records), 0, 0, skipped=False)

    def sync_sector_mapping(self) -> SyncResult:
        """Refresh stock-sector mapping when stale."""
        logger.info("data_sync.sync_sector_mapping started")
        max_age_hours = int(self.config["data_source"]["cache"]["sector_expire_days"]) * 24
        if self._table_is_fresh(SectorMapping, max_age_hours):
            logger.info("sector_mapping is fresh; skipped")
            return SyncResult(0, 0, 0, skipped=True)
        try:
            frame = run_with_degradation(self.providers, self._event_chain(), "get_sector_mapping", self.degradation_manager)
            self._upsert_sector_mapping(frame)
            return SyncResult(len(frame), 0, 1 if frame.attrs.get("data_quality") != "full" else 0, skipped=False)
        except Exception as exc:
            logger.warning("sync_sector_mapping failed reason=%s", exc)
            return SyncResult(0, 1, 0, skipped=False)

    def sync_sector_daily(self, date_text: str) -> SyncResult:
        """Aggregate a minimal sector daily summary from cached stock rows."""
        logger.info("data_sync.sync_sector_daily date=%s", date_text)
        target_date = self._parse_compact_date(date_text)
        with self.session_factory() as session:
            mappings = session.query(SectorMapping).all()
            if not mappings:
                return SyncResult(0, 0, 0, skipped=False)
            rows = []
            for sector_name in sorted({item.sector_name for item in mappings}):
                symbols = [item.symbol for item in mappings if item.sector_name == sector_name]
                klines = session.query(DailyKline).filter(DailyKline.symbol.in_(symbols), DailyKline.date == target_date).all()
                limit_count = session.query(LimitUpRecord).filter(LimitUpRecord.symbol.in_(symbols), LimitUpRecord.date == target_date).count()
                lianban_count = session.query(LianbanRecord).filter(LianbanRecord.symbol.in_(symbols), LianbanRecord.date == target_date, LianbanRecord.lianban_count >= 2).count()
                if klines:
                    pct_values = [(row.close - row.open) / row.open * 100 for row in klines if row.open]
                    pct_chg = sum(pct_values) / len(pct_values) if pct_values else 0.0
                    amount = sum(row.amount for row in klines)
                else:
                    pct_chg = 0.0
                    amount = 0.0
                rows.append(
                    {
                        "sector_name": sector_name,
                        "date": target_date,
                        "pct_chg": pct_chg,
                        "amount": amount,
                        "limit_up_count": limit_count,
                        "lianban_count": lianban_count,
                        "updated_at": self._now(),
                    }
                )
            statement = insert(SectorDaily).values(rows)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["sector_name", "date"],
                    set_={
                        "pct_chg": statement.excluded.pct_chg,
                        "amount": statement.excluded.amount,
                        "limit_up_count": statement.excluded.limit_up_count,
                        "lianban_count": statement.excluded.lianban_count,
                        "updated_at": statement.excluded.updated_at,
                    },
                )
            )
        return SyncResult(len(rows), 0, 0, skipped=False)

    def sync_all(self) -> SyncResult:
        """Run Phase 1 sync unless today's daily data has already been completed."""
        logger.info("data_sync.sync_all started")
        today = self._today_iso()
        last_update = self._get_meta("last_daily_update")
        if last_update == today and not self.force:
            logger.info("data already synced for today; skipped")
            return SyncResult(0, 0, 0, skipped=True)

        symbols = self.stock_pool_filter.load_watchlist(str(self.config["stock_pool"]["watchlist_path"]))
        if not symbols:
            symbols = [f"{index:06d}.SZ" for index in range(1, 6)]

        trade_date = self._today_compact()
        result = SyncResult(0, 0, 0, skipped=False)
        for step_result in (
            self.sync_sector_mapping(),
            self.sync_daily(symbols),
            self.sync_limit_up(trade_date),
            self.sync_lianban(trade_date),
            self.sync_sector_daily(trade_date),
        ):
            result = result.combine(step_result)
        self._set_meta("last_daily_update", today)
        logger.info("data_sync.sync_all finished result=%s", result)
        return result

    def _build_providers(self) -> dict[str, DataProvider]:
        providers: dict[str, DataProvider] = {"mock": MockProvider()}
        try:
            providers["tushare"] = TushareProvider(self.config)
        except ConfigError as exc:
            logger.info("tushare provider disabled: %s", exc)
        providers["akshare"] = AkshareProvider(self.config)
        return providers

    def _daily_chain(self) -> list[str]:
        if "tushare" not in self.providers:
            return ["mock"]
        chain = [source for source in self.config["data_source"]["daily"]["chain"] if source in self.providers]
        return chain if chain else ["mock"]

    def _event_chain(self) -> list[str]:
        if "tushare" not in self.providers:
            return ["mock"]
        return ["tushare", "akshare", "mock"]

    def _upsert_limit_up(self, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        rows = []
        for record in frame.to_dict("records"):
            rows.append(
                {
                    "symbol": self._normalize_symbol(str(record["symbol"])),
                    "date": self._parse_any_date(record["date"]),
                    "limit_type": self._optional_str(record.get("limit_type")),
                    "first_time": self._optional_str(record.get("first_time")),
                    "last_time": self._optional_str(record.get("last_time")),
                    "open_count": self._optional_int(record.get("open_count")),
                    "updated_at": self._now(),
                }
            )
        with self.session_factory() as session:
            statement = insert(LimitUpRecord).values(rows)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["symbol", "date"],
                    set_={
                        "limit_type": statement.excluded.limit_type,
                        "first_time": statement.excluded.first_time,
                        "last_time": statement.excluded.last_time,
                        "open_count": statement.excluded.open_count,
                        "updated_at": statement.excluded.updated_at,
                    },
                )
            )

    def _upsert_sector_mapping(self, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        rows = []
        for record in frame.to_dict("records"):
            rows.append(
                {
                    "symbol": str(record["symbol"]),
                    "sector_name": str(record["sector_name"]),
                    "sector_code": str(record["sector_code"]),
                    "updated_at": self._now(),
                }
            )
        with self.session_factory() as session:
            statement = insert(SectorMapping).values(rows)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["symbol", "sector_code"],
                    set_={
                        "sector_name": statement.excluded.sector_name,
                        "updated_at": statement.excluded.updated_at,
                    },
                )
            )

    def _table_is_fresh(self, model: type[Any], max_age_hours: int) -> bool:
        with self.session_factory() as session:
            latest = session.query(model.updated_at).order_by(model.updated_at.desc()).limit(1).scalar()
        if latest is None:
            return False
        return (self._now() - latest).total_seconds() <= max_age_hours * 3600

    def _get_meta(self, key: str) -> str:
        with self.session_factory() as session:
            row = session.query(SystemMeta).filter_by(key=key).one_or_none()
            return row.value if row else ""

    def _set_meta(self, key: str, value: str) -> None:
        with self.session_factory() as session:
            row = session.query(SystemMeta).filter_by(key=key).one_or_none()
            if row is None:
                session.add(SystemMeta(key=key, value=value))
            else:
                row.value = value

    def _today_iso(self) -> str:
        return self._local_now().date().isoformat()

    def _today_compact(self) -> str:
        return self._local_now().strftime("%Y%m%d")

    def _compact_days_ago(self, days: int) -> str:
        return (self._local_now().date() - timedelta(days=days)).strftime("%Y%m%d")

    def _parse_compact_date(self, value: str) -> date:
        return datetime.strptime(value, "%Y%m%d").date()

    def _parse_any_date(self, value: Any) -> date:
        if isinstance(value, date) and not isinstance(value, datetime):
            return value
        text = str(value)
        if "-" in text:
            return datetime.strptime(text, "%Y-%m-%d").date()
        return self._parse_compact_date(text)

    def _now(self) -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)

    def _local_now(self) -> datetime:
        timezone_name = str(self.config["system"]["timezone"])
        return datetime.now(ZoneInfo(timezone_name))

    def _optional_str(self, value: Any) -> str | None:
        if value is None or pd.isna(value):
            return None
        return str(value)

    def _optional_int(self, value: Any) -> int | None:
        if value is None or pd.isna(value):
            return None
        return int(value)

    def _normalize_symbol(self, value: str) -> str:
        text = value.strip().upper()
        if "." in text:
            return text
        if text.startswith(("6", "9")):
            return f"{text}.SH"
        return f"{text}.SZ"
