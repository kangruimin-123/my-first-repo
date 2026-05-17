from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.engine.grading import Evaluation


CSV_COLUMNS = [
    "symbol",
    "name",
    "sector",
    "role",
    "stage",
    "buy_grade",
    "buy_score",
    "sell_urgency",
    "strategy_name",
    "action",
    "confidence",
    "data_quality",
    "entry_low",
    "entry_high",
    "stop_loss",
    "position_pct",
    "action_text",
    "risk_warnings",
]


def write_evaluation_csv(evaluations: list[Evaluation], output_dir: Path) -> Path:
    """Write evaluation rows to output/{date}/evaluation.csv."""
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = [{column: getattr(item, column) for column in CSV_COLUMNS if column != "risk_warnings"} | {"risk_warnings": ";".join(item.risk_warnings)} for item in evaluations]
    frame = pd.DataFrame(rows, columns=CSV_COLUMNS)
    path = output_dir / "evaluation.csv"
    frame.to_csv(path, index=False, encoding="utf-8")
    return path
