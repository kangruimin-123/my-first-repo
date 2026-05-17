from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd

from backend.db import DailyKline, StrategySignal, get_session
from backend.strategy.signal_eval_strategy import SignalEval


def eval_config(tmp_path) -> dict[str, object]:
    return {"system": {"db_path": str(tmp_path / "test.db")}}


def add_kline(session, symbol: str, row_date: date, close: float, low: float | None = None) -> None:
    session.add(
        DailyKline(
            symbol=symbol,
            date=row_date,
            open=close,
            high=close * 1.02,
            low=low if low is not None else close * 0.98,
            close=close,
            volume=1000,
            amount=close * 1000,
            turnover_rate=1.0,
        )
    )


def add_signal(
    session,
    symbol: str,
    signal_date: date,
    strategy: str = "leader_breakout",
    stop_loss: float = 9.0,
    action: str = "buy",
    stage: str = "",
    reason: str = "",
) -> None:
    session.add(
        StrategySignal(
            date=signal_date,
            symbol=symbol,
            strategy_name=strategy,
            action=action,
            confidence=0.7,
            data_quality="full",
            signal_json=json.dumps({"stop_loss_price": stop_loss, "stage": stage, "reason": reason}, ensure_ascii=False),
        )
    )


def test_signal_eval_win_rate_calculation(db_engine, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    signal_date = date.today() - timedelta(days=10)
    with get_session(db_engine) as session:
        for index in range(10):
            symbol = f"0000{index:02d}.SZ"
            add_signal(session, symbol, signal_date)
            add_kline(session, symbol, signal_date, 10.0)
            for day in range(1, 6):
                close = 11.0 if index < 6 else 9.0
                add_kline(session, symbol, signal_date + timedelta(days=day), close)

    results = SignalEval(config=eval_config(tmp_path), session_factory=lambda: get_session(db_engine)).evaluate(60)

    assert len(results) == 1
    assert results[0].total_signals == 10
    assert results[0].win_rate_1d == 0.6
    assert results[0].win_rate_3d == 0.6
    assert results[0].win_rate_5d == 0.6
    assert round(results[0].avg_return_5d, 4) == 0.02
    assert (tmp_path / "output" / "signal_eval_report.csv").exists()


def test_signal_eval_insufficient_signals(db_engine, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    signal_date = date.today() - timedelta(days=10)
    with get_session(db_engine) as session:
        add_signal(session, "000001.SZ", signal_date)
        add_kline(session, "000001.SZ", signal_date, 10.0)
        add_kline(session, "000001.SZ", signal_date + timedelta(days=1), 11.0)

    results = SignalEval(config=eval_config(tmp_path), session_factory=lambda: get_session(db_engine)).evaluate(60)

    assert results == []
    assert (tmp_path / "output" / "signal_eval_report.csv").exists()


def test_signal_eval_max_drawdown_and_stop_loss(db_engine, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    signal_date = date.today() - timedelta(days=10)
    with get_session(db_engine) as session:
        for index in range(5):
            symbol = f"1000{index:02d}.SZ"
            add_signal(session, symbol, signal_date, stop_loss=9.2)
            add_kline(session, symbol, signal_date, 10.0)
            add_kline(session, symbol, signal_date + timedelta(days=1), 10.5, low=9.5)
            add_kline(session, symbol, signal_date + timedelta(days=2), 10.8, low=9.0)
            add_kline(session, symbol, signal_date + timedelta(days=3), 11.0, low=9.6)
            add_kline(session, symbol, signal_date + timedelta(days=4), 10.7, low=9.7)
            add_kline(session, symbol, signal_date + timedelta(days=5), 10.9, low=9.8)

    results = SignalEval(config=eval_config(tmp_path), session_factory=lambda: get_session(db_engine)).evaluate(60)

    assert len(results) == 1
    assert round(results[0].max_drawdown_5d, 4) == -0.1
    assert results[0].hit_stop_loss_rate == 1.0


def test_signal_eval_groups_by_stage(db_engine, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    signal_date = date.today() - timedelta(days=10)
    with get_session(db_engine) as session:
        for index in range(5):
            symbol = f"2000{index:02d}.SZ"
            add_signal(session, symbol, signal_date, stage="stage_2_rising")
            add_kline(session, symbol, signal_date, 10.0)
            for day in range(1, 6):
                add_kline(session, symbol, signal_date + timedelta(days=day), 11.0)

    SignalEval(config=eval_config(tmp_path), session_factory=lambda: get_session(db_engine)).evaluate(60)

    frame = pd.read_csv(tmp_path / "output" / "signal_eval_by_stage.csv")
    row = frame[frame["stage"] == "stage_2_rising"].iloc[0]
    assert int(row["total_signals"]) == 5
    assert row["win_rate_5d"] == 1.0


def test_signal_eval_stage_blocked_hypothetical_performance(db_engine, tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    signal_date = date.today() - timedelta(days=10)
    with get_session(db_engine) as session:
        for index in range(3):
            symbol = f"3000{index:02d}.SZ"
            add_signal(
                session,
                symbol,
                signal_date,
                strategy="leader_pullback",
                action="deny",
                stage="stage_3_distribution",
                reason="阶段门控禁止买入",
            )
            add_kline(session, symbol, signal_date, 10.0)
            for day in range(1, 6):
                add_kline(session, symbol, signal_date + timedelta(days=day), 9.0, low=8.8)

    SignalEval(config=eval_config(tmp_path), session_factory=lambda: get_session(db_engine)).evaluate(60)

    frame = pd.read_csv(tmp_path / "output" / "signal_eval_by_stage.csv")
    row = frame[frame["stage"] == "stage_3_distribution(拦截)"].iloc[0]
    assert int(row["blocked_signals"]) == 3
    assert row["win_rate_5d"] == 0.0
    assert round(row["avg_return_5d"], 4) == -0.1
