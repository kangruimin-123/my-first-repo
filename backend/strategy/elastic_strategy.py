from __future__ import annotations

from backend.strategy.base_strategy import BaseStrategy, StrategyContext, StrategySignal, stage_allows_buy


class PanicReversalStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "panic_reversal"

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        """Find panic reversal attempts in weak markets when core stock structure survives."""
        config = self.config["strategies"][self.name]
        results: list[StrategySignal] = []
        market_regime = context.stock_analysis.get("market_regime", "neutral")
        for role in context.role_results.values():
            analysis = context.stock_analysis.get(role.symbol, {})
            if not analysis:
                continue
            if not stage_allows_buy(analysis, self.config, self.name):
                continue
            trend = analysis["trend"]
            current_price = float(analysis.get("current_price", 0.0))
            panic_days = int(analysis.get("panic_days", 0))
            has_support = bool(analysis.get("has_intraday_support", False))
            if market_regime == "weak" and current_price >= trend.ma60 and panic_days >= 3 and has_support:
                max_pct = float(config["max_position_pct"])
                results.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=role.symbol,
                        action="buy",
                        confidence=0.52,
                        reason="弱市恐慌三日后核心股仍守 MA60 且有承接",
                        action_text="仅可小仓位博弈恐慌修复",
                        data_quality=context.data_quality,
                        entry_price_low=current_price * 0.98,
                        entry_price_high=current_price,
                        stop_loss_price=trend.ma60 * 0.97,
                        position_pct=max_pct,
                        grade="C",
                    )
                )
        context.add_signals(results)
        return results


class ElasticBreakoutStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "elastic_breakout"

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        """Find daily elastic breakouts near a 20-day high inside active mainlines."""
        config = self.config["strategies"][self.name]
        results: list[StrategySignal] = []
        for role in context.role_results.values():
            if getattr(role, "role", "") != "elastic":
                continue
            analysis = context.stock_analysis.get(role.symbol, {})
            if not analysis:
                continue
            mainline = next((item for item in context.mainline_results if item.sector_name == role.sector_name), None)
            if mainline is None or float(getattr(mainline, "mainline_score", 0.0)) < 40:
                continue
            if bool(config.get("require_mainline", True)) and getattr(mainline, "mainline_status", "") == "fading":
                continue
            if not stage_allows_buy(analysis, self.config, self.name):
                continue
            current_price = float(analysis.get("current_price", 0.0))
            high_20 = float(analysis.get("high_20", 0.0))
            pct_chg = float(analysis.get("pct_chg", 0.0))
            turnover_rate = float(analysis.get("turnover_rate", 0.0))
            if high_20 <= 0:
                continue
            close_to_high = current_price >= high_20 * 0.97
            if close_to_high and pct_chg > 0 and turnover_rate >= 3.0:
                max_pct = float(config.get("max_position_pct", 0.10))
                results.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=role.symbol,
                        action="watch",
                        confidence=0.54,
                        reason="弹性股接近 20 日高点且保持正涨幅",
                        action_text="弹性突破候选，仅观察小仓机会",
                        data_quality=context.data_quality,
                        entry_price_low=current_price * 0.98,
                        entry_price_high=current_price,
                        stop_loss_price=high_20 * 0.94,
                        position_pct=max_pct,
                        grade="C",
                    )
                )
        context.add_signals(results)
        return results


def elastic_breakout_intraday(symbol: str, intraday_data, role: object, mainline: object, high_20: float) -> StrategySignal | None:
    """Detect intraday elastic breakout above daily 20-day high with volume expansion."""
    if intraday_data is None or len(intraday_data) == 0:
        return None
    if getattr(role, "role", "") != "elastic":
        return None
    if getattr(mainline, "mainline_score", 0.0) < 50:
        return None
    latest = intraday_data.iloc[-1]
    price = float(latest["price"])
    avg_volume = float(intraday_data["volume"].mean())
    recent_volume = float(intraday_data["volume"].tail(5).mean())
    if price > high_20 and recent_volume > avg_volume * 1.5:
        return StrategySignal(
            strategy_name="elastic_breakout_intraday",
            symbol=symbol,
            action="watch",
            confidence=0.56,
            reason="弹性股盘中放量突破 20 日高点",
            action_text=f"{symbol} 弹性突破，仅观察小仓机会",
            data_quality="full",
            entry_price_low=price * 0.99,
            entry_price_high=price,
            stop_loss_price=high_20 * 0.97,
            position_pct=0.1,
            grade="C",
        )
    return None
