from __future__ import annotations

import argparse
import json
import sys
import uuid
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

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

    existing = session.sql(
        f"SHOW SERVICES LIKE '{service_short}' IN SCHEMA {database}.{binding['schema']}"
    ).collect()
    if not existing:
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
        held_out_ds.read.to_snowpark_dataframe()
        .select(feature_columns)
        .limit(5)
    )
    mv.run(
        smoke_sample,
        function_name="predict_proba",
        service_name=service_fqn,
    ).collect()

    deployment_id = f"SVC_DEP_{uuid.uuid4().hex[:10].upper()}"
    session.sql(
        f"""
        INSERT INTO {database}.{control_schema}.SERVICE_DEPLOYMENT (
            DEPLOYMENT_ID, ENVIRONMENT, MODEL_NAME, MODEL_VERSION,
            SERVICE_NAME, COMPUTE_POOL, AUTOCAPTURE_ENABLED,
            STATUS, DEPLOYED_BY, DEPLOYED_AT
        )
        SELECT ?, ?, ?, ?, ?, ?, TRUE, 'SMOKE_TESTED', CURRENT_ROLE(), CURRENT_TIMESTAMP()
        """,
        params=[
            deployment_id,
            args.environment,
            model_name,
            args.version,
            service_fqn,
            binding["compute_pool"],
        ],
    ).collect()

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
