from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel


DATA_FILE = Path(__file__).resolve().parents[2] / "data" / "review_items.json"

ReviewAction = Literal["claim", "approve", "reject", "escalate"]


class ActionRequest(BaseModel):
    action: ReviewAction
    reviewer: str = "alex"


app = FastAPI(title="Reviewer Queue API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def load_seed_items() -> list[dict]:
    with DATA_FILE.open() as file:
        return json.load(file)


ITEMS = load_seed_items()


# Centralised state machine: maps current status -> set of allowed actions.
# Single source of truth for transitions. Any change to workflow rules
# should happen here, not scattered across the route handler.
ALLOWED_ACTIONS: dict[str, set[ReviewAction]] = {
    "unassigned": {"claim"},
    "in_review": {"approve", "reject", "escalate"},
    "approved": set(),
    "rejected": set(),
    "escalated": set(),
}


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.post("/dev/reset")
async def reset_items() -> dict:
    global ITEMS
    ITEMS = load_seed_items()
    return {"items": deepcopy(ITEMS)}


@app.get("/review-items")
async def list_review_items(active_only: bool = True) -> dict:
    items = deepcopy(ITEMS)

    if active_only:
        items = [item for item in items if item["status"] != "approved"]

    items.sort(key=lambda item: item["submitted_at"], reverse=True)
    return {"items": items}


@app.get("/review-items/{item_id}")
async def get_review_item(item_id: str) -> dict:
    item = find_item(item_id)
    return {"item": deepcopy(item)}


@app.post("/review-items/{item_id}/actions")
async def apply_action(item_id: str, request: ActionRequest) -> dict:
    item = find_item(item_id)
    current_status = item["status"]

    if request.action not in ALLOWED_ACTIONS.get(current_status, set()):
        raise HTTPException(
            status_code=409,
            detail=f"Action '{request.action}' is not allowed on an item with status '{current_status}'",
        )

    if request.action == "claim":
        item["status"] = "in_review"
        item["assigned_reviewer"] = request.reviewer
    else:
        item["status"] = status_for_action(request.action)

    return {"item": deepcopy(item)}


def find_item(item_id: str) -> dict:
    for item in ITEMS:
        if item["id"] == item_id:
            return item
    raise HTTPException(status_code=404, detail="Review item not found")


def status_for_action(action: ReviewAction) -> str:
    if action == "approve":
        return "approved"
    if action == "reject":
        return "rejected"
    if action == "escalate":
        return "escalated"
    return "in_review"