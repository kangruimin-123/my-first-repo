from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

from backend.db import SystemMeta, get_session, get_system_meta
from backend.engine.trade_day_runner import TradeDayRunner


def trade_day_config(tmp_path) -> dict[str, object]:
    return {"system": {"timezone": "Asia/Shanghai", "db_path": str(tmp_path / "test.db")}}


class FakeAuctionRunner:
    def run(self):
        return SimpleNamespace(skipped=False, message="竞价信号 2 条", snapshot_count=10, signals=[object(), object()])


class FakeIntradayRunner:
    def run_once(self):
        return SimpleNamespace(skipped=False, message="盘中快照 3 条", snapshot_count=3, alerts=["突破提示"])


class FakeDailyRunner:
    def run(self):
        return SimpleNamespace(
            sync_result=SimpleNamespace(skipped=False),
            focus_pool=[object()],
            observation_pool=[object(), object()],
            radar_results=[object()],
            risk_warnings=[],
            output_dir="output/20260518",
        )


def test_trade_day_auto_routes_to_opening(db_engine, tmp_path) -> None:
    runner = TradeDayRunner(
        config=trade_day_config(tmp_path),
        session_factory=lambda: get_session(db_engine),
        now_func=lambda: datetime(2026, 5, 18, 9, 25),
        auction_factory=FakeAuctionRunner,
    )

    result = runner.run_phase("auto")

    assert result.phase == "opening"
    assert "开盘指导完成" in result.message
    with get_session(db_engine) as session:
        meta = get_system_meta(session)
    assert meta["trade_day.last_phase"] == "opening"
    assert meta["trade_day.opening.last_date"] == "2026-05-18"


def test_trade_day_intraday_records_alert_detail(db_engine, tmp_path) -> None:
    runner = TradeDayRunner(
        config=trade_day_config(tmp_path),
        session_factory=lambda: get_session(db_engine),
        now_func=lambda: datetime(2026, 5, 18, 10, 15),
        intraday_factory=FakeIntradayRunner,
    )

    result = runner.run_phase("intraday")

    assert result.phase == "intraday"
    assert "alerts=1" in result.detail
    assert "突破提示" in result.detail


def test_trade_day_pending_skips_repeated_review(db_engine, tmp_path) -> None:
    with get_session(db_engine) as session:
        session.add(SystemMeta(key="trade_day.review.last_date", value="2026-05-18"))
    runner = TradeDayRunner(
        config=trade_day_config(tmp_path),
        session_factory=lambda: get_session(db_engine),
        now_func=lambda: datetime(2026, 5, 18, 15, 30),
        daily_factory=FakeDailyRunner,
    )

    result = runner.run_pending_once()

    assert result.phase == "review"
    assert result.skipped
    assert "今日已执行" in result.message
