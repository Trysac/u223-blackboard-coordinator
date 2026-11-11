"""Tests for blackboard_coordinator."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest

from blackboard_coordinator import (
    Blackboard,
    BlackboardError,
    Coordinator,
    Entry,
    KnowledgeSource,
)


class _FixedClock:
    def __init__(self, start: float = 1000.0) -> None:
        self.current = start

    def __call__(self) -> float:
        self.current += 1.0
        return self.current


# ---------------------------------------------------------------------------
# Board tests
# ---------------------------------------------------------------------------


def test_post_and_get_basic() -> None:
    board = Blackboard(clock=lambda: 42.0)
    entry = board.post("k", 1, author="a")
    assert entry == Entry(key="k", value=1, version=1, author="a", at=42.0)
    assert board.get("k") == entry
    assert board.versions() == {"k": 1}


def test_post_increments_version() -> None:
    clock = _FixedClock()
    board = Blackboard(clock=clock)
    board.post("k", 1, author="a")
    entry2 = board.post("k", 2, author="b")
    assert entry2 == Entry(key="k", value=2, version=2, author="b", at=clock.current)
    assert board.get("k") == entry2
    assert board.versions()["k"] == 2


def test_post_returns_deep_copy_of_value() -> None:
    board = Blackboard()
    original = [1, 2, 3]
    entry = board.post("k", original, author="a")
    original.append(4)
    assert entry.value == [1, 2, 3]
    # Mutating the entry's value does not affect board
    entry.value.append(4)
    assert board.get("k").value == [1, 2, 3]


def test_get_returns_deep_copy() -> None:
    board = Blackboard()
    board.post("k", [1, 2], author="a")
    entry = board.get("k")
    assert entry is not None
    entry.value.append(3)
    assert board.get("k").value == [1, 2]


def test_view_is_read_only_and_deep_copied() -> None:
    board = Blackboard()
    board.post("k", [1, 2], author="a")
    view = board.view()
    with pytest.raises(TypeError):
        view["k"] = [3]  # type: ignore[index]
    # view value is a deep copy; mutating it doesn't affect board
    view["k"].append(3)
    assert board.get("k").value == [1, 2]


def test_versions_returns_copy() -> None:
    board = Blackboard()
    board.post("a", 1, author="x")
    board.post("b", 2, author="x")
    versions = board.versions()
    versions["c"] = 3
    assert "c" not in board.versions()


def test_invalid_key_raises() -> None:
    board = Blackboard()
    with pytest.raises(BlackboardError) as excinfo:
        board.post("", 1, author="a")
    assert excinfo.value.code == "invalid_key"
    with pytest.raises(BlackboardError) as excinfo:
        board.post("a" * 129, 1, author="a")
    assert excinfo.value.code == "invalid_key"
    with pytest.raises(BlackboardError):
        board.post(123, 1, author="a")  # type: ignore[arg-type]


def test_value_too_large() -> None:
    board = Blackboard()
    # JSON encoding of a string adds two quote characters: 65_534 + 2 == 65_536.
    board.post("k", "a" * 65_534, author="a")
    with pytest.raises(BlackboardError) as excinfo:
        board.post("k", "a" * 65_535, author="a")
    assert excinfo.value.code == "value_too_large"


def test_invalid_value_not_json_serializable() -> None:
    board = Blackboard()
    with pytest.raises(BlackboardError) as excinfo:
        board.post("k", {1, 2}, author="a")  # set is not JSON serializable
    assert excinfo.value.code == "invalid_value"


def test_board_full() -> None:
    board = Blackboard(max_entries=2)
    board.post("a", 1, author="x")
    board.post("b", 2, author="x")
    with pytest.raises(BlackboardError) as excinfo:
        board.post("c", 3, author="x")
    assert excinfo.value.code == "board_full"
    # Updating existing key is allowed even when full
    board.post("a", 4, author="x")


def test_constructor_validation() -> None:
    with pytest.raises(BlackboardError) as excinfo:
        Blackboard(max_entries=-1)
    assert excinfo.value.code == "invalid_config"
    with pytest.raises(BlackboardError) as excinfo:
        Blackboard(max_value_bytes=-1)
    assert excinfo.value.code == "invalid_config"


# ---------------------------------------------------------------------------
# Coordinator tests
# ---------------------------------------------------------------------------


def _make_splitter_solver() -> tuple[Blackboard, list[KnowledgeSource]]:
    board = Blackboard()
    board.post("question", "2+3", author="user")

    def splitter(view: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"subtasks": ["2", "3"]}

    def solver(view: Mapping[str, Any]) -> Mapping[str, Any]:
        subtasks = view["subtasks"]
        return {"answer": str(sum(map(int, subtasks)))}

    sources = [
        KnowledgeSource(
            name="splitter",
            triggers=frozenset({"question"}),
            writes=frozenset({"subtasks"}),
            run=splitter,
        ),
        KnowledgeSource(
            name="solver",
            triggers=frozenset({"subtasks"}),
            writes=frozenset({"answer"}),
            run=solver,
        ),
    ]
    return board, sources


def test_acceptance_goal_scenario() -> None:
    board, sources = _make_splitter_solver()
    coordinator = Coordinator(board, sources, goal=lambda view: "answer" in view)
    report = coordinator.run()
    assert report.status == "goal"
    assert report.cycles == 2
    assert report.history == (("splitter", ("subtasks",)), ("solver", ("answer",)))
    assert report.failures == ()


def test_priority_and_name_order() -> None:
    board = Blackboard()
    board.post("input", 1, author="system")

    def run_alpha(view: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"alpha_out": 1}

    def run_beta(view: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"beta_out": 1}

    # alpha higher priority
    sources = [
        KnowledgeSource("beta", {"input"}, {"beta_out"}, run_beta, priority=10),
        KnowledgeSource("alpha", {"input"}, {"alpha_out"}, run_alpha, priority=20),
    ]
    coordinator = Coordinator(board, sources, max_cycles=1)
    report = coordinator.run()
    assert report.history[0][0] == "alpha"

    # equal priority: alphabetical order
    sources = [
        KnowledgeSource("beta", {"input"}, {"beta_out"}, run_beta),
        KnowledgeSource("alpha", {"input"}, {"alpha_out"}, run_alpha),
    ]
    coordinator = Coordinator(board, sources, max_cycles=1)
    report = coordinator.run()
    assert report.history[0][0] == "alpha"


def test_quiescent_and_max_cycles() -> None:
    # No eligible source -> quiescent
    board = Blackboard()
    source = KnowledgeSource(
        name="only",
        triggers=frozenset({"missing"}),
        writes=frozenset(),
        run=lambda view: {},
    )
    coordinator = Coordinator(board, [source], max_cycles=5)
    report = coordinator.run()
    assert report.status == "quiescent"
    assert report.cycles == 0

    # Mutual rewriting -> max_cycles
    board = Blackboard()
    board.post("a", 1, author="x")

    def flip_a(view: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"b": view["a"]}

    def flip_b(view: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"a": view["b"]}

    sources = [
        KnowledgeSource("flip_a", {"a"}, {"b"}, flip_a),
        KnowledgeSource("flip_b", {"b"}, {"a"}, flip_b),
    ]
    coordinator = Coordinator(board, sources, max_cycles=5)
    report = coordinator.run()
    assert report.status == "max_cycles"
    assert report.cycles == 5
    assert len(report.history) == 5


def test_trigger_version_gating() -> None:
    board = Blackboard()
    board.post("key", 1, author="a")

    calls = []

    def src_run(view: Mapping[str, Any]) -> Mapping[str, Any]:
        calls.append(view["key"])
        return {"out": 1}

    source = KnowledgeSource(
        name="src",
        triggers=frozenset({"key"}),
        writes=frozenset({"out"}),
        run=src_run,
    )
    coordinator = Coordinator(board, [source], max_cycles=3)
    report = coordinator.run()
    assert report.status == "quiescent"
    assert calls == [1]
    # Update key again -> source runs once more
    board.post("key", 2, author="b")
    coordinator = Coordinator(board, [source], max_cycles=3)
    report = coordinator.run()
    assert calls == [1, 2]


def test_source_failure_exception() -> None:
    board = Blackboard()
    board.post("input", 1, author="x")

    def bad_run(view: Mapping[str, Any]) -> Mapping[str, Any]:
        raise ValueError("boom")

    source = KnowledgeSource(
        name="solver",
        triggers=frozenset({"input"}),
        writes=frozenset({"output"}),
        run=bad_run,
    )
    events: list[dict[str, str]] = []
    coordinator = Coordinator(board, [source], on_event=events.append)
    report = coordinator.run()
    assert report.status == "quiescent"  # no other eligible sources
    assert report.failures == ("solver",)
    assert len(events) == 1
    assert events[0] == {"event": "source_failed", "source": "solver", "error": "ValueError"}
    assert "boom" not in str(events[0])


def test_undeclared_write_failure() -> None:
    board = Blackboard()
    board.post("input", 1, author="x")

    def bad_run(view: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"allowed": 1, "not_allowed": 2}

    source = KnowledgeSource(
        name="writer",
        triggers=frozenset({"input"}),
        writes=frozenset({"allowed"}),
        run=bad_run,
    )
    events: list[dict[str, str]] = []
    coordinator = Coordinator(board, [source], on_event=events.append)
    report = coordinator.run()
    assert report.failures == ("writer",)
    assert events[0]["error"] == "undeclared_write"
    # any invalid write discards the whole write set
    assert board.get("allowed") is None
    assert board.get("not_allowed") is None


def test_invalid_value_write_failure() -> None:
    board = Blackboard()
    board.post("input", 1, author="x")

    def bad_run(view: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"out": 1, "other": {1, 2}}  # set not JSON serializable

    source = KnowledgeSource(
        name="writer",
        triggers=frozenset({"input"}),
        writes=frozenset({"out", "other"}),
        run=bad_run,
    )
    events: list[dict[str, str]] = []
    coordinator = Coordinator(board, [source], on_event=events.append)
    report = coordinator.run()
    assert report.failures == ("writer",)
    assert events[0]["error"] == "invalid_value"
    # any invalid write discards the whole write set
    assert board.get("out") is None
    assert board.get("other") is None
    assert coordinator.run().failures == ("writer",)  # no duplication


def test_can_run_false() -> None:
    board = Blackboard()
    board.post("input", 1, author="x")

    def run_source(view: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"out": 1}

    source = KnowledgeSource(
        name="src",
        triggers=frozenset({"input"}),
        writes=frozenset({"out"}),
        run=run_source,
        can_run=lambda view: False,
    )
    coordinator = Coordinator(board, [source], max_cycles=2)
    report = coordinator.run()
    assert report.status == "quiescent"
    assert report.cycles == 0


def test_source_writes_nothing() -> None:
    board = Blackboard()
    board.post("input", 1, author="x")

    def run_source(view: Mapping[str, Any]) -> Mapping[str, Any]:
        return {}

    source = KnowledgeSource(
        name="noop",
        triggers=frozenset({"input"}),
        writes=frozenset(),
        run=run_source,
    )
    coordinator = Coordinator(board, [source], max_cycles=2)
    report = coordinator.run()
    assert report.status == "quiescent"
    assert report.cycles == 1
    assert report.history == (("noop", ()),)


def test_trigger_key_missing_no_run() -> None:
    board = Blackboard()

    def run_source(view: Mapping[str, Any]) -> Mapping[str, Any]:
        return {}

    source = KnowledgeSource(
        name="waiter",
        triggers=frozenset({"nonexistent"}),
        writes=frozenset(),
        run=run_source,
    )
    coordinator = Coordinator(board, [source], max_cycles=1)
    report = coordinator.run()
    assert report.cycles == 0


def test_max_history_truncation() -> None:
    board = Blackboard()
    board.post("a", 1, author="x")

    def run_a(view: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"b": 1}

    def run_b(view: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"a": 1}

    sources = [
        KnowledgeSource("a_src", {"a"}, {"b"}, run_a),
        KnowledgeSource("b_src", {"b"}, {"a"}, run_b),
    ]
    coordinator = Coordinator(board, sources, max_cycles=5, max_history=2)
    report = coordinator.run()
    assert report.status == "max_cycles"
    assert report.cycles == 5
    assert len(report.history) == 2


def test_goal_true_before_first_cycle() -> None:
    board = Blackboard()
    board.post("answer", 42, author="x")
    sources = [
        KnowledgeSource(
            name="unused",
            triggers=frozenset({"input"}),
            writes=frozenset(),
            run=lambda view: {},
        )
    ]
    coordinator = Coordinator(board, sources, goal=lambda view: "answer" in view)
    report = coordinator.run()
    assert report.status == "goal"
    assert report.cycles == 0


def test_on_event_run_payload() -> None:
    board = Blackboard()
    board.post("input", 1, author="x")
    events: list[dict[str, str]] = []

    def run_source(view: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"out1": 1, "out2": 2}

    source = KnowledgeSource(
        name="multi",
        triggers=frozenset({"input"}),
        writes=frozenset({"out1", "out2"}),
        run=run_source,
    )
    coordinator = Coordinator(board, [source], on_event=events.append, max_cycles=1)
    report = coordinator.run()
    assert report.history == (("multi", ("out1", "out2")),)
    assert events == [
        {"event": "run", "source": "multi", "writes": "out1,out2"},
    ]


def test_multiple_failures_and_events() -> None:
    board = Blackboard()
    board.post("input", 1, author="x")

    def fail1(view: Mapping[str, Any]) -> Mapping[str, Any]:
        raise RuntimeError("first")

    def fail2(view: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"undeclared": 1}

    sources = [
        KnowledgeSource("f1", {"input"}, {"out"}, fail1),
        KnowledgeSource("f2", {"input"}, {"out"}, fail2),
    ]
    events: list[dict[str, str]] = []
    coordinator = Coordinator(board, sources, on_event=events.append, max_cycles=3)
    report = coordinator.run()
    assert report.failures == ("f1", "f2")
    assert len(events) == 2
    assert events[0]["error"] == "RuntimeError"
    assert events[1]["error"] == "undeclared_write"
    assert report.status == "quiescent"


def test_invalid_config_duplicate_source_names() -> None:
    board = Blackboard()
    source1 = KnowledgeSource("dup", frozenset(), frozenset(), lambda v: {})
    source2 = KnowledgeSource("dup", frozenset(), frozenset(), lambda v: {})
    with pytest.raises(BlackboardError) as excinfo:
        Coordinator(board, [source1, source2])
    assert excinfo.value.code == "invalid_config"


def test_invalid_config_max_cycles() -> None:
    board = Blackboard()
    with pytest.raises(BlackboardError) as excinfo:
        Coordinator(board, [], max_cycles=0)
    assert excinfo.value.code == "invalid_config"


def test_invalid_config_bad_name_or_keys() -> None:
    board = Blackboard()
    bad_name_source = KnowledgeSource("", frozenset(), frozenset(), lambda v: {})
    with pytest.raises(BlackboardError) as excinfo:
        Coordinator(board, [bad_name_source])
    assert excinfo.value.code == "invalid_config"
    bad_trigger_source = KnowledgeSource("ok", frozenset({"a" * 129}), frozenset(), lambda v: {})
    with pytest.raises(BlackboardError) as excinfo:
        Coordinator(board, [bad_trigger_source])
    assert excinfo.value.code == "invalid_config"


def test_coordinator_resets_state_on_reuse() -> None:
    board = Blackboard()
    board.post("input", 1, author="x")

    def run_source(view: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"out": 1}

    source = KnowledgeSource("src", {"input"}, {"out"}, run_source)
    coordinator = Coordinator(board, [source], max_cycles=1)
    first = coordinator.run()
    assert first.cycles == 1
    second = coordinator.run()
    assert second.cycles == 1  # state reset
