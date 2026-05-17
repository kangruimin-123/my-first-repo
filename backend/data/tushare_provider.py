from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import pandas as pd

from backend.config import load_config
from backend.data.provider_base import ConfigError, DataProvider


logger = logging.getLogger(__name__)


class TushareProvider(DataProvider):
    """Tushare pro provider with throttling, retry, and normalized output."""

    name = "tushare"

    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self.config = config or load_config()
        tushare_config = self.config.get("data_source", {}).get("tushare", {})
        self.token = str(tushare_config.get("token", ""))
        if not self.token:
            raise ConfigError("Tushare token is required; set config data_source.tushare.token or TS_TOKEN")
        self.request_interval = float(tushare_config.get("request_interval", 0.3))
        self.retry_times = int(tushare_config.get("retry_times", 3))
        self._last_request_at = 0.0
        self._client: Any | None = None

    def get_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        frame = self._request(lambda: self.client.daily(ts_code=symbol, start_date=start, end_date=end))
        return self._normalize_daily(frame, symbol_column="ts_code", output_symbol_column="symbol")

    def get_index_daily(self, code: str, start: str, end: str) -> pd.DataFrame:
        frame = self._request(lambda: self.client.index_daily(ts_code=code, start_date=start, end_date=end))
        return self._normalize_daily(frame, symbol_column="ts_code", output_symbol_column="code").drop(columns=["turnover_rate"], errors="ignore")

    def get_limit_up(self, date: str) -> pd.DataFrame:
        frame = self._request(lambda: self.client.limit_list_d(trade_date=date))
        rename_map = {"ts_code": "symbol", "trade_date": "date", "limit_times": "open_count"}
        normalized = frame.rename(columns=rename_map)
        return self._ensure_columns(normalized, ["symbol", "date", "limit_type", "first_time", "last_time", "open_count"])

    def get_daily_basic(self, date: str) -> pd.DataFrame:
        frame = self._request(lambda: self.client.daily_basic(trade_date=date))
        rename_map = {"ts_code": "symbol", "trade_date": "date", "total_mv": "market_cap"}
        normalized = frame.rename(columns=rename_map)
        return self._ensure_columns(normalized, ["symbol", "date", "market_cap", "pe", "turnover_rate"])

    def get_sector_mapping(self) -> pd.DataFrame:
        frame = self._request(lambda: self.client.stock_basic(fields="ts_code,name,industry"))
        normalized = frame.rename(columns={"ts_code": "symbol", "industry": "sector_name"})
        normalized["sector_code"] = normalized["sector_name"].fillna("UNKNOWN")
        return self._ensure_columns(normalized, ["symbol", "sector_name", "sector_code"])

    @property
    def client(self) -> Any:
        if self._client is None:
            import tushare as ts

            self._client = ts.pro_api(self.token)
        return self._client

    def _request(self, call: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        last_error: Exception | None = None
        for attempt in range(1, self.retry_times + 1):
            try:
                self._throttle()
                frame = call()
                if not isinstance(frame, pd.DataFrame):
                    raise RuntimeError("Tushare returned non-DataFrame result")
                return frame
            except Exception as exc:
                last_error = exc
                logger.warning("tushare request failed attempt=%s reason=%s", attempt, exc)
                time.sleep(self.request_interval * attempt)
        raise RuntimeError(f"Tushare request failed after {self.retry_times} retries: {last_error}")

    def _throttle(self) -> None:
        now = time.monotonic()
        wait_seconds = self.request_interval - (now - self._last_request_at)
        if wait_seconds > 0:
            time.sleep(wait_seconds)
        self._last_request_at = time.monotonic()

    def _normalize_daily(self, frame: pd.DataFrame, symbol_column: str, output_symbol_column: str) -> pd.DataFrame:
        rename_map = {"trade_date": "date", "vol": "volume"}
        normalized = frame.rename(columns=rename_map)
        normalized[output_symbol_column] = normalized[symbol_column]
        columns = [output_symbol_column, "date", "open", "high", "low", "close", "volume", "amount", "turnover_rate"]
        return self._ensure_columns(normalized, columns)

    def _ensure_columns(self, frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        normalized = frame.copy()
        for column in columns:
            if column not in normalized.columns:
                normalized[column] = None
        return normalized[columns]
