from __future__ import annotations

from types import SimpleNamespace

from backend.engine.grading import Evaluation, Grader
from backend.strategy.base_strategy import StrategySignal


def grading_config() -> dict[str, object]:
    return {
        "grading": {
            "a_grade": {"min_confidence": 0.6},
            "b_grade": {"min_confidence": 0.4},
        }
    }


def signal(**kwargs) -> StrategySignal:
    base = {
        "strategy_name": "leader_breakout",
        "symbol": "000001.SZ",
        "action": "buy",
        "confidence": 0.7,
        "stop_loss_price": 9.0,
    }
    base.update(kwargs)
    return StrategySignal(**base)


def mainline(rank: int = 1) -> SimpleNamespace:
    return SimpleNamespace(sector_name="AI应用", rank=rank)


def deny(action: str = "pass") -> SimpleNamespace:
    return SimpleNamespace(action=action)


def test_grade_buy_a() -> None:
    assert Grader(grading_config()).grade_buy(signal(), mainline(1), deny("pass"), "full") == "A"


def test_grade_buy_b_by_rank() -> None:
    assert Grader(grading_config()).grade_buy(signal(), mainline(8), deny("pass"), "full") == "B"


def test_grade_buy_b_by_degraded() -> None:
    assert Grader(grading_config()).grade_buy(signal(), mainline(1), deny("pass"), "degraded") == "B"


def test_grade_buy_c_by_mock() -> None:
    assert Grader(grading_config()).grade_buy(signal(), mainline(1), deny("pass"), "mock") == "C"


def test_degraded_does_not_enter_a() -> None:
    assert Grader(grading_config()).grade_buy(signal(confidence=0.9), mainline(1), deny("pass"), "degraded") != "A"


def test_grade_none_when_not_mainline() -> None:
    assert Grader(grading_config()).grade_buy(signal(), None, deny("pass"), "full") == "NONE"


def test_grade_none_when_deny() -> None:
    assert Grader(grading_config()).grade_buy(signal(), mainline(1), deny("deny"), "full") == "NONE"


def test_select_focus_pool_limit_and_order() -> None:
    grader = Grader(grading_config())
    rows = [
        Evaluation(f"A{i}", "", "", "", "A", 90 - i, "无", "s", "buy", 0.9, "full", 0, 0, 1, 0.1, "")
        for i in range(3)
    ] + [
        Evaluation(f"B{i}", "", "", "", "B", 60 - i, "无", "s", "buy", 0.8 - i * 0.01, "full", 0, 0, 1, 0.1, "")
        for i in range(20)
    ] + [
        Evaluation("SELL", "", "", "", "C", 10, "清仓", "s", "sell", 0.1, "full", 0, 0, 1, 0.1, "")
    ]

    focus = grader.select_focus_pool(rows, max_n=10)

    assert len(focus) == 10
    assert [item.buy_grade for item in focus[:3]] == ["A", "A", "A"]
    assert any(item.symbol == "SELL" for item in focus)
