# Submission

## Summary of changes

Three coherent improvements, prioritised against the brief:

1. **Backend state machine made correct and centralised.** Workflow rules now live in one `ALLOWED_ACTIONS` table; every action is guarded against the item's current status before any mutation. Closes two correctness bugs (terminal-state guard only covered `approved`; `approve`/`reject`/`escalate` could be applied to `unassigned` items, skipping the claim step and leaving no assignee).
2. **Active queue filter and ordering implemented per the brief.** Excludes all three terminal statuses (was only `approved`) and orders by risk → customer tier → age (was reverse-chronological).
3. **Reviewer UX: actions mirror the state machine.** Invalid action buttons are disabled with per-status tooltip explanations; raw enum values replaced with human-readable labels; a banner on terminal items confirms no further actions are possible.

## Bugs fixed

- **Terminal-state guard incomplete** (`backend/app/main.py`). Old code only blocked further actions on `approved`; `rejected` and `escalated` items still accepted any action.
- **Actions skipped the claim step** (`backend/app/main.py`). No status check guarded `approve`/`reject`/`escalate`, so an `unassigned` item could be approved directly with no `assigned_reviewer` recorded.
- **Active queue filter incomplete** (`backend/app/main.py`). Only `approved` items were excluded; `rejected` and `escalated` items remained in the active queue.
- **Queue ordering ignored the brief's three urgency rules** (`backend/app/main.py`). Sorted by newest submission instead of risk → tier → age.

## Product/UX decisions

**Disable invalid actions, don't hide them.** A reviewer learning the workflow should see the full action set and which one is currently available, not have buttons appear and disappear. Buttons that aren't permitted by the state machine are disabled and carry a `title` tooltip explaining the reason (e.g. "Claim this item first.", "Already claimed — only approve, reject, or escalate are available."). The terminal-item banner reinforces the same message at the item level.

**Tradeoff:** the frontend duplicates the backend's `ALLOWED_ACTIONS` table rather than fetching it from an endpoint. For a 5-rule state machine this is acceptable; the backend remains the source of truth and will still 409 on any bypass.

**Human-readable labels via display maps** rather than mutating the data — types stay precise; if a new status is added, the unused enum in the map will fail type checks.

## Tests added

`backend/tests/test_state_machine.py` — targeted coverage on the high-risk behaviour changed in slices 1 and 2:

- claim happy path moves `unassigned` → `in_review` and records the reviewer
- re-claiming an `in_review` item rejected with 409
- `approve`/`reject`/`escalate` rejected on `unassigned` items (parametrised)
- every action rejected on every terminal status (4 × 3 cross-product, parametrised)
- active queue excludes all three terminal statuses
- active queue ordering: risk → customer tier → age (structural assertion over adjacent pairs)

19 tests total in the suite (16 new), all passing.

## Known gaps

- **No persistence.** Mutations live in module-level memory; a process restart resets state. Out of scope per the brief ("a full database migration" is explicitly not expected). A real product would back this with SQLite or similar.
- **No frontend tests.** No Vue test runner is configured; setup time would exceed the value at this scope. The frontend changes are easily manually verified and the high-risk logic (state-machine enforcement) is covered on the backend.
- **Layout collapses on short queues.** The detail and list panels shrink with content. Cosmetic only; would add a viewport min-height.
- **`/dev/reset` is unauthenticated.** Fine for the take-home; would gate behind dev-only routing in production.
- **No optimistic update / loading state on action buttons.** Actions block via `pendingAction` but don't show a spinner. Acceptable for the timebox.
- **Reviewers can act on items claimed by others.** The brief doesn't require ownership scoping — any `in_review` item accepts approve/reject/escalate regardless of which reviewer claimed it. In a real product I'd scope these actions to the assignee (and add a "reassign" affordance). Out of scope here per the brief.

## Files changed and why

- `backend/app/main.py` — centralised `ALLOWED_ACTIONS` state machine; replaced scattered status checks in `apply_action` with a single guard; fixed active-queue filter and added risk → tier → age ordering with named constants.
- `backend/tests/test_state_machine.py` — new test file covering the state machine and queue behaviour.
- `frontend/src/App.vue` — frontend mirror of `ALLOWED_ACTIONS`; `isActionAllowed` + `disabledReason` helpers; label maps for status / risk / tier; terminal-item banner; `title` tooltips on action buttons.
- `frontend/src/styles.css` — single new rule (`.terminal-note`) matching the existing palette.

## AI assistance used

Ran the app locally and did a manual bug bash against the brief's requirements. Took those observations to Claude as a pairing partner, which produced the implementation plan we followed slice by slice. Paired with Claude throughout the build — reviewed every change before committing, and rejected suggestions that violated the brief (notably one frontend state-machine variant that would have permitted re-claiming an already-claimed item).