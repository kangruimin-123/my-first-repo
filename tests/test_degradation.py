from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
import pytest
from sqlalchemy.engine import Engine

from backend.data.degradation import DegradationManager
from backend.data.provider_base import DataProvider, DataUnavailableError, run_with_degradation
from backend.db import get_session, get_system_meta


@dataclass
class FakeProvider(DataProvider):
    name: str
    should_fail: bool = False

    def get_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        if self.should_fail:
            raise RuntimeError(f"{self.name} failed")
        return pd.DataFrame(
            [
                {
                    "symbol": symbol,
                    "date": start,
                    "open": 10.0,
                    "high": 10.5,
                    "low": 9.8,
                    "close": 10.2,
                    "volume": 1000,
                    "amount": 10200,
                    "turnover_rate": 1.2,
                }
            ]
        )

    def get_index_daily(self, code: str, start: str, end: str) -> pd.DataFrame:
        return self.get_daily(code, start, end).rename(columns={"symbol": "code"}).drop(columns=["turnover_rate"])

    def get_limit_up(self, date: str) -> pd.DataFrame:
        if self.should_fail:
            raise RuntimeError(f"{self.name} failed")
        return pd.DataFrame([{"symbol": "000001.SZ", "date": date}])

    def get_daily_basic(self, date: str) -> pd.DataFrame:
        if self.should_fail:
            raise RuntimeError(f"{self.name} failed")
        return pd.DataFrame([{"symbol": "000001.SZ", "date": date, "market_cap": 100.0, "pe": 12.0, "turnover_rate": 2.0}])

    def get_sector_mapping(self) -> pd.DataFrame:
        if self.should_fail:
            raise RuntimeError(f"{self.name} failed")
        return pd.DataFrame([{"symbol": "000001.SZ", "sector_name": "AI应用", "sector_code": "BK001"}])


def manager_for_engine(db_engine: Engine) -> DegradationManager:
    return DegradationManager(session_factory=lambda: get_session(db_engine))


def test_degradation_chain_falls_back_from_level1_to_level2(db_engine: Engine) -> None:
    manager = manager_for_engine(db_engine)
    providers = {"tushare": FakeProvider("tushare", True), "akshare": FakeProvider("akshare"), "mock": FakeProvider("mock")}

    frame = run_with_degradation(providers, ["tushare", "akshare", "mock"], "get_daily", manager, "002415.SZ", "20260515", "20260515")

    assert frame.attrs["source"] == "akshare"
    assert frame.attrs["data_quality"] == "degraded"
    with get_session(db_engine) as session:
        meta = get_system_meta(session)
    assert meta["data_source_status"] == "degraded"
    assert "tushare failed" in meta["degradation_log"]


def test_degradation_chain_falls_back_to_level3_mock(db_engine: Engine) -> None:
    manager = manager_for_engine(db_engine)
    providers = {"tushare": FakeProvider("tushare", True), "akshare": FakeProvider("akshare", True), "mock": FakeProvider("mock")}

    frame = run_with_degradation(providers, ["tushare", "akshare", "mock"], "get_daily", manager, "002415.SZ", "20260515", "20260515")

    assert frame.attrs["source"] == "mock"
    assert frame.attrs["data_quality"] == "mock"
    with get_session(db_engine) as session:
        meta = get_system_meta(session)
    assert "akshare failed" in meta["degradation_log"]


def test_degradation_chain_all_failed_raises(db_engine: Engine) -> None:
    manager = manager_for_engine(db_engine)
    providers = {"tushare": FakeProvider("tushare", True), "akshare": FakeProvider("akshare", True), "mock": FakeProvider("mock", True)}

    with pytest.raises(DataUnavailableError):
        run_with_degradation(providers, ["tushare", "akshare", "mock"], "get_daily", manager, "002415.SZ", "20260515", "20260515")


def test_successful_level1_marks_full_quality(db_engine: Engine) -> None:
    manager = manager_for_engine(db_engine)
    providers = {"tushare": FakeProvider("tushare"), "akshare": FakeProvider("akshare"), "mock": FakeProvider("mock")}

    frame = run_with_degradation(providers, ["tushare", "akshare", "mock"], "get_daily", manager, "002415.SZ", "20260515", "20260515")

    assert frame.attrs["source"] == "tushare"
    assert frame.attrs["data_quality"] == "full"
    with get_session(db_engine) as session:
        assert get_system_meta(session) == {}
