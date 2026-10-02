import unittest
from pathlib import Path

import yaml


PROJECT_DIR = Path(__file__).resolve().parents[1]


def load_yaml(relative_path: str) -> dict:
    return yaml.safe_load((PROJECT_DIR / relative_path).read_text())


class ControlContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.project = load_yaml("project.yaml")
        self.environments = load_yaml("config/environments.yaml")
        self.workflow = load_yaml("config/workflow.yaml")
        self.control_sql = (
            PROJECT_DIR / "deployment" / "04_control_contracts.sql"
        ).read_text()
        self.verify_sql = (
            PROJECT_DIR / "deployment" / "03_verify_data.sql"
        ).read_text()

    def test_project_points_at_separately_versioned_contracts(self) -> None:
        self.assertEqual(
            self.project["contracts"]["environments"],
            "config/environments.yaml",
        )
        self.assertEqual(
            self.project["contracts"]["workflow"],
            "config/workflow.yaml",
        )

    def test_test_schema_is_labelled_pre_prod(self) -> None:
        test_env = self.environments["environments"]["TEST"]
        self.assertEqual(test_env["presentation_name"], "Pre-Prod")
        self.assertFalse(test_env["may_approve_future_prod_model"])
        self.assertFalse(test_env["may_change_live_serving"])

    def test_write_paths_keep_run_evidence_off_approval_tables(self) -> None:
        writes = self.environments["write_paths"]
        self.assertEqual(writes["pipeline_attempt"]["writer_roles"], ["service"])
        self.assertEqual(writes["promotion_decision"]["writer_roles"], ["prod_owner"])
        self.assertEqual(writes["serving_selection"]["writer_roles"], ["prod_owner"])
        self.assertNotIn("service", writes["promotion_decision"]["writer_roles"])
        self.assertNotIn("service", writes["serving_selection"]["writer_roles"])

    def test_workflow_contract_freezes_notebook_handoff(self) -> None:
        self.assertEqual(self.workflow["contract_id"], "CREDIT_DEFAULT_WORKFLOW_V01")
        self.assertEqual(self.workflow["model"]["name"], "CREDIT_DEFAULT_EARLY_WARNING")
        self.assertEqual(
            self.workflow["model"]["experiment_name"],
            "CREDIT_DEFAULT_DEVELOPMENT",
        )
        self.assertEqual(self.workflow["temporal_policy"]["development_cutoff"], "2025-07-01")
        self.assertEqual(self.workflow["feature_inventory"]["version"], "V01")
        self.assertEqual(len(self.workflow["feature_inventory"]["views"]), 6)
        self.assertEqual(
            self.workflow["features"]["categorical"],
            ["PRODUCT_CODE", "ORIGINATION_CHANNEL"],
        )
        self.assertEqual(self.workflow["estimator"]["family"], "HIST")
        self.assertFalse(self.workflow["unattended_replays_hpo"])
        self.assertEqual(self.workflow["screening"]["minimum_roc_auc"], 0.72)
        self.assertEqual(
            self.workflow["screening"]["accepted_does_not_mean"],
            "live-serving",
        )
        self.assertTrue(
            all(view["demo_developed"] for view in self.workflow["feature_inventory"]["views"])
        )

    def test_control_sql_separates_write_grants(self) -> None:
        self.assertIn("CREATE TABLE IF NOT EXISTS SOURCE_RELEASE", self.control_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS PIPELINE_ATTEMPT", self.control_sql)
        self.assertIn("CREATE TABLE IF NOT EXISTS SERVING_SELECTION", self.control_sql)
        self.assertIn("GRANT CREATE CODE BUNDLE", self.control_sql)
        self.assertIn(
            "REVOKE INSERT, UPDATE ON TABLE {{DATABASE}}.{{CONTROL_SCHEMA}}.PROMOTION_DECISION\n"
            "  FROM ROLE {{SERVICE_ROLE}}",
            self.control_sql,
        )
        self.assertIn(
            "REVOKE INSERT, UPDATE ON TABLE {{DATABASE}}.{{CONTROL_SCHEMA}}.SERVING_SELECTION\n"
            "  FROM ROLE {{SERVICE_ROLE}}",
            self.control_sql,
        )
        self.assertIn("TEST means Pre-Prod", self.control_sql)

    def test_phase_one_gate_stays_scoped_to_original_tables(self) -> None:
        self.assertIn("EXPECTED_PROJECT_TABLES', COUNT(*) = 12", self.verify_sql)
        self.assertNotIn("SOURCE_RELEASE", self.verify_sql)
        self.assertNotIn("PIPELINE_ATTEMPT", self.verify_sql)
        self.assertNotIn("SERVING_SELECTION", self.verify_sql)


if __name__ == "__main__":
    unittest.main()
