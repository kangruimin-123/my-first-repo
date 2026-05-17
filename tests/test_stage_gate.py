from __future__ import annotations

from types import SimpleNamespace

from backend.analysis.stage_analyzer import StageResult
from backend.engine.pipeline import StrategyPipeline
from backend.strategy.base_strategy import BaseStrategy, StrategyContext, StrategySignal
from backend.strategy.risk_rules import DenyCheck


class DummyStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "leader_pullback"

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        signal = StrategySignal(strategy_name=self.name, symbol="000001.SZ", action="buy", reason="allowed")
        context.add_signals([signal])
        return [signal]


class NoGateStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "no_gate"

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        return [StrategySignal(strategy_name=self.name, symbol="000001.SZ", action="buy")]


class PanicStrategy(DummyStrategy):
    @property
    def name(self) -> str:
        return "panic_reversal"


def config() -> dict[str, object]:
    return {
        "strategies": {
            "leader_pullback": {"allowed_stages": ["stage_1_start", "stage_2_rising"]},
            "leader_breakout": {"allowed_stages": ["stage_1_start", "stage_2_rising"]},
            "panic_reversal": {"allowed_stages": ["stage_0_accumulation", "stage_1_start"]},
        },
        "risk": {"deny_check": {"min_risk_reward_ratio": 2.0}},
    }


def stage(stage_name: str) -> StageResult:
    return StageResult(
        symbol="000001.SZ",
        stage=stage_name,
        confidence=0.8,
        stage_score=70,
        dow_trend="uptrend",
        wave_position="unknown",
        chip_status="unknown",
        volume_price_status="healthy",
        chart_pattern="breakout",
        allow_buy=stage_name not in {"stage_3_distribution", "stage_4_decline"},
        risk_level="low",
        reason=[],
    )


def risk_stock(**kwargs) -> dict[str, object]:
    base = {
        "consecutive_up_days": 0,
        "total_pct_chg": 0,
        "stop_loss_price": 9.0,
        "target_price": 13.0,
        "current_price": 10.0,
        "data_quality": "full",
    }
    base.update(kwargs)
    return base


def role(score: float = 80.0) -> SimpleNamespace:
    return SimpleNamespace(sector_name="AI", score=score)


def mainlines() -> list[SimpleNamespace]:
    return [SimpleNamespace(sector_name="AI", rank=1)]


def test_stage2_leader_pullback_allows_execute() -> None:
    context = StrategyContext(config=config())
    signals = DummyStrategy(config()).execute_with_stage_gate(context, stage("stage_2_rising"))

    assert signals[0].action == "buy"
    assert signals[0].reason == "allowed"


def test_stage3_leader_pullback_denies_with_reason() -> None:
    signals = DummyStrategy(config()).execute_with_stage_gate(StrategyContext(config=config()), stage("stage_3_distribution"))

    assert signals[0].action == "deny"
    assert "stage_3_distribution" in signals[0].reason
    assert signals[0].risk_warnings == ["阶段限制：stage_3_distribution"]


def test_stage4_buy_strategy_denies() -> None:
    signals = DummyStrategy(config()).execute_with_stage_gate(StrategyContext(config=config()), stage("stage_4_decline"))

    assert signals[0].action == "deny"


def test_stage0_panic_reversal_allows() -> None:
    signals = PanicStrategy(config()).execute_with_stage_gate(StrategyContext(config=config()), stage("stage_0_accumulation"))

    assert signals[0].action == "buy"


def test_stage0_leader_breakout_denies() -> None:
    denied = DummyStrategy(config()).execute_with_stage_gate(StrategyContext(config=config()), stage("stage_0_accumulation"))

    assert denied[0].action == "deny"


def test_unconfigured_allowed_stages_skip_gate() -> None:
    signals = NoGateStrategy(config()).execute_with_stage_gate(StrategyContext(config=config()), stage("stage_4_decline"))

    assert signals[0].action == "buy"


def test_deny_check_stage4_direct_deny() -> None:
    result = DenyCheck().check(risk_stock(), mainlines(), role(), config(), stage("stage_4_decline"), "leader_pullback")

    assert result.action == "deny"
    assert result.reasons == ["退潮期，只卖不买"]


def test_deny_check_stage3_adds_risk() -> None:
    result = DenyCheck().check(risk_stock(), mainlines(), role(), config(), stage("stage_3_distribution"), "leader_pullback")

    assert result.action == "deny"
    assert result.risk_score >= 30
    assert "派发期，风险显著升高" in result.reasons


def test_deny_check_stage2_keeps_normal_flow() -> None:
    result = DenyCheck().check(risk_stock(), mainlines(), role(), config(), stage("stage_2_rising"), "leader_pullback")

    assert result.action == "pass"
    assert result.risk_score == 0


def test_pipeline_stage_analyze_before_role_detect() -> None:
    steps = {step.name: step.order for step in StrategyPipeline(config()).STEPS}

    assert steps["mainline_switch"] < steps["stage_analyze"] < steps["leader_detect"]


def test_context_contains_stage_results() -> None:
    context = StrategyContext(config=config(), stage_results={"000001.SZ": stage("stage_2_rising")})

    assert context.stage_results["000001.SZ"].stage == "stage_2_rising"
