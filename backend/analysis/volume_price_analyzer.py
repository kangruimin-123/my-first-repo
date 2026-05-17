from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


EPSILON = 1e-9


@dataclass(frozen=True)
class VolumePriceResult:
    volume_ratio: float
    turnover_rate: float
    price_volume_divergence: bool
    upper_shadow_ratio: float
    lower_shadow_ratio: float
    body_ratio: float
    volume_price_status: str = "healthy"
    score: float = 70.0


def analyze_volume_price(df: pd.DataFrame) -> VolumePriceResult:
    """Analyze volume expansion, turnover, and candle structure."""
    ordered = df.sort_values("date") if "date" in df.columns else df.copy()
    latest = ordered.iloc[-1]
    volumes = pd.to_numeric(ordered["volume"], errors="coerce")
    avg_volume_5 = float(volumes.tail(5).mean())
    current_volume = float(latest["volume"])
    volume_ratio = 0.0 if abs(avg_volume_5) <= EPSILON else current_volume / avg_volume_5

    close = float(latest["close"])
    open_price = float(latest["open"])
    high = float(latest["high"])
    low = float(latest["low"])
    amplitude = high - low
    upper_shadow = high - max(open_price, close)
    lower_shadow = min(open_price, close) - low
    body = abs(close - open_price)
    denominator = amplitude if abs(amplitude) > EPSILON else 1.0
    closes = pd.to_numeric(ordered["close"], errors="coerce")
    previous_close = float(closes.iloc[-2]) if len(closes) > 1 else open_price
    pct_chg = (close - previous_close) / max(previous_close, EPSILON) * 100
    previous_high = float(closes.iloc[:-1].max()) if len(ordered) > 1 else close
    status, score = _classify_status(pct_chg, volume_ratio, close, open_price)

    return VolumePriceResult(
        volume_ratio=volume_ratio,
        turnover_rate=float(latest.get("turnover_rate", 0.0) or 0.0),
        price_volume_divergence=close > previous_high and volume_ratio < 0.8,
        upper_shadow_ratio=upper_shadow / denominator,
        lower_shadow_ratio=lower_shadow / denominator,
        body_ratio=body / denominator,
        volume_price_status=status,
        score=score,
    )


def _classify_status(pct_chg: float, volume_ratio: float, close: float, open_price: float) -> tuple[str, float]:
    if volume_ratio > 3.0 and pct_chg < -5.0:
        return "panic", 10.0
    if volume_ratio > 1.5 and (pct_chg < 0.0 or abs(pct_chg) < 1.0):
        return "distribution", 25.0
    if pct_chg > 0.0 and volume_ratio < 0.8:
        return "weakening", 50.0
    if (pct_chg > 0.0 and volume_ratio >= 1.0) or (pct_chg < 0.0 and volume_ratio < 1.0 and close >= open_price * 0.97):
        return "healthy", 80.0
    return "weakening", 55.0
