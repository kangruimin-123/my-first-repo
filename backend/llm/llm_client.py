from __future__ import annotations

import json
import logging
import os
from typing import Any

import httpx


logger = logging.getLogger(__name__)


class LLMClient:
    """OpenRouter client used only for non-binding market explanations."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.api_key = str(config.get("api_key") or os.getenv("LLM_API_KEY") or "")
        self.model = str(config.get("model", "anthropic/claude-3-haiku"))
        self.timeout = float(config.get("timeout", 10))
        self.base_url = str(config.get("base_url", "https://openrouter.ai/api/v1/chat/completions"))

    def ask(self, prompt: str) -> dict[str, Any] | None:
        """Ask OpenRouter for a JSON analysis; return None on timeout/API/parse errors."""
        if not self.api_key:
            logger.warning("LLM_API_KEY missing; LLM review skipped")
            return None
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "response_format": {"type": "json_object"},
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        try:
            response = httpx.post(self.base_url, headers=headers, json=payload, timeout=self.timeout)
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = json.loads(content) if isinstance(content, str) else content
            if not isinstance(parsed, dict):
                raise ValueError("LLM response is not a JSON object")
            return parsed
        except Exception as exc:
            logger.warning("LLM request failed: %s", exc)
            return None
