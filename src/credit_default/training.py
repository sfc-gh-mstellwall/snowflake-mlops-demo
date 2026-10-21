from __future__ import annotations

import json
import uuid
from typing import Any, Mapping

from .contracts import (
    expected_feature_columns,
    expected_feature_views,
    load_project,
    load_workflow_contract,
    resolve_environment,
    validate_feature_columns,
)
from .evaluation import evaluate_candidate
from .evidence import evidence_handoff
from .features import ensure_environment_datasets
from .release import resolve_binding


def estimator_specification(contract: Mapping[str, Any]) -> dict[str, Any]:
    estimator = contract["estimator"]
    return {
        "family": estimator["family"],
        "classifier": estimator["classifier"],
        "parameters": dict(estimator["parameters"]),
        "seed": contract["model"]["seed"],
        "numeric_features": list(contract["features"]["numeric"]),
        "categorical_features": list(contract["features"]["categorical"]),
        "replays_hpo": bool(contract.get("unattended_replays_hpo", False)),
    }


def pipeline_params(spec: Mapping[str, Any]) -> dict[str, Any]:
    return {
        f"classifier__{name}": value for name, value in spec["parameters"].items()
    }


def build_training_pipeline(contract: Mapping[str, Any] | None = None):
    """Build the frozen scikit-learn preprocessing and HistGradientBoosting pipeline."""
    from sklearn.compose import ColumnTransformer
    from sklearn.ensemble import HistGradientBoostingClassifier
    from sklearn.impute import SimpleImputer
    from sklearn.pipeline import Pipeline
    from sklearn.preprocessing import OneHotEncoder, StandardScaler

    resolved_contract = contract or load_workflow_contract()
    spec = estimator_specification(resolved_contract)
    preprocessor = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                spec["numeric_features"],
            ),
            (
                "categorical",
                Pipeline(
                    [
                        ("imputer", SimpleImputer(strategy="most_frequent")),
                        (
                            "encoder",
                            OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                        ),
                    ]
                ),
                spec["categorical_features"],
            ),
        ],
        remainder="drop",
    )
    classifier = HistGradientBoostingClassifier(
        random_state=int(spec["seed"]),
        **spec["parameters"],
    )
    return Pipeline(
        [
            ("preprocessor", preprocessor),
            ("classifier", classifier),
        ]
    )


