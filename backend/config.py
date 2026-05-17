from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml


ConfigDict = dict[str, Any]


def load_config(path: str = "config.yaml") -> ConfigDict:
    """Load YAML config and override sensitive fields from environment variables."""
    config_path = Path(path)
    with config_path.open("r", encoding="utf-8") as file:
        config: ConfigDict = yaml.safe_load(file) or {}

    tushare_token = os.getenv("TS_TOKEN")
    if tushare_token:
        config.setdefault("data_source", {}).setdefault("tushare", {})["token"] = tushare_token

    llm_api_key = os.getenv("LLM_API_KEY")
    if llm_api_key:
        config.setdefault("llm", {})["api_key"] = llm_api_key

    return config
