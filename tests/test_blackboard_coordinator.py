"""Behavior tests for the public API of blackboard_coordinator."""

from __future__ import annotations

import pytest

import blackboard_coordinator


def test_normalize_trims_and_lowercases() -> None:
    assert blackboard_coordinator.normalize("  Hello World ") == "hello world"


@pytest.mark.parametrize("value", ["", "   ", "\t\n"])
def test_normalize_rejects_blank_input(value: str) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        blackboard_coordinator.normalize(value)


def test_version_is_semver() -> None:
    parts = blackboard_coordinator.__version__.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
