from __future__ import annotations

import logging
from typing import Any

import pandas as pd


logger = logging.getLogger(__name__)


class EfinanceProvider:
    """Efinance market data provider for auction and realtime snapshots."""

    name = "efinance"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def get_auction_snapshot(self, symbols: list[str]) -> pd.DataFrame | None:
        """Fetch pre-market auction snapshots; return None when unavailable."""
        try:
            import efinance as ef

            plain_symbols = [symbol.split(".")[0] for symbol in symbols]
            quotes = ef.stock.get_quote_history(plain_symbols, klt=1)
            if quotes is None:
                return None
            frame = self._normalize_auction(quotes, symbols)
            return frame if not frame.empty else None
        except Exception as exc:
            logger.warning("efinance auction snapshot unavailable: %s", exc)
            return None

    def get_realtime_quotes(self, symbols: list[str]) -> pd.DataFrame | None:
        """Fetch realtime quotes for Phase 5; return None when unavailable."""
        try:
            import efinance as ef

            frame = ef.stock.get_realtime_quotes([symbol.split(".")[0] for symbol in symbols])
            if frame is None or frame.empty:
                return None
            normalized = frame.rename(columns={"代码": "symbol", "最新价": "price", "成交量": "volume", "成交额": "amount", "涨跌幅": "pct_chg"})
            if "symbol" in normalized.columns:
                normalized["symbol"] = normalized["symbol"].map(lambda code: next((symbol for symbol in symbols if symbol.startswith(str(code))), str(code)))
            for column in ["symbol", "price", "volume", "amount", "pct_chg"]:
                if column not in normalized.columns:
                    normalized[column] = 0.0 if column != "symbol" else ""
            return normalized[["symbol", "price", "volume", "amount", "pct_chg"]]
        except Exception as exc:
            logger.warning("efinance realtime quotes unavailable: %s", exc)
            return None

    def _normalize_auction(self, quotes: object, symbols: list[str]) -> pd.DataFrame:
        if isinstance(quotes, dict):
            rows = []
            for symbol in symbols:
                item = quotes.get(symbol.split(".")[0])
                if isinstance(item, pd.DataFrame) and not item.empty:
                    latest = item.iloc[-1]
                    rows.append(self._row_from_quote(symbol, latest))
            return pd.DataFrame(rows)
        if isinstance(quotes, pd.DataFrame):
            rows = []
            for _, row in quotes.iterrows():
                code = str(row.get("股票代码", row.get("代码", "")))
                symbol = next((item for item in symbols if item.startswith(code)), code)
                rows.append(self._row_from_quote(symbol, row))
            return pd.DataFrame(rows)
        return pd.DataFrame(columns=["symbol", "open_price", "auction_amount", "auction_volume", "pct_chg"])

    def _row_from_quote(self, symbol: str, row: pd.Series) -> dict[str, float | str]:
        open_price = float(row.get("开盘", row.get("最新价", row.get("open", 0.0))) or 0.0)
        pct_chg = float(row.get("涨跌幅", row.get("pct_chg", 0.0)) or 0.0)
        volume = float(row.get("成交量", row.get("volume", 0.0)) or 0.0)
        amount = float(row.get("成交额", row.get("amount", 0.0)) or 0.0)
        return {
            "symbol": symbol,
            "open_price": open_price,
            "auction_amount": amount,
            "auction_volume": volume,
            "pct_chg": pct_chg,
        }
