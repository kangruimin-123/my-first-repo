from __future__ import annotations

import logging

import pandas as pd

from backend.strategy.base_strategy import BaseStrategy, StrategyContext, StrategySignal


logger = logging.getLogger(__name__)


class AuctionStrategy(BaseStrategy):
    @property
    def name(self) -> str:
        return "auction_relative_strength"

    def execute(self, context: StrategyContext) -> list[StrategySignal]:
        """Score auction relative strength; skip cleanly when auction data is unavailable."""
        auction_df = context.stock_analysis.get("auction_snapshot")
        if auction_df is None or not isinstance(auction_df, pd.DataFrame) or auction_df.empty:
            logger.warning("竞价数据不可用，跳过 auction_relative_strength")
            return []

        frame = auction_df.copy()
        sector_map = context.stock_analysis.get("sector_map", {})
        frame["sector_name"] = frame["symbol"].map(lambda symbol: sector_map.get(symbol, "UNKNOWN"))
        frame["sector_avg_pct_chg"] = frame.groupby("sector_name")["pct_chg"].transform("mean")
        frame["auction_volume_ratio"] = frame.apply(self._volume_ratio, axis=1)
        frame["auction_turnover"] = frame.apply(self._turnover, axis=1)
        frame["rank"] = frame["pct_chg"].rank(ascending=False, method="min").astype(int)

        signals: list[StrategySignal] = []
        for _, row in frame.iterrows():
            status = self._status(row)
            confidence = min(1.0, max(0.0, (float(row["pct_chg"]) + 5.0) / 15.0))
            signals.append(
                StrategySignal(
                    strategy_name=self.name,
                    symbol=str(row["symbol"]),
                    action="watch",
                    confidence=confidence,
                    reason=f"auction_status={status}",
                    action_text=f"竞价{status}，排名第{int(row['rank'])}，较板块均值{float(row['pct_chg']) - float(row['sector_avg_pct_chg']):.2f}%",
                    data_quality=str(frame.attrs.get("data_quality", context.data_quality)),
                    grade="NONE",
                    risk_warnings=[] if status in ("strong_open", "weak_to_strong", "neutral") else [status],
                )
            )
        context.add_signals(signals)
        return signals

    def _status(self, row: pd.Series) -> str:
        pct_chg = float(row["pct_chg"])
        sector_avg = float(row["sector_avg_pct_chg"])
        volume_ratio = float(row["auction_volume_ratio"])
        previous_pct_chg = float(row.get("previous_pct_chg", 0.0) or 0.0)
        if pct_chg > 7.0:
            return "overheated"
        if pct_chg > sector_avg + 2.0 and volume_ratio > 1.5:
            return "strong_open"
        if previous_pct_chg < 0 and pct_chg > sector_avg:
            return "weak_to_strong"
        if pct_chg < sector_avg - 1.0:
            return "below_expectation"
        return "neutral"

    def _volume_ratio(self, row: pd.Series) -> float:
        avg_volume = float(row.get("avg_auction_volume_5d", 0.0) or 0.0)
        if avg_volume <= 0:
            return 1.0
        return float(row.get("auction_volume", 0.0) or 0.0) / avg_volume

    def _turnover(self, row: pd.Series) -> float:
        market_cap = float(row.get("market_cap", 0.0) or 0.0)
        if market_cap <= 0:
            return 0.0
        return float(row.get("auction_amount", 0.0) or 0.0) / market_cap
