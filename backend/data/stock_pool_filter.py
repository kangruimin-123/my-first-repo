from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import pandas as pd

from backend.config import load_config


logger = logging.getLogger(__name__)
EPSILON = 1e-9


class StockPoolFilter:
    """Apply the Phase 1 universe filters configured in config.yaml."""

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_config()
        self.pool_config = self.config["stock_pool"]

    def filter_universe(self, daily_basic: pd.DataFrame) -> list[str]:
        """
        Filter the market universe by ST, BSE, listing age, liquidity, and suspension rules.

        判断依据来自 v4.2：先排除不可交易或流动性不足标的，策略层只消费过滤后的股票池。
        """
        logger.info("stock_pool_filter.filter_universe started rows=%s", len(daily_basic))
        frame = daily_basic.copy()
        if frame.empty:
            logger.info("stock_pool_filter.filter_universe finished rows=0")
            return []

        mask = pd.Series(True, index=frame.index)
        if bool(self.pool_config["exclude_st"]) and "name" in frame.columns:
            names = frame["name"].fillna("").astype(str)
            mask &= ~names.str.contains("ST", case=False, regex=False)

        if bool(self.pool_config["exclude_bse"]):
            symbols = frame["symbol"].fillna("").astype(str)
            plain_codes = symbols.str.split(".").str[0]
            mask &= ~symbols.str.endswith(".BJ")
            mask &= ~plain_codes.str.startswith(("8", "9"))

        if "list_days" in frame.columns:
            min_list_days = int(self.pool_config["min_list_days"])
            mask &= frame["list_days"].fillna(0).astype(float) + EPSILON >= min_list_days

        amount_column = "avg_amount_5d" if "avg_amount_5d" in frame.columns else "amount"
        if amount_column in frame.columns:
            min_amount = float(self.pool_config["min_avg_amount_5d"])
            mask &= frame[amount_column].fillna(0).astype(float) + EPSILON >= min_amount

        if bool(self.pool_config["exclude_suspended"]) and "is_suspended" in frame.columns:
            suspended = frame["is_suspended"].fillna(False)
            mask &= ~suspended.astype(bool)

        symbols = frame.loc[mask, "symbol"].dropna().astype(str).drop_duplicates().tolist()
        logger.info("stock_pool_filter.filter_universe finished rows=%s", len(symbols))
        return symbols

    def load_watchlist(self, path: str) -> list[str]:
        """Load manually curated watchlist symbols from CSV."""
        logger.info("stock_pool_filter.load_watchlist path=%s", path)
        watchlist_path = Path(path)
        if not watchlist_path.exists():
            logger.warning("watchlist file missing: %s", watchlist_path)
            return []
        frame = pd.read_csv(watchlist_path)
        if "symbol" not in frame.columns:
            logger.warning("watchlist file has no symbol column: %s", watchlist_path)
            return []
        return frame["symbol"].dropna().astype(str).drop_duplicates().tolist()
