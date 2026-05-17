from __future__ import annotations

from types import SimpleNamespace

from backend.analysis.stage_analyzer import StageResult
from backend.llm.llm_review import LLMReview
from backend.llm.prompts import build_full_context
from backend.strategy.base_strategy import StrategyContext, StrategySignal


class FakeLLMClient:
    def __init__(self, result: dict[str, object]) -> None:
        self.result = result

    def ask(self, prompt: str) -> dict[str, object]:
        return self.result


def stage() -> StageResult:
    return StageResult(
        symbol="000001.SZ",
        stage="stage_3_distribution",
        confidence=0.8,
        stage_score=32.5,
        dow_trend="weakening",
        wave_position="unknown",
        chip_status="unknown",
        volume_price_status="distribution",
        chart_pattern="distribution_risk",
        allow_buy=False,
        risk_level="high",
        reason=["高位放量滞涨", "道氏结构转弱"],
    )


def context_for() -> StrategyContext:
    symbol = "000001.SZ"
    return StrategyContext(
        config={"llm": {"enabled": True}},
        mainline_results=[SimpleNamespace(sector_name="AI", mainline_score=80, mainline_status="rising", rank=1)],
        stage_results={symbol: stage()},
        role_results={symbol: SimpleNamespace(symbol=symbol, sector_name="AI", role="leader")},
        stock_analysis={symbol: {"deny_result": "stage deny"}},
        focus_pool=[SimpleNamespace(symbol=symbol)],
        signals=[StrategySignal(strategy_name="leader_pullback", symbol=symbol, action="deny", reason="阶段门控禁止买入")],
    )


def test_build_full_context_contains_stage_fields() -> None:
    prompt = build_full_context(context_for(), "000001.SZ")

    for fragment in [
        "【阶段引擎】",
        "stage: stage_3_distribution",
        "stage_score: 32.5",
        "dow_trend: weakening",
        "wave_position: unknown",
        "chip_status: unknown",
        "volume_price_status: distribution",
        "chart_pattern: distribution_risk",
        "risk_level: high",
        "stage_reason:",
    ]:
        assert fragment in prompt


def test_llm_stage_judgement_does_not_override_deny() -> None:
    context = context_for()
    client = FakeLLMClient(
        {
            "judgement": "可能是洗盘而非派发",
            "buy_probability": 0.7,
            "reason": "阶段可能误判，但系统风控仍应保留",
            "risk_points": ["阶段误判风险：洗盘被识别为派发"],
        }
    )

    signals = LLMReview({"llm": {"enabled": True}}, llm_client=client).execute(context)

    assert signals[0].action == "hold"
    assert "阶段误判风险" in signals[0].risk_warnings[0]
    assert any(signal.action == "deny" for signal in context.signals)
