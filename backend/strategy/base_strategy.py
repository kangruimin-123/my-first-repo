from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class StrategySignal:
    strategy_name: str = ""
    symbol: str = ""
    action: str = ""
    confidence: float = 0.0
    reason: str = ""
    action_text: str = ""
    data_quality: str = "full"
    entry_price_low: float = 0.0
    entry_price_high: float = 0.0
    stop_loss_price: float = 0.0
    position_pct: float = 0.0
    grade: str = "NONE"
    sell_urgency: str = "无"
    risk_warnings: list[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class StrategyContext:
    config: dict[str, Any]
    mainline_results: list[Any] = field(default_factory=list)
    stage_results: dict[str, Any] = field(default_factory=dict)
    role_results: dict[str, Any] = field(default_factory=dict)
    stock_analysis: dict[str, dict[str, Any]] = field(default_factory=dict)
    focus_pool: list[Any] = field(default_factory=list)
    signals: list[StrategySignal] = field(default_factory=list)
    data_quality: str = "full"

    def add_signals(self, signals: list[StrategySignal]) -> None:
        self.signals.extend(signals)


class BaseStrategy(ABC):
    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Return strategy name."""

    @property
    def enabled(self) -> bool:
        if self.name == "mainline_detect":
            return True
        return bool(self.config.get("strategies", {}).get(self.name, {}).get("enabled", False))

    @abstractmethod
    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        """Execute strategy and return signals."""

    def execute_with_stage_gate(self, context: StrategyContext, stage_result: Any) -> list[StrategySignal]:
        allowed_stages = self.config.get("strategies", {}).get(self.name, {}).get("allowed_stages")
        if not allowed_stages or getattr(stage_result, "stage", None) in allowed_stages:
            return self.execute(context)
        signal = StrategySignal(
            strategy_name=self.name,
            symbol=getattr(stage_result, "symbol", ""),
            action="deny",
            confidence=1.0,
            reason=f"当前处于{getattr(stage_result, 'stage', 'unknown')}，不允许执行{self.name}",
            action_text=f"阶段不允许：{getattr(stage_result, 'stage', 'unknown')}",
            data_quality=context.data_quality,
            risk_warnings=[f"阶段限制：{getattr(stage_result, 'stage', 'unknown')}"],
            grade="NONE",
        )
        context.add_signals([signal])
        return [signal]


def stage_allows_buy(stock_analysis: dict[str, Any], config: dict[str, Any] | None = None, strategy_name: str = "") -> bool:
    stage = stock_analysis.get("stage")
    if stage is None:
        return True
    if config is not None and strategy_name:
        allowed_stages = config.get("strategies", {}).get(strategy_name, {}).get("allowed_stages")
        if allowed_stages:
            return getattr(stage, "stage", "") in allowed_stages
    return bool(getattr(stage, "allow_buy", True))


def stage_deny_reason(stock_analysis: dict[str, Any]) -> str:
    stage = stock_analysis.get("stage")
    stage_name = getattr(stage, "stage", "unknown")
    risk_level = getattr(stage, "risk_level", "unknown")
    return f"阶段门控禁止买入：{stage_name}，风险等级 {risk_level}"
