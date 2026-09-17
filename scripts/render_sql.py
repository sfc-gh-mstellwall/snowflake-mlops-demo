from __future__ import annotations

import argparse
import re
import os
import sys
from datetime import date
from calendar import monthrange
from pathlib import Path
from typing import Any

import yaml


IDENTIFIER_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{2,62}$")
TOKEN_PATTERN = re.compile(r"\{\{([A-Z0-9_]+)\}\}")
#PROJECT_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = Path(os.getcwd()).parent
DEFAULT_CONFIG_PATH = PROJECT_DIR / "project.yaml"
DEFAULT_OUTPUT_DIR = PROJECT_DIR / "build"


def load_config(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file)
    if not isinstance(config, dict):
        raise ValueError("Configuration root must be a mapping")
    return config


def require_identifier(name: str, value: Any) -> str:
    text = str(value).upper()
    if not IDENTIFIER_PATTERN.fullmatch(text):
        raise ValueError(f"{name} must be a safe unquoted Snowflake identifier: {value!r}")
    return text


def build_tokens(config: dict[str, Any]) -> dict[str, str]:
    project = config["project"]
    snowflake = config["snowflake"]
    compute = config["compute"]
    data = config["data"]
    schemas = snowflake["schemas"]
    stages = snowflake["stages"]
    roles = snowflake["roles"]

    prefix = require_identifier("project.prefix", project["prefix"])
    if not prefix.endswith("_DEMO"):
        raise ValueError("project.prefix must end with '_DEMO' to protect non-demo objects")

    identifiers = {
        "PREFIX": prefix,
        "DATABASE": snowflake["database"],
        "WAREHOUSE": snowflake["warehouse"],
        "COMPUTE_POOL": snowflake["compute_pool"],
        "RAW_SCHEMA": schemas["raw"],
        "DEV_SCHEMA": schemas["dev"],
        "TEST_SCHEMA": schemas["test"],
        "PROD_SCHEMA": schemas["prod"],
        "CONTROL_SCHEMA": schemas["control"],
        "FEATURE_STORE_SCHEMA": schemas["feature_store"],
        "RELEASE_STAGE": stages["releases"],
        "JOB_STAGE": stages["jobs"],
        "DAG_STAGE": stages["dags"],
        "DEVELOPER_ROLE": roles["developer"],
        "ENGINEER_ROLE": roles["engineer"],
        "PROD_OWNER_ROLE": roles["prod_owner"],
        "SERVICE_ROLE": roles["service"],
        "WAREHOUSE_SIZE": compute["warehouse_size"],
        "POOL_INSTANCE_FAMILY": compute["pool_instance_family"],
    }
    tokens = {name: require_identifier(name, value) for name, value in identifiers.items()}
    destructive_names = {
        name: tokens[name]
        for name in (
            "DATABASE",
            "WAREHOUSE",
            "COMPUTE_POOL",
            "DEVELOPER_ROLE",
            "ENGINEER_ROLE",
            "PROD_OWNER_ROLE",
            "SERVICE_ROLE",
        )
    }
    for name, value in destructive_names.items():
        if not value.startswith(f"{prefix}_"):
            raise ValueError(f"{name} must start with the protected prefix '{prefix}_'")

    integer_tokens = {
        "WAREHOUSE_AUTO_SUSPEND": compute["warehouse_auto_suspend_seconds"],
        "POOL_MIN_NODES": compute["pool_min_nodes"],
        "POOL_MAX_NODES": compute["pool_max_nodes"],
        "POOL_AUTO_SUSPEND": compute["pool_auto_suspend_seconds"],
        "DATA_SEED": data["seed"],
        "ACCOUNT_COUNT": data["account_count"],
        "OBSERVATION_MONTHS": data["observation_months"],
        "OUTCOME_WINDOW_DAYS": data["outcome_window_days"],
    }
    for name, value in integer_tokens.items():
        if isinstance(value, bool) or not str(value).isdigit():
            raise ValueError(f"{name} must be a positive integer")
        number = int(value)
        if number < 1:
            raise ValueError(f"{name} must be positive")
        tokens[name] = str(number)

    date_tokens = {
        "FIRST_OBSERVATION_MONTH": data["first_observation_month"],
        "AS_OF_DATE": data["as_of_date"],
        "DRIFT_START_DATE": data["drift_start_date"],
    }
    for name, value in date_tokens.items():
        text = str(value)
        try:
            date.fromisoformat(text)
        except ValueError as error:
            raise ValueError(f"{name} must be a valid YYYY-MM-DD date") from error
        tokens[name] = text

    first_month = date.fromisoformat(tokens["FIRST_OBSERVATION_MONTH"])
    as_of_date = date.fromisoformat(tokens["AS_OF_DATE"])
    drift_date = date.fromisoformat(tokens["DRIFT_START_DATE"])
    if not first_month < drift_date <= as_of_date:
        raise ValueError("Dates must satisfy FIRST_OBSERVATION_MONTH < DRIFT_START_DATE <= AS_OF_DATE")
    if int(tokens["POOL_MIN_NODES"]) > int(tokens["POOL_MAX_NODES"]):
        raise ValueError("POOL_MIN_NODES cannot exceed POOL_MAX_NODES")

    if first_month.day != 1:
        raise ValueError("FIRST_OBSERVATION_MONTH must be the first day of a month")
    final_month_number = first_month.month - 1 + int(tokens["OBSERVATION_MONTHS"]) - 1
    final_observation = date(
        first_month.year + final_month_number // 12,
        final_month_number % 12 + 1,
        1,
    )
    if final_observation > as_of_date:
        raise ValueError("The final observation month cannot be after AS_OF_DATE")

    history_month_number = first_month.month - 1 - 12
    history_start = date(
        first_month.year + history_month_number // 12,
        history_month_number % 12 + 1,
        1,
    )
    tokens["FINANCIAL_SNAPSHOT_MONTHS"] = str(int(tokens["OBSERVATION_MONTHS"]) + 12)
    tokens["DAILY_HISTORY_DAYS"] = str((as_of_date - history_start).days + 1)

    return tokens


