from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from backend.analysis.chart_pattern_analyzer import ChartPatternAnalyzer, PatternResult
from backend.analysis.chip_analyzer import ChipAnalyzer, ChipResult
from backend.analysis.dow_analyzer import DowAnalyzer, DowResult
from backend.analysis.volume_price_analyzer import VolumePriceResult, analyze_volume_price
from backend.analysis.wave_analyzer import WaveAnalyzer, WaveResult


@dataclass(frozen=True)
class StageResult:
    symbol: str
    stage: str
    confidence: float
    stage_score: float
    dow_trend: str
    wave_position: str
    chip_status: str
    volume_price_status: str
    chart_pattern: str
    allow_buy: bool
    risk_level: str
    reason: list[str]


class StageAnalyzer:
    def __init__(
        self,
        dow_analyzer: DowAnalyzer | None = None,
        pattern_analyzer: ChartPatternAnalyzer | None = None,
        chip_analyzer: ChipAnalyzer | None = None,
        wave_analyzer: WaveAnalyzer | None = None,
    ) -> None:
        self.dow_analyzer = dow_analyzer or DowAnalyzer()
        self.pattern_analyzer = pattern_analyzer or ChartPatternAnalyzer()
        self.chip_analyzer = chip_analyzer or ChipAnalyzer()
        self.wave_analyzer = wave_analyzer or WaveAnalyzer()

    def analyze(self, symbol: str, daily_df: pd.DataFrame, config: dict[str, Any]) -> StageResult:
        dow = self.dow_analyzer.analyze(daily_df)
        volume_price = analyze_volume_price(daily_df)
        pattern = self.pattern_analyzer.analyze(daily_df)
        chip = self.chip_analyzer.analyze(daily_df)
        wave = self.wave_analyzer.analyze(daily_df)
        weights = normalize_stage_weights(config.get("stage", {}).get("weights", {}))
        score = (
            weights["dow"] * dow.trend_score
            + weights["volume_price"] * volume_price.score
            + weights["pattern"] * pattern.pattern_score
            + weights["chip"] * chip.score
            + weights["wave"] * wave.score
        )
        stage, allow_buy, risk_level = self._determine_stage(score, dow, volume_price.volume_price_status, pattern.pattern)
        confidence = min(1.0, max(0.0, abs(score - 50.0) / 50.0 + 0.35))
        return StageResult(
            symbol=symbol,
            stage=stage,
            confidence=round(confidence, 4),
            stage_score=round(score, 2),
            dow_trend=dow.trend,
            wave_position=wave.position,
            chip_status=chip.status,
            volume_price_status=volume_price.volume_price_status,
            chart_pattern=pattern.pattern,
            allow_buy=allow_buy,
            risk_level=risk_level,
            reason=[
                f"道氏趋势：{dow.reason}",
                f"量价状态：{volume_price.volume_price_status}",
                f"图表形态：{pattern.reason}",
                f"阶段结论：{stage}，风险等级 {risk_level}",
            ],
        )

    def _determine_stage(self, score: float, dow: DowResult, vp_status: str, pattern: str) -> tuple[str, bool, str]:
        if score >= 60 and vp_status == "distribution":
            return "stage_3_distribution", False, "high"
        if score < 25:
            return "stage_4_decline", False, "critical"
        if 25 <= score < 40 and dow.trend == "reversal":
            return "stage_0_accumulation", True, "high"
        if 25 <= score < 40 and dow.trend == "weakening":
            return "stage_3_distribution", False, "high"
        if 40 <= score < 60:
            if dow.trend == "downtrend":
                return "stage_0_accumulation", True, "high"
            if pattern == "breakout" or dow.trend in {"reversal", "uptrend"}:
                return "stage_1_start", True, "medium"
        if score >= 60 and dow.trend == "uptrend":
            return "stage_2_rising", True, "low"
        if dow.trend == "weakening" or pattern == "distribution_risk":
            return "stage_3_distribution", False, "high"
        if dow.trend == "downtrend":
            return "stage_4_decline", False, "critical"
        return "stage_1_start", True, "medium"


def normalize_stage_weights(raw_weights: dict[str, Any]) -> dict[str, float]:
    defaults = {"dow": 0.45, "chip": 0.0, "wave": 0.0, "pattern": 0.30, "volume_price": 0.25}
    weights = {key: float(raw_weights.get(key, value)) for key, value in defaults.items()}
    active_total = sum(value for value in weights.values() if value > 0)
    if active_total <= 0:
        return defaults
    return {key: (value / active_total if value > 0 else 0.0) for key, value in weights.items()}
