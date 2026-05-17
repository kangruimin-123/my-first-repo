from __future__ import annotations

from backend.strategy.base_strategy import BaseStrategy, StrategyContext, StrategySignal, stage_allows_buy, stage_deny_reason
from backend.strategy.leader_trade_strategy import _mainline_for


class LianbanLeaderStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "lianban_leader_template"

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        """Detect lianban leaders with auction strength and mainline support."""
        lianban_records = context.stock_analysis.get("lianban_records", {})
        auction_scores = context.stock_analysis.get("auction_scores", {})
        if not lianban_records or not auction_scores:
            return []
        config = self.config["strategies"][self.name]
        min_lianban = int(config["min_lianban_count"])
        results: list[StrategySignal] = []
        for role in context.role_results.values():
            mainline = _mainline_for(context, role.sector_name)
            if mainline is None or getattr(mainline, "rank", 999) > 5:
                continue
            symbol = role.symbol
            lianban_count = int(lianban_records.get(symbol, 0))
            auction_score = float(auction_scores.get(symbol, 0.0))
            leader_score = float(getattr(role, "score", 0.0))
            analysis = context.stock_analysis.get(symbol, {})
            if not stage_allows_buy(analysis, self.config, self.name):
                results.append(self._signal(symbol, "stage_deny", 0.0, stage_deny_reason(analysis), 0.0))
                continue
            consecutive_up_days = int(analysis.get("consecutive_up_days", 0))
            total_pct_chg = float(analysis.get("total_pct_chg", 0.0))
            turnover_acceptance = float(analysis.get("turnover_acceptance", 50.0))
            if lianban_count < min_lianban:
                continue
            if auction_score < 50.0:
                continue
            if leader_score < 50.0:
                results.append(self._signal(symbol, "back_row_follow", 0.0, "后排跟风，跳过", 0.0))
                continue
            if consecutive_up_days >= 5 and total_pct_chg >= 30.0:
                results.append(self._signal(symbol, "high_open_risk", auction_score, "高位一致性过热，谨慎", 0.0))
                continue
            score = min(100.0, lianban_count * 15.0 * 0.3 + auction_score * 0.3 + float(mainline.mainline_score) * 0.2 + turnover_acceptance * 0.2)
            status = self._status(score, auction_score, analysis)
            position_pct = 0.15 if score > 85 else float(config["max_position_pct"])
            results.append(self._signal(symbol, status, score, f"连板高度{lianban_count}，竞价强度{auction_score:.0f}", position_pct))
        context.add_signals(results)
        return results

    def _status(self, score: float, auction_score: float, analysis: dict) -> str:
        if float(analysis.get("auction_pct_chg", 0.0)) > 7.0:
            return "high_open_risk"
        if bool(analysis.get("broken_board_yesterday", False)):
            return "broken_board_risk"
        if float(analysis.get("previous_pct_chg", 0.0)) < 0 and auction_score > 60:
            return "weak_to_strong"
        if score > 70:
            return "lianban_leader"
        return "neutral"

    def _signal(self, symbol: str, status: str, score: float, text: str, position_pct: float) -> StrategySignal:
        return StrategySignal(
            strategy_name=self.name,
            symbol=symbol,
            action="buy" if status in ("lianban_leader", "weak_to_strong") else "deny" if status == "stage_deny" else "watch",
            confidence=min(1.0, score / 100.0),
            reason=f"lianban_status={status}",
            action_text=text,
            data_quality="full",
            entry_price_low=0.0,
            entry_price_high=0.0,
            stop_loss_price=0.0,
            position_pct=position_pct,
            grade="B" if status in ("lianban_leader", "weak_to_strong") else "NONE" if status == "stage_deny" else "C",
            risk_warnings=[] if status in ("lianban_leader", "weak_to_strong") else [status],
        )
