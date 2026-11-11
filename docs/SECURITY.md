# Security

## Threat Model

Defended: board values are deep-copied through a JSON round trip on `post` and on read, so callers and sources cannot mutate internal state through returned objects or the read-only `view()`. Values must be JSON-serializable with `allow_nan=False`, must fit `max_value_bytes`, and new keys beyond `max_entries` are rejected. Source failures and invalid writes are contained: the source is disabled, its writes are discarded, and the failure is recorded without the exception message.

Not defended: the library does not execute untrusted code safely, does not authenticate sources, does not provide concurrency control, and does not persist or distribute the board. A source receives a view containing all current board values and can read every key, not only its declared triggers. A malicious or buggy source can consume cycles until `max_cycles` and can raise arbitrary exceptions; these are reported only as the exception class name.

## Input Validation

- **Keys and names**: must be strings of 1–128 characters. Invalid keys raise `BlackboardError` with `invalid_key`; invalid source names or trigger/write keys raise `invalid_config`.
- **Values**: must be JSON-serializable with `allow_nan=False`. Non-serializable values and non-finite floats raise `invalid_value`.
- **Size limits**: the UTF-8 JSON encoding of a value must not exceed `max_value_bytes` (default 65,536 bytes). Exceeding it raises `value_too_large`.
- **Capacity**: the board holds at most `max_entries` keys (default 10,000). Posting a new key beyond that raises `board_full`.
- **Cycles**: `max_cycles` must be at least 1; invalid values raise `invalid_config`.
- **History**: `max_history` must be non-negative; the run history retains at most that many newest entries.

## Data Integrity

Values are stored as deep copies via `json.dumps`/`json.loads` and returned as deep copies. `view()` returns a `MappingProxyType` over deep copies, so assignment raises `TypeError` while nested values are still separate copies. Versions start at 1 for each key and increase by 1 on every `post`.

## Logging and Events

The library uses `logging.getLogger(__name__)` with a `NullHandler` and logs only debug-level source names and error codes; it does not log values or exception messages. `on_event` receives `{"event": "run", "source": name, "writes": comma_joined_keys}` and `{"event": "source_failed", "source": name, "error": code}` payloads, never board values.

## Determinism

Scheduling is single-threaded. Eligible sources are sorted by priority descending, then name ascending, and exactly one source runs per cycle. The `clock` callable is injectable for reproducible timestamps.
