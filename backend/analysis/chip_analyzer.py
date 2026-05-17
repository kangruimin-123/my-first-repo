from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class ChipResult:
    status: str
    score: float
    reason: str


class ChipAnalyzer:
    def analyze(self, df: pd.DataFrame) -> ChipResult:
        """Reserved chip analysis interface."""
        return ChipResult(status="unknown", score=50.0, reason="筹码分析待接入")
