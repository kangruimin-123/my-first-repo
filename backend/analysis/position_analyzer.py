from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


EPSILON = 1e-9


@dataclass(frozen=True)
class PositionResult:
    pct_from_high_20: float
    pct_from_low_20: float
    close_position: float
    near_support: bool
    near_resistance: bool
    close_position_in_bar: float


def analyze_position(df: pd.DataFrame) -> PositionResult:
    """Analyze where the latest close sits within the 20-day range and today's bar."""
    recent = df.sort_values("date").tail(20) if "date" in df.columns else df.tail(20)
    latest = recent.iloc[-1]
    high_20 = float(pd.to_numeric(recent["high"], errors="coerce").max())
    low_20 = float(pd.to_numeric(recent["low"], errors="coerce").min())
    close = float(latest["close"])
    high = float(latest["high"])
    low = float(latest["low"])

    pct_from_high_20 = 0.0 if abs(high_20) <= EPSILON else (close - high_20) / high_20
    pct_from_low_20 = 0.0 if abs(low_20) <= EPSILON else (close - low_20) / low_20
    close_position = 0.5 if abs(high_20 - low_20) <= EPSILON else (close - low_20) / (high_20 - low_20)
    close_position_in_bar = 0.5 if abs(high - low) <= EPSILON else (close - low) / (high - low)
    return PositionResult(
        pct_from_high_20=pct_from_high_20,
        pct_from_low_20=pct_from_low_20,
        close_position=close_position,
        near_support=close_position < 0.2,
        near_resistance=close_position > 0.85,
        close_position_in_bar=close_position_in_bar,
    )
