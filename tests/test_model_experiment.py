import ast
import json
import re
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
NOTEBOOK_DIR = PROJECT_DIR / "notebooks"
NOTEBOOK_PATHS = {
    "exploration": NOTEBOOK_DIR / "01_credit_default_exploration.ipynb",
    "features": NOTEBOOK_DIR / "02_credit_default_feature_engineering.ipynb",
    "models": NOTEBOOK_DIR / "03_credit_default_model_experiment.ipynb",
}


def load_notebook(name):
    return json.loads(NOTEBOOK_PATHS[name].read_text())


def notebook_text(notebook, cell_type=None):
    return "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell_type is None or cell["cell_type"] == cell_type
    )


class NotebookStructureTests(unittest.TestCase):
    def test_all_notebooks_have_unique_ids_and_valid_python(self):
        for name, path in NOTEBOOK_PATHS.items():
            notebook = json.loads(path.read_text())
            cell_ids = [cell.get("id") for cell in notebook["cells"]]
            with self.subTest(notebook=name):
                self.assertEqual(notebook["nbformat"], 4)
                self.assertGreaterEqual(notebook["nbformat_minor"], 5)
                self.assertTrue(all(cell_ids))
                self.assertEqual(len(cell_ids), len(set(cell_ids)))
            for cell in notebook["cells"]:
                if cell["cell_type"] != "code":
                    continue
                source = "".join(cell.get("source", []))
                self.assertTrue(source.strip())
                if not source.lstrip().startswith("%%"):
                    ast.parse(source)

    def test_sql_cells_use_workspace_magic_and_never_rows_alias(self):
        sql_cell_count = 0
        for name in NOTEBOOK_PATHS:
            notebook = load_notebook(name)
            for cell in notebook["cells"]:
                if cell["cell_type"] != "code":
                    continue
                source = "".join(cell.get("source", []))
                stripped = source.lstrip()
                self.assertFalse(bool(re.match(r"(SELECT|WITH|SHOW|DESCRIBE|USE)\b", stripped, re.I)))
                self.assertIsNone(re.search(r"\bAS\s+ROWS\b", source, re.I))
                if not stripped.startswith("%%sql -r "):
                    continue
                sql_cell_count += 1
                variable_name = stripped.splitlines()[0].removeprefix("%%sql -r ").strip()
                metadata = cell.get("metadata", {})
                with self.subTest(notebook=name, variable=variable_name):
                    self.assertRegex(variable_name, r"^[a-z][a-z0-9_]+$")
                    self.assertEqual(metadata.get("language"), "sql")
                    self.assertEqual(metadata.get("name"), variable_name)
                    self.assertEqual(metadata.get("resultVariableName"), variable_name)
        self.assertGreaterEqual(sql_cell_count, 1)


class SourceExplorationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = notebook_text(load_notebook("exploration"))

    def test_starts_from_dimensions_and_facts(self):
        for object_name in (
            "DIM_CUSTOMER", "DIM_CREDIT_ACCOUNT", "FACT_ACCOUNT_DAILY_SNAPSHOT",
            "FACT_CUSTOMER_FINANCIAL_SNAPSHOT", "FACT_PAYMENT",
            "FACT_CUSTOMER_CONTACT", "FACT_ACCOUNT_EVENT", "FACT_DEFAULT_EVENT",
        ):
            self.assertIn(object_name, self.text)
        for prohibited in ("TRAINING_BASE", "ACCOUNT_SNAPSHOT", "ACCOUNT_MASTER"):
            self.assertNotIn(prohibited, self.text)

    def test_feature_hypotheses_follow_source_evidence(self):
        self.assertLess(self.text.index("FACT_ACCOUNT_DAILY_SNAPSHOT"), self.text.index("Provisional feature hypotheses"))
        for family in ("Account profile", "Balance and utilisation", "Payment behaviour", "Delinquency and contact"):
            self.assertIn(family, self.text)

    def test_every_fact_has_grain_missingness_and_relationship_checks(self):
        self.assertIn("fact_contracts", self.text)
        self.assertIn("DUPLICATE_GRAIN_KEYS", self.text)
        self.assertIn("ORPHAN_RECORDS", self.text)
        self.assertIn("NULL_COUNT", self.text)


class FeatureEngineeringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = load_notebook("features")
        cls.code = notebook_text(cls.notebook, "code")
        cls.markdown = notebook_text(cls.notebook, "markdown")

    def test_develops_six_reviewed_feature_views(self):
        for name in (
            "ACCOUNT_PROFILE_FV", "ACCOUNT_BALANCE_FV", "ACCOUNT_PAYMENT_FV",
            "ACCOUNT_CONTACT_FV", "ACCOUNT_DELINQUENCY_FV", "ACCOUNT_AGGREGATION_FV",
        ):
            self.assertIn(name, self.code)
        self.assertIn("attach_feature_desc", self.code)
        self.assertIn("range_between(-29, 0)", self.code)
        self.assertIn("range_between(-89, 0)", self.code)
        self.assertIn("range_between(-179, 0)", self.code)

    def test_implements_native_365_day_aggregation(self):
        self.assertIn('Feature.avg("DAILY_UTILISATION", "365d")', self.code)
        self.assertIn('Feature.max("DAILY_DAYS_PAST_DUE", "365d")', self.code)
        self.assertIn('feature_granularity="1 day"', self.code)
        self.assertIn('refresh_freq="1 day"', self.code)

    def test_implements_complete_planned_feature_contract(self):
        for feature_name in (
            "ACCOUNT_AGE_MONTHS", "CUSTOMER_TENURE_MONTHS", "PRODUCT_CODE",
            "ORIGINATION_CHANNEL", "CURRENT_CREDIT_LIMIT", "CURRENT_INCOME_ESTIMATE",
            "LIMIT_TO_INCOME_RATIO", "MONTHS_SINCE_LIMIT_CHANGE", "LIMIT_CHANGE_PERCENT_12M",
            "CURRENT_BALANCE", "CURRENT_UTILISATION", "AVG_UTILISATION_30D",
            "AVG_UTILISATION_90D", "MAX_UTILISATION_90D", "UTILISATION_STDDEV_90D",
            "BALANCE_CHANGE_30D", "BALANCE_CHANGE_90D", "DAYS_OVER_LIMIT_30D",
            "AVAILABLE_CREDIT_RATIO", "AVG_UTILISATION_365D", "MAX_UTILISATION_365D",
            "PAYMENT_SUM_30D", "PAYMENT_SUM_90D", "PAYMENT_COUNT_90D",
            "PAYMENT_TO_BALANCE_RATIO_30D", "PAYMENT_TO_AMOUNT_DUE_RATIO_30D",
            "MISSED_PAYMENT_COUNT_3M", "MISSED_PAYMENT_COUNT_6M",
            "DAYS_SINCE_LAST_PAYMENT", "PAYMENT_AMOUNT_TREND_3M",
            "CURRENT_DAYS_PAST_DUE", "MAX_DAYS_PAST_DUE_3M",
            "MAX_DAYS_PAST_DUE_6M", "DELINQUENT_DAYS_90D",
            "DELINQUENCY_EPISODES_6M", "CONSECUTIVE_DELINQUENT_MONTHS",
            "DAYS_SINCE_LAST_DELINQUENCY", "MAX_DAYS_PAST_DUE_365D",
            "CONTACT_COUNT_30D", "CONTACT_COUNT_90D", "BROKEN_PROMISE_COUNT_90D",
        ):
            self.assertIn(feature_name, self.code)

    def test_selected_account_review_and_lineage_precede_handoff(self):
        selected_review = self.code.index("selected_accounts =")
        registration = self.code.index("feature_version =")
        lineage = self.code.index("fs.load_feature_views_from_dataset")
        self.assertLess(selected_review, registration)
        self.assertIn("plt.subplots", self.code)
        self.assertIn('lineage(direction="upstream")', self.code)
        self.assertGreater(lineage, registration)

    def test_datasets_are_created_here_not_models(self):
        for name in ("CREDIT_DEVELOPMENT", "CREDIT_VALIDATION"):
            self.assertIn(name, self.code)
        for name in ("CREDIT_REFIT", "CREDIT_HELD_OUT"):
            self.assertNotIn(name, self.code)
        self.assertIn("spine_timestamp_col=\"OBSERVATION_TS\"", self.code)
        self.assertGreaterEqual(self.code.count('join_method="cte"'), 3)
        self.assertNotIn(".fit(", self.code)
        self.assertNotIn("ExperimentTracking", self.code)

    def test_metadata_uses_business_definitions(self):
        registration_text = self.code[self.code.index("feature_descriptions") :]
        self.assertNotIn("synthetic", registration_text.lower())
        self.assertIn("account currency units", registration_text)
        self.assertIn("trailing 90-day window", registration_text)


class ModelExperimentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.notebook = load_notebook("models")
        cls.code = notebook_text(cls.notebook, "code")
        cls.markdown = notebook_text(cls.notebook, "markdown")

    def test_reads_immutable_datasets_without_source_engineering(self):
        self.assertIn("dataset.load_dataset", self.code)
        for name in ("CREDIT_DEVELOPMENT", "CREDIT_VALIDATION", "CREDIT_REFIT", "CREDIT_HELD_OUT"):
            self.assertIn(name, self.code)
        for prohibited in ("FeatureView(", "register_entity", "TRAINING_BASE", "ACCOUNT_MASTER"):
            self.assertNotIn(prohibited, self.code)
        self.assertEqual(self.code.count("fs.generate_dataset("), 2)
        self.assertEqual(self.code.count('join_method="cte"'), 2)
        self.assertIn("ACCOUNT_AGGREGATION_FV", self.code)
        self.assertIn('categorical_features = ["PRODUCT_CODE", "ORIGINATION_CHANNEL"]', self.code)

    def test_every_fit_is_experiment_tracked_and_logged(self):
        self.assertIn("with exp.start_run(linear_run):", self.code)
        self.assertIn("with exp.start_run(tree_run):", self.code)
        self.assertIn("with exp.start_run(run_name):", self.code)
        self.assertIn("with exp.start_run(final_run):", self.code)
        self.assertIn("with exp.start_run(conclusion_run):", self.code)
        self.assertNotIn("exp.end_run()", self.code)
        self.assertGreaterEqual(self.code.count("exp.log_model("), 4)

    def test_dataset_backed_signature_and_manual_holdout_gate(self):
        self.assertIn("training_sample = development_df.select(feature_columns).limit(50)", self.code)
        self.assertIn("sample_input_data=training_sample", self.code)
        hpo = self.code.index("Tuner(")
        selection = self.code.index("selected_run = None")
        checkpoint = self.code.index("evaluate_holdout = False")
        reveal = self.code.index("held_out_dataset = fs.generate_dataset")
        self.assertLess(hpo, selection)
        self.assertLess(selection, checkpoint)
        self.assertLess(checkpoint, reveal)

    def test_unsupported_or_missing_segments_fail_acceptance(self):
        self.assertIn("PRESENT_IN_VALIDATION", self.code)
        self.assertIn("PRESENT_IN_HELD_OUT", self.code)
        self.assertIn('"CHECK": "All required segments have support"', self.code)
        self.assertIn('"PASS": unsupported_segment_count == 0', self.code)

    def test_ml_metadata_uses_business_descriptions(self):
        for line in self.code.splitlines():
            if "comment=" in line or "desc=" in line:
                self.assertNotIn("synthetic", line.lower())


if __name__ == "__main__":
    unittest.main()