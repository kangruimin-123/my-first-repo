from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace

import pandas as pd

from backend.analysis.risk_radar import RiskRadar


def config() -> dict[str, object]:
    return {
        "radar": {
            "risk_radar": {
                "leader_decay": {
                    "volume_decay_ratio": 0.8,
                    "stagnation_volume_ratio": 1.5,
                    "stagnation_max_pct": 1.0,
                    "upper_shadow_threshold": 0.3,
                },
                "sector_decay": {
                    "limit_up_decrease_days": 2,
                    "breadth_warning": 0.4,
                    "amount_shrink_ratio": 0.7,
                },
            }
        }
    }


def kline(rows: list[dict[str, float]]) -> pd.DataFrame:
    start = date(2026, 1, 1)
    data = []
    for index, row in enumerate(rows):
        data.append({"date": start + timedelta(days=index), **row})
    return pd.DataFrame(data)


def test_limit_up_volume_decay_warns_caution() -> None:
    daily = kline(
        [
            {"open": 10, "high": 11, "low": 9.8, "close": 11, "volume": 1000},
            {"open": 11, "high": 12.1, "low": 10.9, "close": 12.1, "volume": 700},
        ]
    )
    history = pd.DataFrame(
        [
            {"symbol": "000001.SZ", "date": date(2026, 1, 1), "lianban_count": 1},
            {"symbol": "000001.SZ", "date": date(2026, 1, 2), "lianban_count": 2},
        ]
    )

    warning = RiskRadar(config()).scan_leader_decay("000001.SZ", daily, history)

    assert warning is not None
    assert warning.level == "caution"
    assert "封单力量衰减" in warning.reason[0]


def test_high_position_volume_down_day_is_danger() -> None:
    daily = kline(
        [
            {"open": 9.6, "high": 10.0, "low": 9.4, "close": 9.8, "volume": 500},
            {"open": 9.8, "high": 10.5, "low": 9.7, "close": 10.4, "volume": 500},
            {"open": 10.4, "high": 11.0, "low": 10.3, "close": 10.9, "volume": 500},
            {"open": 10.9, "high": 11.6, "low": 10.8, "close": 11.5, "volume": 500},
            {"open": 11.5, "high": 12.2, "low": 11.4, "close": 12.0, "volume": 500},
            {"open": 12, "high": 12.3, "low": 11.0, "close": 11.8, "volume": 4000},
        ]
    )

    warning = RiskRadar(config()).scan_leader_decay("000002.SZ", daily, pd.DataFrame())

    assert warning is not None
    assert warning.level == "danger"
    assert "可能出货" in warning.reason[0]


def test_sector_leader_divergence_is_danger() -> None:
    sector_daily = pd.DataFrame(
        [
            {
                "date": date(2026, 1, 3),
                "sector_name": "AI应用",
                "pct_chg": 1.2,
                "leader_pct_chg": -2.0,
                "amount": 1000,
                "limit_up_count": 3,
            }
        ]
    )

    warning = RiskRadar(config()).scan_sector_decay("AI应用", sector_daily, pd.DataFrame())

    assert warning is not None
    assert warning.level == "danger"
    assert "龙头与板块背离" in warning.reason[0]


def test_multiple_mainlines_fading_is_danger() -> None:
    mainlines = [
        SimpleNamespace(sector_name=f"主线{index}", rank=index, mainline_status="fading")
        for index in range(1, 4)
    ] + [
        SimpleNamespace(sector_name="主线4", rank=4, mainline_status="rising"),
        SimpleNamespace(sector_name="主线5", rank=5, mainline_status="rising"),
    ]

    warnings = RiskRadar(config()).scan_cycle_end({}, mainlines)

    assert any(warning.level == "danger" and "系统性风险" in warning.reason[0] for warning in warnings)


def test_normal_uptrend_has_no_warning() -> None:
    daily = kline(
        [
            {"open": 10, "high": 10.6, "low": 9.9, "close": 10.5, "volume": 1000},
            {"open": 10.5, "high": 11.0, "low": 10.4, "close": 10.9, "volume": 1100},
            {"open": 10.9, "high": 11.4, "low": 10.8, "close": 11.3, "volume": 1200},
        ]
    )

    warning = RiskRadar(config()).scan_leader_decay("000003.SZ", daily, pd.DataFrame())

    assert warning is None
