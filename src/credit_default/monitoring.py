from __future__ import annotations

from datetime import date, timedelta
import uuid
from typing import Any, Iterable, Mapping

from snowflake.snowpark import functions as F

# Load project.yaml and config/workflow.yaml via contracts.py so batch scoring
# and delayed-outcome replay use the shared schemas, horizon dates, and screening gates.
from .contracts import (
    expected_feature_columns,
    expected_feature_views,
    load_project,
    load_workflow_contract,
)
from .features import ensure_environment_feature_store
from .release import resolve_binding


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
        and str(row["OBSERVATION_DATE"]) == str(prediction["OBSERVATION_DATE"])
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


def run_warehouse_batch_scoring(
    session,
    *,
    observation_date: str,
    release_id: str,
    environment_name: str = "PROD",
    model_alias: str = "PRODUCTION",
    threshold: float = 0.25,
    project: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Score RAW.SCORING_POPULATION on a warehouse using the aliased Registry model and write to CONTROL.PREDICTION_RECORD."""
    from snowflake.ml.registry import Registry

    config = project or load_project()
    contract = load_workflow_contract(config)
    binding = resolve_binding(environment_name, config)
    database = binding["database"]
    raw_schema = config["snowflake"]["schemas"]["raw"]
    control_schema = config["snowflake"]["schemas"]["control"]
    feature_columns = expected_feature_columns(contract)
    feature_contract_str = ",".join(
        f"{name}@{ver}" for name, ver in expected_feature_views(contract)
    )

    fs, feature_views = ensure_environment_feature_store(
        session,
        database_name=database,
        raw_schema=raw_schema,
        feature_store_schema=binding["feature_store_schema"],
        warehouse_name=binding["warehouse"],
    )

    # Single point of definition for the scoring population view and prediction ledger table.
    scoring_population = session.table(f"{database}.{raw_schema}.SCORING_POPULATION")
    prediction_table_fqn = f"{database}.{control_schema}.PREDICTION_RECORD"
    prediction_records = session.table(prediction_table_fqn)

    spine_df = (
        scoring_population.filter(
            F.col("OBSERVATION_DATE") == F.to_date(F.lit(observation_date))
        )
        .with_column("OBSERVATION_TS", F.to_timestamp_ntz("OBSERVATION_DATE"))
        .select("OBSERVATION_ID", "ACCOUNT_ID", "OBSERVATION_DATE", "OBSERVATION_TS")
    )
    scoring_features_df = fs.retrieve_feature_values(
        spine_df=spine_df,
        features=feature_views,
        spine_timestamp_col="OBSERVATION_TS",
        join_method="cte",
    )

    reg = Registry(
        session=session,
        database_name=database,
        schema_name=binding["model_schema"],
    )
    mv = reg.get_model(contract["model"]["name"]).version(model_alias)
    resolved_version = mv.version_name

    scored_df = mv.run(
        scoring_features_df.select(
            ["OBSERVATION_ID", "ACCOUNT_ID", "OBSERVATION_DATE"] + feature_columns
        ),
        function_name="predict_proba",
    )
    prob_cols = [
        c for c in scored_df.columns if c.upper().endswith("_1") or "PROBA_1" in c.upper()
    ]
    prob_col = prob_cols[0] if prob_cols else scored_df.columns[-1]

    batch_id = f"BATCH_{observation_date.replace('-', '')}_{uuid.uuid4().hex[:6].upper()}"
    records_df = scored_df.select(
        F.concat(F.lit(f"{batch_id}_"), F.col("OBSERVATION_ID")).alias("PREDICTION_ID"),
        F.col("ACCOUNT_ID"),
        F.col("OBSERVATION_DATE"),
        F.current_timestamp().alias("SCORED_AT"),
        F.lit(database).alias("MODEL_DATABASE"),
        F.lit(binding["model_schema"]).alias("MODEL_SCHEMA"),
        F.lit(contract["model"]["name"]).alias("MODEL_NAME"),
        F.lit(resolved_version).alias("MODEL_VERSION"),
        F.lit(release_id).alias("RELEASE_ID"),
        F.col(prob_col).cast("NUMBER(10,6)").alias("SCORE"),
        F.iff(F.col(prob_col) >= F.lit(threshold), 1, 0)
        .cast("NUMBER(1,0)")
        .alias("PREDICTION_CLASS"),
        F.lit(batch_id).alias("BATCH_ID"),
        F.lit(feature_contract_str).alias("FEATURE_CONTRACT"),
    )
    records_df.write.mode("append").save_as_table(prediction_table_fqn)
    row_count = prediction_records.filter(F.col("BATCH_ID") == batch_id).count()
    return {
        "batch_id": batch_id,
        "observation_date": observation_date,
        "model_name": contract["model"]["name"],
        "model_version": resolved_version,
        "rows_written": int(row_count),
        "feature_contract": feature_contract_str,
    }


def evaluate_delayed_outcomes(
    session,
    *,
    replay_date: str,
    model_version: str | None = None,
    drift_detected: bool | None = None,
    score_drift_threshold: float = 0.02,
    project: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Join CONTROL.PREDICTION_RECORD to RAW.ACCOUNT_OBSERVATION via Snowpark pushdown without treating pending labels as 0."""
    from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score

    config = project or load_project()
    contract = load_workflow_contract(config)
    database = config["snowflake"]["database"]
    raw_schema = config["snowflake"]["schemas"]["raw"]
    control_schema = config["snowflake"]["schemas"]["control"]
    as_of_horizon = str(config["data"]["as_of_date"])
    if date.fromisoformat(replay_date) > date.fromisoformat(as_of_horizon):
        raise ValueError(
            f"Replay date {replay_date} exceeds generated-data horizon {as_of_horizon}"
        )

    # Single point of definition for the prediction ledger and ground-truth observation tables.
    predictions_df = session.table(f"{database}.{control_schema}.PREDICTION_RECORD")
    observations_df = session.table(f"{database}.{raw_schema}.ACCOUNT_OBSERVATION").select(
        F.col("ACCOUNT_ID").alias("OBS_ACCOUNT_ID"),
        F.col("OBSERVATION_DATE").alias("OBS_DATE"),
        F.col("OUTCOME_FINALITY_DATE"),
        F.col("DEFAULT_WITHIN_90D"),
    )

    replay_date_expr = F.to_date(F.lit(replay_date))
    filtered_predictions = predictions_df.filter(
        F.col("OBSERVATION_DATE") <= replay_date_expr
    )
    if model_version:
        filtered_predictions = filtered_predictions.filter(
            F.col("MODEL_VERSION") == F.lit(model_version)
        )

    # Detect prediction score drift directly in Snowflake by comparing the earliest scored
    # cohort (baseline) against the most recent scored cohort up to replay_date.
    cohort_scores_pdf = (
        filtered_predictions.group_by("OBSERVATION_DATE")
        .agg(F.avg(F.col("SCORE").cast("FLOAT")).alias("AVG_SCORE"))
        .sort("OBSERVATION_DATE")
        .to_pandas()
    )
    baseline_avg_score: float | None = None
    latest_avg_score: float | None = None
    score_drift_delta: float | None = None
    if len(cohort_scores_pdf) > 0:
        baseline_avg_score = float(cohort_scores_pdf["AVG_SCORE"].iloc[0])
        latest_avg_score = float(cohort_scores_pdf["AVG_SCORE"].iloc[-1])
        score_drift_delta = abs(latest_avg_score - baseline_avg_score)
    computed_drift_detected = bool(
        score_drift_delta is not None and score_drift_delta >= score_drift_threshold
    )
    effective_drift_detected = (
        computed_drift_detected if drift_detected is None else bool(drift_detected)
    )

    joined_df = (
        filtered_predictions.join(
            observations_df,
            (filtered_predictions["ACCOUNT_ID"] == observations_df["OBS_ACCOUNT_ID"])
            & (filtered_predictions["OBSERVATION_DATE"] == observations_df["OBS_DATE"]),
            join_type="left",
        )
        .select(
            F.col("PREDICTION_ID"),
            F.col("ACCOUNT_ID"),
            F.col("OBSERVATION_DATE"),
            F.col("MODEL_VERSION"),
            F.col("SCORE").cast("FLOAT").alias("SCORE"),
            F.col("OUTCOME_FINALITY_DATE"),
            F.when(F.col("OBS_ACCOUNT_ID").is_null(), F.lit("unmatched"))
            .when(replay_date_expr < F.col("OUTCOME_FINALITY_DATE"), F.lit("pending"))
            .otherwise(F.lit("matched"))
            .alias("MATCH_STATUS"),
            F.when(F.col("OBS_ACCOUNT_ID").is_null(), F.lit(UNKNOWN_LABEL))
            .when(replay_date_expr < F.col("OUTCOME_FINALITY_DATE"), F.lit(PENDING_LABEL))
            .otherwise(F.lit(FINAL_LABEL))
            .alias("LABEL_STATUS"),
            F.when(
                F.col("OBS_ACCOUNT_ID").is_not_null()
                & (replay_date_expr >= F.col("OUTCOME_FINALITY_DATE")),
                F.col("DEFAULT_WITHIN_90D"),
            )
            .otherwise(F.lit(None))
            .alias("MATURED_DEFAULT_WITHIN_90D"),
        )
    )

    # Push down the coverage aggregation to Snowflake; only 1 summary row is returned.
    coverage_row = (
        joined_df.agg(
            F.count("*").alias("PREDICTIONS"),
            F.coalesce(
                F.sum(F.iff(F.col("LABEL_STATUS") == F.lit(FINAL_LABEL), 1, 0)), F.lit(0)
            ).alias("MATCHED_FINAL"),
            F.coalesce(
                F.sum(F.iff(F.col("LABEL_STATUS") == F.lit(PENDING_LABEL), 1, 0)), F.lit(0)
            ).alias("PENDING"),
            F.coalesce(
                F.sum(F.iff(F.col("MATCH_STATUS") == F.lit("unmatched"), 1, 0)), F.lit(0)
            ).alias("UNMATCHED"),
        )
        .to_pandas()
        .iloc[0]
    )
    coverage = {
        "predictions": int(coverage_row["PREDICTIONS"]),
        "matched_final": int(coverage_row["MATCHED_FINAL"]),
        "pending": int(coverage_row["PENDING"]),
        "unmatched": int(coverage_row["UNMATCHED"]),
    }

    metrics: dict[str, float | None] = {
        "roc_auc": None,
        "average_precision": None,
        "brier_score": None,
    }
    performance_degraded = False
    if coverage["matched_final"] > 0:
        # Filter in Snowflake so only matured final-label rows cross to scikit-learn.
        matured = (
            joined_df.filter(F.col("LABEL_STATUS") == F.lit(FINAL_LABEL))
            .select("SCORE", "MATURED_DEFAULT_WITHIN_90D")
            .to_pandas()
        )
        if len(matured) > 0 and matured["MATURED_DEFAULT_WITHIN_90D"].nunique() > 1:
            y_true = matured["MATURED_DEFAULT_WITHIN_90D"].astype(int).to_numpy()
            y_score = matured["SCORE"].astype(float).to_numpy()
            metrics = {
                "roc_auc": float(roc_auc_score(y_true, y_score)),
                "average_precision": float(average_precision_score(y_true, y_score)),
                "brier_score": float(brier_score_loss(y_true, y_score)),
            }
            gates = contract.get("screening") or contract["screening_gates"]
            performance_degraded = bool(
                metrics["roc_auc"] < float(gates["minimum_roc_auc"])
                or metrics["brier_score"] > float(gates["maximum_brier_score"])
            )

    rec = recommended_action(
        drift_detected=effective_drift_detected,
        performance_degraded=performance_degraded,
        coverage=coverage,
    )
    return {
        "replay_date": replay_date,
        "coverage": coverage,
        "baseline_avg_score": baseline_avg_score,
        "latest_avg_score": latest_avg_score,
        "score_drift_delta": score_drift_delta,
        "drift_detected": effective_drift_detected,
        "matured_metrics": metrics,
        "performance_degraded": performance_degraded,
        "recommendation": rec,
    }


def record_operational_action(
    session,
    *,
    model_version: str,
    action: str,
    rationale: str,
    prediction_id: str | None = None,
    project: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Record a reviewed monitoring action in CONTROL.OPERATIONAL_ACTION via Snowpark pushdown."""
    config = project or load_project()
    database = config["snowflake"]["database"]
    control_schema = config["snowflake"]["schemas"]["control"]
    action_id = f"ACT_{uuid.uuid4().hex[:10].upper()}"

    action_row_df = session.range(1).select(
        F.lit(action_id).alias("ACTION_ID"),
        F.lit(prediction_id).cast("STRING").alias("PREDICTION_ID"),
        F.lit(model_version).alias("MODEL_VERSION"),
        F.lit(action).alias("ACTION"),
        F.lit(rationale).alias("RATIONALE"),
        F.lit(False).alias("LAUNCHES_TRAINING"),
        F.lit(False).alias("CHANGES_INCUMBENT"),
        F.current_role().alias("RECORDED_BY"),
        F.current_timestamp().alias("RECORDED_AT"),
    )
    action_row_df.write.mode("append").save_as_table(
        f"{database}.{control_schema}.OPERATIONAL_ACTION"
    )
    return {
        "action_id": action_id,
        "model_version": model_version,
        "action": action,
        "rationale": rationale,
        "launches_training": False,
        "changes_incumbent": False,
    }
