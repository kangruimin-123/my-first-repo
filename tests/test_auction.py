from __future__ import annotations

from datetime import date

import pandas as pd

from backend.db import AuctionSnapshot, DailyKline, get_session
from backend.engine.auction_runner import AuctionRunner
from backend.strategy.auction_strategy import AuctionStrategy
from backend.strategy.base_strategy import StrategyContext


def auction_config(tmp_path=None) -> dict[str, object]:
    return {
        "system": {"timezone": "Asia/Shanghai", "db_path": str(tmp_path / "test.db") if tmp_path else ":memory:"},
        "data_source": {"auction": {"chain": ["efinance", "mock"]}},
        "strategies": {"auction_relative_strength": {"enabled": True}},
    }


def test_auction_strategy_scores_when_data_available() -> None:
    frame = pd.DataFrame(
        [
            {"symbol": "A", "pct_chg": 4.0, "auction_volume": 200, "avg_auction_volume_5d": 100, "auction_amount": 1000, "market_cap": 10000},
            {"symbol": "B", "pct_chg": 0.5, "auction_volume": 100, "avg_auction_volume_5d": 100, "auction_amount": 800, "market_cap": 10000},
        ]
    )
    context = StrategyContext(config=auction_config(), stock_analysis={"auction_snapshot": frame, "sector_map": {"A": "AI", "B": "AI"}})

    signals = AuctionStrategy(auction_config()).execute(context)

    assert len(signals) == 2
    assert signals[0].strategy_name == "auction_relative_strength"
    assert "排名第" in signals[0].action_text


def test_auction_strategy_data_unavailable_returns_empty() -> None:
    context = StrategyContext(config=auction_config(), stock_analysis={})

    assert AuctionStrategy(auction_config()).execute(context) == []


def test_auction_status_strong_open() -> None:
    frame = pd.DataFrame(
        [
            {"symbol": "A", "pct_chg": 5.0, "auction_volume": 300, "avg_auction_volume_5d": 100, "auction_amount": 1000, "market_cap": 10000},
            {"symbol": "B", "pct_chg": 0.0, "auction_volume": 100, "avg_auction_volume_5d": 100, "auction_amount": 800, "market_cap": 10000},
        ]
    )
    context = StrategyContext(config=auction_config(), stock_analysis={"auction_snapshot": frame, "sector_map": {"A": "AI", "B": "AI"}})
    signals = AuctionStrategy(auction_config()).execute(context)

    assert "strong_open" in signals[0].reason


def test_auction_status_below_expectation() -> None:
    frame = pd.DataFrame(
        [
            {"symbol": "A", "pct_chg": -2.0, "auction_volume": 100, "avg_auction_volume_5d": 100, "auction_amount": 1000, "market_cap": 10000},
            {"symbol": "B", "pct_chg": 2.0, "auction_volume": 100, "avg_auction_volume_5d": 100, "auction_amount": 800, "market_cap": 10000},
        ]
    )
    context = StrategyContext(config=auction_config(), stock_analysis={"auction_snapshot": frame, "sector_map": {"A": "AI", "B": "AI"}})
    signals = AuctionStrategy(auction_config()).execute(context)

    assert "below_expectation" in signals[0].reason


def test_auction_status_overheated() -> None:
    frame = pd.DataFrame(
        [
            {"symbol": "A", "pct_chg": 8.0, "auction_volume": 300, "avg_auction_volume_5d": 100, "auction_amount": 1000, "market_cap": 10000},
            {"symbol": "B", "pct_chg": 1.0, "auction_volume": 100, "avg_auction_volume_5d": 100, "auction_amount": 800, "market_cap": 10000},
        ]
    )
    context = StrategyContext(config=auction_config(), stock_analysis={"auction_snapshot": frame, "sector_map": {"A": "AI", "B": "AI"}})
    signals = AuctionStrategy(auction_config()).execute(context)

    assert "overheated" in signals[0].reason


class FakeAuctionProvider:
    def get_auction_snapshot(self, symbols: list[str]) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"symbol": symbols[0], "open_price": 10.2, "auction_amount": 1000, "auction_volume": 100, "pct_chg": 2.0},
            ]
        )


def test_auction_runner_writes_snapshot(db_engine, tmp_path) -> None:
    config = auction_config(tmp_path)
    target_date = date(2026, 5, 17)
    with get_session(db_engine) as session:
        session.add(
            DailyKline(
                symbol="000001.SZ",
                date=target_date,
                open=10,
                high=11,
                low=9,
                close=10.5,
                volume=1000,
                amount=1000,
                turnover_rate=1.0,
            )
        )

    result = AuctionRunner(config=config, provider=FakeAuctionProvider(), session_factory=lambda: get_session(db_engine)).run()

    with get_session(db_engine) as session:
        rows = session.query(AuctionSnapshot).all()
    assert result.snapshot_count == 1
    assert rows[0].symbol == "000001.SZ"
