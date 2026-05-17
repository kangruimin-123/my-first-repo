from __future__ import annotations

import logging
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from backend.config import load_config
from backend.data.efinance_provider import EfinanceProvider
from backend.db import AuctionSnapshot, DailyKline, SectorMapping, get_session, init_db
from backend.strategy.auction_strategy import AuctionStrategy
from backend.strategy.base_strategy import StrategyContext, StrategySignal


logger = logging.getLogger(__name__)
SessionContextFactory = Callable[[], AbstractContextManager[Session]]


@dataclass(frozen=True)
class AuctionRunResult:
    signals: list[StrategySignal]
    snapshot_count: int
    skipped: bool
    message: str


class AuctionRunner:
    def __init__(
        self,
        config: dict[str, Any] | None = None,
        provider: EfinanceProvider | None = None,
        session_factory: SessionContextFactory | None = None,
    ) -> None:
        self.config = config or load_config()
        self.provider = provider or EfinanceProvider(self.config)
        if session_factory is None:
            engine = init_db(db_path=str(self.config["system"]["db_path"]))
            self.session_factory = lambda: get_session(engine)
        else:
            self.session_factory = session_factory

    def run(self) -> AuctionRunResult:
        """Fetch auction data, persist snapshot and run auction_relative_strength."""
        symbols = self._symbols()
        if not symbols:
            return AuctionRunResult([], 0, True, "无可监控标的，跳过竞价")
        snapshot = self.provider.get_auction_snapshot(symbols)
        data_quality = "full"
        if snapshot is None or snapshot.empty:
            if "mock" not in self.config["data_source"]["auction"]["chain"]:
                return AuctionRunResult([], 0, True, "竞价数据不可用，跳过")
            snapshot = self._mock_snapshot(symbols)
            data_quality = "mock"
        snapshot.attrs["data_quality"] = data_quality
        self._write_snapshot(snapshot)

        context = StrategyContext(config=self.config, data_quality=data_quality)
        context.stock_analysis["auction_snapshot"] = snapshot
        context.stock_analysis["sector_map"] = self._sector_map()
        signals = AuctionStrategy(self.config).execute(context)
        return AuctionRunResult(signals, len(snapshot), False, f"竞价信号 {len(signals)} 条")

    def _symbols(self) -> list[str]:
        with self.session_factory() as session:
            latest_date = session.query(DailyKline.date).order_by(DailyKline.date.desc()).limit(1).scalar()
            if latest_date is None:
                return []
            rows = session.query(DailyKline.symbol).filter(DailyKline.date == latest_date).order_by(DailyKline.amount.desc()).limit(30).all()
        return [row[0] for row in rows]

    def _sector_map(self) -> dict[str, str]:
        with self.session_factory() as session:
            rows = session.query(SectorMapping).all()
        return {row.symbol: row.sector_name for row in rows}

    def _mock_snapshot(self, symbols: list[str]) -> pd.DataFrame:
        rows = []
        for index, symbol in enumerate(symbols):
            pct_chg = 1.0 + (index % 5) * 0.8
            rows.append(
                {
                    "symbol": symbol,
                    "open_price": 10.0 + index,
                    "auction_amount": 10_000_000 + index * 1_000_000,
                    "auction_volume": 100_000 + index * 10_000,
                    "pct_chg": pct_chg,
                    "avg_auction_volume_5d": 80_000,
                    "market_cap": 10_000_000_000,
                    "previous_pct_chg": -1.0 if index % 3 == 0 else 1.0,
                }
            )
        return pd.DataFrame(rows)

    def _write_snapshot(self, frame: pd.DataFrame) -> None:
        target_date = self._today()
        rows = []
        for record in frame.to_dict("records"):
            rows.append(
                {
                    "symbol": str(record["symbol"]),
                    "date": target_date,
                    "open_price": float(record.get("open_price", 0.0) or 0.0),
                    "auction_amount": float(record.get("auction_amount", 0.0) or 0.0),
                    "auction_volume": float(record.get("auction_volume", 0.0) or 0.0),
                    "pct_chg": float(record.get("pct_chg", 0.0) or 0.0),
                    "updated_at": datetime.now(UTC).replace(tzinfo=None),
                }
            )
        if not rows:
            return
        with self.session_factory() as session:
            statement = insert(AuctionSnapshot).values(rows)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["symbol", "date"],
                    set_={
                        "open_price": statement.excluded.open_price,
                        "auction_amount": statement.excluded.auction_amount,
                        "auction_volume": statement.excluded.auction_volume,
                        "pct_chg": statement.excluded.pct_chg,
                        "updated_at": statement.excluded.updated_at,
                    },
                )
            )

    def _today(self) -> date:
        return datetime.now(ZoneInfo(str(self.config["system"]["timezone"]))).date()