def train_and_register_candidate(
    session,
    *,
    environment_name: str,
    release_id: str,
    dataset_version: str,
    source_state: str = "reviewed-release",
    bundle_name: str | None = None,
) -> dict[str, Any]:
    """Train the frozen candidate in the target environment, log to Experiment & Registry, and record evidence."""
    from snowflake.ml.experiment import ExperimentTracking
    from snowflake.ml.model import task as ml_task

    project = load_project()
    contract = load_workflow_contract(project)
    environment = resolve_environment(environment_name, project)
    binding = resolve_binding(environment_name, project)
    spec = estimator_specification(contract)
    if spec["replays_hpo"]:
        raise ValueError("Unattended training must not replay exploratory HPO")

    database_name = binding["database"]
    raw_schema = project["snowflake"]["schemas"]["raw"]
    control_schema = project["snowflake"]["schemas"]["control"]
    feature_columns = expected_feature_columns(contract)
    target_col = contract["model"]["target_column"]
    temporal = contract["temporal_policy"]

    datasets = ensure_environment_datasets(
        session,
        database_name=database_name,
        raw_schema=raw_schema,
        dataset_schema=binding["dataset_schema"],
        feature_store_schema=binding["feature_store_schema"],
        warehouse_name=binding["warehouse"],
        dataset_version=dataset_version,
        development_cutoff=str(temporal["development_cutoff"]),
        refit_cutoff=str(temporal["refit_cutoff"]),
        holdout_cutoff=str(temporal["holdout_cutoff"]),
    )

    refit_sp_df = datasets["refit"].read.to_snowpark_dataframe()
    held_out_sp_df = datasets["held_out"].read.to_snowpark_dataframe()
    validation_sp_df = datasets["validation"].read.to_snowpark_dataframe()

    validate_feature_columns(refit_sp_df.columns, contract)
    training_sample = refit_sp_df.select(feature_columns).limit(50)

    refit_pdf = refit_sp_df.select(feature_columns + [target_col]).to_pandas()
    held_out_pdf = held_out_sp_df.select(feature_columns + [target_col]).to_pandas()
    validation_pdf = validation_sp_df.select(list(contract["features"]["categorical"])).to_pandas()

    pipeline = build_training_pipeline(contract)
    pipeline.fit(refit_pdf[feature_columns], refit_pdf[target_col].astype(int))
    probabilities = pipeline.predict_proba(held_out_pdf[feature_columns])[:, 1]
    eval_result = evaluate_candidate(held_out_pdf, validation_pdf, probabilities, contract)
    metrics = eval_result["metrics"]
    screening_status = eval_result["screening"]["status"]

    clean_rel = "".join(c if c.isalnum() else "_" for c in release_id).upper()
    version_name = f"CANDIDATE_{environment_name}_{clean_rel}"
    run_id = f"RUN_{environment_name}_{clean_rel}_{uuid.uuid4().hex[:6].upper()}"
    attempt_id = f"ATT_{uuid.uuid4().hex[:10].upper()}"

    exp = ExperimentTracking(
        session=session,
        database_name=database_name,
        schema_name=binding["experiment_schema"],
    )
    exp.set_experiment(contract["model"]["experiment_name"])
    with exp.start_run(run_id):
        exp.log_params(
            {
                "environment": environment_name,
                "release_id": release_id,
                "dataset_version": dataset_version,
                "feature_store_schema": binding["feature_store_schema"],
                "estimator_family": spec["family"],
                **{k: str(v) for k, v in spec["parameters"].items()},
            }
        )
        exp.log_metrics(
            {
                "held_out_roc_auc": metrics["roc_auc"],
                "held_out_average_precision": metrics["average_precision"],
                "held_out_brier_score": metrics["brier_score"],
                "screening_passed": 1.0 if screening_status == "accepted" else 0.0,
            }
        )
        exp.log_model(
            model=pipeline,
            model_name=contract["model"]["name"],
            version_name=version_name,
            sample_input_data=training_sample,
            task=ml_task.Task.TABULAR_BINARY_CLASSIFICATION,
            target_platforms=list(contract["model"]["target_platforms"]),
            options={
                "relax_version": False,
                "target_methods": ["predict", "predict_proba"],
            },
            comment=f"Unattended candidate for {environment_name} from release {release_id}",
        )

    feature_contract_str = ",".join(
        f"{name}@{ver}" for name, ver in expected_feature_views(contract)
    )
    handoff = evidence_handoff(
        environment=environment,
        dataset_name=contract["datasets"]["refit"],
        dataset_version=dataset_version,
        feature_views=expected_feature_views(contract),
        experiment_name=contract["model"]["experiment_name"],
        run_id=run_id,
        model_name=contract["model"]["name"],
        model_version=version_name,
        screening_status=screening_status,
        source_state=source_state,
    )

    metrics_json = json.dumps(metrics, sort_keys=True)
    evidence_json = json.dumps(
        {
            "handoff": handoff,
            "gates": eval_result["gate_table"],
        },
        sort_keys=True,
    )

    session.sql(
        f"""
        INSERT INTO {database_name}.{control_schema}.PIPELINE_ATTEMPT (
            ATTEMPT_ID, RUN_ID, RELEASE_ID, DEPLOYMENT_ID, ENVIRONMENT,
            EXECUTION_IDENTITY, BUNDLE_NAME, BUNDLE_QUERY_ID,
            DATASET_NAME, DATASET_VERSION, FEATURE_CONTRACT,
            MODEL_DATABASE, MODEL_SCHEMA, MODEL_NAME, MODEL_VERSION,
            METRICS, EVIDENCE, STATUS, FAILURE_DETAIL, STARTED_AT, COMPLETED_AT
        )
        SELECT
            ?, ?, ?, ?, ?,
            CURRENT_ROLE(), ?, LAST_QUERY_ID(),
            ?, ?, ?,
            ?, ?, ?, ?,
            PARSE_JSON(?), PARSE_JSON(?), ?, NULL, CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
        """,
        params=[
            attempt_id,
            run_id,
            release_id,
            f"DEPLOY_{environment_name}_{clean_rel}",
            environment_name,
            bundle_name or f"CRISK_DEMO_TRAIN_{clean_rel}",
            contract["datasets"]["refit"],
            dataset_version,
            feature_contract_str,
            database_name,
            binding["model_schema"],
            contract["model"]["name"],
            version_name,
            metrics_json,
            evidence_json,
            screening_status,
        ],
    ).collect()

    session.sql(
        f"""
        INSERT INTO {database_name}.{control_schema}.PIPELINE_RUN (
            RUN_ID, RELEASE_ID, ENVIRONMENT, STATUS, MODEL_NAME, MODEL_VERSION,
            SOURCE_COMMIT, METRICS, DECISION_EVIDENCE, STARTED_AT, COMPLETED_AT
        )
        SELECT
            ?, ?, ?, ?, ?, ?,
            ?, PARSE_JSON(?), PARSE_JSON(?), CURRENT_TIMESTAMP(), CURRENT_TIMESTAMP()
        """,
        params=[
            run_id,
            release_id,
            environment_name,
            screening_status,
            contract["model"]["name"],
            version_name,
            source_state,
            metrics_json,
            evidence_json,
        ],
    ).collect()

    return {
        "attempt_id": attempt_id,
        "run_id": run_id,
        "environment": environment_name,
        "presentation_environment": environment["presentation_name"],
        "feature_store_schema": binding["feature_store_schema"],
        "release_id": release_id,
        "model_name": contract["model"]["name"],
        "model_version": version_name,
        "metrics": metrics,
        "gate_table": eval_result["gate_table"],
        "screening_status": screening_status,
        "handoff": handoff,
        "changes_live_serving": False,
    }
