from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

from snowflake.snowpark import functions as F

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

# Load project.yaml and config/workflow.yaml via credit_default.contracts so
# the SPCS service deployment binds to the environment's compute pool and model schema.
from credit_default.contracts import (  # noqa: E402
    expected_feature_columns,
    get_session,
    load_project,
    load_workflow_contract,
)
from credit_default.release import resolve_binding  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Idempotently deploy and smoke-test a candidate SPCS model service"
    )
    parser.add_argument("--environment", default="PROD", choices=["TEST", "PROD"])
    parser.add_argument("--version", required=True, help="Exact Model Registry version")
    parser.add_argument("--dataset-version", default="V01")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    from snowflake.ml.dataset import load_dataset
    from snowflake.ml.registry import Registry

    args = parse_args(argv)
    session = get_session()
    project = load_project()
    contract = load_workflow_contract(project)
    binding = resolve_binding(args.environment, project)

    database = binding["database"]
    control_schema = project["snowflake"]["schemas"]["control"]
    model_name = contract["model"]["name"]
    feature_columns = expected_feature_columns(contract)

    reg = Registry(
        session=session,
        database_name=database,
        schema_name=binding["model_schema"],
    )
    mv = reg.get_model(model_name).version(args.version)

    clean_ver = "".join(c if c.isalnum() else "_" for c in args.version).upper()
    service_short = f"CREDIT_DEFAULT_SVC_{clean_ver}"
    service_fqn = f"{database}.{binding['schema']}.{service_short}"

    existing_count = session.sql(
        f"SHOW SERVICES LIKE '{service_short}' IN SCHEMA {database}.{binding['schema']}"
    ).count()
    if existing_count == 0:
        mv.create_service(
            service_name=service_fqn,
            service_compute_pool=binding["compute_pool"],
            ingress_enabled=True,
            max_instances=1,
            autocapture=True,
        )

    held_out_ds = load_dataset(
        session,
        f"{database}.{binding['dataset_schema']}.{contract['datasets']['held_out']}",
        version=args.dataset_version,
    )
    smoke_sample = (
        held_out_ds.read.to_snowpark_dataframe(only_feature_cols=False)
        .select(feature_columns)
        .limit(5)
    )
    # Push down the smoke-test invocation against the SPCS service without collecting rows to Python.
    smoke_count = mv.run(
        smoke_sample,
        function_name="predict_proba",
        service_name=service_fqn,
    ).count()
    if smoke_count == 0:
        raise RuntimeError(f"Smoke test returned 0 rows for service {service_fqn}")

    deployment_id = f"SVC_DEP_{uuid.uuid4().hex[:10].upper()}"
    deployment_row_df = session.range(1).select(
        F.lit(deployment_id).alias("DEPLOYMENT_ID"),
        F.lit(args.environment).alias("ENVIRONMENT"),
        F.lit(model_name).alias("MODEL_NAME"),
        F.lit(args.version).alias("MODEL_VERSION"),
        F.lit(service_fqn).alias("SERVICE_NAME"),
        F.lit(binding["compute_pool"]).alias("COMPUTE_POOL"),
        F.lit(True).alias("AUTOCAPTURE_ENABLED"),
        F.lit("SMOKE_TESTED").alias("STATUS"),
        F.current_role().alias("DEPLOYED_BY"),
        F.current_timestamp().alias("DEPLOYED_AT"),
    )
    deployment_row_df.write.mode("append").save_as_table(
        f"{database}.{control_schema}.SERVICE_DEPLOYMENT"
    )

    payload = {
        "deployment_id": deployment_id,
        "environment": args.environment,
        "model_name": model_name,
        "model_version": args.version,
        "service_name": service_fqn,
        "autocapture": True,
        "status": "SMOKE_TESTED",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
