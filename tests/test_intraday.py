from __future__ import annotations

from datetime import date, datetime

import pandas as pd

from backend.db import DailyKline, IntradaySnapshot, ManualPosition, get_session
from backend.engine.intraday_runner import IntradayRunner


def intraday_config(tmp_path=None) -> dict[str, object]:
    return {
        "system": {"timezone": "Asia/Shanghai", "db_path": str(tmp_path / "test.db") if tmp_path else ":memory:"},
        "data_source": {"intraday": {"chain": ["efinance", "mock"]}},
    }


class NoneProvider:
    def get_realtime_quotes(self, symbols: list[str]):
        return None


class QuoteProvider:
    def __init__(self, price: float = 8.8) -> None:
        self.price = price

    def get_realtime_quotes(self, symbols: list[str]):
        return pd.DataFrame([{"symbol": symbols[0], "price": self.price, "volume": 1000, "amount": 10000, "pct_chg": -2.0}])


def test_intraday_runner_exits_outside_trading_time(db_engine, tmp_path) -> None:
    runner = IntradayRunner(
        config=intraday_config(tmp_path),
        provider=NoneProvider(),
        session_factory=lambda: get_session(db_engine),
        now_func=lambda: datetime(2026, 5, 17, 16, 0),
    )

    result = runner.run_loop(interval=0)

    assert result.skipped
    assert "非交易时段" in result.message


def test_intraday_stop_loss_alert(db_engine, tmp_path) -> None:
    with get_session(db_engine) as session:
        session.add(ManualPosition(symbol="000001.SZ", name="测试股", entry_price=10, entry_date=date(2026, 5, 1), quantity=100, stop_loss=9.0))
        session.add(DailyKline(symbol="000001.SZ", date=date(2026, 5, 16), open=10, high=10.5, low=9.5, close=10, volume=1000, amount=10000, turnover_rate=1))

    runner = IntradayRunner(
        config=intraday_config(tmp_path),
        provider=QuoteProvider(8.8),
        session_factory=lambda: get_session(db_engine),
        now_func=lambda: datetime(2026, 5, 18, 10, 0),
    )

    result = runner.run_once()

    assert any("止损预警" in alert for alert in result.alerts)
    with get_session(db_engine) as session:
        assert session.query(IntradaySnapshot).count() == 1


def test_intraday_data_unavailable_uses_mock(db_engine, tmp_path) -> None:
    with get_session(db_engine) as session:
        session.add(DailyKline(symbol="000001.SZ", date=date(2026, 5, 16), open=10, high=10.5, low=9.5, close=10, volume=1000, amount=10000, turnover_rate=1))

    runner = IntradayRunner(
        config=intraday_config(tmp_path),
        provider=NoneProvider(),
        session_factory=lambda: get_session(db_engine),
        now_func=lambda: datetime(2026, 5, 18, 10, 0),
    )

    result = runner.run_once()

    assert not result.skipped
    assert result.snapshot_count == 1
