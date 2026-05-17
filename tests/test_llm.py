from __future__ import annotations

from types import SimpleNamespace

from backend.llm.llm_review import LLMReview
from backend.llm.prompts import build_full_context
from backend.strategy.base_strategy import StrategyContext, StrategySignal


class FakeLLMClient:
    def __init__(self, result: dict[str, object] | None) -> None:
        self.result = result
        self.prompts: list[str] = []

    def ask(self, prompt: str) -> dict[str, object] | None:
        self.prompts.append(prompt)
        return self.result


def llm_config(enabled: bool = True) -> dict[str, object]:
    return {"llm": {"enabled": enabled}}


def context_for() -> StrategyContext:
    symbol = "000001.SZ"
    return StrategyContext(
        config=llm_config(),
        mainline_results=[
            SimpleNamespace(
                sector_name="AI",
                mainline_score=82.5,
                mainline_status="rising",
                rank=3,
            )
        ],
        role_results={
            symbol: SimpleNamespace(symbol=symbol, sector_name="AI", role="leader"),
        },
        stock_analysis={
            symbol: {
                "last_5d_summary": "每日涨跌幅 + 量能变化",
                "last_10d_summary": "趋势方向向上，关键价位 12.80",
                "amount_trend": "放量",
                "turnover_trend": "换手率上升",
                "deny_result": "pass",
            },
            "manual_positions": {symbol: {"entry_price": 10.2, "position_pct": 0.2, "pnl_pct": 8.0}},
            "auction": {symbol: {"auction_score": 78, "status": "弱转强"}},
            "realtime": {symbol: {"price": 11.3, "pct_chg": 3.2}},
            "intraday_summary": {symbol: {"vwap_position": "above", "feature": "震荡上行"}},
        },
        focus_pool=[SimpleNamespace(symbol=symbol)],
        signals=[
            StrategySignal(
                strategy_name="leader_breakout",
                symbol=symbol,
                action="buy",
                reason="突破平台",
            )
        ],
    )


def test_llm_review_parses_mock_result() -> None:
    client = FakeLLMClient(
        {
            "judgement": "分歧洗盘，非退潮",
            "buy_probability": 0.65,
            "reason": "主线仍强，量能健康",
            "risk_points": ["高位分歧加剧风险"],
        }
    )
    signals = LLMReview(llm_config(), llm_client=client).execute(context_for())

    assert len(signals) == 1
    assert signals[0].strategy_name == "llm_review"
    assert signals[0].action == "hold"
    assert signals[0].action_text == "分歧洗盘，非退潮"
    assert signals[0].risk_warnings == ["高位分歧加剧风险"]
    assert signals[0].confidence == 0.65


def test_llm_unavailable_returns_empty_list() -> None:
    context = context_for()
    signals = LLMReview(llm_config(), llm_client=FakeLLMClient(None)).execute(context)

    assert signals == []
    assert [signal.strategy_name for signal in context.signals] == ["leader_breakout"]


def test_llm_bullish_does_not_override_deny_signal() -> None:
    context = context_for()
    deny_signal = StrategySignal(
        strategy_name="deny_check",
        symbol="000001.SZ",
        action="deny",
        reason="非主线或无止损",
    )
    context.signals.append(deny_signal)
    client = FakeLLMClient(
        {
            "judgement": "强势可关注",
            "buy_probability": 0.98,
            "reason": "承接强",
            "risk_points": [],
            "action": "buy",
        }
    )

    llm_signals = LLMReview(llm_config(), llm_client=client).execute(context)

    assert deny_signal in context.signals
    assert any(signal.action == "deny" for signal in context.signals)
    assert all(signal.action not in {"buy", "sell"} for signal in llm_signals)
    assert llm_signals[0].action == "hold"


def test_build_full_context_contains_required_fields() -> None:
    prompt = build_full_context(context_for(), "000001.SZ")

    required_fragments = [
        "【板块强度】",
        "sector_score: 82.5",
        "mainline_status: rising",
        "【板块排名】",
        "rank: 3",
        "【个股角色】",
        "role: leader",
        "【近 5 日走势摘要】",
        "每日涨跌幅 + 量能变化",
        "【近 10 日走势摘要】",
        "趋势方向向上",
        "【成交额变化趋势】",
        "放量",
        "【换手率变化趋势】",
        "换手率上升",
        "【策略命中结果】",
        "leader_breakout:buy:突破平台",
        "【风控结果】",
        "pass",
        "【当前持仓状态】",
        "entry_price",
        "【竞价数据】",
        "auction_score",
        "【实时行情】",
        "pct_chg",
        "【分时摘要】",
        "vwap_position",
    ]
    for fragment in required_fragments:
        assert fragment in prompt


def test_llm_signal_action_is_never_buy_or_sell() -> None:
    client = FakeLLMClient(
        {
            "judgement": "模型极度看多",
            "buy_probability": 1.0,
            "reason": "模拟结果",
            "risk_points": [],
            "action": "buy",
        }
    )
    signals = LLMReview(llm_config(), llm_client=client).execute(context_for())

    assert signals[0].action == "hold"
    assert signals[0].action not in {"buy", "sell"}


def test_llm_disabled_skips_client_call() -> None:
    client = FakeLLMClient({"judgement": "不会被调用"})

    signals = LLMReview(llm_config(enabled=False), llm_client=client).execute(context_for())

    assert signals == []
    assert client.prompts == []
