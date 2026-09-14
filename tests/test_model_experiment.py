import ast
import json
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = (
    PROJECT_DIR / "notebooks" / "02_credit_default_model_experiment.ipynb"
)


class ModelExperimentNotebookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.notebook = json.loads(NOTEBOOK_PATH.read_text())
        cls.cells = cls.notebook["cells"]
        cls.code_cells = [
            "".join(cell.get("source", []))
            for cell in cls.cells
            if cell["cell_type"] == "code"
        ]
        cls.code = "\n".join(cls.code_cells)
        cls.markdown = "\n".join(
            "".join(cell.get("source", []))
            for cell in cls.cells
            if cell["cell_type"] == "markdown"
        )

    def test_notebook_structure_and_python_syntax(self) -> None:
        self.assertEqual(self.notebook["nbformat"], 4)
        self.assertGreaterEqual(self.notebook["nbformat_minor"], 5)
        cell_ids = [cell.get("id") for cell in self.cells]
        self.assertTrue(all(cell_ids))
        self.assertEqual(len(cell_ids), len(set(cell_ids)))
        self.assertTrue(all(source.strip() for source in self.code_cells))
        for index, source in enumerate(self.code_cells):
            with self.subTest(code_cell=index):
                ast.parse(source)

    def test_project_yaml_is_only_the_platform_handoff(self) -> None:
        self.assertIn('config["snowflake"]', self.code)
        self.assertIn('config["data"]["as_of_date"]', self.code)
        self.assertNotIn('config["model"]', self.code)
        self.assertNotIn('config["experiment"]', self.code)
        self.assertIn("platform hand-off", self.code)

    def test_feature_reasoning_precedes_feature_view_creation(self) -> None:
        first_feature_view_cell = next(
            index
            for index, cell in enumerate(self.cells)
            if "FeatureView(" in "".join(cell.get("source", []))
        )
        hypothesis_cell = next(
            index
            for index, cell in enumerate(self.cells)
            if "relatively stable account context"
            in "".join(cell.get("source", []))
        )
        self.assertLess(hypothesis_cell, first_feature_view_cell)

    def test_temporal_choices_follow_visible_label_coverage(self) -> None:
        coverage = self.code.index("monthly_label_coverage")
        development_cutoff = self.code.index("development_cutoff = pd.Timestamp")
        holdout_cutoff = self.code.index("holdout_cutoff = pd.Timestamp")
        self.assertLess(coverage, development_cutoff)
        self.assertLess(coverage, holdout_cutoff)
        early_code = self.code[:holdout_cutoff]
        self.assertNotIn("DEFAULT_RATE", early_code)
        self.assertNotIn('sf.avg("DEFAULT_WITHIN_90D")', early_code)

    def test_every_fit_is_covered_by_an_experiment_run(self) -> None:
        self.assertIn("with exp.start_run(linear_run):", self.code)
        self.assertIn("with exp.start_run(tree_run):", self.code)
        self.assertIn("with exp.start_run(run_name):", self.code)
        self.assertIn("exp.start_run(final_run)", self.code)
        self.assertIn("exp.end_run()", self.code)
        self.assertEqual(self.code.count(".fit("), 4)

    def test_model_logging_uses_dataset_backed_snowpark_samples(self) -> None:
        self.assertIn(
            "training_sample = development_df.select(feature_columns).limit(50)",
            self.code,
        )
        self.assertIn(
            "refit_sample = refit_df.select(feature_columns).limit(50)",
            self.code,
        )
        self.assertGreaterEqual(
            self.code.count("sample_input_data=training_sample"),
            4,
        )
        self.assertIn("sample_input_data=refit_sample", self.code)

    def test_hpo_and_manual_choice_precede_holdout_access(self) -> None:
        hpo = self.code.index("Tuner(")
        selection = self.code.index("selected_run = None")
        checkpoint = self.code.index("evaluate_holdout = False")
        reveal = self.code.index("held_out_spine = labels.filter")
        self.assertLess(hpo, selection)
        self.assertLess(selection, checkpoint)
        self.assertLess(checkpoint, reveal)
        self.assertIn("There is intentionally no default winner", self.markdown)

    def test_notebook_keeps_production_automation_out_of_scope(self) -> None:
        for prohibited in (
            "PIPELINE_RUN",
            "CREATE TASK",
            "set_default_version",
            "set_alias",
            "session.builder",
            "pip install",
        ):
            with self.subTest(prohibited=prohibited):
                self.assertNotIn(prohibited, self.code)


if __name__ == "__main__":
    unittest.main()