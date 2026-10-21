from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from credit_default.contracts import get_session, load_project  # noqa: E402
from credit_default.release import pipeline_release_decision  # noqa: E402
from credit_default.training import train_and_register_candidate  # noqa: E402


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Unattended credit-default training entrypoint")
    parser.add_argument("--environment", required=True, choices=["DEV", "TEST", "PROD"])
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--dataset-version", required=True)
    parser.add_argument("--source-state", default="reviewed-release")
    parser.add_argument("--bundle-name", default=None)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    session = get_session()
    project = load_project()
    database = project["snowflake"]["database"]
    control_schema = project["snowflake"]["schemas"]["control"]

    result = train_and_register_candidate(
        session,
        environment_name=args.environment,
        release_id=args.release_id,
        dataset_version=args.dataset_version,
        source_state=args.source_state,
        bundle_name=args.bundle_name,
    )

    release_gate = pipeline_release_decision(
        environment_name=args.environment,
        checks_passed=(result["screening_status"] == "accepted"),
        project=project,
    )
    result["pipeline_release_decision"] = release_gate

    if args.environment == "TEST":
        session.sql(
            f"""
            UPDATE {database}.{control_schema}.ENVIRONMENT_DEPLOYMENT
            SET PIPELINE_VALIDATION_STATUS = ?
            WHERE RELEASE_ID = ? AND ENVIRONMENT = 'TEST'
            """,
            params=[release_gate["decision"], args.release_id],
        ).collect()

    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["screening_status"] == "accepted" else 1


if __name__ == "__main__":
    raise SystemExit(main())
