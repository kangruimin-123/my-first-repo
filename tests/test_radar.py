from __future__ import annotations

from types import SimpleNamespace

import pandas as pd

from backend.analysis.mainline_radar import MainlineRadar


def radar_config(min_score: float = 50) -> dict[str, object]:
    return {
        "radar": {
            "mainline_radar": {
                "scan_range": [6, 20],
                "min_radar_score": min_score,
                "signal_weights": {
                    "limit_up_cluster": 0.35,
                    "volume_surge": 0.25,
                    "leader_move": 0.25,
                    "sustained": 0.15,
                },
                "stage_multiplier": {
                    "stage_0": 1.0,
                    "stage_1": 1.0,
                    "stage_2": 0.8,
                    "stage_3": 0.3,
                    "stage_4": 0.3,
                },
            }
        }
    }


def sector_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"sector_name": f"Top{i}", "rank": i, "pct_chg": 4.0, "amount": 1000, "avg_amount_5d": 900, "limit_up_count": 5}
            for i in range(1, 6)
        ]
        + [
            {"sector_name": "固态电池", "rank": 6, "pct_chg": 1.2, "amount": 1200, "avg_amount_5d": 1000, "limit_up_count": 2},
            {"sector_name": "低空经济", "rank": 7, "pct_chg": 1.0, "amount": 1700, "avg_amount_5d": 1000, "limit_up_count": 0},
        ]
    )


def stage_result(sector_name: str, stage: str) -> SimpleNamespace:
    return SimpleNamespace(symbol=f"{sector_name}1", sector_name=sector_name, stage=stage)


def test_limit_up_cluster_stage1_scores_high() -> None:
    results = MainlineRadar().scan(
        sector_frame(),
        pd.DataFrame(),
        [],
        {"A": stage_result("固态电池", "stage_1_start")},
        radar_config(),
    )

    solid = next(item for item in results if item.sector_name == "固态电池")
    assert solid.radar_score >= 50
    assert solid.signal_type == "limit_up_cluster"
    assert solid.stage_filter == "early"


def test_limit_up_cluster_stage4_is_discounted() -> None:
    results = MainlineRadar().scan(
        sector_frame(),
        pd.DataFrame(),
        [],
        {"A": stage_result("固态电池", "stage_4_decline")},
        radar_config(min_score=0),
    )

    solid = next(item for item in results if item.sector_name == "固态电池")
    assert solid.radar_score < 30
    assert solid.stage_filter == "decline"


def test_top5_sector_is_not_scanned() -> None:
    results = MainlineRadar().scan(
        sector_frame(),
        pd.DataFrame(),
        [],
        {"A": stage_result("Top1", "stage_1_start")},
        radar_config(min_score=0),
    )

    assert all(item.sector_name != "Top1" for item in results)


def test_sustained_signal_adds_score() -> None:
    base_results = MainlineRadar().scan(
        sector_frame(),
        pd.DataFrame(),
        [],
        {"A": stage_result("低空经济", "stage_1_start")},
        radar_config(min_score=0),
    )
    sustained_results = MainlineRadar().scan(
        sector_frame(),
        pd.DataFrame(),
        [{"sector_name": "低空经济", "signal_type": "volume_surge"}],
        {"A": stage_result("低空经济", "stage_1_start")},
        radar_config(min_score=0),
    )

    base = next(item for item in base_results if item.sector_name == "低空经济")
    sustained = next(item for item in sustained_results if item.sector_name == "低空经济")
    assert sustained.radar_score > base.radar_score
    assert sustained.signal_type == "sustained"
