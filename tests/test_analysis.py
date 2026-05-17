from __future__ import annotations

import pandas as pd

from backend.analysis.market_risk_analyzer import analyze_market_risk
from backend.analysis.position_analyzer import analyze_position
from backend.analysis.trend_analyzer import analyze_trend
from backend.analysis.volume_price_analyzer import analyze_volume_price


def kline_from_closes(closes: list[float], volume: float = 1000.0) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2026-01-01") + pd.Timedelta(days=index),
                "open": close * 0.99,
                "high": close * 1.02,
                "low": close * 0.98,
                "close": close,
                "volume": volume,
                "turnover_rate": 5.0,
            }
            for index, close in enumerate(closes)
        ]
    )


def test_trend_strong_up() -> None:
    result = analyze_trend(kline_from_closes([10 + index * 0.2 for index in range(80)]), {})

    assert result.state == "strong_up"
    assert result.ma_alignment == "多头排列"


def test_trend_strong_down() -> None:
    result = analyze_trend(kline_from_closes([30 - index * 0.2 for index in range(80)]), {})

    assert result.state == "strong_down"
    assert result.ma_alignment == "空头排列"


def test_trend_consolidation() -> None:
    result = analyze_trend(kline_from_closes([10.0] * 80), {})

    assert result.state == "consolidation"


def test_position_near_resistance() -> None:
    frame = kline_from_closes([10 + index * 0.1 for index in range(20)])
    result = analyze_position(frame)

    assert result.near_resistance


def test_position_near_support() -> None:
    frame = kline_from_closes([12 - index * 0.1 for index in range(20)])
    result = analyze_position(frame)

    assert result.near_support


def test_position_middle_when_flat_range() -> None:
    frame = pd.DataFrame([{"date": "2026-01-01", "open": 10, "high": 10, "low": 10, "close": 10, "volume": 100}])
    result = analyze_position(frame)

    assert result.close_position == 0.5
    assert result.close_position_in_bar == 0.5


def test_volume_price_volume_expansion() -> None:
    frame = kline_from_closes([10, 10.1, 10.2, 10.3, 10.4], volume=1000)
    frame.loc[4, "volume"] = 3000
    result = analyze_volume_price(frame)

    assert result.volume_ratio > 1.5


def test_volume_price_shrink() -> None:
    frame = kline_from_closes([10, 10.1, 10.2, 10.3, 10.4], volume=1000)
    frame.loc[4, "volume"] = 300
    result = analyze_volume_price(frame)

    assert result.volume_ratio < 0.8


def test_volume_price_divergence() -> None:
    frame = kline_from_closes([10, 10.1, 10.2, 10.3, 11.0], volume=1000)
    frame.loc[4, "volume"] = 200
    result = analyze_volume_price(frame)

    assert result.price_volume_divergence


def index_data(closes: list[float]) -> dict[str, pd.DataFrame]:
    frame = pd.DataFrame({"date": list(range(len(closes))), "close": closes})
    return {"sh": frame.copy(), "sz": frame.copy(), "cy": frame.copy()}


def test_market_risk_on() -> None:
    result = analyze_market_risk(index_data([10 + index * 0.1 for index in range(30)]), pd.DataFrame({"pct_chg": [1, 2, -1]}))

    assert result.regime == "risk_on"
    assert result.index_above_ma20
    assert result.breadth == 2 / 3


def test_market_risk_weak() -> None:
    result = analyze_market_risk(index_data([20 - index * 0.2 for index in range(30)]), pd.DataFrame({"pct_chg": [-1, -2, 1]}))

    assert result.regime == "weak"
    assert not result.index_above_ma20


def test_market_risk_neutral() -> None:
    closes = [10.0] * 30
    result = analyze_market_risk(index_data(closes), pd.DataFrame({"pct_chg": [1, -1]}))

    assert result.regime == "neutral"
