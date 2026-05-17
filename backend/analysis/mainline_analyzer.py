from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import pandas as pd


logger = logging.getLogger(__name__)
EPSILON = 1e-9


@dataclass(frozen=True)
class MainlineResult:
    sector_name: str
    mainline_score: float
    mainline_status: str
    rank: int
    factors: dict[str, float]


class MainlineAnalyzer:
    """Detect Top-N market mainlines from sector strength and limit-up structure."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.mainline_config = config["mainline"]

    def detect(
        self,
        sector_daily: pd.DataFrame,
        limit_up: pd.DataFrame,
        lianban: pd.DataFrame,
        history: list[MainlineResult] | None = None,
    ) -> list[MainlineResult]:
        """
        Score sectors from breadth, amount, limit-up structure and continuity.

        判断依据：主线应同时体现板块涨幅、成交额、涨停/连板数量、龙头强度和持续性；资金流缺失时，
        将资金流权重按比例重分配给其他因子，避免空数据拖低有效主线。
        """
        logger.info("mainline_analyzer.detect started sectors=%s", len(sector_daily))
        if sector_daily.empty:
            logger.info("mainline_analyzer.detect finished results=0")
            return []

        frame = self._prepare_sector_frame(sector_daily, limit_up, lianban)
        weights = dict(self.mainline_config["score_weights"])
        factor_columns = [
            "sector_pct_chg",
            "sector_amount",
            "limit_up_count",
            "lianban_count",
            "leader_strength",
            "duration",
            "money_flow",
        ]
        normalized_factors = self._normalized_factors(frame, factor_columns, history or [])
        active_weights = self._active_weights(weights, normalized_factors)

        scored_rows: list[dict[str, Any]] = []
        for index, row in frame.iterrows():
            score = 0.0
            factors: dict[str, float] = {}
            for factor_name, factor_frame in normalized_factors.items():
                raw_score = factor_frame.loc[index]
                if pd.isna(raw_score):
                    factors[factor_name] = float("nan")
                    continue
                factor_score = float(raw_score)
                factors[factor_name] = round(factor_score, 4)
                score += factor_score * active_weights.get(factor_name, 0.0)
            scored_rows.append({"sector_name": row["sector_name"], "score": round(score, 4), "factors": factors})

        top_n = int(self.mainline_config["top_n"])
        sorted_rows = sorted(scored_rows, key=lambda item: item["score"], reverse=True)
        yesterday_top = [result.sector_name for result in history or [] if result.rank <= top_n]
        today_top = [item["sector_name"] for item in sorted_rows[:top_n]]
        rotation_count = len(set(today_top) - set(yesterday_top)) if yesterday_top else 0

        results: list[MainlineResult] = []
        for rank, item in enumerate(sorted_rows[:top_n], start=1):
            status = self._status_for(item["sector_name"], float(item["score"]), yesterday_top, rotation_count)
            results.append(
                MainlineResult(
                    sector_name=str(item["sector_name"]),
                    mainline_score=round(float(item["score"]), 2),
                    mainline_status=status,
                    rank=rank,
                    factors=item["factors"],
                )
            )
        logger.info("mainline_analyzer.detect finished results=%s", len(results))
        return results

    def _prepare_sector_frame(self, sector_daily: pd.DataFrame, limit_up: pd.DataFrame, lianban: pd.DataFrame) -> pd.DataFrame:
        frame = sector_daily.copy()
        for column in ("limit_up_count", "lianban_count"):
            if column not in frame.columns:
                frame[column] = 0
        if "limit_up_count" not in sector_daily.columns and not limit_up.empty and "sector_name" in limit_up.columns:
            counts = limit_up.groupby("sector_name").size().rename("limit_up_count")
            frame = frame.drop(columns=["limit_up_count"], errors="ignore").merge(counts, on="sector_name", how="left")
        if "lianban_count" not in sector_daily.columns and not lianban.empty and "sector_name" in lianban.columns:
            counts = lianban.groupby("sector_name").size().rename("lianban_count")
            frame = frame.drop(columns=["lianban_count"], errors="ignore").merge(counts, on="sector_name", how="left")
        if "leader_strength" not in frame.columns:
            frame["leader_strength"] = frame.get("leader_pct_chg", frame.get("pct_chg", 0.0))
        if "sector_pct_chg" not in frame.columns:
            frame["sector_pct_chg"] = frame.get("pct_chg", 0.0)
        if "sector_amount" not in frame.columns:
            frame["sector_amount"] = frame.get("amount", 0.0)
        if "money_flow" not in frame.columns:
            frame["money_flow"] = pd.NA
        return frame.fillna({"limit_up_count": 0, "lianban_count": 0, "leader_strength": 0, "sector_pct_chg": 0, "sector_amount": 0})

    def _normalized_factors(
        self,
        frame: pd.DataFrame,
        factor_columns: list[str],
        history: list[MainlineResult],
    ) -> dict[str, pd.Series]:
        factors: dict[str, pd.Series] = {}
        for factor_name in factor_columns:
            if factor_name == "duration":
                previous_top = {result.sector_name for result in history if result.rank <= 10}
                factors[factor_name] = frame["sector_name"].map(lambda name: 100.0 if name in previous_top else 0.0)
                continue
            series = pd.to_numeric(frame[factor_name], errors="coerce")
            if series.isna().all():
                factors[factor_name] = pd.Series([pd.NA] * len(frame), index=frame.index)
            else:
                factors[factor_name] = self._minmax(series.fillna(0.0))
        return factors

    def _active_weights(self, weights: dict[str, float], factors: dict[str, pd.Series]) -> dict[str, float]:
        active = {name: weight for name, weight in weights.items() if name in factors and not factors[name].isna().all()}
        total = sum(active.values())
        if total <= EPSILON:
            return {name: 0.0 for name in weights}
        return {name: weight / total for name, weight in active.items()}

    def _minmax(self, series: pd.Series) -> pd.Series:
        min_value = float(series.min())
        max_value = float(series.max())
        if abs(max_value - min_value) <= EPSILON:
            return pd.Series([50.0] * len(series), index=series.index)
        return (series - min_value) / (max_value - min_value) * 100.0

    def _status_for(self, sector_name: str, score: float, yesterday_top: list[str], rotation_count: int) -> str:
        thresholds = self.mainline_config["status_thresholds"]
        if score > float(thresholds["rising_min_score"]):
            return "rising"
        if score < float(thresholds["fading_max_score"]):
            return "fading"
        if sector_name in yesterday_top:
            return "continuing"
        if yesterday_top and rotation_count >= 3:
            return "rotation"
        return "risk"
