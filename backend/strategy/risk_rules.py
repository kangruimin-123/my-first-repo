from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from backend.analysis.market_risk_analyzer import MarketRiskResult
from backend.analysis.trend_analyzer import TrendResult
from backend.strategy.base_strategy import StrategySignal


EPSILON = 1e-9


@dataclass(frozen=True)
class DenyResult:
    action: str
    reasons: list[str]
    risk_score: float = 0.0


@dataclass(frozen=True)
class StopLossResult:
    urgency: str
    reason: str


class DenyCheck:
    def check(
        self,
        stock_analysis: dict[str, Any],
        mainline_results: list[Any],
        role_result: Any,
        config: dict[str, Any],
        stage_result: Any | None = None,
        strategy_name: str | None = None,
    ) -> DenyResult:
        """Apply hard deny rules before any buy signal can be upgraded."""
        reasons: list[str] = []
        risk_score = 0.0
        stage = getattr(stage_result or stock_analysis.get("stage"), "stage", "")
        if stage == "stage_4_decline":
            return DenyResult("deny", ["退潮期，只卖不买"], 100.0)
        if stage == "stage_0_accumulation" and strategy_name and strategy_name != "panic_reversal":
            return DenyResult("deny", ["吸筹期，仅允许错杀反弹小仓试错"], 60.0)
        if stage == "stage_3_distribution":
            risk_score += 30.0
        mainline_sectors = [item.sector_name for item in mainline_results[:5]]
        rank = _sector_rank(role_result.sector_name, mainline_results)
        if role_result.sector_name not in mainline_sectors and rank > 10:
            reasons.append("非主线板块")
            risk_score += 30.0
        if getattr(role_result, "score", 0.0) < 50.0:
            reasons.append("后排跟风")
            risk_score += 30.0
        if int(stock_analysis.get("consecutive_up_days", 0)) >= 5 and float(stock_analysis.get("total_pct_chg", 0.0)) > 30.0:
            reasons.append("高位一致性过热")
            risk_score += 40.0
        if float(stock_analysis.get("stop_loss_price", 0.0)) == 0.0:
            reasons.append("无止损位")
            risk_score += 30.0
        reward = float(stock_analysis.get("target_price", 0.0)) - float(stock_analysis.get("current_price", 0.0))
        risk = float(stock_analysis.get("current_price", 0.0)) - float(stock_analysis.get("stop_loss_price", 0.0))
        min_ratio = float(config["risk"]["deny_check"]["min_risk_reward_ratio"])
        if risk > EPSILON and reward / risk < min_ratio:
            reasons.append("风险收益比不足")
            risk_score += 20.0
        volume_price = stock_analysis.get("volume_price")
        if volume_price and volume_price.upper_shadow_ratio > 0.5 and volume_price.volume_ratio > 2.0:
            reasons.append("爆量长上影")
            risk_score += 30.0
        if stock_analysis.get("data_quality") in ("partial", "mock"):
            reasons.append("数据缺失或 mock")
            risk_score += 50.0
        if stage == "stage_3_distribution":
            reasons.append("派发期，风险显著升高")
        if reasons:
            return DenyResult("deny", reasons, risk_score)
        warnings = []
        if 6 <= rank <= 10:
            warnings.append("板块 Top6-10，降为观察")
        if float(stock_analysis.get("confidence", 1.0)) < 0.6:
            warnings.append("置信度不足")
        return DenyResult("watch", warnings, risk_score) if warnings else DenyResult("pass", [], risk_score)


class PositionControl:
    def calculate(self, signal: StrategySignal, current_positions: list[dict[str, Any]], market_risk: MarketRiskResult, config: dict[str, Any]) -> float:
        """Calculate final position pct under strategy and market exposure limits."""
        if signal.stop_loss_price == 0:
            return 0.0
        key = _position_key(signal.strategy_name)
        low, high = config["risk"]["position_control"].get(key, [0.0, signal.position_pct])
        desired = min(max(signal.position_pct, float(low)), float(high))
        current_total = sum(float(item.get("position_pct", 0.0)) for item in current_positions)
        max_total = float(config["risk"]["position_control"]["weak_market_max"] if market_risk.regime == "weak" else config["risk"]["position_control"]["max_total_position"])
        remaining = max(0.0, max_total - current_total)
        if signal.grade != "A" and signal.strategy_name not in ("leader_pullback", "leader_breakout", "core_mid_trend_pullback"):
            desired = min(desired, 0.1)
        return round(min(desired, remaining), 4)


class StopLoss:
    def check(
        self,
        position: dict[str, Any],
        current_price: float,
        trend: TrendResult,
        market_risk: MarketRiskResult,
        config: dict[str, Any],
    ) -> StopLossResult:
        """Classify sell urgency; clear signals are never downgraded by strong-stock protection."""
        volume_ratio = float(position.get("volume_ratio", 1.0))
        mainline_status = str(position.get("mainline_status", ""))
        upper_shadow_ratio = float(position.get("upper_shadow_ratio", 0.0))
        stop_loss = float(position.get("stop_loss", 0.0))
        strong_protected = bool(position.get("is_top5_mainline", False) and position.get("role") == "leader")

        if current_price < trend.ma60 and trend.slope_20 < 0 and not bool(position.get("has_rebound", False)):
            return StopLossResult("清仓", "跌破 MA60 且趋势向下")

        urgency = "无"
        reason = "未触发止损"
        if current_price < trend.ma20 and volume_ratio > 1.5:
            urgency = "减仓"
            reason = "跌破 MA20 且放量"
        if mainline_status == "fading":
            urgency = _max_urgency(urgency, "减仓")
            reason = "板块退潮初期"
        if stop_loss > 0 and (current_price - stop_loss) / stop_loss < 0.02:
            urgency = _max_urgency(urgency, "防守")
            reason = "接近止损价"
        if upper_shadow_ratio > 0.3:
            urgency = _max_urgency(urgency, "防守")
            reason = "放量长上影"
        if market_risk.regime == "weak" and urgency == "减仓":
            return StopLossResult("清仓", "弱市中减仓信号升级为清仓")
        if strong_protected and urgency == "减仓":
            return StopLossResult("防守", "强势股保护，减仓降为防守")
        if strong_protected and urgency == "防守":
            return StopLossResult("无", "强势股保护，防守降为无")
        return StopLossResult(urgency, reason)


def _sector_rank(sector_name: str, mainline_results: list[Any]) -> int:
    for index, item in enumerate(mainline_results, start=1):
        if item.sector_name == sector_name:
            return index
    return 999


def _position_key(strategy_name: str) -> str:
    mapping = {
        "leader_pullback": "leader_pullback",
        "leader_breakout": "leader_pullback",
        "core_mid_trend_pullback": "core_mid_trend",
        "elastic_breakout": "elastic",
    }
    return mapping.get(strategy_name, strategy_name)


def _max_urgency(current: str, candidate: str) -> str:
    order = {"无": 0, "防守": 1, "减仓": 2, "清仓": 3}
    return candidate if order[candidate] > order[current] else current
