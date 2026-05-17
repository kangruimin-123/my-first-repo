from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


EPSILON = 1e-9


@dataclass(frozen=True)
class PatternResult:
    pattern: str
    pattern_score: float
    support_level: float
    resistance_level: float
    reason: str


class ChartPatternAnalyzer:
    def analyze(self, df: pd.DataFrame) -> PatternResult:
        """Detect a small set of explainable chart patterns."""
        if df.empty:
            return PatternResult("none", 50.0, 0.0, 0.0, "K线数据缺失")
        ordered = df.sort_values("date") if "date" in df.columns else df.copy()
        close = pd.to_numeric(ordered["close"], errors="coerce")
        high = pd.to_numeric(ordered["high"], errors="coerce")
        low = pd.to_numeric(ordered["low"], errors="coerce")
        volume = pd.to_numeric(ordered["volume"], errors="coerce")
        latest = ordered.iloc[-1]
        current_close = float(latest["close"])
        current_open = float(latest["open"])
        current_high = float(latest["high"])
        current_low = float(latest["low"])
        previous_close = float(close.iloc[-2]) if len(close) > 1 else current_open
        pct_chg = (current_close - previous_close) / max(previous_close, EPSILON) * 100
        avg_volume_5 = float(volume.iloc[-6:-1].mean()) if len(volume) >= 6 else float(volume.tail(5).mean())
        volume_ratio = 0.0 if abs(avg_volume_5) <= EPSILON else float(latest["volume"]) / avg_volume_5
        support = float(low.tail(min(20, len(low))).min())
        resistance = float(high.iloc[-21:-1].max()) if len(high) >= 21 else float(high.iloc[:-1].max() if len(high) > 1 else current_high)
        close_position = (current_close - float(low.tail(60).min())) / max(float(high.tail(60).max()) - float(low.tail(60).min()), EPSILON)
        upper_shadow_mean = _upper_shadow_mean(ordered.tail(5))

        if close_position > 0.8 and volume_ratio > 1.5 and pct_chg < 1.0 and upper_shadow_mean > 0.3:
            return PatternResult("distribution_risk", 30.0, support, resistance, "高位放量滞涨且长上影增多")

        previous_20 = ordered.iloc[-21:-1] if len(ordered) >= 21 else ordered.iloc[:-1]
        if not previous_20.empty:
            base_width_20 = (float(previous_20["high"].max()) - float(previous_20["low"].min())) / max(float(previous_20["low"].min()), EPSILON)
            if base_width_20 < 0.05 and current_close > float(previous_20["high"].max()) and volume_ratio > 1.3:
                return PatternResult("breakout", 82.0, support, float(previous_20["high"].max()), "横盘后放量突破平台上轨")

        recent_40 = ordered.tail(40)
        if len(recent_40) >= 30:
            range_width = (float(recent_40["high"].max()) - float(recent_40["low"].min())) / max(float(recent_40["low"].min()), EPSILON)
            support_40 = float(recent_40["low"].min())
            touches = int((pd.to_numeric(recent_40["low"], errors="coerce") <= support_40 * 1.03).sum())
            volume_shrinking = float(volume.tail(5).mean()) < float(volume.tail(20).mean())
            if range_width <= 0.10 and touches >= 2 and volume_shrinking:
                return PatternResult("base", 62.0, support_40, float(recent_40["high"].max()), "底部窄幅震荡，多次触及支撑不破且量能萎缩")

        if len(ordered) >= 40:
            last_high = float(high.tail(20).max())
            previous_high = float(high.iloc[-40:-20].max())
            last_low = float(low.tail(20).min())
            previous_low = float(low.iloc[-40:-20].min())
            ma20 = float(close.tail(20).mean())
            if last_high > previous_high and last_low > previous_low and current_close >= ma20:
                return PatternResult("trend_channel", 72.0, ma20, last_high, "高低点抬升，价格沿 MA20 上方运行")

        return PatternResult("none", 50.0, support, resistance, "未匹配明确形态")


def _upper_shadow_mean(frame: pd.DataFrame) -> float:
    ratios: list[float] = []
    for _, row in frame.iterrows():
        high = float(row["high"])
        low = float(row["low"])
        open_price = float(row["open"])
        close = float(row["close"])
        amplitude = high - low
        if amplitude <= EPSILON:
            ratios.append(0.0)
        else:
            ratios.append((high - max(open_price, close)) / amplitude)
    return sum(ratios) / max(len(ratios), 1)
