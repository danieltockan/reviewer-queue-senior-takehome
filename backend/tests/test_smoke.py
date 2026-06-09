import asyncio

import pytest
from fastapi import HTTPException

from app import main
from app.main import (
    ActionRequest,
    apply_action,
    list_review_items,
    reset_items,
)


def run_async(coro):
    return asyncio.run(coro)


@pytest.fixture(autouse=True)
def reset_state() -> None:
    """Each test starts from the seed data so state doesn't leak between tests."""
    run_async(reset_items())


def find_item_with_status(status: str) -> dict:
    items = run_async(list_review_items(active_only=False))["items"]
    for item in items:
        if item["status"] == status:
            return item
    raise AssertionError(f"No seed item with status '{status}'")


# ---------------------------------------------------------------------------
# State machine
# ---------------------------------------------------------------------------


def test_claim_moves_unassigned_to_in_review_and_records_reviewer() -> None:
    item = find_item_with_status("unassigned")
    response = run_async(
        apply_action(item["id"], ActionRequest(action="claim", reviewer="alex"))
    )
    assert response["item"]["status"] == "in_review"
    assert response["item"]["assigned_reviewer"] == "alex"


def test_cannot_claim_an_already_claimed_item() -> None:
    item = find_item_with_status("in_review")
    with pytest.raises(HTTPException) as exc:
        run_async(apply_action(item["id"], ActionRequest(action="claim")))
    assert exc.value.status_code == 409


@pytest.mark.parametrize("action", ["approve", "reject", "escalate"])
def test_cannot_act_on_unassigned_item_without_claiming_first(action: str) -> None:
    item = find_item_with_status("unassigned")
    with pytest.raises(HTTPException) as exc:
        run_async(apply_action(item["id"], ActionRequest(action=action)))
    assert exc.value.status_code == 409


@pytest.mark.parametrize("terminal_status", ["approved", "rejected", "escalated"])
@pytest.mark.parametrize("action", ["claim", "approve", "reject", "escalate"])
def test_terminal_items_reject_all_actions(terminal_status: str, action: str) -> None:
    # TAKEHOME: cross-product covers the bug we fixed (terminal-state guard
    # previously only checked 'approved', leaving rejected/escalated open).
    main.ITEMS.append({
        "id": f"RV-TEST-{terminal_status}",
        "title": "test",
        "submitted_at": "2026-01-01T00:00:00Z",
        "risk_level": "low",
        "customer_tier": "standard",
        "status": terminal_status,
        "assigned_reviewer": "alex",
        "notes_count": 0,
        "summary": "",
    })
    with pytest.raises(HTTPException) as exc:
        run_async(apply_action(f"RV-TEST-{terminal_status}", ActionRequest(action=action)))
    assert exc.value.status_code == 409


# ---------------------------------------------------------------------------
# Active queue: filter + ordering
# ---------------------------------------------------------------------------


def test_active_queue_excludes_all_terminal_statuses() -> None:
    items = run_async(list_review_items(active_only=True))["items"]
    statuses = {item["status"] for item in items}
    assert statuses.isdisjoint({"approved", "rejected", "escalated"})


def test_active_queue_ordered_by_risk_then_tier_then_age() -> None:
    items = run_async(list_review_items(active_only=True))["items"]

    risk_rank = {"high": 0, "medium": 1, "low": 2}
    tier_rank = {"priority": 0, "standard": 1}

    for earlier, later in zip(items, items[1:]):
        key_earlier = (risk_rank[earlier["risk_level"]], tier_rank[earlier["customer_tier"]], earlier["submitted_at"])
        key_later = (risk_rank[later["risk_level"]], tier_rank[later["customer_tier"]], later["submitted_at"])
        assert key_earlier <= key_later, f"{earlier['id']} should not come before {later['id']}"