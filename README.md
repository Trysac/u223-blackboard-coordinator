# trysac-blackboard-coordinator

[![CI](https://github.com/Trysac/u223-blackboard-coordinator/actions/workflows/ci.yml/badge.svg)](https://github.com/Trysac/u223-blackboard-coordinator/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Coordinate agents through a shared blackboard: versioned JSON entries, knowledge sources triggered by key changes, deterministic priority scheduling, fault isolation and a goal check.

## Installation

```bash
pip install trysac-blackboard-coordinator
```

## Quick Start

```python
from blackboard_coordinator import Blackboard, Coordinator, KnowledgeSource

board = Blackboard()
board.post("question", "2+3", author="user")
splitter = KnowledgeSource(
    "splitter", {"question"}, {"subtasks"}, lambda v: {"subtasks": ["2", "3"]}
)
solver = KnowledgeSource(
    "solver", {"subtasks"}, {"answer"}, lambda v: {"answer": str(sum(map(int, v["subtasks"])))}
)
report = Coordinator(board, [solver, splitter], goal=lambda v: "answer" in v).run()
print(report.status)  # 'goal'
```

## API Overview

- `Entry`: frozen dataclass with `key`, `value`, `version`, `author`, `at`.
- `Blackboard(*, max_entries=10_000, max_value_bytes=65_536, clock=time.time)`: versioned store for JSON-compatible values. `post(key, value, *, author)` returns an `Entry` and increments the key's version; `get(key)` returns an `Entry` or `None`; `versions()` returns a copy of the key-to-version mapping; `view()` returns a read-only mapping of current values.
- `BlackboardError`: exception with a machine-readable `code` attribute: `invalid_value`, `value_too_large`, `board_full`, `invalid_key`, or `invalid_config`.
- `KnowledgeSource(name, triggers, writes, run, priority=0, can_run=None)`: declares trigger keys, allowed write keys, a synchronous `run(view)` callable returning a mapping, and optional priority and `can_run(view)` predicate.
- `Coordinator(board, sources, *, goal=None, max_cycles=100, max_history=1_000, on_event=None)`: runs sources until the goal is true, no source is eligible, or `max_cycles` is reached. Only one source runs per cycle; eligible sources are ordered by priority descending, then name ascending.
- `RunReport`: frozen dataclass with `status` (`goal`, `quiescent`, or `max_cycles`), `cycles`, `history`, and `failures`.

Keys and source names are 1–128 characters. Values must be JSON-serializable with `allow_nan=False`; their UTF-8 JSON encoding must not exceed `max_value_bytes`. The board holds at most `max_entries` keys. A failing source is disabled for the rest of the run and its name is recorded in `failures`. History is capped at `max_history` newest entries. The board is single-threaded and not synchronized.

## Why not message passing between agents

Direct message passing couples agents to each other's addresses and call order: adding a specialist means rewiring the others. This library uses a shared, inspectable board with versioned entries, declared trigger and write keys, deterministic priority scheduling, bounded cycles, and isolation of failing sources.

## Development

Run the tests with `python -m pytest`. Testing details are in [docs/TESTING.md](docs/TESTING.md); the security model and limits are in [docs/SECURITY.md](docs/SECURITY.md).

## License

MIT
