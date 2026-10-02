from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from credit_default.contracts import (  # noqa: E402
    expected_feature_views,
    load_workflow_contract,
    resolve_environment,
    validate_feature_columns,
)
from credit_default.evidence import evidence_handoff  # noqa: E402
from credit_default.release import resolve_binding  # noqa: E402
from credit_default.training import estimator_specification  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unattended credit-default training")
    parser.add_argument("--environment", required=True, choices=["DEV", "TEST", "PROD"])
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--source-state", default="reviewed-release")
    return parser.parse_args(argv)


def planned_attempt(args: argparse.Namespace) -> dict:
    contract = load_workflow_contract()
    environment = resolve_environment(args.environment)
    binding = resolve_binding(args.environment)
    spec = estimator_specification(contract)
    if spec["replays_hpo"]:
        raise ValueError("Unattended training must not replay exploratory HPO")
    validate_feature_columns(
        contract["features"]["numeric"] + contract["features"]["categorical"],
        contract,
    )
    handoff = evidence_handoff(
        environment=environment,
        dataset_name=contract["datasets"]["development"],
        dataset_version=args.dataset_version,
        feature_views=expected_feature_views(contract),
        experiment_name=contract["model"]["experiment_name"],
        run_id="UNATTENDED_PENDING",
        model_name=contract["model"]["name"],
        model_version=None,
        screening_status="running",
        source_state=args.source_state,
    )
    return {
        "environment": environment["name"],
        "presentation_environment": environment["presentation_name"],
        "feature_store_schema": binding["feature_store_schema"],
        "release_id": args.release_id,
        "estimator": spec,
        "handoff": handoff,
        "changes_live_serving": False,
        "execute_from_notebook_cell": False,
    }


def main(argv: list[str] | None = None) -> int:
    result = planned_attempt(parse_args(argv))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
