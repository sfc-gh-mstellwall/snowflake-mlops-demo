from __future__ import annotations

import json
import uuid
from typing import Any, Mapping

from snowflake.snowpark import functions as F

# Load project.yaml via contracts.py so approval and serving-selection tables
# resolve against the configured database and CONTROL schema.
from .contracts import load_project


def decide_approval(
    *,
    screening_status: str,
    candidate_version: str,
    incumbent_version: str | None,
    approver: str,
    exact_candidate_smoke_passed: bool,
    rollback_ready: bool,
) -> dict[str, Any]:
    """Evaluate deterministic owner approval rules without mutating live serving."""
    checks = {
        "screening_accepted": screening_status == "accepted",
        "exact_candidate_smoke_passed": bool(exact_candidate_smoke_passed),
        "rollback_ready": True if not incumbent_version else bool(rollback_ready),
    }
    decision = "approve" if all(checks.values()) else "reject"
    return {
        "decision": decision,
        "candidate_version": candidate_version,
        "incumbent_version": incumbent_version,
        "approver": approver,
        "checks": checks,
        "changes_serving_selection": False,
        "note": "Approval is recorded in PROMOTION_DECISION; it is not serving activation.",
    }


def record_promotion_decision(
    session,
    *,
    run_id: str,
    candidate_version: str,
    incumbent_version: str | None,
    screening_status: str,
    exact_candidate_smoke_passed: bool,
    rollback_ready: bool,
    approver: str | None = None,
    project: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Evaluate and persist an accountable owner decision in CONTROL.PROMOTION_DECISION via Snowpark pushdown."""
    config = project or load_project()
    database = config["snowflake"]["database"]
    control_schema = config["snowflake"]["schemas"]["control"]
    effective_approver = approver or session.get_current_role().strip('"')

    result = decide_approval(
        screening_status=screening_status,
        candidate_version=candidate_version,
        incumbent_version=incumbent_version,
        approver=effective_approver,
        exact_candidate_smoke_passed=exact_candidate_smoke_passed,
        rollback_ready=rollback_ready,
    )
    decision_id = f"DEC_{uuid.uuid4().hex[:10].upper()}"
    result["decision_id"] = decision_id
    result["run_id"] = run_id

    checks_json = json.dumps(result["checks"], sort_keys=True)
    decision_row_df = session.range(1).select(
        F.lit(decision_id).alias("DECISION_ID"),
        F.lit(run_id).alias("RUN_ID"),
        F.lit(candidate_version).alias("CANDIDATE_VERSION"),
        F.lit(incumbent_version).cast("STRING").alias("INCUMBENT_VERSION"),
        F.lit(result["decision"]).alias("DECISION"),
        F.parse_json(F.lit(checks_json)).alias("CHECKS"),
        F.current_role().alias("DECIDED_BY"),
        F.current_timestamp().alias("DECIDED_AT"),
    )
    decision_row_df.write.mode("append").save_as_table(
        f"{database}.{control_schema}.PROMOTION_DECISION"
    )
    return result


def activate_serving(
    session,
    *,
    candidate_version: str,
    decision_id: str,
    mode: str = "BATCH",
    candidate_weight: int = 100,
    project: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Invoke the owner's-rights CONTROL.ACTIVATE_SERVING procedure (BATCH, SHADOW, or SPLIT)."""
    config = project or load_project()
    database = config["snowflake"]["database"]
    control_schema = config["snowflake"]["schemas"]["control"]

    status_message = session.call(
        f"{database}.{control_schema}.ACTIVATE_SERVING",
        candidate_version,
        decision_id,
        mode.upper(),
        int(candidate_weight),
    )
    return {
        "status_message": status_message,
        "activated": str(status_message).startswith("activated"),
        "candidate_version": candidate_version,
        "decision_id": decision_id,
        "mode": mode.upper(),
        "candidate_weight": int(candidate_weight),
    }


def recover_serving(
    session,
    *,
    environment_name: str = "PROD",
    project: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Invoke the owner's-rights CONTROL.RECOVER_SERVING procedure to restore the prior selection."""
    config = project or load_project()
    database = config["snowflake"]["database"]
    control_schema = config["snowflake"]["schemas"]["control"]

    status_message = session.call(
        f"{database}.{control_schema}.RECOVER_SERVING",
        environment_name,
    )
    return {
        "status_message": status_message,
        "recovered": str(status_message).startswith("recovered"),
        "environment": environment_name,
    }
