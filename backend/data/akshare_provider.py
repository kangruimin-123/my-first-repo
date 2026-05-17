from __future__ import annotations

from typing import Any

import pandas as pd

from backend.data.provider_base import DataProvider


class AkshareProvider(DataProvider):
    """Akshare fallback provider with normalized DataFrame outputs."""

    name = "akshare"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or {}

    def get_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        import akshare as ak

        frame = ak.stock_zh_a_hist(symbol=self._plain_symbol(symbol), period="daily", start_date=start, end_date=end, adjust="")
        normalized = frame.rename(
            columns={
                "日期": "date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",
                "换手率": "turnover_rate",
            }
        )
        normalized["symbol"] = symbol
        return self._ensure_columns(normalized, ["symbol", "date", "open", "high", "low", "close", "volume", "amount", "turnover_rate"])

    def get_index_daily(self, code: str, start: str, end: str) -> pd.DataFrame:
        import akshare as ak

        frame = ak.index_zh_a_hist(symbol=self._plain_symbol(code), period="daily", start_date=start, end_date=end)
        normalized = frame.rename(
            columns={
                "日期": "date",
                "开盘": "open",
                "最高": "high",
                "最低": "low",
                "收盘": "close",
                "成交量": "volume",
                "成交额": "amount",
            }
        )
        normalized["code"] = code
        return self._ensure_columns(normalized, ["code", "date", "open", "high", "low", "close", "volume", "amount"])

    def get_limit_up(self, date: str) -> pd.DataFrame:
        import akshare as ak

        frame = ak.stock_zt_pool_em(date=date)
        normalized = frame.rename(columns={"代码": "symbol", "首次封板时间": "first_time", "最后封板时间": "last_time", "炸板次数": "open_count"})
        normalized["date"] = date
        normalized["limit_type"] = "涨停"
        return self._ensure_columns(normalized, ["symbol", "date", "limit_type", "first_time", "last_time", "open_count"])

    def get_daily_basic(self, date: str) -> pd.DataFrame:
        import akshare as ak

        frame = ak.stock_zh_a_spot_em()
        normalized = frame.rename(columns={"代码": "symbol", "总市值": "market_cap", "市盈率-动态": "pe", "换手率": "turnover_rate"})
        normalized["date"] = date
        return self._ensure_columns(normalized, ["symbol", "date", "market_cap", "pe", "turnover_rate"])

    def get_sector_mapping(self) -> pd.DataFrame:
        import akshare as ak

        board_frame = ak.stock_board_concept_name_em()
        rows: list[dict[str, str]] = []
        for _, board in board_frame.head(20).iterrows():
            sector_name = str(board.get("板块名称", "UNKNOWN"))
            sector_code = str(board.get("板块代码", sector_name))
            constituents = ak.stock_board_concept_cons_em(symbol=sector_name)
            for _, stock in constituents.iterrows():
                rows.append({"symbol": str(stock.get("代码", "")), "sector_name": sector_name, "sector_code": sector_code})
        return pd.DataFrame(rows, columns=["symbol", "sector_name", "sector_code"])

    def _plain_symbol(self, symbol: str) -> str:
        return symbol.split(".")[0]

    def _ensure_columns(self, frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        normalized = frame.copy()
        for column in columns:
            if column not in normalized.columns:
                normalized[column] = None
        return normalized[columns]
