from __future__ import annotations

import logging
import time as time_module
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.orm import Session

from backend.config import load_config
from backend.data.efinance_provider import EfinanceProvider
from backend.db import DailyKline, IntradaySnapshot, ManualPosition, get_session, init_db


logger = logging.getLogger(__name__)
SessionContextFactory = Callable[[], AbstractContextManager[Session]]


@dataclass(frozen=True)
class IntradayRunResult:
    alerts: list[str]
    snapshot_count: int
    skipped: bool
    message: str


class IntradayRunner:
    def __init__(
        self,
        config: dict[str, Any] | None = None,
        provider: EfinanceProvider | None = None,
        session_factory: SessionContextFactory | None = None,
        now_func: Callable[[], datetime] | None = None,
    ) -> None:
        self.config = config or load_config()
        self.provider = provider or EfinanceProvider(self.config)
        self.now_func = now_func or self._local_now
        if session_factory is None:
            engine = init_db(db_path=str(self.config["system"]["db_path"]))
            self.session_factory = lambda: get_session(engine)
        else:
            self.session_factory = session_factory

    def run_loop(self, interval: int = 30) -> IntradayRunResult:
        """Run intraday monitoring loop; in this MVP, execute once per invocation."""
        if not self.is_trading_time(self.now_func()):
            result = IntradayRunResult([], 0, True, "非交易时段，盘中监控退出")
            print_intraday_result(result)
            return result
        result = self.run_once()
        print_intraday_result(result)
        if interval > 0:
            logger.info("intraday loop interval=%s seconds; MVP exits after one iteration", interval)
        return result

    def run_once(self) -> IntradayRunResult:
        symbols = self._symbols()
        if not symbols:
            return IntradayRunResult([], 0, True, "无盘中监控标的")
        quotes = self.provider.get_realtime_quotes(symbols)
        if quotes is None or quotes.empty:
            if "mock" not in self.config["data_source"]["intraday"]["chain"]:
                return IntradayRunResult([], 0, True, "实时数据不可用，跳过")
            quotes = self._mock_quotes(symbols)
        self._write_snapshots(quotes)
        alerts = self._stop_loss_alerts(quotes)
        alerts.extend(self._breakout_alerts(quotes))
        return IntradayRunResult(alerts, len(quotes), False, f"盘中快照 {len(quotes)} 条")

    def is_trading_time(self, now: datetime) -> bool:
        current = now.time()
        return time(9, 30) <= current <= time(11, 30) or time(13, 0) <= current <= time(15, 0)

    def _symbols(self) -> list[str]:
        with self.session_factory() as session:
            positions = [row.symbol for row in session.query(ManualPosition).all()]
            latest_date = session.query(DailyKline.date).order_by(DailyKline.date.desc()).limit(1).scalar()
            daily_symbols = []
            if latest_date is not None:
                daily_symbols = [row[0] for row in session.query(DailyKline.symbol).filter(DailyKline.date == latest_date).limit(30).all()]
        return list(dict.fromkeys(positions + daily_symbols))[:30]

    def _mock_quotes(self, symbols: list[str]) -> pd.DataFrame:
        rows = []
        for index, symbol in enumerate(symbols):
            rows.append({"symbol": symbol, "price": 10.0 + index, "volume": 1000 + index * 100, "amount": 10000 + index * 1000, "pct_chg": 0.5})
        return pd.DataFrame(rows)

    def _write_snapshots(self, quotes: pd.DataFrame) -> None:
        now = self.now_func()
        rows = []
        for record in quotes.to_dict("records"):
            rows.append(
                {
                    "symbol": str(record["symbol"]),
                    "date": now.date(),
                    "time": now.time().replace(microsecond=0),
                    "price": float(record.get("price", 0.0) or 0.0),
                    "volume": float(record.get("volume", 0.0) or 0.0),
                    "amount": float(record.get("amount", 0.0) or 0.0),
                    "updated_at": datetime.now(UTC).replace(tzinfo=None),
                }
            )
        with self.session_factory() as session:
            statement = insert(IntradaySnapshot).values(rows)
            session.execute(
                statement.on_conflict_do_update(
                    index_elements=["symbol", "date", "time"],
                    set_={
                        "price": statement.excluded.price,
                        "volume": statement.excluded.volume,
                        "amount": statement.excluded.amount,
                        "updated_at": statement.excluded.updated_at,
                    },
                )
            )

    def _stop_loss_alerts(self, quotes: pd.DataFrame) -> list[str]:
        price_map = {str(row["symbol"]): float(row["price"]) for _, row in quotes.iterrows()}
        alerts = []
        with self.session_factory() as session:
            positions = session.query(ManualPosition).all()
        for position in positions:
            current_price = price_map.get(position.symbol)
            if current_price is not None and position.stop_loss and current_price <= position.stop_loss:
                alerts.append(f"⚠ 止损预警：{position.name} {position.entry_price:.2f} → {current_price:.2f} 触及止损位 {position.stop_loss:.2f}")
        return alerts

    def _breakout_alerts(self, quotes: pd.DataFrame) -> list[str]:
        alerts = []
        with self.session_factory() as session:
            for _, quote in quotes.iterrows():
                symbol = str(quote["symbol"])
                highs = [row[0] for row in session.query(DailyKline.high).filter(DailyKline.symbol == symbol).order_by(DailyKline.date.desc()).limit(20).all()]
                if highs and float(quote["price"]) > max(highs):
                    alerts.append(f"📈 突破提示：{symbol} {float(quote['price']):.2f} 突破 20 日高点")
        return alerts

    def _local_now(self) -> datetime:
        return datetime.now(ZoneInfo(str(self.config["system"]["timezone"])))


def print_intraday_result(result: IntradayRunResult) -> None:
    print("Intraday monitor")
    print("----------------")
    print(result.message)
    print(f"snapshot_count: {result.snapshot_count}")
    if result.alerts:
        for alert in result.alerts:
            print(alert)
