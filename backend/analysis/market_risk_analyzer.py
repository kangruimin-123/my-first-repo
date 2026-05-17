from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class MarketRiskResult:
    regime: str
    index_above_ma20: bool
    breadth: float


def analyze_market_risk(index_data: dict[str, pd.DataFrame], pool_data: pd.DataFrame) -> MarketRiskResult:
    """Classify market regime from weighted indexes and pool breadth."""
    composite = _composite_index(index_data)
    closes = pd.to_numeric(composite["close"], errors="coerce")
    ma20 = closes.rolling(20, min_periods=1).mean()
    index_above_ma20 = bool(closes.iloc[-1] > ma20.iloc[-1])
    recent_diff = closes.diff().tail(5)
    up_days = int((recent_diff > 0).sum())
    down_days = int((recent_diff < 0).sum())

    if pool_data.empty:
        breadth = 0.0
    else:
        pct_chg = pd.to_numeric(pool_data["pct_chg"], errors="coerce").fillna(0.0)
        breadth = float((pct_chg > 0).sum() / len(pct_chg))

    if index_above_ma20 and up_days > down_days:
        regime = "risk_on"
    elif not index_above_ma20 and down_days >= 3:
        regime = "weak"
    else:
        regime = "neutral"
    return MarketRiskResult(regime=regime, index_above_ma20=index_above_ma20, breadth=breadth)


def _composite_index(index_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    weights = {"sh": 0.4, "sz": 0.3, "cy": 0.3}
    series_list = []
    for key, weight in weights.items():
        frame = index_data[key].sort_values("date")
        close = pd.to_numeric(frame["close"], errors="coerce").reset_index(drop=True) * weight
        series_list.append(close)
    composite_close = sum(series_list)
    return pd.DataFrame({"close": composite_close})
