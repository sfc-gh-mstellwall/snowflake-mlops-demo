from __future__ import annotations

from typing import Any, Mapping

from .contracts import load_project, resolve_environment


def _lookup(config: Mapping[str, Any], dotted_path: str) -> Any:
    current: Any = config
    for part in dotted_path.split("."):
        current = current[part]
    return current


def resolve_binding(
    environment_name: str,
    project: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    config = project or load_project()
    environment = resolve_environment(environment_name, config)
    database = config["snowflake"]["database"]
    schema_ref = environment["schema_ref"]
    schema = _lookup(config, schema_ref)
    binding = {
        "environment": environment["name"],
        "presentation_environment": environment["presentation_name"],
        "database": database,
        "schema": schema,
        "feature_store_schema": environment["feature_store_schema"],
        "experiment_schema": _lookup(config, environment["experiment_schema_ref"]),
        "dataset_schema": _lookup(config, environment["dataset_schema_ref"]),
        "model_schema": _lookup(config, environment["model_schema_ref"]),
        "bundle_schema": _lookup(config, environment["bundle_schema_ref"]),
        "warehouse": config["snowflake"]["warehouse"],
        "compute_pool": config["snowflake"]["compute_pool"],
        "may_approve_future_prod_model": bool(
            environment.get("may_approve_future_prod_model", False)
        ),
        "may_change_live_serving": bool(environment.get("may_change_live_serving", False)),
    }
    if binding["environment"] == "PROD" and binding["feature_store_schema"].startswith("DEV_"):
        raise ValueError("Prod training cannot bind to a DEV Feature Store")
    if (
        binding["environment"] == "TEST"
        and binding["may_approve_future_prod_model"]
    ):
        raise ValueError("Pre-Prod cannot approve a future Prod model")
    return binding


def pipeline_release_decision(
    *,
    environment_name: str,
    checks_passed: bool,
    project: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    binding = resolve_binding(environment_name, project)
    if environment_name == "TEST":
        decision = "approve_pipeline" if checks_passed else "reject_pipeline"
        model_approved = False
    else:
        decision = "record_only"
        model_approved = False
    return {
        "environment": binding["environment"],
        "presentation_environment": binding["presentation_environment"],
        "decision": decision,
        "pipeline_release_approved": decision == "approve_pipeline",
        "model_approved": model_approved,
        "serving_changed": False,
        "feature_store_schema": binding["feature_store_schema"],
    }


def record_source_release(
    session,
    *,
    release_id: str,
    source_commit: str,
    payload_digest: str,
    manifest_digest: str = "WORKFLOW_V01",
    specification_digest: str = "CODE_BUNDLE_V01",
    runtime_contract: str = "V2.9-CPU-PY3.11",
    project: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Insert an immutable reviewed source release into CONTROL.SOURCE_RELEASE."""
    config = project or load_project()
    database = config["snowflake"]["database"]
    control_schema = config["snowflake"]["schemas"]["control"]
    session.sql(
        f"""
        INSERT INTO {database}.{control_schema}.SOURCE_RELEASE (
            RELEASE_ID, SOURCE_COMMIT, PAYLOAD_DIGEST, MANIFEST_DIGEST,
            SPECIFICATION_DIGEST, RUNTIME_CONTRACT, APPROVED_SOURCE_IDENTITY,
            CREATED_BY, CREATED_AT
        )
        SELECT ?, ?, ?, ?, ?, ?, ?, CURRENT_ROLE(), CURRENT_TIMESTAMP()
        """,
        params=[
            release_id,
            source_commit,
            payload_digest,
            manifest_digest,
            specification_digest,
            runtime_contract,
            f"{release_id}:{source_commit}",
        ],
    ).collect()
    return {
        "release_id": release_id,
        "source_commit": source_commit,
        "payload_digest": payload_digest,
        "runtime_contract": runtime_contract,
    }


def record_environment_deployment(
    session,
    *,
    release_id: str,
    environment_name: str,
    bundle_name: str,
    pipeline_validation_status: str = "PENDING",
    project: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Record a release-specific Code Bundle deployment in CONTROL.ENVIRONMENT_DEPLOYMENT."""
    import hashlib
    import json

    config = project or load_project()
    binding = resolve_binding(environment_name, config)
    database = binding["database"]
    control_schema = config["snowflake"]["schemas"]["control"]
    clean_rel = "".join(c if c.isalnum() else "_" for c in release_id).upper()
    deployment_id = f"DEPLOY_{environment_name}_{clean_rel}"
    binding_digest = hashlib.sha256(
        json.dumps(binding, sort_keys=True).encode("utf-8")
    ).hexdigest()

    session.sql(
        f"""
        INSERT INTO {database}.{control_schema}.ENVIRONMENT_DEPLOYMENT (
            DEPLOYMENT_ID, RELEASE_ID, ENVIRONMENT, BINDING_DIGEST,
            BUNDLE_DATABASE, BUNDLE_SCHEMA, BUNDLE_NAME,
            DEPLOYED_BY, PIPELINE_VALIDATION_STATUS, DEPLOYED_AT
        )
        SELECT ?, ?, ?, ?, ?, ?, ?, CURRENT_ROLE(), ?, CURRENT_TIMESTAMP()
        """,
        params=[
            deployment_id,
            release_id,
            environment_name,
            binding_digest,
            database,
            binding["bundle_schema"],
            bundle_name,
            pipeline_validation_status,
        ],
    ).collect()
    return {
        "deployment_id": deployment_id,
        "release_id": release_id,
        "environment": environment_name,
        "presentation_environment": binding["presentation_environment"],
        "bundle_schema": binding["bundle_schema"],
        "bundle_name": bundle_name,
        "pipeline_validation_status": pipeline_validation_status,
    }

