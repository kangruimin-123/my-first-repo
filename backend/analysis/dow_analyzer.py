from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


EPSILON = 1e-9


@dataclass(frozen=True)
class DowResult:
    trend: str
    higher_highs: bool
    higher_lows: bool
    ma_structure: str
    trend_score: float
    reason: str


class DowAnalyzer:
    def analyze(self, df: pd.DataFrame) -> DowResult:
        """Classify trend from HH/HL structure and moving-average alignment."""
        if df.empty:
            return DowResult("downtrend", False, False, "混乱", 20.0, "K线数据缺失")
        ordered = df.sort_values("date") if "date" in df.columns else df.copy()
        recent = ordered.tail(60).copy()
        closes = pd.to_numeric(recent["close"], errors="coerce")
        highs = pd.to_numeric(recent["high"], errors="coerce")
        lows = pd.to_numeric(recent["low"], errors="coerce")

        last_high, previous_high = _recent_pair(highs, "max")
        last_low, previous_low = _recent_pair(lows, "min")
        higher_highs = last_high > previous_high * (1 + 0.002)
        higher_lows = last_low > previous_low * (1 + 0.002)
        lower_highs = last_high < previous_high * (1 - 0.002)
        lower_lows = last_low < previous_low * (1 - 0.002)

        ma5 = float(closes.tail(5).mean())
        ma10 = float(closes.tail(10).mean())
        ma20 = float(closes.tail(20).mean())
        ma60 = float(closes.tail(min(60, len(closes))).mean())
        previous_ma20 = float(closes.iloc[-25:-5].mean()) if len(closes) >= 25 else ma20
        ma20_slope = (ma20 - previous_ma20) / max(abs(previous_ma20), EPSILON)

        if ma5 > ma10 > ma20 > ma60:
            ma_structure = "多头排列"
        elif ma5 < ma10 < ma20 < ma60:
            ma_structure = "空头排列"
        else:
            ma_structure = "混乱"

        if higher_highs and higher_lows and ma_structure == "多头排列":
            trend = "uptrend"
            score = 90.0
            reason = "高点和低点同步抬升，均线多头排列"
        elif lower_highs and lower_lows and ma_structure == "空头排列":
            trend = "downtrend"
            score = 15.0
            reason = "高点和低点同步下移，均线空头排列"
        elif higher_lows and ma20_slope >= -0.01 and ma_structure != "多头排列":
            trend = "reversal"
            score = 55.0
            reason = "低点抬升且 MA20 走平，存在底部反转迹象"
        elif not higher_highs and ma5 < ma10:
            trend = "weakening"
            score = 35.0
            reason = "高点未继续抬升，MA5 下穿 MA10"
        elif higher_highs and higher_lows:
            trend = "uptrend"
            score = 72.0
            reason = "高点和低点抬升，趋势保持"
        elif lower_highs and lower_lows:
            trend = "downtrend"
            score = 25.0
            reason = "高低点下移，趋势偏弱"
        else:
            trend = "weakening"
            score = 45.0
            reason = "结构不清晰，趋势进入震荡转弱"

        return DowResult(trend, higher_highs, higher_lows, ma_structure, score, reason)


def _recent_pair(series: pd.Series, method: str) -> tuple[float, float]:
    clean = pd.to_numeric(series, errors="coerce").dropna()
    if clean.empty:
        return 0.0, 0.0
    last_window = clean.tail(20)
    previous_window = clean.iloc[-40:-20] if len(clean) >= 40 else clean.iloc[:-20]
    if previous_window.empty:
        previous_window = clean.iloc[:-1]
    if previous_window.empty:
        previous_window = clean
    if method == "max":
        return float(last_window.max()), float(previous_window.max())
    return float(last_window.min()), float(previous_window.min())