def render(template: str, tokens: dict[str, str]) -> str:
    referenced = set(TOKEN_PATTERN.findall(template))
    missing = referenced - tokens.keys()
    if missing:
        raise ValueError(f"Missing template tokens: {sorted(missing)}")
    return TOKEN_PATTERN.sub(lambda match: tokens[match.group(1)], template)


def render_project(config_path: Path, output_dir: Path) -> list[Path]:
    config = load_config(config_path)
    tokens = build_tokens(config)
    template_dir = PROJECT_DIR / "deployment"
    output_dir.mkdir(parents=True, exist_ok=True)

    template_names = {path.name for path in template_dir.glob("*.sql")}
    unexpected_sql = {path.name for path in output_dir.glob("*.sql")} - template_names
    if unexpected_sql:
        raise ValueError(
            "Output directory contains SQL without a matching template; "
            f"review and remove stale files before rendering: {sorted(unexpected_sql)}"
        )

    output_paths = []
    for template_path in sorted(template_dir.glob("*.sql")):
        output_path = output_dir / template_path.name
        output_path.write_text(render(template_path.read_text(), tokens), encoding="utf-8")
        output_paths.append(output_path)
    return output_paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Render portable Snowflake demo SQL")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args()

    for output_path in render_project(args.config, args.output_dir):
        print(f"Rendered {output_path}")


_in_notebook_kernel = "ipykernel" in sys.modules
if _in_notebook_kernel:
    for output_path in render_project(DEFAULT_CONFIG_PATH, DEFAULT_OUTPUT_DIR):
        print(f"Rendered {output_path}")
elif __name__ == "__main__":
    main()