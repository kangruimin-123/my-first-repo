from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from backend.analysis.leader_radar import LeaderRadar


def config() -> dict[str, object]:
    return {
        "radar": {
            "leader_radar": {
                "factor_weights": {
                    "history": 0.30,
                    "purity": 0.20,
                    "capacity": 0.20,
                    "turnover": 0.15,
                    "stage": 0.15,
                }
            }
        }
    }


def stage(stage_name: str) -> SimpleNamespace:
    return SimpleNamespace(stage=stage_name)


def test_limit_up_history_pure_theme_stage1_scores_high() -> None:
    stocks = pd.DataFrame(
        [
            {
                "symbol": "000001.SZ",
                "name": "核心科技",
                "sector_name": "AI应用",
                "concept_count": 1,
                "float_market_cap": 120,
                "turnover_20d": 120,
            }
        ]
    )
    history = pd.DataFrame([{"symbol": "000001.SZ", "lianban_count": 2, "was_sector_leader": False}])

    results = LeaderRadar().scan("AI应用", stocks, history, {"000001.SZ": stage("stage_1_start")}, config())

    assert results[0].symbol == "000001.SZ"
    assert results[0].leader_probability >= 0.75
    assert results[0].role_type == "potential_leader"
    assert results[0].factors["history"] == 50.0


def test_multi_concept_stage3_scores_low() -> None:
    stocks = pd.DataFrame(
        [
            {
                "symbol": "000002.SZ",
                "name": "泛概念",
                "sector_name": "AI应用",
                "concept_count": 7,
                "float_market_cap": 120,
                "turnover_20d": 30,
            }
        ]
    )

    results = LeaderRadar().scan("AI应用", stocks, pd.DataFrame(), {"000002.SZ": stage("stage_3_distribution")}, config())

    assert results[0].leader_probability < 0.45
    assert results[0].factors["purity"] == 20.0
    assert results[0].factors["stage"] == 10.0
    assert "Stage 3/4 降权" in results[0].reason


def test_large_market_cap_marks_potential_mid() -> None:
    stocks = pd.DataFrame(
        [
            {
                "symbol": "000003.SZ",
                "name": "大市值中军",
                "sector_name": "AI应用",
                "concept_count": 2,
                "float_market_cap": 900,
                "turnover_20d": 90,
            }
        ]
    )
    history = pd.DataFrame([{"symbol": "000003.SZ", "lianban_count": 1, "was_sector_leader": False}])

    results = LeaderRadar().scan("AI应用", stocks, history, {"000003.SZ": stage("stage_1_start")}, config())

    assert results[0].role_type == "potential_mid"
    assert results[0].factors["capacity"] == 40.0
