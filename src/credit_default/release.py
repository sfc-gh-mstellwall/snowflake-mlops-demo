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
