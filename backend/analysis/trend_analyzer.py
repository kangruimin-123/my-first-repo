from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd


EPSILON = 1e-9


@dataclass(frozen=True)
class TrendResult:
    state: str
    ma5: float
    ma10: float
    ma20: float
    ma60: float
    ma_alignment: str
    slope_20: float


def analyze_trend(df: pd.DataFrame, config: dict[str, Any] | None = None) -> TrendResult:
    """Calculate moving-average alignment and MA20 slope for trend classification."""
    ordered = df.sort_values("date") if "date" in df.columns else df.copy()
    close = pd.to_numeric(ordered["close"], errors="coerce").ffill()
    ma5_series = close.rolling(5, min_periods=1).mean()
    ma10_series = close.rolling(10, min_periods=1).mean()
    ma20_series = close.rolling(20, min_periods=1).mean()
    ma60_series = close.rolling(60, min_periods=1).mean()
    ma5 = float(ma5_series.iloc[-1])
    ma10 = float(ma10_series.iloc[-1])
    ma20 = float(ma20_series.iloc[-1])
    ma60 = float(ma60_series.iloc[-1])
    base_index = -6 if len(ma20_series) >= 6 else 0
    previous_ma20 = float(ma20_series.iloc[base_index])
    slope_20 = 0.0 if abs(previous_ma20) <= EPSILON else (ma20 - previous_ma20) / previous_ma20

    if ma5 > ma10 > ma20 > ma60:
        alignment = "多头排列"
    elif ma5 < ma10 < ma20 < ma60:
        alignment = "空头排列"
    else:
        alignment = "混乱"

    if alignment == "多头排列" and slope_20 > 0.02:
        state = "strong_up"
    elif alignment == "空头排列" and slope_20 < -0.02:
        state = "strong_down"
    elif abs(slope_20) < 0.005:
        state = "consolidation"
    elif ma5 > ma20 and slope_20 > 0:
        state = "up"
    elif ma5 < ma20 and slope_20 < 0:
        state = "down"
    else:
        state = "consolidation"

    return TrendResult(state, ma5, ma10, ma20, ma60, alignment, slope_20)
