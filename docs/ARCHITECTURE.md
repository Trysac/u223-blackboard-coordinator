# Architecture

## Overview

`blackboard_coordinator` implements the blackboard pattern in one module. The system consists of a versioned blackboard, knowledge sources that read from and write to it, a deterministic coordinator that schedules sources, and a run report.

## Components

- **Blackboard**: stores JSON-compatible values with key, author, timestamp and version. Values are deep-copied on write and read, and limits are enforced on the number of keys and serialized value size.
- **KnowledgeSource**: frozen dataclass declaring a name, trigger keys, allowed write keys, a synchronous `run` callable, a priority, and an optional `can_run` predicate.
- **Coordinator**: schedules sources. It evaluates the board, selects one eligible source per cycle, passes a read-only view, validates the whole returned write set, posts writes in sorted key order, records history, and detects termination.
- **RunReport**: immutable result with status, cycle count, source/write history, and failed source names.

## Scheduling Algorithm

1. Before each cycle, if `goal` is provided and true on the current view, the run ends with `goal` and the current cycle count (0 if true before the first cycle).
2. Eligible sources are enabled sources for which at least one trigger key has a version greater than the version the source last observed (0 if never run), and `can_run(view)` is true or absent.
3. If no source is eligible, the run ends with `quiescent`.
4. Eligible sources are sorted by priority descending, then name ascending; exactly one source runs.
5. The source's `run` receives the read-only view and returns a mapping of writes.
6. Writes are validated as a whole: every key must be declared in `source.writes`, new keys must not exceed `max_entries`, and values must satisfy the board's JSON and size checks. Any invalid write discards the whole write set and counts as a source failure.
7. On success, writes are posted in sorted key order with the source name as author. The source records the trigger versions observed before it ran, and history receives `(source_name, sorted_written_keys)`.
8. Steps repeat until a termination condition is met or `max_cycles` is reached. After `max_cycles`, the goal is checked once more; if true the status is `goal`, otherwise `max_cycles`.

History keeps at most `max_history` newest entries.

## Error Handling

`BlackboardError` carries a stable `code`:

- `invalid_key`: key is not a string or is outside 1–128 characters.
- `invalid_value`: value is not JSON-serializable with `allow_nan=False`.
- `value_too_large`: JSON encoding exceeds `max_value_bytes`.
- `board_full`: a new key would exceed `max_entries`.
- `invalid_config`: duplicate source names, invalid source names or trigger/write keys, `max_cycles < 1`, or `max_history < 0`.

A source that raises any exception is disabled for the rest of the run. Its failure is recorded as the exception class name, or as `undeclared_write`, `invalid_value`, `value_too_large`, or `board_full` for invalid writes. Exception messages are not included in `failures` or events.

## Limits

- Keys and source names: 1–128 characters.
- Default `max_entries`: 10,000.
- Default `max_value_bytes`: 65,536.
- Default `max_cycles`: 100.
- Default `max_history`: 1,000.
- Single-threaded, synchronous execution; sources must be synchronous callables.
