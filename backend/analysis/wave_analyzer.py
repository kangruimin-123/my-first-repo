from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class WaveResult:
    position: str
    score: float
    reason: str


class WaveAnalyzer:
    def analyze(self, df: pd.DataFrame) -> WaveResult:
        """Reserved wave analysis interface."""
        return WaveResult(position="unknown", score=50.0, reason="波浪分析待接入")
