from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable, Mapping
from typing import Any, ParamSpec, Protocol, TypeVar, cast

import pandas as pd


logger = logging.getLogger(__name__)
P = ParamSpec("P")
R = TypeVar("R")


class ConfigError(RuntimeError):
    """Raised when a provider is missing required configuration."""


class DataUnavailableError(RuntimeError):
    """Raised when every provider in a degradation chain fails."""


class DegradationRecorder(Protocol):
    def record_degradation(self, source: str, target: str, reason: str) -> None:
        """Persist a degradation event."""


class DataProvider(ABC):
    name: str

    @abstractmethod
    def get_daily(self, symbol: str, start: str, end: str) -> pd.DataFrame:
        """Return daily kline data in normalized column format."""

    @abstractmethod
    def get_index_daily(self, code: str, start: str, end: str) -> pd.DataFrame:
        """Return index daily kline data in normalized column format."""

    @abstractmethod
    def get_limit_up(self, date: str) -> pd.DataFrame:
        """Return daily limit-up records."""

    @abstractmethod
    def get_daily_basic(self, date: str) -> pd.DataFrame:
        """Return daily basic valuation and turnover fields."""

    @abstractmethod
    def get_sector_mapping(self) -> pd.DataFrame:
        """Return stock-to-sector mapping."""


def attach_quality(frame: pd.DataFrame, source: str, data_quality: str) -> pd.DataFrame:
    """Attach source and data-quality metadata to a provider result."""
    frame.attrs["source"] = source
    frame.attrs["data_quality"] = data_quality
    return frame


def quality_for_level(source: str, level_index: int) -> str:
    """Map degradation level to strategy data-quality labels."""
    if source == "mock":
        return "mock"
    if level_index == 0:
        return "full"
    return "degraded"


def run_with_degradation(
    providers: Mapping[str, DataProvider],
    chain: list[str],
    method_name: str,
    recorder: DegradationRecorder | None,
    *args: Any,
    **kwargs: Any,
) -> pd.DataFrame:
    """Try providers in chain order and return the first successful DataFrame."""
    failures: list[str] = []
    previous_source = chain[0] if chain else ""
    for level_index, source in enumerate(chain):
        provider = providers.get(source)
        if provider is None:
            reason = f"provider {source} is not registered"
            failures.append(reason)
            logger.warning("data provider unavailable: %s", reason)
            if recorder and level_index + 1 < len(chain):
                recorder.record_degradation(source, chain[level_index + 1], reason)
            continue

        try:
            method = getattr(provider, method_name)
            result = method(*args, **kwargs)
            if not isinstance(result, pd.DataFrame):
                raise DataUnavailableError(f"{source}.{method_name} returned {type(result).__name__}")
            data_quality = quality_for_level(source, level_index)
            return attach_quality(result, source=source, data_quality=data_quality)
        except Exception as exc:
            reason = str(exc)
            failures.append(f"{source}: {reason}")
            logger.warning("provider %s failed for %s: %s", source, method_name, reason)
            if recorder and level_index + 1 < len(chain):
                target = chain[level_index + 1]
                recorder.record_degradation(source, target, reason)
            previous_source = source

    failure_text = "; ".join(failures) or f"empty degradation chain for {method_name}"
    raise DataUnavailableError(f"all providers failed for {method_name}: {failure_text}")


def with_degradation(chain: list[str]) -> Callable[[Callable[P, pd.DataFrame]], Callable[P, pd.DataFrame]]:
    """Decorate a method so it tries self.providers by degradation-chain order."""

    def decorator(function: Callable[P, pd.DataFrame]) -> Callable[P, pd.DataFrame]:
        method_name = function.__name__

        def wrapper(*args: P.args, **kwargs: P.kwargs) -> pd.DataFrame:
            if not args:
                raise DataUnavailableError("degradation wrapper requires an owner instance")
            owner = args[0]
            providers = cast(Mapping[str, DataProvider], getattr(owner, "providers"))
            recorder = cast(DegradationRecorder | None, getattr(owner, "degradation_manager", None))
            return run_with_degradation(providers, chain, method_name, recorder, *args[1:], **kwargs)

        return wrapper

    return decorator
