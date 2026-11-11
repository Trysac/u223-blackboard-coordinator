# Testing

## Running

```sh
python -m pytest
```

## Policy

- Tests import and exercise the public API from `blackboard_coordinator`.
- The suite uses a fixed clock and does not use the network.
- Tests assert return values, raised exceptions and their `code` attributes, deep-copy behavior, read-only views, scheduling order, failure isolation, history limits, and the acceptance scenario.

## Tiers

Only the local unit-test tier exists in this repository. There are no conformance tests, external-tool setup, or CI-only test markers in the provided test file.

## Layout

`tests/test_blackboard.py` contains the tests:

- `test_post_and_get_basic`: post and get return the expected `Entry` and version mapping.
- `test_post_increments_version`: posting the same key twice yields version 2 and the latest author and value.
- `test_post_returns_deep_copy_of_value`: mutating a posted list does not change stored state.
- `test_get_returns_deep_copy`: mutating an entry returned by `get` does not change stored state.
- `test_view_is_read_only_and_deep_copied`: `view()` rejects assignment and returns deep copies.
- `test_versions_returns_copy`: mutating the mapping returned by `versions()` does not change the board.
- `test_invalid_key_raises`: empty and overlong keys raise `BlackboardError` with `invalid_key`.
- `test_value_too_large`: values over 65,536 bytes raise `value_too_large`, while exactly 65,536 bytes is accepted.
- `test_invalid_value_not_json_serializable`: a `set` value raises `invalid_value`.
- `test_board_full`: posting a new key beyond `max_entries` raises `board_full`.
- `test_constructor_validation`: invalid `Blackboard` and `Coordinator` configuration raises `invalid_config`.
- `test_acceptance_goal_scenario`: the splitter/solver scenario returns status `goal`, two cycles, the expected history and no failures.

There is no `tests/conftest.py` in this repository.
