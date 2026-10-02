from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Mapping

import yaml


PROJECT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_PROJECT_PATH = PROJECT_DIR / "project.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a mapping")
    return payload


def load_project(path: Path | None = None) -> dict[str, Any]:
    return _load_yaml(path or DEFAULT_PROJECT_PATH)


def load_environment_map(project: Mapping[str, Any] | None = None) -> dict[str, Any]:
    config = project or load_project()
    return _load_yaml(PROJECT_DIR / config["contracts"]["environments"])


def load_workflow_contract(project: Mapping[str, Any] | None = None) -> dict[str, Any]:
    config = project or load_project()
    return _load_yaml(PROJECT_DIR / config["contracts"]["workflow"])


def resolve_environment(name: str, project: Mapping[str, Any] | None = None) -> dict[str, Any]:
    mapping = load_environment_map(project)
    try:
        environment = mapping["environments"][name]
    except KeyError as error:
        raise KeyError(f"Unknown environment {name!r}") from error
    resolved = dict(environment)
    resolved["name"] = name
    resolved["presentation_name"] = environment.get(
        "presentation_name",
        "Pre-Prod" if name == "TEST" else name.title(),
    )
    return resolved


def expected_feature_columns(contract: Mapping[str, Any]) -> list[str]:
    features = contract["features"]
    return list(features["numeric"]) + list(features["categorical"])


def expected_feature_views(contract: Mapping[str, Any]) -> list[tuple[str, str]]:
    inventory = contract["feature_inventory"]
    version = inventory["version"]
    return [(view["name"], version) for view in inventory["views"]]


def validate_feature_columns(
    available_columns: Iterable[str],
    contract: Mapping[str, Any] | None = None,
) -> list[str]:
    expected = expected_feature_columns(contract or load_workflow_contract())
    missing = sorted(set(expected) - set(available_columns))
    if missing:
        raise ValueError(f"Dataset is missing expected features: {missing}")
    return expected
