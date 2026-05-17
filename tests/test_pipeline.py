from __future__ import annotations

from pathlib import Path

from backend.config import load_config
from backend.engine.daily_runner import DailyRunner
from backend.engine.pipeline import StrategyPipeline


def test_pipeline_enabled_steps_include_phase3() -> None:
    names = StrategyPipeline(load_config()).enabled_step_names()
    assert "mainline_detect" in names
    assert "leader_pullback" in names
    assert "core_mid_trend_pullback" in names


def test_pipeline_skips_future_steps() -> None:
    names = StrategyPipeline(load_config()).enabled_step_names()
    assert "llm_review" in names
    assert "auction_relative_strength" not in names


def test_daily_runner_smoke_mock_data(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    config = load_config("/Users/company/股票交易系统3.0/config.yaml")
    config["system"]["db_path"] = str(tmp_path / "trading_system.db")
    config["stock_pool"]["watchlist_path"] = "/Users/company/股票交易系统3.0/sample_data/watchlist.csv"

    result = DailyRunner(config).run()

    assert len(result.focus_pool) <= 10
    assert result.output_dir.joinpath("evaluation.csv").exists()
    assert result.output_dir.joinpath("report.html").exists()
