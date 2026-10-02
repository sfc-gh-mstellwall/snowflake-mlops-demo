from __future__ import annotations

from typing import Any, Mapping


def evidence_handoff(
    *,
    environment: Mapping[str, Any],
    dataset_name: str,
    dataset_version: str,
    feature_views: list[tuple[str, str]],
    experiment_name: str,
    run_id: str,
    model_name: str,
    model_version: str | None,
    screening_status: str,
    source_state: str,
) -> dict[str, Any]:
    return {
        "environment": environment["name"],
        "presentation_environment": environment.get("presentation_name"),
        "dataset": f"{dataset_name}:{dataset_version}",
        "feature_views": [f"{name}@{version}" for name, version in feature_views],
        "experiment": experiment_name,
        "run_id": run_id,
        "model": model_name,
        "model_version": model_version,
        "registration_complete": model_version is not None,
        "screening_status": screening_status,
        "approved": False,
        "serving_active": False,
        "source_state": source_state,
        "note": "Registration is not approval or serving activation.",
    }
