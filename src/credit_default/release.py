from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from snowflake.snowpark import functions as F

# Load project.yaml and config/environments.yaml via contracts.py so each logical
# environment resolves its dedicated Feature Store, Dataset, Model, and Bundle schemas.
from .contracts import load_project, lookup_dotted, resolve_environment


def resolve_binding(
    environment_name: str,
    project: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    config = project or load_project()
    environment = resolve_environment(environment_name, config)
    database = config["snowflake"]["database"]
    schema_ref = environment["schema_ref"]
    schema = lookup_dotted(config, schema_ref)
    binding = {
        "environment": environment["name"],
        "presentation_environment": environment["presentation_name"],
        "database": database,
        "schema": schema,
        "feature_store_schema": environment["feature_store_schema"],
        "experiment_schema": lookup_dotted(config, environment["experiment_schema_ref"]),
        "dataset_schema": lookup_dotted(config, environment["dataset_schema_ref"]),
        "model_schema": lookup_dotted(config, environment["model_schema_ref"]),
        "bundle_schema": lookup_dotted(config, environment["bundle_schema_ref"]),
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
    """Insert an immutable reviewed source release into CONTROL.SOURCE_RELEASE via Snowpark pushdown."""
    config = project or load_project()
    database = config["snowflake"]["database"]
    control_schema = config["snowflake"]["schemas"]["control"]

    release_row_df = session.range(1).select(
        F.lit(release_id).alias("RELEASE_ID"),
        F.lit(source_commit).alias("SOURCE_COMMIT"),
        F.lit(payload_digest).alias("PAYLOAD_DIGEST"),
        F.lit(manifest_digest).alias("MANIFEST_DIGEST"),
        F.lit(specification_digest).alias("SPECIFICATION_DIGEST"),
        F.lit(runtime_contract).alias("RUNTIME_CONTRACT"),
        F.lit(f"{release_id}:{source_commit}").alias("APPROVED_SOURCE_IDENTITY"),
        F.current_role().alias("CREATED_BY"),
        F.current_timestamp().alias("CREATED_AT"),
    )
    release_row_df.write.mode("append").save_as_table(
        f"{database}.{control_schema}.SOURCE_RELEASE"
    )
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
    """Record a release-specific Code Bundle deployment in CONTROL.ENVIRONMENT_DEPLOYMENT via Snowpark pushdown."""
    config = project or load_project()
    binding = resolve_binding(environment_name, config)
    database = binding["database"]
    control_schema = config["snowflake"]["schemas"]["control"]
    clean_rel = "".join(c if c.isalnum() else "_" for c in release_id).upper()
    deployment_id = f"DEPLOY_{environment_name}_{clean_rel}"
    binding_digest = hashlib.sha256(
        json.dumps(binding, sort_keys=True).encode("utf-8")
    ).hexdigest()

    deployment_row_df = session.range(1).select(
        F.lit(deployment_id).alias("DEPLOYMENT_ID"),
        F.lit(release_id).alias("RELEASE_ID"),
        F.lit(environment_name).alias("ENVIRONMENT"),
        F.lit(binding_digest).alias("BINDING_DIGEST"),
        F.lit(database).alias("BUNDLE_DATABASE"),
        F.lit(binding["bundle_schema"]).alias("BUNDLE_SCHEMA"),
        F.lit(bundle_name).alias("BUNDLE_NAME"),
        F.current_role().alias("DEPLOYED_BY"),
        F.lit(pipeline_validation_status).alias("PIPELINE_VALIDATION_STATUS"),
        F.current_timestamp().alias("DEPLOYED_AT"),
    )
    deployment_row_df.write.mode("append").save_as_table(
        f"{database}.{control_schema}.ENVIRONMENT_DEPLOYMENT"
    )
    return {
        "deployment_id": deployment_id,
        "release_id": release_id,
        "environment": environment_name,
        "presentation_environment": binding["presentation_environment"],
        "bundle_schema": binding["bundle_schema"],
        "bundle_name": bundle_name,
        "pipeline_validation_status": pipeline_validation_status,
    }
