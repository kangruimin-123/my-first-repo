from __future__ import annotations

from datetime import date

import pandas as pd

from backend.analysis.mainline_analyzer import MainlineAnalyzer, MainlineResult
from backend.db import MainlineHistory, SectorDaily, get_session
from backend.strategy.base_strategy import StrategyContext
from backend.strategy.mainline_strategy import MainlineStrategy


def mainline_config() -> dict[str, object]:
    return {
        "mainline": {
            "top_n": 5,
            "score_weights": {
                "sector_pct_chg": 0.20,
                "sector_amount": 0.15,
                "limit_up_count": 0.20,
                "lianban_count": 0.15,
                "leader_strength": 0.15,
                "duration": 0.10,
                "money_flow": 0.05,
            },
            "status_thresholds": {
                "rising_min_score": 60,
                "fading_max_score": 30,
                "rotation_volatility": 0.5,
            },
            "switch_threshold": 0.3,
        },
        "strategies": {},
    }


def sector_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"sector_name": "AI应用", "pct_chg": 5.5, "amount": 900, "limit_up_count": 8, "lianban_count": 3, "leader_strength": 9.5},
            {"sector_name": "机器人", "pct_chg": 4.0, "amount": 800, "limit_up_count": 6, "lianban_count": 2, "leader_strength": 8.0},
            {"sector_name": "有色金属", "pct_chg": 2.5, "amount": 700, "limit_up_count": 4, "lianban_count": 1, "leader_strength": 6.0},
            {"sector_name": "电力", "pct_chg": 1.5, "amount": 500, "limit_up_count": 3, "lianban_count": 1, "leader_strength": 4.5},
            {"sector_name": "军工", "pct_chg": 1.0, "amount": 400, "limit_up_count": 2, "lianban_count": 0, "leader_strength": 3.0},
            {"sector_name": "消费", "pct_chg": -1.0, "amount": 200, "limit_up_count": 0, "lianban_count": 0, "leader_strength": -0.5},
        ]
    )


def test_detect_orders_top5_by_score() -> None:
    analyzer = MainlineAnalyzer(mainline_config())

    results = analyzer.detect(sector_frame(), pd.DataFrame(), pd.DataFrame())

    assert [result.sector_name for result in results] == ["AI应用", "机器人", "有色金属", "电力", "军工"]
    assert [result.rank for result in results] == [1, 2, 3, 4, 5]
    assert results[0].mainline_score > results[1].mainline_score


def test_money_flow_missing_redistributes_weight() -> None:
    analyzer = MainlineAnalyzer(mainline_config())
    results = analyzer.detect(sector_frame(), pd.DataFrame(), pd.DataFrame())

    top_factors = results[0].factors
    assert "money_flow" in top_factors
    assert pd.isna(top_factors["money_flow"])
    assert results[0].mainline_score == 89.47


def test_status_rising_and_fading() -> None:
    analyzer = MainlineAnalyzer(mainline_config())
    results = analyzer.detect(sector_frame(), pd.DataFrame(), pd.DataFrame())

    assert results[0].mainline_status == "rising"
    assert results[-1].mainline_status == "fading"


def test_status_continuing_when_previous_top_remains() -> None:
    config = mainline_config()
    config["mainline"]["status_thresholds"]["rising_min_score"] = 95
    analyzer = MainlineAnalyzer(config)
    history = [MainlineResult("机器人", 70.0, "rising", 1, {})]

    results = analyzer.detect(sector_frame(), pd.DataFrame(), pd.DataFrame(), history)
    robot = next(result for result in results if result.sector_name == "机器人")

    assert robot.mainline_status == "continuing"


def test_status_rotation_when_top5_changes_fast() -> None:
    config = mainline_config()
    config["mainline"]["status_thresholds"]["rising_min_score"] = 95
    analyzer = MainlineAnalyzer(config)
    history = [
        MainlineResult("旧主线1", 70.0, "rising", 1, {}),
        MainlineResult("旧主线2", 69.0, "rising", 2, {}),
        MainlineResult("旧主线3", 68.0, "rising", 3, {}),
        MainlineResult("旧主线4", 67.0, "rising", 4, {}),
        MainlineResult("旧主线5", 66.0, "rising", 5, {}),
    ]

    results = analyzer.detect(sector_frame(), pd.DataFrame(), pd.DataFrame(), history)

    assert any(result.mainline_status == "rotation" for result in results)


def test_mainline_strategy_writes_history(db_engine) -> None:
    target_date = date(2026, 5, 17)
    with get_session(db_engine) as session:
        session.add_all(
            [
                SectorDaily(sector_name="AI应用", date=target_date, pct_chg=5.5, amount=900, limit_up_count=8, lianban_count=3),
                SectorDaily(sector_name="机器人", date=target_date, pct_chg=4.0, amount=800, limit_up_count=6, lianban_count=2),
                SectorDaily(sector_name="有色金属", date=target_date, pct_chg=2.5, amount=700, limit_up_count=4, lianban_count=1),
                SectorDaily(sector_name="电力", date=target_date, pct_chg=1.5, amount=500, limit_up_count=3, lianban_count=1),
                SectorDaily(sector_name="军工", date=target_date, pct_chg=1.0, amount=400, limit_up_count=2, lianban_count=0),
            ]
        )

    context = StrategyContext(config=mainline_config())
    signals = MainlineStrategy(mainline_config(), session_factory=lambda: get_session(db_engine)).execute(context)

    with get_session(db_engine) as session:
        rows = session.query(MainlineHistory).order_by(MainlineHistory.rank).all()
    assert len(rows) == 5
    assert rows[0].sector_name == "AI应用"
    assert len(signals) == 5
    assert context.mainline_results[0].sector_name == "AI应用"
