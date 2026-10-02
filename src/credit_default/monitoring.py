from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Iterable, Mapping


UNKNOWN_LABEL = "unknown"
FINAL_LABEL = "final"
PENDING_LABEL = "pending"


def advance_replay(current_date: str, step_days: int, as_of_date: str) -> str:
    replay = date.fromisoformat(current_date) + timedelta(days=step_days)
    horizon = date.fromisoformat(as_of_date)
    if replay > horizon:
        raise ValueError("Replay cannot invent outcomes beyond the generated-data horizon")
    return replay.isoformat()


def attach_outcome(
    prediction: Mapping[str, Any],
    outcomes: Iterable[Mapping[str, Any]],
    *,
    replay_date: str,
) -> dict[str, Any]:
    matches = [
        row
        for row in outcomes
        if row["ACCOUNT_ID"] == prediction["ACCOUNT_ID"]
        and row["OBSERVATION_DATE"] == prediction["OBSERVATION_DATE"]
    ]
    if not matches:
        return {
            "prediction_id": prediction["prediction_id"],
            "match_status": "unmatched",
            "label_status": UNKNOWN_LABEL,
            "treated_as_negative": False,
        }
    outcome = matches[0]
    finality = date.fromisoformat(str(outcome["OUTCOME_FINALITY_DATE"]))
    if date.fromisoformat(replay_date) < finality:
        return {
            "prediction_id": prediction["prediction_id"],
            "match_status": "pending",
            "label_status": PENDING_LABEL,
            "treated_as_negative": False,
        }
    return {
        "prediction_id": prediction["prediction_id"],
        "match_status": "matched",
        "label_status": FINAL_LABEL,
        "default_within_90d": outcome.get("DEFAULT_WITHIN_90D"),
        "treated_as_negative": False,
    }


def coverage_summary(attachments: Iterable[Mapping[str, Any]]) -> dict[str, int]:
    rows = list(attachments)
    return {
        "predictions": len(rows),
        "matched_final": sum(1 for row in rows if row["label_status"] == FINAL_LABEL),
        "pending": sum(1 for row in rows if row["label_status"] == PENDING_LABEL),
        "unmatched": sum(1 for row in rows if row["match_status"] == "unmatched"),
    }


def recommended_action(
    *,
    drift_detected: bool,
    performance_degraded: bool,
    coverage: Mapping[str, int],
) -> dict[str, Any]:
    if coverage["matched_final"] == 0:
        action = "investigate"
    elif performance_degraded:
        action = "train_candidate"
    elif drift_detected:
        action = "investigate"
    else:
        action = "retain"
    return {
        "action": action,
        "launches_training": False,
        "changes_incumbent": False,
        "drift_is_not_performance": True,
    }


def prediction_record(
    *,
    prediction_id: str,
    account_id: str,
    observation_date: str,
    scored_at: str,
    model_version: str,
    score: float,
    release_id: str,
) -> dict[str, Any]:
    return {
        "prediction_id": prediction_id,
        "ACCOUNT_ID": account_id,
        "OBSERVATION_DATE": observation_date,
        "scored_at": scored_at,
        "model_version": model_version,
        "score": score,
        "release_id": release_id,
    }
