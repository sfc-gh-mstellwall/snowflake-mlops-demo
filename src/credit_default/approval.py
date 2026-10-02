from __future__ import annotations

from typing import Any, Mapping


def decide_approval(
    *,
    screening_status: str,
    candidate_version: str,
    incumbent_version: str | None,
    approver: str,
    exact_candidate_smoke_passed: bool,
    rollback_ready: bool,
) -> dict[str, Any]:
    if screening_status != "accepted":
        decision = "reject"
    elif not exact_candidate_smoke_passed:
        decision = "reject"
    elif incumbent_version and not rollback_ready:
        decision = "reject"
    else:
        decision = "approve"
    return {
        "decision": decision,
        "candidate_version": candidate_version,
        "incumbent_version": incumbent_version,
        "approver": approver,
        "changes_serving_selection": False,
        "note": "Approval is not serving activation.",
    }


def activate_serving(
    *,
    approval: Mapping[str, Any],
    current_selection: Mapping[str, Any] | None,
    actor: str,
) -> dict[str, Any]:
    if approval["decision"] != "approve":
        raise ValueError("Rejected or unapproved candidates cannot change serving")
    previous_id = None if current_selection is None else current_selection.get("selection_id")
    return {
        "active": True,
        "model_version": approval["candidate_version"],
        "previous_selection_id": previous_id,
        "selected_by": actor,
        "verification_status": "pending",
        "recovery_status": None,
    }


def recover_serving(current_selection: Mapping[str, Any]) -> dict[str, Any]:
    previous = current_selection.get("previous_selection_id")
    if not previous:
        raise ValueError("No previous compatible selection is available")
    return {
        "active": True,
        "restored_selection_id": previous,
        "verification_status": "pending",
        "recovery_status": "restored",
        "model_version": current_selection.get("previous_model_version"),
    }
