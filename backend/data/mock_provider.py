from __future__ import annotations

from datetime import datetime

import numpy as np
import pandas as pd

from backend.data.provider_base import DataProvider


class MockProvider(DataProvider):
    """Generate deterministic development data when real providers are unavailable."""

    name = "mock"

    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    def get_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        dates = self._date_range(start, end, periods=120)
        rng = np.random.default_rng(self._seed_for(symbol))
        close_prices = [float(rng.uniform(10.0, 50.0))]
        for _ in range(1, len(dates)):
            pct_change = float(rng.uniform(-0.03, 0.03))
            close_prices.append(max(1.0, close_prices[-1] * (1.0 + pct_change)))

        rows: list[dict[str, object]] = []
        for row_date, close in zip(dates, close_prices, strict=True):
            open_price = close * float(rng.uniform(0.985, 1.015))
            high = max(open_price, close) * float(rng.uniform(1.0, 1.02))
            low = min(open_price, close) * float(rng.uniform(0.98, 1.0))
            volume = int(rng.integers(800_000, 12_000_000))
            amount = float(volume * close)
            rows.append(
                {
                    "symbol": symbol,
                    "date": row_date.strftime("%Y-%m-%d"),
                    "open": round(open_price, 2),
                    "high": round(high, 2),
                    "low": round(low, 2),
                    "close": round(close, 2),
                    "volume": volume,
                    "amount": round(amount, 2),
                    "turnover_rate": round(float(rng.uniform(0.5, 8.0)), 2),
                }
            )
        return pd.DataFrame(rows)

    def get_index_daily(self, code: str, start: str, end: str) -> pd.DataFrame:
        frame = self.get_daily(code, start, end).rename(columns={"symbol": "code"})
        return frame.drop(columns=["turnover_rate"])

    def get_limit_up(self, date: str) -> pd.DataFrame:
        rng = np.random.default_rng(self._seed_for(date))
        count = int(rng.integers(5, 16))
        rows = []
        for index in range(count):
            symbol = f"{index + 1:06d}.SZ"
            rows.append(
                {
                    "symbol": symbol,
                    "date": date,
                    "limit_type": "首板" if index % 3 else "连板",
                    "first_time": "09:35:00",
                    "last_time": "14:50:00",
                    "open_count": int(rng.integers(0, 4)),
                }
            )
        return pd.DataFrame(rows)

    def get_daily_basic(self, date: str) -> pd.DataFrame:
        rng = np.random.default_rng(self._seed_for(date) + 7)
        rows = []
        for index in range(100):
            rows.append(
                {
                    "symbol": f"{index + 1:06d}.SZ",
                    "date": date,
                    "market_cap": round(float(rng.uniform(20.0, 500.0)), 2),
                    "pe": round(float(rng.uniform(8.0, 80.0)), 2),
                    "turnover_rate": round(float(rng.uniform(0.5, 12.0)), 2),
                }
            )
        return pd.DataFrame(rows)

    def get_sector_mapping(self) -> pd.DataFrame:
        sectors = [
            ("AI应用", "BK001"),
            ("机器人", "BK002"),
            ("有色金属", "BK003"),
            ("电力", "BK004"),
            ("军工", "BK005"),
        ]
        rows = []
        for sector_index, (sector_name, sector_code) in enumerate(sectors):
            for offset in range(20):
                symbol_index = sector_index * 20 + offset + 1
                rows.append(
                    {
                        "symbol": f"{symbol_index:06d}.SZ",
                        "sector_name": sector_name,
                        "sector_code": sector_code,
                    }
                )
        return pd.DataFrame(rows)

    def get_moneyflow(self, date: str) -> pd.DataFrame:
        rng = np.random.default_rng(self._seed_for(date) + 13)
        rows = []
        for index in range(100):
            rows.append(
                {
                    "symbol": f"{index + 1:06d}.SZ",
                    "date": date,
                    "net_amount": round(float(rng.uniform(-50_000_000, 80_000_000)), 2),
                }
            )
        return pd.DataFrame(rows)

    def _date_range(self, start: str, end: str, periods: int) -> pd.DatetimeIndex:
        start_dt = datetime.strptime(start, "%Y%m%d")
        end_dt = datetime.strptime(end, "%Y%m%d")
        dates = pd.bdate_range(start=start_dt, end=end_dt)
        if len(dates) >= periods:
            return dates[-periods:]
        end_ts = pd.Timestamp(end_dt)
        if end_ts.weekday() >= 5:
            end_ts = end_ts - pd.offsets.BDay(1)
        return pd.bdate_range(end=end_ts, periods=periods)

    def _seed_for(self, text: str) -> int:
        return self.seed + sum(ord(char) for char in text)
