"""Behavior tests for the public API of blackboard_coordinator."""

from __future__ import annotations

import blackboard_coordinator

PUBLIC_NAMES = {
    "Blackboard",
    "BlackboardError",
    "Coordinator",
    "Entry",
    "KnowledgeSource",
    "RunReport",
}


def test_public_api_is_exported() -> None:
    for name in PUBLIC_NAMES:
        assert hasattr(blackboard_coordinator, name)


def test_all_matches_public_api() -> None:
    assert set(blackboard_coordinator.__all__) == PUBLIC_NAMES
