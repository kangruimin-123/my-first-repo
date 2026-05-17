from __future__ import annotations

from datetime import date

import pandas as pd

from backend.db import DailyKline, MainlineHistory, RoleAssignment, SectorMapping, get_session
from backend.strategy.base_strategy import StrategyContext
from backend.strategy.leader_detect_strategy import LeaderDetectStrategy


def role_config() -> dict[str, object]:
    return {
        "role_detect": {
            "leader": {"min_amount_rank_pct": 0.2, "min_pct_chg_rank_pct": 0.2},
            "core_mid": {"min_market_cap": 100, "require_ma20_up": True, "require_ma60_up": True},
            "elastic": {"max_market_cap": 100, "min_turnover": 5.0},
        },
        "strategies": {"leader_detect": {"enabled": True}},
    }


def stocks_df() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"symbol": "A", "pct_chg": 9.0, "amount": 900, "market_cap": 80, "turnover_rate": 8, "ma20_slope": 0.01, "ma60_slope": 0.01, "volatility": 0.08},
            {"symbol": "B", "pct_chg": 6.0, "amount": 850, "market_cap": 160, "turnover_rate": 4, "ma20_slope": 0.02, "ma60_slope": 0.01, "volatility": 0.04},
            {"symbol": "C", "pct_chg": 4.0, "amount": 500, "market_cap": 70, "turnover_rate": 9, "ma20_slope": 0.00, "ma60_slope": 0.00, "volatility": 0.06},
            {"symbol": "D", "pct_chg": 2.0, "amount": 300, "market_cap": 60, "turnover_rate": 3, "ma20_slope": -0.01, "ma60_slope": -0.01, "volatility": 0.02},
            {"symbol": "E", "pct_chg": 1.0, "amount": 100, "market_cap": 200, "turnover_rate": 2, "ma20_slope": 0.01, "ma60_slope": 0.01, "volatility": 0.01},
        ]
    )


def test_detect_leaders_normal() -> None:
    results = LeaderDetectStrategy(role_config()).detect_leaders("AI应用", stocks_df())

    assert [item.symbol for item in results] == ["A"]
    assert results[0].role == "leader"


def test_detect_leaders_no_match() -> None:
    frame = stocks_df()
    frame["amount"] = [100, 900, 800, 700, 600]

    assert LeaderDetectStrategy(role_config()).detect_leaders("AI应用", frame) == []


def test_detect_leaders_sector_only_two_stocks() -> None:
    assert LeaderDetectStrategy(role_config()).detect_leaders("AI应用", stocks_df().head(2)) == []


def test_detect_core_mid_normal() -> None:
    results = LeaderDetectStrategy(role_config()).detect_core_mid("AI应用", stocks_df())

    assert [item.symbol for item in results] == ["B", "E"]
    assert all(item.role == "core_mid" for item in results)


def test_detect_core_mid_market_cap_too_small() -> None:
    frame = stocks_df()
    frame["market_cap"] = 80

    assert LeaderDetectStrategy(role_config()).detect_core_mid("AI应用", frame) == []


def test_detect_core_mid_ma_not_up() -> None:
    frame = stocks_df()
    frame["ma20_slope"] = -0.01

    assert LeaderDetectStrategy(role_config()).detect_core_mid("AI应用", frame) == []


def test_detect_elastic_normal() -> None:
    results = LeaderDetectStrategy(role_config()).detect_elastic("AI应用", stocks_df())

    assert [item.symbol for item in results] == ["A", "C"]
    assert all(item.role == "elastic" for item in results)


def test_detect_elastic_market_cap_too_large() -> None:
    frame = stocks_df()
    frame["market_cap"] = 120

    assert LeaderDetectStrategy(role_config()).detect_elastic("AI应用", frame) == []


def test_detect_elastic_turnover_too_low() -> None:
    frame = stocks_df()
    frame["turnover_rate"] = 3

    assert LeaderDetectStrategy(role_config()).detect_elastic("AI应用", frame) == []


def test_execute_writes_role_assignment(db_engine) -> None:
    target_date = date(2026, 5, 17)
    with get_session(db_engine) as session:
        session.add(MainlineHistory(date=target_date, sector_name="AI应用", mainline_score=80, mainline_status="rising", rank=1, factors_json="{}"))
        session.add_all([SectorMapping(symbol=f"00000{index}.SZ", sector_name="AI应用", sector_code="BK001") for index in range(1, 6)])
        for index in range(1, 6):
            session.add(
                DailyKline(
                    symbol=f"00000{index}.SZ",
                    date=target_date,
                    open=10,
                    high=11 + index,
                    low=9,
                    close=10 + index * 0.2,
                    volume=1000000,
                    amount=1000000 * index,
                    turnover_rate=2 + index,
                )
            )

    context = StrategyContext(config=role_config())
    signals = LeaderDetectStrategy(role_config(), session_factory=lambda: get_session(db_engine)).execute(context)

    with get_session(db_engine) as session:
        rows = session.query(RoleAssignment).all()
    assert rows
    assert signals
    assert context.role_results
