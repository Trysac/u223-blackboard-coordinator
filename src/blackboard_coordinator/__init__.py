"""Blackboard coordinator for synchronising agents through a shared, versioned board.

Public API:
- ``Entry``: frozen dataclass representing a board entry.
- ``Blackboard``: versioned key-value store with size limits and deep copying.
- ``BlackboardError``: typed error with machine-readable code.
- ``KnowledgeSource``: describes an agent with triggers, writes, and a run callable.
- ``Coordinator``: schedules sources deterministically until a goal, quiescence, or max cycles.
- ``RunReport``: result of a coordinator run.
"""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal

logger = logging.getLogger(__name__)
logger.addHandler(logging.NullHandler())

# Error codes for BlackboardError
ErrorCode = Literal[
    "invalid_value",
    "value_too_large",
    "board_full",
    "invalid_key",
    "invalid_config",
]


class BlackboardError(Exception):
    """Raised for all blackboard-related configuration and data errors."""

    def __init__(self, code: ErrorCode, message: str = "") -> None:
        super().__init__(message)
        self.code = code


class _SourceFailure(Exception):
    """Internal signal for a source's invalid write set; reported as ``code``."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Entry:
    """A versioned entry on the blackboard."""

    key: str
    value: Any
    version: int
    author: str
    at: float


@dataclass(frozen=True)
class KnowledgeSource:
    """A unit of work that reacts to changes on selected trigger keys."""

    name: str
    triggers: frozenset[str]
    writes: frozenset[str]
    run: Callable[[Mapping[str, Any]], Mapping[str, Any]]
    priority: int = 0
    can_run: Callable[[Mapping[str, Any]], bool] | None = None


@dataclass(frozen=True)
class RunReport:
    """Outcome of a coordinator run."""

    status: Literal["goal", "quiescent", "max_cycles"]
    cycles: int
    history: tuple[tuple[str, tuple[str, ...]], ...]
    failures: tuple[str, ...]


class Blackboard:
    """Thread-unsafe versioned key-value store for JSON-compatible values.

    Values are stored as deep copies (via JSON round trip) and returned as deep
    copies, so callers cannot mutate the internal state. Size limits are enforced
    on post.
    """

    def __init__(
        self,
        *,
        max_entries: int = 10_000,
        max_value_bytes: int = 65_536,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if max_entries < 0:
            raise BlackboardError("invalid_config", "max_entries must be non-negative")
        if max_value_bytes < 0:
            raise BlackboardError("invalid_config", "max_value_bytes must be non-negative")
        self._max_entries = max_entries
        self._max_value_bytes = max_value_bytes
        self._clock = clock
        self._values: dict[str, Any] = {}
        self._versions: dict[str, int] = {}
        self._authors: dict[str, str] = {}
        self._timestamps: dict[str, float] = {}

    @property
    def max_entries(self) -> int:
        return self._max_entries

    @property
    def max_value_bytes(self) -> int:
        return self._max_value_bytes

    def _validate_key(self, key: str) -> None:
        if not isinstance(key, str) or not (1 <= len(key) <= 128):
            raise BlackboardError("invalid_key", "key must be a string of 1-128 characters")

    def _deepcopy_json(self, value: Any) -> Any:
        """Return a deep copy of value via JSON round trip."""
        return json.loads(json.dumps(value, allow_nan=False))

    def _validate_value(self, value: Any) -> None:
        """Raise BlackboardError if value is not a valid, bounded JSON value."""
        try:
            dumped = json.dumps(value, allow_nan=False)
        except (TypeError, ValueError) as exc:
            raise BlackboardError("invalid_value", "value is not JSON-serializable") from exc
        if len(dumped.encode("utf-8")) > self._max_value_bytes:
            raise BlackboardError(
                "value_too_large",
                f"JSON encoding exceeds {self._max_value_bytes} bytes",
            )

    def post(self, key: str, value: Any, *, author: str) -> Entry:
        """Post a new value for *key*, incrementing its version.

        Raises:
            BlackboardError: with codes ``invalid_key``, ``board_full``,
                ``invalid_value`` or ``value_too_large``.
        """
        self._validate_key(key)
        if key not in self._versions and len(self._versions) >= self._max_entries:
            raise BlackboardError("board_full", "blackboard already has max_entries keys")
        self._validate_value(value)
        stored_value = self._deepcopy_json(value)
        self._values[key] = stored_value
        if key not in self._versions:
            self._versions[key] = 1
        else:
            self._versions[key] += 1
        self._authors[key] = author
        self._timestamps[key] = self._clock()
        return Entry(
            key=key,
            value=self._deepcopy_json(stored_value),
            version=self._versions[key],
            author=author,
            at=self._timestamps[key],
        )

    def get(self, key: str) -> Entry | None:
        """Return the current entry for *key*, or ``None`` if absent."""
        if key not in self._values:
            return None
        return Entry(
            key=key,
            value=self._deepcopy_json(self._values[key]),
            version=self._versions[key],
            author=self._authors[key],
            at=self._timestamps[key],
        )

    def versions(self) -> dict[str, int]:
        """Return a copy of the current key-to-version mapping."""
        return dict(self._versions)

    def view(self) -> Mapping[str, Any]:
        """Return a read-only mapping of current values (deep copies)."""
        copy = {key: self._deepcopy_json(value) for key, value in self._values.items()}
        return MappingProxyType(copy)


class Coordinator:
    """Deterministically schedules knowledge sources against a blackboard."""

    def __init__(
        self,
        board: Blackboard,
        sources: Sequence[KnowledgeSource],
        *,
        goal: Callable[[Mapping[str, Any]], bool] | None = None,
        max_cycles: int = 100,
        max_history: int = 1_000,
        on_event: Callable[[dict[str, str]], None] | None = None,
    ) -> None:
        if max_cycles < 1:
            raise BlackboardError("invalid_config", "max_cycles must be at least 1")
        if max_history < 0:
            raise BlackboardError("invalid_config", "max_history must be non-negative")
        source_names = [source.name for source in sources]
        if len(source_names) != len(set(source_names)):
            raise BlackboardError("invalid_config", "duplicate source names")
        for source in sources:
            if not (1 <= len(source.name) <= 128):
                raise BlackboardError("invalid_config", "source name must be 1-128 characters")
            for key in source.triggers | source.writes:
                if not (1 <= len(key) <= 128):
                    raise BlackboardError(
                        "invalid_config", "trigger/write keys must be 1-128 characters"
                    )
        self._board = board
        self._sources = list(sources)
        self._goal = goal
        self._max_cycles = max_cycles
        self._max_history = max_history
        self._on_event = on_event

    def _eligible_sources(
        self,
        view: Mapping[str, Any],
        seen_versions: dict[str, dict[str, int]],
        disabled: set[str],
    ) -> list[KnowledgeSource]:
        """Return sources that are enabled, have a trigger change, and can_run."""
        current_versions = self._board.versions()
        eligible = []
        for source in self._sources:
            if source.name in disabled:
                continue
            trigger_changed = any(
                current_versions.get(trigger, 0)
                > seen_versions.get(source.name, {}).get(trigger, 0)
                for trigger in source.triggers
            )
            if not trigger_changed:
                continue
            can_run = source.can_run
            if can_run is not None and not can_run(view):
                continue
            eligible.append(source)
        # Sort by priority descending, then name ascending
        eligible.sort(key=lambda s: (-s.priority, s.name))
        return eligible

    def _validate_writes(self, source: KnowledgeSource, writes: Mapping[str, Any]) -> None:
        """Validate that writes stay within declared keys and are acceptable values."""
        for key in writes:
            if key not in source.writes:
                raise _SourceFailure("undeclared_write")
        new_keys = set(writes.keys()) - set(self._board.versions().keys())
        if len(self._board.versions()) + len(new_keys) > self._board.max_entries:
            raise BlackboardError("board_full", "would exceed board max_entries")
        for value in writes.values():
            self._board._validate_value(value)

    def _commit_writes(
        self,
        source: KnowledgeSource,
        writes: Mapping[str, Any],
    ) -> list[str]:
        """Post writes in sorted key order; returns sorted list of written keys."""
        written_keys = sorted(writes.keys())
        for key in written_keys:
            self._board.post(key, writes[key], author=source.name)
        return written_keys

    def _update_seen_versions(
        self,
        source: KnowledgeSource,
        seen_versions: dict[str, dict[str, int]],
        trigger_versions_before: dict[str, int],
    ) -> None:
        """Record the trigger versions observed before the source ran."""
        for trigger in source.triggers:
            seen_versions.setdefault(source.name, {})[trigger] = trigger_versions_before.get(
                trigger, 0
            )

    def _handle_failure(
        self,
        source: KnowledgeSource,
        disabled: set[str],
        failures: list[str],
        error_code: str,
    ) -> None:
        """Disable source, record failure, and emit source_failed event."""
        disabled.add(source.name)
        if source.name not in failures:
            failures.append(source.name)
        if self._on_event is not None:
            self._on_event({"event": "source_failed", "source": source.name, "error": error_code})

    def run(self) -> RunReport:
        """Execute the coordination loop and return a report."""
        seen_versions: dict[str, dict[str, int]] = {
            source.name: {trigger: 0 for trigger in source.triggers} for source in self._sources
        }
        disabled: set[str] = set()
        failures: list[str] = []
        history: deque[tuple[str, tuple[str, ...]]] = deque(maxlen=self._max_history)
        cycles = 0

        while cycles < self._max_cycles:
            view = self._board.view()
            if self._goal is not None and self._goal(view):
                return RunReport(
                    status="goal",
                    cycles=cycles,
                    history=tuple(history),
                    failures=tuple(failures),
                )
            eligible = self._eligible_sources(view, seen_versions, disabled)
            if not eligible:
                return RunReport(
                    status="quiescent",
                    cycles=cycles,
                    history=tuple(history),
                    failures=tuple(failures),
                )
            source = eligible[0]
            cycles += 1
            try:
                writes = source.run(view)
                if not isinstance(writes, Mapping):
                    raise BlackboardError("invalid_value", "run must return a Mapping")
                self._validate_writes(source, writes)
                trigger_versions_before = {
                    trigger: self._board.versions().get(trigger, 0) for trigger in source.triggers
                }
                written_keys = self._commit_writes(source, writes)
                self._update_seen_versions(source, seen_versions, trigger_versions_before)
                history.append((source.name, tuple(sorted(written_keys))))
                if self._on_event is not None:
                    self._on_event(
                        {
                            "event": "run",
                            "source": source.name,
                            "writes": ",".join(sorted(written_keys)),
                        }
                    )
            except _SourceFailure as failure:
                logger.debug("source %s failed: %s", source.name, failure.code)
                self._handle_failure(source, disabled, failures, failure.code)
            except BlackboardError as be:
                logger.debug("source %s failed: %s", source.name, be.code)
                self._handle_failure(source, disabled, failures, be.code)
            except Exception as exc:
                logger.debug("source %s raised %s", source.name, type(exc).__name__)
                self._handle_failure(source, disabled, failures, type(exc).__name__)

        # Final goal check after reaching max_cycles
        final_view = self._board.view()
        if self._goal is not None and self._goal(final_view):
            return RunReport(
                status="goal",
                cycles=cycles,
                history=tuple(history),
                failures=tuple(failures),
            )
        return RunReport(
            status="max_cycles",
            cycles=cycles,
            history=tuple(history),
            failures=tuple(failures),
        )


__all__ = [
    "Blackboard",
    "BlackboardError",
    "Coordinator",
    "Entry",
    "KnowledgeSource",
    "RunReport",
]
