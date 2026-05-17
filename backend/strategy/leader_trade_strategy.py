from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from backend.strategy.base_strategy import BaseStrategy, StrategyContext, StrategySignal, stage_allows_buy, stage_deny_reason


EPSILON = 1e-9


class LeaderPullbackStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "leader_pullback"

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        """Find缩量回踩 MA20 的龙头低吸信号."""
        config = self.config["strategies"][self.name]
        results: list[StrategySignal] = []
        for role in context.role_results.values():
            if getattr(role, "role", "") != "leader":
                continue
            analysis = context.stock_analysis.get(role.symbol, {})
            mainline = _mainline_for(context, role.sector_name)
            if not analysis or mainline is None:
                continue
            if not stage_allows_buy(analysis, self.config, self.name):
                results.append(_deny_signal(self.name, role.symbol, stage_deny_reason(analysis)))
                continue
            trend = analysis["trend"]
            volume_price = analysis["volume_price"]
            current_price = float(analysis["current_price"])
            pct_chg = float(analysis.get("pct_chg", 0.0))
            ma20 = float(trend.ma20)
            distance_to_ma20 = abs(current_price - ma20) / max(ma20, EPSILON) * 100
            if volume_price.volume_ratio > 1.5 and pct_chg < -2.0:
                results.append(_deny_signal(self.name, role.symbol, "放量下跌，禁止低吸"))
                continue
            if mainline.mainline_status == "fading":
                results.append(_deny_signal(self.name, role.symbol, "板块退潮，禁止低吸"))
                continue
            if (
                trend.state in ("strong_up", "up")
                and distance_to_ma20 <= float(config["pullback_max_pct"]) + EPSILON
                and volume_price.volume_ratio < 1.0
                and float(mainline.mainline_score) > float(config["min_sector_score"])
            ):
                low_pct, high_pct = config["position_pct"]
                results.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=role.symbol,
                        action="buy",
                        confidence=0.68,
                        reason="龙头趋势向上，缩量回踩 MA20",
                        action_text="可在 MA20 附近分批低吸",
                        data_quality=context.data_quality,
                        entry_price_low=ma20,
                        entry_price_high=ma20 * 1.02,
                        stop_loss_price=ma20 * 0.97,
                        position_pct=(float(low_pct) + float(high_pct)) / 2,
                        grade="B",
                    )
                )
        context.add_signals(results)
        return results


class LeaderBreakoutStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "leader_breakout"

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        """Find 龙头放量突破 20 日新高信号."""
        config = self.config["strategies"][self.name]
        results: list[StrategySignal] = []
        for role in context.role_results.values():
            if getattr(role, "role", "") != "leader":
                continue
            analysis = context.stock_analysis.get(role.symbol, {})
            mainline = _mainline_for(context, role.sector_name)
            if not analysis or mainline is None:
                continue
            if not stage_allows_buy(analysis, self.config, self.name):
                results.append(_deny_signal(self.name, role.symbol, stage_deny_reason(analysis)))
                continue
            volume_price = analysis["volume_price"]
            position = analysis["position"]
            current_price = float(analysis["current_price"])
            high_20 = float(analysis["high_20"])
            pct_chg = float(analysis.get("pct_chg", 0.0))
            sector_pct_chg = float(analysis.get("sector_pct_chg", 0.0))
            if volume_price.volume_ratio < 1.0:
                results.append(_deny_signal(self.name, role.symbol, "缩量假突破"))
                continue
            if bool(config["require_sector_sync"]) and sector_pct_chg < 0:
                results.append(_deny_signal(self.name, role.symbol, "板块无跟随"))
                continue
            if (
                current_price > high_20
                and pct_chg + EPSILON >= float(config["pct_change_min"])
                and volume_price.volume_ratio + EPSILON >= float(config["volume_ratio_min"])
                and position.close_position_in_bar + EPSILON >= float(config["close_position_min"])
            ):
                low_pct, high_pct = config["position_pct"]
                results.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=role.symbol,
                        action="buy",
                        confidence=0.72,
                        reason="龙头放量突破 20 日高点且收盘位置强",
                        action_text="突破确认后轻仓跟随",
                        data_quality=context.data_quality,
                        entry_price_low=current_price * 0.98,
                        entry_price_high=current_price,
                        stop_loss_price=high_20 * 0.97,
                        position_pct=(float(low_pct) + float(high_pct)) / 2,
                        grade="B",
                    )
                )
        context.add_signals(results)
        return results


class LeaderFirstDivergenceStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "leader_first_divergence"

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        """Find first divergence pullback after a leader's main up-leg."""
        config = self.config["strategies"][self.name]
        results: list[StrategySignal] = []
        for role in context.role_results.values():
            if getattr(role, "role", "") != "leader":
                continue
            analysis = context.stock_analysis.get(role.symbol, {})
            mainline = _mainline_for(context, role.sector_name)
            if not analysis or mainline is None or mainline.mainline_status == "fading":
                continue
            if not stage_allows_buy(analysis, self.config, self.name):
                results.append(_deny_signal(self.name, role.symbol, stage_deny_reason(analysis)))
                continue
            drop_from_high = float(analysis.get("drop_from_high", 0.0))
            close_above_prev_low = bool(analysis.get("close_above_prev_low", False))
            if drop_from_high > 5.0 and drop_from_high <= float(config["max_drop_from_high"]) and close_above_prev_low:
                low_pct, high_pct = config["position_pct"]
                current_price = float(analysis.get("current_price", 0.0))
                results.append(
                    StrategySignal(
                        strategy_name=self.name,
                        symbol=role.symbol,
                        action="buy",
                        confidence=0.62,
                        reason="龙头主升后首次分歧回落且未破前低",
                        action_text="首次分歧可轻仓试错",
                        data_quality=context.data_quality,
                        entry_price_low=current_price * 0.98,
                        entry_price_high=current_price,
                        stop_loss_price=current_price * 0.94,
                        position_pct=(float(low_pct) + float(high_pct)) / 2,
                        grade="B",
                    )
                )
        context.add_signals(results)
        return results


class LeaderTrendContinueStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "leader_trend_continue"

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        """Hold or add leaders that keep MA20 and rising high/low structure."""
        results: list[StrategySignal] = []
        for role in context.role_results.values():
            if getattr(role, "role", "") != "leader":
                continue
            analysis = context.stock_analysis.get(role.symbol, {})
            if not analysis:
                continue
            trend = analysis["trend"]
            current_price = float(analysis.get("current_price", 0.0))
            higher_high_low = bool(analysis.get("higher_high_low", False))
            if current_price >= trend.ma20 and higher_high_low:
                action = "add" if trend.state == "strong_up" else "hold"
                text = "趋势延续，可持有或小幅加仓" if action == "add" else "趋势未破，继续持有"
            else:
                action = "reduce"
                text = "跌破 MA20 或结构转弱，降低仓位"
            signal = StrategySignal(
                strategy_name=self.name,
                symbol=role.symbol,
                action=action,
                confidence=0.58,
                reason=text,
                action_text=text,
                data_quality=context.data_quality,
            )
            results.append(signal)
        context.add_signals(results)
        return results


def leader_pullback_intraday(symbol: str, intraday_data: Any) -> StrategySignal | None:
    """Confirm daily leader pullback when intraday price returns near VWAP with volume recovery."""
    if intraday_data is None or len(intraday_data) == 0:
        return None
    total_volume = float(intraday_data["volume"].sum())
    if total_volume <= 0:
        return None
    vwap = float((intraday_data["price"] * intraday_data["volume"]).sum() / total_volume)
    latest = intraday_data.iloc[-1]
    price = float(latest["price"])
    distance = abs(price - vwap) / max(vwap, EPSILON)
    if len(intraday_data) >= 6:
        early_volume = float(intraday_data["volume"].iloc[-6:-3].mean())
        recent_volume = float(intraday_data["volume"].iloc[-3:].mean())
    else:
        early_volume = recent_volume = float(intraday_data["volume"].mean())
    if distance < 0.01 and recent_volume > early_volume:
        return StrategySignal(
            strategy_name="leader_pullback_intraday",
            symbol=symbol,
            action="watch",
            confidence=0.6,
            reason="分时回踩 VWAP 后量能回升",
            action_text=f"{symbol} 回踩 VWAP 附近，有承接迹象",
            data_quality="full",
        )
    return None


def leader_reseal(symbol: str, intraday_data: Any) -> StrategySignal | None:
    """Simplified reseal watch: opened after limit-up and now near limit price with volume recovery."""
    if intraday_data is None or len(intraday_data) == 0:
        return None
    latest = intraday_data.iloc[-1]
    limit_price = float(latest.get("limit_price", 0.0) or 0.0)
    if limit_price <= 0:
        return None
    price = float(latest["price"])
    ever_limit = bool(intraday_data.get("hit_limit", False).any()) if "hit_limit" in intraday_data.columns else False
    opened_board = bool(intraday_data.get("opened_board", False).any()) if "opened_board" in intraday_data.columns else False
    avg_volume = float(intraday_data["volume"].mean())
    recent_volume = float(intraday_data["volume"].tail(5).mean())
    if ever_limit and opened_board and (limit_price - price) / limit_price < 0.02 and recent_volume > avg_volume:
        return StrategySignal(
            strategy_name="leader_reseal",
            symbol=symbol,
            action="watch",
            confidence=0.58,
            reason="开板后接近涨停且量能恢复",
            action_text=f"{symbol} 接近回封，观察封板强度",
            data_quality="full",
        )
    return None


def _mainline_for(context: StrategyContext, sector_name: str) -> Any | None:
    for item in context.mainline_results:
        if getattr(item, "sector_name", "") == sector_name:
            return item
    manual_sectors = context.stock_analysis.get("manual_watchlist_sectors", set())
    if sector_name in manual_sectors:
        return SimpleNamespace(sector_name=sector_name, mainline_score=50.0, mainline_status="manual_watchlist", rank=10)
    return None


def _deny_signal(strategy_name: str, symbol: str, reason: str) -> StrategySignal:
    return StrategySignal(strategy_name=strategy_name, symbol=symbol, action="deny", confidence=1.0, reason=reason, action_text=reason, grade="NONE")
