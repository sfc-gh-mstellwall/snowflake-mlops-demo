import json
import sys
import unittest
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR / "src"))

from credit_default.contracts import (
    expected_feature_columns,
    expected_feature_views,
    load_workflow_contract,
    resolve_environment,
    validate_feature_columns,
)
from credit_default.evaluation import (
    decide_screening,
    screening_gate_table,
    segment_support_rows,
)
from credit_default.evidence import evidence_handoff
from credit_default.approval import activate_serving, decide_approval
from credit_default.release import pipeline_release_decision, resolve_binding
from credit_default.training import estimator_specification


class WorkflowExtractionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.contract = load_workflow_contract()
        notebook = json.loads(
            (PROJECT_DIR / "notebooks" / "03_credit_default_model_experiment.ipynb").read_text()
        )
        cls.notebook_code = "\n".join(
            "".join(cell.get("source", []))
            for cell in notebook["cells"]
            if cell["cell_type"] == "code"
        )

    def test_frozen_features_match_notebook_handoff(self) -> None:
        self.assertEqual(
            self.contract["features"]["categorical"],
            ["PRODUCT_CODE", "ORIGINATION_CHANNEL"],
        )
        for feature in expected_feature_columns(self.contract):
            self.assertIn(f'"{feature}"', self.notebook_code)
        for name, version in expected_feature_views(self.contract):
            self.assertIn(name, self.notebook_code)
            self.assertIn(f'feature_version = "{version}"', self.notebook_code)

    def test_missing_required_feature_fails_closed(self) -> None:
        available = expected_feature_columns(self.contract)[:-1]
        with self.assertRaisesRegex(ValueError, "missing expected features"):
            validate_feature_columns(available, self.contract)

    def test_unattended_spec_does_not_replay_hpo(self) -> None:
        spec = estimator_specification(self.contract)
        self.assertEqual(spec["family"], "HIST")
        self.assertFalse(spec["replays_hpo"])
        self.assertEqual(spec["parameters"]["max_leaf_nodes"], 15)

    def test_test_environment_is_pre_prod_and_cannot_approve_prod_model(self) -> None:
        environment = resolve_environment("TEST")
        binding = resolve_binding("TEST")
        self.assertEqual(environment["presentation_name"], "Pre-Prod")
        self.assertFalse(environment["may_approve_future_prod_model"])
        self.assertEqual(binding["feature_store_schema"], "TEST_FEATURE_STORE")
        self.assertNotEqual(binding["feature_store_schema"], "DEV_FEATURE_STORE")
        decision = pipeline_release_decision(
            environment_name="TEST",
            checks_passed=True,
        )
        self.assertTrue(decision["pipeline_release_approved"])
        self.assertFalse(decision["model_approved"])
        self.assertFalse(decision["serving_changed"])

    def test_prod_training_cannot_bind_dev_features(self) -> None:
        binding = resolve_binding("PROD")
        self.assertEqual(binding["feature_store_schema"], "PROD_FEATURE_STORE")
        self.assertFalse(binding["feature_store_schema"].startswith("DEV_"))

    def test_unsupported_segment_rejects_without_serving(self) -> None:
        scores = [
            {
                "PRODUCT_CODE": "REVOLVING_CREDIT",
                "ORIGINATION_CHANNEL": "DIGITAL",
                "DEFAULT_WITHIN_90D": label,
                "PROBABILITY": 0.8 if label else 0.2,
            }
            for label in [1, 0] * 5
        ]
        validation = list(scores)
        segments = segment_support_rows(
            scores,
            validation,
            target_column="DEFAULT_WITHIN_90D",
            categorical_features=["PRODUCT_CODE", "ORIGINATION_CHANNEL"],
            segment_support={
                "minimum_observations": 200,
                "minimum_positives": 20,
                "minimum_negatives": 20,
            },
            minimum_segment_roc_auc=0.62,
            roc_auc_fn=lambda labels, scores_: 0.9,
        )
        gates = screening_gate_table(
            {"roc_auc": 0.8, "average_precision": 0.3, "brier_score": 0.1},
            segments,
            self.contract["screening"],
        )
        decision = decide_screening(gates)
        self.assertEqual(decision["status"], "rejected")
        self.assertFalse(decision["changes_live_serving"])
        self.assertFalse(
            next(
                row["PASS"]
                for row in decision["gates"]
                if row["CHECK"] == "All required segments have support"
            )
        )

    def test_evidence_handoff_does_not_imply_approval(self) -> None:
        handoff = evidence_handoff(
            environment=resolve_environment("DEV"),
            dataset_name="CREDIT_DEVELOPMENT",
            dataset_version="D_TEST",
            feature_views=expected_feature_views(self.contract),
            experiment_name=self.contract["model"]["experiment_name"],
            run_id="FINAL_TEST",
            model_name=self.contract["model"]["name"],
            model_version="CANDIDATE_TEST",
            screening_status="accepted",
            source_state="dirty-interactive",
        )
        self.assertTrue(handoff["registration_complete"])
        self.assertFalse(handoff["approved"])
        self.assertFalse(handoff["serving_active"])
        self.assertEqual(handoff["source_state"], "dirty-interactive")

    def test_accepted_unapproved_candidate_cannot_serve(self) -> None:
        approval = decide_approval(
            screening_status="accepted",
            candidate_version="CANDIDATE_A",
            incumbent_version="CANDIDATE_INCUMBENT",
            approver="",
            exact_candidate_smoke_passed=True,
            rollback_ready=True,
        )
        approval["decision"] = "pending"
        with self.assertRaisesRegex(ValueError, "cannot change serving"):
            activate_serving(
                approval=approval,
                current_selection={"selection_id": "SEL_1"},
                actor="CRISK_DEMO_PROD_OWNER",
            )

    def test_rejection_does_not_change_incumbent(self) -> None:
        approval = decide_approval(
            screening_status="rejected",
            candidate_version="CANDIDATE_B",
            incumbent_version="CANDIDATE_INCUMBENT",
            approver="CRISK_DEMO_PROD_OWNER",
            exact_candidate_smoke_passed=True,
            rollback_ready=True,
        )
        self.assertEqual(approval["decision"], "reject")
        self.assertFalse(approval["changes_serving_selection"])
        self.assertEqual(approval["incumbent_version"], "CANDIDATE_INCUMBENT")


if __name__ == "__main__":
    unittest.main()
