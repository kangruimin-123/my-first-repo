from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from backend.strategy.base_strategy import StrategySignal


@dataclass(frozen=True)
class Evaluation:
    symbol: str
    name: str
    sector: str
    role: str
    buy_grade: str
    buy_score: float
    sell_urgency: str
    strategy_name: str
    action: str
    confidence: float
    data_quality: str
    entry_low: float
    entry_high: float
    stop_loss: float
    position_pct: float
    action_text: str
    risk_warnings: list[str] = field(default_factory=list)
    stage: str = ""


class Grader:
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def grade_buy(self, signal: StrategySignal, mainline: Any | None, deny_result: Any | None, data_quality: str) -> str:
        """Grade buy signal into A/B/C/NONE based on mainline, deny and signal quality."""
        if mainline is None:
            return "NONE"
        deny_action = getattr(deny_result, "action", "pass")
        if signal.action == "deny" or deny_action == "deny":
            return "NONE"
        if data_quality in ("partial", "mock"):
            return "C"
        rank = int(getattr(mainline, "rank", 999))
        if (
            rank <= 5
            and deny_action == "pass"
            and signal.action == "buy"
            and data_quality == "full"
            and signal.confidence >= float(self.config["grading"]["a_grade"]["min_confidence"])
            and signal.stop_loss_price > 0
        ):
            return "A"
        if rank <= 10 or data_quality == "degraded" or 0.4 <= signal.confidence < 0.6 or deny_action == "watch":
            return "B"
        if rank <= 5 or signal.risk_warnings:
            return "C"
        return "NONE"

    def grade_sell(self, stop_loss_result: Any, strong_stock: bool) -> str:
        """Return sell urgency label."""
        return str(getattr(stop_loss_result, "urgency", "无"))

    def select_focus_pool(self, evaluations: list[Evaluation], max_n: int = 10) -> list[Evaluation]:
        """Select focus pool from evaluations, keeping A and sell signals first."""
        selected: list[Evaluation] = []
        seen: set[str] = set()

        def add(item: Evaluation) -> None:
            if len(selected) >= max_n or item.symbol in seen:
                return
            selected.append(item)
            seen.add(item.symbol)

        for item in sorted(evaluations, key=lambda row: row.buy_score, reverse=True):
            if item.buy_grade == "A":
                add(item)
        for item in sorted(evaluations, key=lambda row: row.buy_score, reverse=True):
            if item.sell_urgency != "无":
                add(item)
        for item in sorted(evaluations, key=lambda row: row.confidence, reverse=True):
            if item.buy_grade == "B":
                add(item)
        return selected
