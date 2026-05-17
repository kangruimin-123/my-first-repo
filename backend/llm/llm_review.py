from __future__ import annotations

import logging
from typing import Any

from backend.llm.llm_client import LLMClient
from backend.llm.prompts import build_full_context
from backend.strategy.base_strategy import BaseStrategy, StrategyContext, StrategySignal


logger = logging.getLogger(__name__)


class LLMReview(BaseStrategy):
    @property
    def name(self) -> str:
        return "llm_review"

    def __init__(self, config: dict[str, Any], llm_client: LLMClient | None = None) -> None:
        super().__init__(config)
        self.llm_client = llm_client or LLMClient(config.get("llm", {}))

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        """Add non-binding LLM review notes for focus-pool symbols."""
        if not bool(self.config.get("llm", {}).get("enabled", False)):
            return []
        signals: list[StrategySignal] = []
        for eval_result in context.focus_pool:
            prompt = build_full_context(context, eval_result.symbol)
            result = self.llm_client.ask(prompt)
            if result is None:
                logger.warning("LLM 不可用，跳过 %s", eval_result.symbol)
                continue
            risk_points = result.get("risk_points", [])
            if isinstance(risk_points, str):
                risk_points = [risk_points]
            confidence = max(0.0, min(1.0, float(result.get("buy_probability", 0.5))))
            signal = StrategySignal(
                strategy_name=self.name,
                symbol=eval_result.symbol,
                action="hold",
                confidence=confidence,
                reason=str(result.get("reason", "")),
                action_text=str(result.get("judgement", "LLM 未给出结论")),
                data_quality=context.data_quality,
                risk_warnings=[str(item) for item in risk_points],
            )
            signals.append(signal)
        context.add_signals(signals)
        return signals
