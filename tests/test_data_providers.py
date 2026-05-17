from __future__ import annotations

import inspect

import pandas as pd
import pytest

from backend.data.akshare_provider import AkshareProvider
from backend.data.mock_provider import MockProvider
from backend.data.provider_base import ConfigError
from backend.data.tushare_provider import TushareProvider


def test_mock_provider_daily_columns_and_types() -> None:
    provider = MockProvider(seed=1)
    frame = provider.get_daily("002415.SZ", "20250101", "20250531")

    assert list(frame.columns) == ["symbol", "date", "open", "high", "low", "close", "volume", "amount", "turnover_rate"]
    assert len(frame) == 120
    assert frame["symbol"].eq("002415.SZ").all()
    assert pd.api.types.is_numeric_dtype(frame["close"])
    assert pd.api.types.is_numeric_dtype(frame["volume"])
    assert frame["close"].between(1, 100).all()


def test_mock_provider_limit_up_and_sector_mapping() -> None:
    provider = MockProvider(seed=1)
    limit_up = provider.get_limit_up("20260515")
    mapping = provider.get_sector_mapping()
    moneyflow = provider.get_moneyflow("20260515")

    assert list(limit_up.columns) == ["symbol", "date", "limit_type", "first_time", "last_time", "open_count"]
    assert 5 <= len(limit_up) <= 15
    assert list(mapping.columns) == ["symbol", "sector_name", "sector_code"]
    assert len(mapping) == 100
    assert list(moneyflow.columns) == ["symbol", "date", "net_amount"]


def test_tushare_provider_without_token_raises_config_error() -> None:
    config = {"data_source": {"tushare": {"token": "", "request_interval": 0.0, "retry_times": 1}}}

    with pytest.raises(ConfigError):
        TushareProvider(config=config)


def test_akshare_provider_interface_signatures() -> None:
    provider = AkshareProvider()
    assert list(inspect.signature(provider.get_daily).parameters) == ["symbol", "start", "end"]
    assert list(inspect.signature(provider.get_index_daily).parameters) == ["code", "start", "end"]
    assert list(inspect.signature(provider.get_limit_up).parameters) == ["date"]
    assert list(inspect.signature(provider.get_daily_basic).parameters) == ["date"]
    assert list(inspect.signature(provider.get_sector_mapping).parameters) == []
