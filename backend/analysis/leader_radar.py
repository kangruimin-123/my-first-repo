from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pandas as pd


@dataclass(frozen=True)
class PotentialLeader:
    symbol: str
    name: str
    sector_name: str
    leader_probability: float
    role_type: str
    confidence: float
    factors: dict[str, float] = field(default_factory=dict)
    reason: list[str] = field(default_factory=list)


class LeaderRadar:
    """Pre-rank potential leaders inside an abnormal sector."""

    def scan(
        self,
        sector_name: str,
        stocks_df: pd.DataFrame,
        limit_up_history: pd.DataFrame,
        stage_results: dict[str, Any],
        config: dict[str, Any],
    ) -> list[PotentialLeader]:
        if stocks_df.empty:
            return []
        weights = config.get("radar", {}).get("leader_radar", {}).get(
            "factor_weights",
            {
                "history": 0.30,
                "purity": 0.20,
                "capacity": 0.20,
                "turnover": 0.15,
                "stage": 0.15,
            },
        )
        results: list[PotentialLeader] = []
        for _, row in stocks_df.iterrows():
            symbol = str(row["symbol"])
            if str(row.get("sector_name", sector_name)) != sector_name:
                continue
            factors = {
                "history": self._history_score(symbol, limit_up_history),
                "purity": self._purity_score(row),
                "capacity": self._capacity_score(row),
                "turnover": self._turnover_score(row),
                "stage": self._stage_score(symbol, stage_results),
            }
            total_score = sum(float(weights.get(key, 0.0)) * value for key, value in factors.items())
            role_type = self._role_type(row, factors)
            results.append(
                PotentialLeader(
                    symbol=symbol,
                    name=str(row.get("name", symbol) or symbol),
                    sector_name=sector_name,
                    leader_probability=round(total_score / 100.0, 4),
                    role_type=role_type,
                    confidence=round(min(1.0, max(0.0, total_score / 100.0)), 4),
                    factors={key: round(value, 2) for key, value in factors.items()},
                    reason=self._reason(factors, role_type),
                )
            )
        return sorted(results, key=lambda item: (item.leader_probability, _role_priority(item.role_type)), reverse=True)[:5]

    def _history_score(self, symbol: str, limit_up_history: pd.DataFrame) -> float:
        if limit_up_history.empty or "symbol" not in limit_up_history.columns:
            return 0.0
        rows = limit_up_history[limit_up_history["symbol"] == symbol]
        if rows.empty:
            return 0.0
        if bool(rows.get("was_sector_leader", pd.Series([False] * len(rows))).fillna(False).any()):
            return 70.0
        if pd.to_numeric(rows.get("lianban_count", pd.Series([0] * len(rows))), errors="coerce").fillna(0).max() >= 2:
            return 50.0
        return 30.0

    def _purity_score(self, row: pd.Series) -> float:
        concept_count = int(row.get("concept_count", row.get("sector_count", 1)) or 1)
        if concept_count <= 2:
            return 90.0
        if concept_count <= 4:
            return 60.0
        return 20.0

    def _capacity_score(self, row: pd.Series) -> float:
        market_cap = float(row.get("float_market_cap", row.get("market_cap", 0.0)) or 0.0)
        if 50 <= market_cap <= 300:
            return 90.0
        if 300 < market_cap <= 800:
            return 70.0
        if 0 < market_cap < 50:
            return 70.0
        return 40.0

    def _turnover_score(self, row: pd.Series) -> float:
        turnover_20d = float(row.get("turnover_20d", 0.0) or 0.0)
        if turnover_20d > 100:
            return 85.0
        if turnover_20d >= 50:
            return 60.0
        return 30.0

    def _stage_score(self, symbol: str, stage_results: dict[str, Any]) -> float:
        stage = str(getattr(stage_results.get(symbol), "stage", "unknown"))
        if stage in {"stage_0_accumulation", "stage_1_start"}:
            return 90.0
        if stage == "stage_2_rising":
            return 60.0
        if stage in {"stage_3_distribution", "stage_4_decline"}:
            return 10.0
        return 50.0

    def _role_type(self, row: pd.Series, factors: dict[str, float]) -> str:
        market_cap = float(row.get("float_market_cap", row.get("market_cap", 0.0)) or 0.0)
        if market_cap > 300:
            return "potential_mid"
        if market_cap < 50:
            return "potential_elastic"
        if factors["history"] >= 30 and factors["purity"] >= 50 and factors["stage"] >= 50:
            return "potential_leader"
        return "potential_elastic"

    def _reason(self, factors: dict[str, float], role_type: str) -> list[str]:
        reasons = [f"角色预判：{role_type}"]
        if factors["history"] >= 50:
            reasons.append("历史辨识度高")
        if factors["purity"] >= 80:
            reasons.append("题材较纯")
        if factors["capacity"] >= 80:
            reasons.append("流通市值适配龙头弹性")
        if factors["turnover"] >= 70:
            reasons.append("近20日筹码交换充分")
        if factors["stage"] <= 20:
            reasons.append("Stage 3/4 降权")
        return reasons


def _role_priority(role_type: str) -> int:
    return {"potential_leader": 3, "potential_mid": 2, "potential_elastic": 1}.get(role_type, 0)
