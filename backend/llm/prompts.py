from __future__ import annotations

from typing import Any

from backend.strategy.base_strategy import StrategyContext


SYSTEM_PROMPT = """
你是一个专业的 A 股短线交易分析师。基于以下盘面数据给出判断。

你需要回答：
1. 当前是分歧还是退潮？
2. 是洗盘还是出货？
3. 是真突破还是诱多？
4. 是弱转强还是假强？
5. 是否适合当前策略操作？
6. 当前阶段判定是否合理？是主升还是派发？
7. 是否存在阶段误判风险？例如洗盘被误判为派发？
8. 阶段与策略信号是否一致？

在 reason 中说明你对阶段判定的看法。
如果你认为阶段判定有误，在 risk_points 中标注。
注意：你的判断仅供参考，不覆盖阶段引擎的结论。

输出 JSON 格式：
{
    "judgement": "一句话结论",
    "buy_probability": 0.0,
    "add_probability": 0.0,
    "reduce_probability": 0.0,
    "reason": "详细分析",
    "risk_points": ["风险1", "风险2"]
}

注意：你的判断仅供参考，不构成交易建议。系统的风控规则（deny_check / stop_loss）不会因为你的判断而改变。
"""


def build_full_context(context: StrategyContext, symbol: str) -> str:
    """Build complete LLM context; never send price-only prompts."""
    role = _role_for_symbol(context, symbol)
    mainline = _mainline_for_sector(context, getattr(role, "sector_name", ""))
    analysis = context.stock_analysis.get(symbol, {})
    signals = [signal for signal in context.signals if signal.symbol == symbol]
    deny_result = analysis.get("deny_result") or _deny_result_for_symbol(signals)
    position = context.stock_analysis.get("manual_positions", {}).get(symbol, {})
    auction = context.stock_analysis.get("auction", {}).get(symbol, {})
    realtime = context.stock_analysis.get("realtime", {}).get(symbol, {})
    intraday = context.stock_analysis.get("intraday_summary", {}).get(symbol, {})
    stage = context.stage_results.get(symbol) or analysis.get("stage")

    lines = [
        SYSTEM_PROMPT.strip(),
        "",
        "【板块强度】",
        f"sector_score: {getattr(mainline, 'mainline_score', 'UNKNOWN')}",
        f"mainline_status: {getattr(mainline, 'mainline_status', 'UNKNOWN')}",
        "【板块排名】",
        f"rank: {getattr(mainline, 'rank', 'UNKNOWN')}",
        "【个股角色】",
        f"role: {getattr(role, 'role', 'UNKNOWN')}",
        "【阶段引擎】",
        f"stage: {getattr(stage, 'stage', 'UNKNOWN')}",
        f"stage_score: {getattr(stage, 'stage_score', 'UNKNOWN')}",
        f"dow_trend: {getattr(stage, 'dow_trend', 'UNKNOWN')}",
        f"wave_position: {getattr(stage, 'wave_position', 'UNKNOWN')}",
        f"chip_status: {getattr(stage, 'chip_status', 'UNKNOWN')}",
        f"volume_price_status: {getattr(stage, 'volume_price_status', 'UNKNOWN')}",
        f"chart_pattern: {getattr(stage, 'chart_pattern', 'UNKNOWN')}",
        f"risk_level: {getattr(stage, 'risk_level', 'UNKNOWN')}",
        f"stage_reason: {getattr(stage, 'reason', 'UNKNOWN')}",
        "【近 5 日走势摘要】",
        str(analysis.get("last_5d_summary", "缺失")),
        "【近 10 日走势摘要】",
        str(analysis.get("last_10d_summary", "缺失")),
        "【成交额变化趋势】",
        str(analysis.get("amount_trend", "缺失")),
        "【换手率变化趋势】",
        str(analysis.get("turnover_trend", "缺失")),
        "【策略命中结果】",
        "; ".join(f"{signal.strategy_name}:{signal.action}:{signal.reason}" for signal in signals) or "无",
        "【风控结果】",
        str(deny_result),
        "【当前持仓状态】",
        str(position or "无持仓"),
        "【竞价数据】",
        str(auction or "无"),
        "【实时行情】",
        str(realtime or "无"),
        "【分时摘要】",
        str(intraday or "无"),
    ]
    return "\n".join(lines)


def _role_for_symbol(context: StrategyContext, symbol: str) -> Any | None:
    for role in context.role_results.values():
        if getattr(role, "symbol", "") == symbol:
            return role
    return None


def _mainline_for_sector(context: StrategyContext, sector_name: str) -> Any | None:
    for mainline in context.mainline_results:
        if getattr(mainline, "sector_name", "") == sector_name:
            return mainline
    return None


def _deny_result_for_symbol(signals: list[Any]) -> str:
    deny_signals = [signal for signal in signals if signal.action == "deny" or signal.strategy_name == "deny_check"]
    if not deny_signals:
        return "未提供"
    return "; ".join(f"{signal.strategy_name}:{signal.action}:{signal.reason}" for signal in deny_signals)
