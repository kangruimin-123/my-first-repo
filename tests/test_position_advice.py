from __future__ import annotations

from datetime import date

from backend.api import _position_action
from backend.db import DailyKline, ManualPosition, StageAnalysis


def position(cost: float = 10.0, stop_loss: float | None = None) -> ManualPosition:
    return ManualPosition(
        symbol="000001.SZ",
        name="测试股",
        entry_price=cost,
        entry_date=date(2026, 5, 1),
        quantity=100,
        stop_loss=stop_loss,
    )


def kline(close: float, open_price: float = 10.0) -> DailyKline:
    return DailyKline(
        symbol="000001.SZ",
        date=date(2026, 5, 18),
        open=open_price,
        high=max(open_price, close),
        low=min(open_price, close),
        close=close,
        volume=1000,
        amount=10000,
        turnover_rate=1,
    )


def stage(name: str, risk: str = "") -> StageAnalysis:
    return StageAnalysis(date=date(2026, 5, 18), symbol="000001.SZ", stage=name, risk_level=risk)


def test_position_action_sells_when_stop_loss_hit() -> None:
    action, reason = _position_action(position(stop_loss=9.2), kline(9.1), stage("stage_2_rising"), -9.0, {"support_5d": 9.0, "ma20": 9.5})

    assert action == "sell"
    assert "止损" in reason


def test_position_action_reduces_distribution_profit() -> None:
    action, reason = _position_action(position(), kline(12.0), stage("stage_3_distribution"), 20.0, {"support_5d": 10.0, "ma20": 11.0})

    assert action == "reduce"
    assert "高位分歧" in reason


def test_position_action_holds_rising_stage() -> None:
    action, reason = _position_action(position(), kline(10.8), stage("stage_2_rising"), 8.0, {"support_5d": 9.8, "ma20": 10.2})

    assert action == "hold"
    assert "主升阶段" in reason


def test_position_action_reduces_instead_of_sells_when_loss_not_broken() -> None:
    action, reason = _position_action(position(), kline(8.9), stage("stage_2_rising"), -11.0, {"support_5d": 8.8, "ma20": 9.2})

    assert action == "reduce"
    assert "未跌破5日低点" in reason


def test_position_action_sells_when_loss_and_structure_broken() -> None:
    action, reason = _position_action(position(), kline(8.6), stage("stage_2_rising"), -14.0, {"support_5d": 8.8, "ma20": 9.2})

    assert action == "sell"
    assert "持仓逻辑失效" in reason


def test_long_term_position_waits_for_cost_repair_when_stage_rising() -> None:
    action, reason = _position_action(
        position(cost=79.149),
        kline(71.15, open_price=71.15),
        stage("stage_2_rising"),
        -10.11,
        {"support_5d": 70.0, "ma20": 72.0, "is_long_term": True, "sector_name": "半导体"},
    )

    assert action == "hold"
    assert "成本修复" in reason or "修复" in reason
    assert "不加仓" in reason


def test_long_term_position_reduces_when_repair_fails() -> None:
    action, reason = _position_action(
        position(cost=79.149),
        kline(65.0, open_price=66.0),
        stage("stage_2_rising"),
        -17.87,
        {"support_5d": 68.0, "ma20": 70.0, "is_long_term": True, "sector_name": "半导体"},
    )

    assert action == "reduce"
    assert "修复失败" in reason
