from __future__ import annotations

import json
from collections.abc import Callable
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from backend.db import SystemMeta, get_session


SessionContextFactory = Callable[[], AbstractContextManager[Session]]


class DegradationManager:
    """Persist and expose provider degradation events through system_meta."""

    def __init__(self, session_factory: SessionContextFactory | None = None) -> None:
        self.session_factory = session_factory or get_session

    def record_degradation(self, source: str, target: str, reason: str) -> None:
        """Record a provider fallback event and update current status."""
        event = {
            "source": source,
            "target": target,
            "reason": reason,
            "timestamp": datetime.now(UTC).isoformat(),
        }
        with self.session_factory() as session:
            events = self._load_events(session)
            events.append(event)
            self._upsert_meta(session, "degradation_log", json.dumps(events, ensure_ascii=False))
            self._upsert_meta(session, "data_source_status", "degraded")

    def get_current_status(self) -> dict[str, Any]:
        """Return current degradation status and recent events."""
        with self.session_factory() as session:
            status_row = session.query(SystemMeta).filter_by(key="data_source_status").one_or_none()
            events = self._load_events(session)
        return {
            "data_source_status": status_row.value if status_row else "full",
            "degradation_log": events,
        }

    def _load_events(self, session: Session) -> list[dict[str, Any]]:
        row = session.query(SystemMeta).filter_by(key="degradation_log").one_or_none()
        if row is None or not row.value:
            return []
        loaded = json.loads(row.value)
        if not isinstance(loaded, list):
            return []
        return [event for event in loaded if isinstance(event, dict)]

    def _upsert_meta(self, session: Session, key: str, value: str) -> None:
        row = session.query(SystemMeta).filter_by(key=key).one_or_none()
        if row is None:
            session.add(SystemMeta(key=key, value=value))
            return
        row.value = value
