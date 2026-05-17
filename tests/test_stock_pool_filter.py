from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.data.stock_pool_filter import StockPoolFilter


def base_config(tmp_path: Path) -> dict[str, object]:
    return {
        "stock_pool": {
            "exclude_st": True,
            "exclude_bse": True,
            "min_list_days": 60,
            "min_avg_amount_5d": 50_000_000,
            "exclude_suspended": True,
            "watchlist_path": str(tmp_path / "watchlist.csv"),
            "max_observation_pool": 50,
            "max_focus_pool": 10,
        }
    }


def test_filter_universe_excludes_st(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        [
            {"symbol": "000001.SZ", "name": "平安银行", "list_days": 100, "avg_amount_5d": 60_000_000, "is_suspended": False},
            {"symbol": "000002.SZ", "name": "*ST测试", "list_days": 100, "avg_amount_5d": 60_000_000, "is_suspended": False},
        ]
    )

    assert StockPoolFilter(base_config(tmp_path)).filter_universe(frame) == ["000001.SZ"]


def test_filter_universe_excludes_bse(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        [
            {"symbol": "430001.BJ", "name": "北交所一", "list_days": 100, "avg_amount_5d": 60_000_000, "is_suspended": False},
            {"symbol": "800001.SZ", "name": "代码八", "list_days": 100, "avg_amount_5d": 60_000_000, "is_suspended": False},
            {"symbol": "600001.SH", "name": "沪市", "list_days": 100, "avg_amount_5d": 60_000_000, "is_suspended": False},
        ]
    )

    assert StockPoolFilter(base_config(tmp_path)).filter_universe(frame) == ["600001.SH"]


def test_filter_universe_excludes_new_stock_and_low_amount(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        [
            {"symbol": "000001.SZ", "name": "合格", "list_days": 61, "avg_amount_5d": 50_000_000, "is_suspended": False},
            {"symbol": "000002.SZ", "name": "次新", "list_days": 30, "avg_amount_5d": 80_000_000, "is_suspended": False},
            {"symbol": "000003.SZ", "name": "低额", "list_days": 100, "avg_amount_5d": 20_000_000, "is_suspended": False},
        ]
    )

    assert StockPoolFilter(base_config(tmp_path)).filter_universe(frame) == ["000001.SZ"]


def test_filter_universe_excludes_suspended(tmp_path: Path) -> None:
    frame = pd.DataFrame(
        [
            {"symbol": "000001.SZ", "name": "合格", "list_days": 100, "avg_amount_5d": 60_000_000, "is_suspended": False},
            {"symbol": "000002.SZ", "name": "停牌", "list_days": 100, "avg_amount_5d": 60_000_000, "is_suspended": True},
        ]
    )

    assert StockPoolFilter(base_config(tmp_path)).filter_universe(frame) == ["000001.SZ"]


def test_load_watchlist(tmp_path: Path) -> None:
    path = tmp_path / "watchlist.csv"
    path.write_text("symbol,name\n000001.SZ,平安银行\n000001.SZ,平安银行\n600001.SH,沪市\n", encoding="utf-8")

    assert StockPoolFilter(base_config(tmp_path)).load_watchlist(str(path)) == ["000001.SZ", "600001.SH"]
