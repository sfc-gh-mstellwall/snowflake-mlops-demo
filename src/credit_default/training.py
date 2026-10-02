from __future__ import annotations

from typing import Any, Mapping


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
