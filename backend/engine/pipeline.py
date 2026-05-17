from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from backend.strategy.elastic_strategy import PanicReversalStrategy
from backend.llm.llm_review import LLMReview
from backend.strategy.leader_detect_strategy import LeaderDetectStrategy
from backend.strategy.leader_trade_strategy import (
    LeaderBreakoutStrategy,
    LeaderFirstDivergenceStrategy,
    LeaderPullbackStrategy,
    LeaderTrendContinueStrategy,
)
from backend.strategy.lianban_strategy import LianbanLeaderStrategy
from backend.strategy.mainline_strategy import MainlineStrategy, MainlineSwitchStrategy
from backend.strategy.mid_trend_strategy import CoreMidPullbackStrategy, TrendHoldStrategy


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineStep:
    order: float
    name: str
    enabled: bool
    phase: int
    handler: Any | None = None


class StrategyPipeline:
    """Phase-aware strategy pipeline with skipped future steps logged explicitly."""

    STEPS: tuple[PipelineStep, ...] = (
        PipelineStep(1, "mainline_detect", True, 2, MainlineStrategy),
        PipelineStep(2, "mainline_switch", True, 4, MainlineSwitchStrategy),
        PipelineStep(2.5, "stage_analyze", True, 6),
        PipelineStep(3, "leader_detect", True, 2, LeaderDetectStrategy),
        PipelineStep(4, "core_mid_detect", True, 2, LeaderDetectStrategy),
        PipelineStep(5, "elastic_detect", True, 2, LeaderDetectStrategy),
        PipelineStep(6, "lianban_leader_template", True, 4, LianbanLeaderStrategy),
        PipelineStep(7, "auction_relative_strength", False, 4),
        PipelineStep(8, "deny_check", True, 3),
        PipelineStep(9, "leader_pullback", True, 3, LeaderPullbackStrategy),
        PipelineStep(10, "leader_breakout", True, 3, LeaderBreakoutStrategy),
        PipelineStep(11, "leader_first_divergence", True, 4, LeaderFirstDivergenceStrategy),
        PipelineStep(12, "leader_trend_continue", True, 4, LeaderTrendContinueStrategy),
        PipelineStep(13, "core_mid_trend_pullback", True, 3, CoreMidPullbackStrategy),
        PipelineStep(14, "elastic_breakout", True, 5),
        PipelineStep(15, "panic_reversal", True, 4, PanicReversalStrategy),
        PipelineStep(16, "position_control", True, 3),
        PipelineStep(17, "stop_loss", True, 3),
        PipelineStep(18, "leader_reseal", True, 5),
        PipelineStep(19, "trend_hold", True, 4, TrendHoldStrategy),
        PipelineStep(20, "llm_review", True, 5, LLMReview),
        PipelineStep(21, "signal_eval", True, 3),
    )

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config

    def enabled_step_names(self) -> list[str]:
        names: list[str] = []
        for step in self.STEPS:
            logger.info("pipeline step %s enabled=%s phase=%s", step.name, step.enabled, step.phase)
            if step.enabled:
                names.append(step.name)
        return names


PIPELINE_STEPS = StrategyPipeline.STEPS


def enabled_step_names() -> list[str]:
    """Return enabled pipeline steps and log each enabled/disabled decision."""
    return StrategyPipeline({}).enabled_step_names()
