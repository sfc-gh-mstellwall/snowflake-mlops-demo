from __future__ import annotations

from math import isnan
from typing import Any, Callable, Iterable, Mapping


SCREENING_ACCEPTED = "accepted"
SCREENING_REJECTED = "rejected"
SCREENING_FAILED = "failed"


def screening_status(all_gates_passed: bool) -> str:
    return SCREENING_ACCEPTED if all_gates_passed else SCREENING_REJECTED


def _unique_values(rows: Iterable[Mapping[str, Any]], column: str) -> list[Any]:
    values = []
    seen = set()
    for row in rows:
        value = row.get(column)
        if value is None or (isinstance(value, float) and isnan(value)):
            continue
        if value not in seen:
            seen.add(value)
            values.append(value)
    return values


def segment_support_rows(
    scores: Iterable[Mapping[str, Any]],
    validation: Iterable[Mapping[str, Any]],
    *,
    target_column: str,
    categorical_features: list[str],
    segment_support: Mapping[str, int],
    minimum_segment_roc_auc: float,
    score_column: str = "PROBABILITY",
    roc_auc_fn: Callable[[list[Any], list[Any]], float],
) -> list[dict[str, Any]]:
    score_rows = list(scores)
    validation_rows = list(validation)
    rows: list[dict[str, Any]] = []
    for segment in categorical_features:
        expected_values = sorted(
            set(_unique_values(validation_rows, segment))
            | set(_unique_values(score_rows, segment)),
            key=str,
        )
        validation_values = set(_unique_values(validation_rows, segment))
        for value in expected_values:
            cohort = [row for row in score_rows if row.get(segment) == value]
            labels = [row[target_column] for row in cohort]
            probabilities = [row[score_column] for row in cohort]
            positives = int(sum(labels))
            negatives = len(cohort) - positives
            sufficient = (
                len(cohort) >= segment_support["minimum_observations"]
                and positives >= segment_support["minimum_positives"]
                and negatives >= segment_support["minimum_negatives"]
            )
            score = (
                float(roc_auc_fn(labels, probabilities))
                if positives and negatives
                else float("nan")
            )
            rows.append(
                {
                    "SEGMENT": segment,
                    "VALUE": value,
                    "PRESENT_IN_VALIDATION": value in validation_values,
                    "PRESENT_IN_HELD_OUT": len(cohort) > 0,
                    "OBSERVATIONS": len(cohort),
                    "POSITIVES": positives,
                    "NEGATIVES": negatives,
                    "ROC_AUC": score,
                    "SUFFICIENT_SUPPORT": sufficient,
                    "MEETS_FLOOR": sufficient and score >= minimum_segment_roc_auc,
                }
            )
    return rows


def screening_gate_table(
    metrics: Mapping[str, float],
    segment_table: Iterable[Mapping[str, Any]],
    gates: Mapping[str, Any],
) -> list[dict[str, Any]]:
    segments = list(segment_table)
    unsupported_segment_count = sum(
        1 for row in segments if not row["SUFFICIENT_SUPPORT"]
    )
    supported = [row for row in segments if row["SUFFICIENT_SUPPORT"]]
    segment_scores = [float(row["ROC_AUC"]) for row in supported]
    segment_floor_observed = min(segment_scores) if segment_scores else float("nan")
    segment_floor_pass = bool(
        supported and all(row["MEETS_FLOOR"] for row in supported)
    )
    return [
        {
            "CHECK": "ROC AUC",
            "OBSERVED": metrics["roc_auc"],
            "THRESHOLD": gates["minimum_roc_auc"],
            "PASS": metrics["roc_auc"] >= gates["minimum_roc_auc"],
        },
        {
            "CHECK": "Average precision",
            "OBSERVED": metrics["average_precision"],
            "THRESHOLD": gates["minimum_average_precision"],
            "PASS": metrics["average_precision"] >= gates["minimum_average_precision"],
        },
        {
            "CHECK": "Brier score (maximum)",
            "OBSERVED": metrics["brier_score"],
            "THRESHOLD": gates["maximum_brier_score"],
            "PASS": metrics["brier_score"] <= gates["maximum_brier_score"],
        },
        {
            "CHECK": "All required segments have support",
            "OBSERVED": unsupported_segment_count,
            "THRESHOLD": 0,
            "PASS": unsupported_segment_count == 0,
        },
        {
            "CHECK": "Supported segment ROC AUC floor",
            "OBSERVED": segment_floor_observed,
            "THRESHOLD": gates["minimum_segment_roc_auc"],
            "PASS": segment_floor_pass,
        },
    ]


def decide_screening(gate_table: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    gates = list(gate_table)
    passed = all(row["PASS"] for row in gates)
    return {
        "status": screening_status(passed),
        "gates": gates,
        "changes_live_serving": False,
    }
