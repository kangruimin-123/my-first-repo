from __future__ import annotations

from backend.strategy.base_strategy import BaseStrategy, StrategyContext, StrategySignal, stage_allows_buy, stage_deny_reason
from backend.strategy.leader_trade_strategy import _mainline_for


EPSILON = 1e-9


class CoreMidPullbackStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "core_mid_trend_pullback"

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        """Find 中军趋势缩量回踩 MA20 信号."""
        config = self.config["strategies"][self.name]
        results: list[StrategySignal] = []
        for role in context.role_results.values():
            if getattr(role, "role", "") != "core_mid":
                continue
            analysis = context.stock_analysis.get(role.symbol, {})
            mainline = _mainline_for(context, role.sector_name)
            if not analysis or mainline is None:
                continue
            if not stage_allows_buy(analysis, self.config, self.name):
                results.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=role.symbol,
                        action="deny",
                        confidence=1.0,
                        reason=stage_deny_reason(analysis),
                        action_text=stage_deny_reason(analysis),
                        data_quality=context.data_quality,
                        grade="NONE",
                    )
                )
                continue
            trend = analysis["trend"]
            volume_price = analysis["volume_price"]
            ma60_slope = float(analysis.get("ma60_slope", trend.slope_20))
            if mainline.mainline_status == "fading":
                continue
            if (
                trend.slope_20 > 0
                and ma60_slope > 0
                and trend.ma20 + EPSILON >= trend.ma60
                and volume_price.volume_ratio < 0.8
            ):
                low_pct, high_pct = config["position_pct"]
                results.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=role.symbol,
                        action="buy",
                        confidence=0.64,
                        reason="中军 MA20/MA60 向上，缩量回踩",
                        action_text="趋势中军可在 MA20 附近配置",
                        data_quality=context.data_quality,
                        entry_price_low=trend.ma20,
                        entry_price_high=trend.ma20 * 1.02,
                        stop_loss_price=trend.ma20 * 0.95,
                        position_pct=(float(low_pct) + float(high_pct)) / 2,
                        grade="B",
                    )
                )
        context.add_signals(results)
        return results


class TrendHoldStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "trend_hold"

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        """Hold trend positions while MA20 and sector status remain intact."""
        results: list[StrategySignal] = []
        for role in context.role_results.values():
            analysis = context.stock_analysis.get(role.symbol, {})
            mainline = _mainline_for(context, role.sector_name)
            if not analysis or mainline is None:
                continue
            trend = analysis["trend"]
            current_price = float(analysis.get("current_price", 0.0))
            if current_price >= trend.ma20 and mainline.mainline_status != "fading":
                action = "hold"
                text = "未跌破 MA20 且板块未退潮，继续持有"
            else:
                action = "reduce"
                text = "跌破 MA20 或板块退潮，减仓"
            results.append(
                StrategySignal(
                    strategy_name=self.name,
                    symbol=role.symbol,
                    action=action,
                    confidence=0.55,
                    reason=text,
                    action_text=text,
                    data_quality=context.data_quality,
                )
            )
        context.add_signals(results)
        return results
