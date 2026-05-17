from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

import pandas as pd

from backend.analysis.chart_pattern_analyzer import ChartPatternAnalyzer, PatternResult
from backend.analysis.chip_analyzer import ChipResult
from backend.analysis.dow_analyzer import DowAnalyzer, DowResult
from backend.analysis.stage_analyzer import StageAnalyzer, normalize_stage_weights
from backend.analysis.volume_price_analyzer import VolumePriceResult
from backend.analysis.wave_analyzer import WaveResult


def frame_from_closes(closes: list[float], volumes: list[float] | None = None, wick: float = 0.02) -> pd.DataFrame:
    rows = []
    start = date(2026, 1, 1)
    volumes = volumes or [100.0] * len(closes)
    for index, close in enumerate(closes):
        open_price = closes[index - 1] if index > 0 else close
        rows.append(
            {
                "date": start + timedelta(days=index),
                "open": open_price,
                "high": max(open_price, close) * (1 + wick),
                "low": min(open_price, close) * (1 - wick),
                "close": close,
                "volume": volumes[index],
                "amount": volumes[index] * close,
                "turnover_rate": 2.0,
            }
        )
    return pd.DataFrame(rows)


def test_dow_uptrend() -> None:
    result = DowAnalyzer().analyze(frame_from_closes([10 + index * 0.2 for index in range(80)]))

    assert result.trend == "uptrend"
    assert result.higher_highs is True
    assert result.higher_lows is True
    assert result.ma_structure == "多头排列"


def test_dow_downtrend() -> None:
    result = DowAnalyzer().analyze(frame_from_closes([30 - index * 0.2 for index in range(80)]))

    assert result.trend == "downtrend"
    assert result.higher_highs is False
    assert result.higher_lows is False
    assert result.ma_structure == "空头排列"


def test_dow_reversal() -> None:
    closes = [20 - index * 0.25 for index in range(40)]
    closes += [10.0 + (index % 3) * 0.03 for index in range(20)]
    closes += [10.8 + (index % 3) * 0.03 for index in range(20)]
    result = DowAnalyzer().analyze(frame_from_closes(closes))

    assert result.trend == "reversal"
    assert result.higher_lows is True


def test_dow_weakening() -> None:
    closes = [10 + index * 0.18 for index in range(60)] + [20 - index * 0.12 for index in range(20)]
    result = DowAnalyzer().analyze(frame_from_closes(closes))

    assert result.trend == "weakening"
    assert result.higher_highs is False


def test_chart_breakout_after_base() -> None:
    closes = [10.0 + (index % 3) * 0.04 for index in range(24)] + [10.8]
    volumes = [100.0] * 24 + [180.0]

    result = ChartPatternAnalyzer().analyze(frame_from_closes(closes, volumes, wick=0.005))

    assert result.pattern == "breakout"


def test_chart_distribution_risk() -> None:
    closes = [10 + index * 0.18 for index in range(55)] + [20.8, 20.9, 20.85, 20.88, 20.98]
    frame = frame_from_closes(closes, [100.0] * 59 + [260.0], wick=0.01)
    frame.loc[55:, "high"] = 23.0

    result = ChartPatternAnalyzer().analyze(frame)

    assert result.pattern == "distribution_risk"


def test_chart_base() -> None:
    closes = [10.2 + (index % 6) * 0.06 for index in range(40)]
    volumes = [180.0 - index for index in range(40)]

    result = ChartPatternAnalyzer().analyze(frame_from_closes(closes, volumes, wick=0.006))

    assert result.pattern == "base"


def test_chart_none() -> None:
    closes = [10, 11, 9.5, 12, 10.5, 13, 11.2, 12.4, 10.8, 12.0, 11.0, 12.2]

    result = ChartPatternAnalyzer().analyze(frame_from_closes(closes))

    assert result.pattern == "none"


@dataclass
class FakeDow:
    result: DowResult

    def analyze(self, df: pd.DataFrame) -> DowResult:
        return self.result


@dataclass
class FakePattern:
    result: PatternResult

    def analyze(self, df: pd.DataFrame) -> PatternResult:
        return self.result


@dataclass
class FakeChip:
    def analyze(self, df: pd.DataFrame) -> ChipResult:
        return ChipResult("unknown", 50.0, "筹码分析待接入")


@dataclass
class FakeWave:
    def analyze(self, df: pd.DataFrame) -> WaveResult:
        return WaveResult("unknown", 50.0, "波浪分析待接入")


def stage_with(dow: DowResult, vp_status: str, vp_score: float, pattern: PatternResult):
    class FakeStageAnalyzer(StageAnalyzer):
        def analyze(self, symbol: str, daily_df: pd.DataFrame, config: dict) -> object:
            original = __import__("backend.analysis.stage_analyzer", fromlist=["analyze_volume_price"])
            old = original.analyze_volume_price
            original.analyze_volume_price = lambda df: VolumePriceResult(1.5, 2.0, False, 0.1, 0.1, 0.6, vp_status, vp_score)
            try:
                return super().analyze(symbol, daily_df, config)
            finally:
                original.analyze_volume_price = old

    analyzer = FakeStageAnalyzer(FakeDow(dow), FakePattern(pattern), FakeChip(), FakeWave())
    return analyzer.analyze("000001.SZ", frame_from_closes([10, 11, 12, 13, 14]), stage_config())


def stage_config() -> dict[str, object]:
    return {"stage": {"weights": {"dow": 0.45, "chip": 0.0, "wave": 0.0, "pattern": 0.30, "volume_price": 0.25}}}


def test_stage_rising_allows_buy() -> None:
    result = stage_with(
        DowResult("uptrend", True, True, "多头排列", 90, "up"),
        "healthy",
        82,
        PatternResult("breakout", 82, 10, 12, "breakout"),
    )

    assert result.stage == "stage_2_rising"
    assert result.allow_buy is True


def test_stage_distribution_blocks_buy() -> None:
    result = stage_with(
        DowResult("weakening", False, True, "混乱", 35, "weak"),
        "distribution",
        25,
        PatternResult("distribution_risk", 30, 10, 12, "dist"),
    )

    assert result.stage == "stage_3_distribution"
    assert result.allow_buy is False


def test_stage_decline_blocks_buy() -> None:
    result = stage_with(
        DowResult("downtrend", False, False, "空头排列", 15, "down"),
        "panic",
        10,
        PatternResult("none", 20, 10, 12, "none"),
    )

    assert result.stage == "stage_4_decline"
    assert result.allow_buy is False


def test_stage_accumulation_allows_small_trial() -> None:
    result = stage_with(
        DowResult("reversal", False, True, "混乱", 35, "reversal"),
        "healthy",
        45,
        PatternResult("base", 35, 10, 12, "base"),
    )

    assert result.stage == "stage_0_accumulation"
    assert result.allow_buy is True
    assert result.risk_level == "high"


def test_stage_distribution_boundary_downgrades_high_score() -> None:
    result = stage_with(
        DowResult("uptrend", True, True, "多头排列", 95, "up"),
        "distribution",
        20,
        PatternResult("breakout", 90, 10, 12, "breakout"),
    )

    assert result.stage == "stage_3_distribution"
    assert result.allow_buy is False


def test_weight_redistribution_when_chip_and_wave_disabled() -> None:
    weights = normalize_stage_weights({"dow": 0.45, "chip": 0, "wave": 0, "pattern": 0.30, "volume_price": 0.25})

    assert weights["chip"] == 0.0
    assert weights["wave"] == 0.0
    assert round(sum(weights.values()), 6) == 1.0
