import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

PROJECT_DIR = Path(__file__).resolve().parents[1]
NOTEBOOK_PATH = PROJECT_DIR / "notebooks" / "01_credit_default_exploration.ipynb"
sys.path.insert(0, str(PROJECT_DIR))

import scripts.render_sql as render_sql_module
from scripts.render_sql import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_OUTPUT_DIR,
    build_tokens,
    load_config,
    render,
    render_project,
)

class RenderSqlTests(unittest.TestCase):
    def test_default_config_is_safe_and_complete(self) -> None:
        tokens = build_tokens(load_config(PROJECT_DIR / "project.yaml"))
        self.assertEqual(tokens["PREFIX"], "CRISK_DEMO")
        self.assertEqual(tokens["DATABASE"], "CRISK_DEMO_DB")
        self.assertEqual(tokens["ACCOUNT_COUNT"], "5000")

    def test_prefix_must_identify_demo_resources(self) -> None:
        config = load_config(PROJECT_DIR / "project.yaml")
        config["project"]["prefix"] = "PRODUCTION"
        with self.assertRaisesRegex(ValueError, "must end with '_DEMO'"):
            build_tokens(config)

    def test_destructive_names_must_use_protected_prefix(self) -> None:
        config = load_config(PROJECT_DIR / "project.yaml")
        config["snowflake"]["database"] = "PRODUCTION"
        with self.assertRaisesRegex(ValueError, "must start with the protected prefix"):
            build_tokens(config)

    def test_invalid_date_is_rejected(self) -> None:
        config = load_config(PROJECT_DIR / "project.yaml")
        config["data"]["as_of_date"] = "2026-02-30"
        with self.assertRaisesRegex(ValueError, "valid YYYY-MM-DD"):
            build_tokens(config)

    def test_invalid_compute_pool_bounds_are_rejected(self) -> None:
        config = load_config(PROJECT_DIR / "project.yaml")
        config["compute"]["pool_min_nodes"] = 2
        config["compute"]["pool_max_nodes"] = 1
        with self.assertRaisesRegex(ValueError, "cannot exceed"):
            build_tokens(config)

    def test_render_rejects_unknown_token(self) -> None:
        with self.assertRaisesRegex(ValueError, "Missing template tokens"):
            render("SELECT '{{UNKNOWN}}'", {})

    def test_all_sql_templates_render_without_tokens_left(self) -> None:
        tokens = build_tokens(load_config(PROJECT_DIR / "project.yaml"))
        for template_path in (PROJECT_DIR / "deployment").glob("*.sql"):
            with self.subTest(template=template_path.name):
                rendered = render(template_path.read_text(), tokens)
                self.assertNotIn("{{", rendered)
                self.assertNotIn("}}", rendered)

    def test_bootstrap_reports_generated_data_summary(self) -> None:
        tokens = build_tokens(load_config(PROJECT_DIR / "project.yaml"))
        template = (PROJECT_DIR / "deployment" / "01_bootstrap.sql").read_text()
        rendered = render(template, tokens)

        for metric in (
            "DIM_CUSTOMER",
            "DIM_CREDIT_ACCOUNT",
            "FACT_ACCOUNT_DAILY_SNAPSHOT",
            "FACT_PAYMENT",
            "FACT_DEFAULT_EVENT",
            "DAILY_SNAPSHOT_COUNT",
            "DEFAULT_EVENT_COUNT",
            "DEFAULT_RATE",
            "OUTCOME_STATUS",
        ):
            with self.subTest(metric=metric):
                self.assertIn(metric, rendered)

    def test_bootstrap_prepares_every_notebook_prerequisite(self) -> None:
        tokens = build_tokens(load_config(PROJECT_DIR / "project.yaml"))
        template = (PROJECT_DIR / "deployment" / "01_bootstrap.sql").read_text()
        rendered = render(template, tokens)

        for statement in (
            f"CREATE SCHEMA IF NOT EXISTS {tokens['DATABASE']}.{tokens['FEATURE_STORE_SCHEMA']}",
            "GRANT CREATE TABLE, CREATE VIEW, CREATE DATASET, CREATE EXPERIMENT, CREATE MODEL",
            "GRANT CREATE TABLE, CREATE TAG, CREATE VIEW",
            "CREATE DYNAMIC TABLE",
            "GRANT REFERENCES ON ALL TABLES",
            "GRANT REFERENCES ON ALL VIEWS",
            f"GRANT VIEW LINEAGE ON ACCOUNT TO ROLE {tokens['DEVELOPER_ROLE']}",
        ):
            with self.subTest(statement=statement):
                self.assertIn(statement, rendered)

    def test_verification_covers_source_integrity_and_drift(self) -> None:
        verification = (PROJECT_DIR / "deployment" / "03_verify_data.sql").read_text()
        for check in (
            "UNIQUE_FINANCIAL_KEYS",
            "FINANCIAL_CUSTOMER_RELATIONSHIPS",
            "EVENT_ACCOUNT_RELATIONSHIPS",
            "OBSERVATION_ACCOUNT_RELATIONSHIPS",
            "EVENT_POPULATIONS_EXIST",
            "CONTROLLED_DRIFT_IS_VISIBLE",
            "EXPECTED_PROJECT_TABLES",
            "UNIQUE_DIMENSION_KEYS",
            "UNIQUE_OBSERVATION_KEYS",
            "SCENARIO_BOUNDARY_MATCHES_CONFIG",
        ):
            self.assertIn(check, verification)

    def test_source_tables_and_columns_have_business_comments(self) -> None:
        tokens = build_tokens(load_config(PROJECT_DIR / "project.yaml"))
        template = (PROJECT_DIR / "deployment" / "01_bootstrap.sql").read_text()
        rendered = render(template, tokens)

        for object_name in (
            "DIM_CUSTOMER",
            "DIM_CREDIT_ACCOUNT",
            "FACT_CUSTOMER_FINANCIAL_SNAPSHOT",
            "FACT_ACCOUNT_DAILY_SNAPSHOT",
            "FACT_PAYMENT",
            "FACT_CUSTOMER_CONTACT",
            "FACT_ACCOUNT_EVENT",
            "FACT_DEFAULT_EVENT",
            "ACCOUNT_OBSERVATION",
        ):
            self.assertRegex(
                rendered,
                rf"CREATE OR REPLACE TABLE {object_name} \([\s\S]*?\) COMMENT = '[^']+';",
            )
        self.assertNotRegex(rendered, r"COMMENT\s*=\s*'[^']*synthetic")
        self.assertNotRegex(rendered, r"\b\w+\s+[^,\n]+ COMMENT '[^']*synthetic")

    def test_sql_templates_do_not_use_rows_as_an_alias(self) -> None:
        for template_path in (PROJECT_DIR / "deployment").glob("*.sql"):
            with self.subTest(template=template_path.name):
                self.assertNotIn(" AS ROWS", template_path.read_text().upper())

    def test_inventory_covers_phase_one_object_categories(self) -> None:
        inventory_sql = (PROJECT_DIR / "deployment" / "02_inventory.sql").read_text()

        for command in (
            "SHOW DATABASES LIKE",
            "SHOW WAREHOUSES LIKE",
            "SHOW COMPUTE POOLS LIKE",
            "SHOW ROLES LIKE",
            "SHOW SCHEMAS IN DATABASE",
            "SHOW TABLES IN DATABASE",
            "SHOW VIEWS IN DATABASE",
            "SHOW STAGES IN DATABASE",
            "SHOW TASKS IN DATABASE",
            "SHOW NOTEBOOK PROJECTS IN DATABASE",
            "SHOW MODELS IN DATABASE",
            "SHOW MODEL MONITORS IN DATABASE",
            "SHOW EXPERIMENTS IN DATABASE",
        ):
            with self.subTest(command=command):
                self.assertIn(command, inventory_sql)

    def test_workspace_defaults_are_relative_to_project_root(self) -> None:
        self.assertEqual(DEFAULT_CONFIG_PATH, PROJECT_DIR / "project.yaml")
        self.assertEqual(DEFAULT_OUTPUT_DIR, PROJECT_DIR / "build")

    def test_workspace_setup_matches_default_compute_pool(self) -> None:
        tokens = build_tokens(load_config(DEFAULT_CONFIG_PATH))
        setup_sql = (PROJECT_DIR / "00_workspace_setup.sql").read_text()

        self.assertIn(
            f"CREATE COMPUTE POOL IF NOT EXISTS {tokens['COMPUTE_POOL']}", setup_sql
        )
        self.assertIn(f"INSTANCE_FAMILY = {tokens['POOL_INSTANCE_FAMILY']}", setup_sql)
        self.assertIn(f"MIN_NODES = {tokens['POOL_MIN_NODES']}", setup_sql)
        self.assertIn(f"MAX_NODES = {tokens['POOL_MAX_NODES']}", setup_sql)
        self.assertIn(f"AUTO_SUSPEND_SECS = {tokens['POOL_AUTO_SUSPEND']}", setup_sql)
        self.assertIn("AUTO_RESUME = TRUE", setup_sql)

    def test_render_project_supports_an_explicit_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            output_paths = render_project(PROJECT_DIR / "project.yaml", output_dir)

            self.assertEqual(
                {path.name for path in output_paths},
                {
                    "01_bootstrap.sql",
                    "02_inventory.sql",
                    "03_verify_data.sql",
                    "99_teardown.sql",
                },
            )
            self.assertTrue(all(path.parent == output_dir for path in output_paths))

    def test_render_project_rejects_stale_sql(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            (output_dir / "obsolete.sql").write_text("SELECT 1")

            with self.assertRaisesRegex(ValueError, "remove stale files"):
                render_project(PROJECT_DIR / "project.yaml", output_dir)

    def test_main_uses_workspace_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            output = io.StringIO()
            with (
                patch.object(render_sql_module, "DEFAULT_OUTPUT_DIR", output_dir),
                patch.object(sys, "argv", ["render_sql.py"]),
                redirect_stdout(output),
            ):
                render_sql_module.main()

            self.assertTrue((output_dir / "01_bootstrap.sql").exists())
            self.assertIn("Rendered", output.getvalue())


class WorkspaceNotebookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.notebook = json.loads(NOTEBOOK_PATH.read_text())
        self.cells = self.notebook["cells"]

    def test_notebook_uses_nbformat_4_5(self) -> None:
        self.assertEqual(self.notebook["nbformat"], 4)
        self.assertGreaterEqual(self.notebook["nbformat_minor"], 5)

    def test_every_cell_has_a_unique_id(self) -> None:
        cell_ids = [cell.get("id") for cell in self.cells]
        self.assertTrue(all(cell_ids))
        self.assertEqual(len(cell_ids), len(set(cell_ids)))

    def test_sql_cells_use_named_workspace_results(self) -> None:
        sql_cell_count = 0
        for cell in self.cells:
            source = "".join(cell.get("source", []))
            if not source.startswith("%%sql -r "):
                continue
            sql_cell_count += 1
            variable_name = source.splitlines()[0].removeprefix("%%sql -r ").strip()
            with self.subTest(variable=variable_name):
                self.assertRegex(variable_name, r"^[a-z][a-z0-9_]+$")
        self.assertGreaterEqual(sql_cell_count, 1)

    def test_notebook_is_workspace_only(self) -> None:
        notebook_text = NOTEBOOK_PATH.read_text().lower()
        for prohibited in (
            "connection_name",
            "session.builder",
            "snowflake.connector",
            "streamlit",
            "ipywidgets",
            "pip install",
        ):
            with self.subTest(prohibited=prohibited):
                self.assertNotIn(prohibited, notebook_text)

    def test_notebook_contains_expected_analysis_sections(self) -> None:
        markdown = "\n".join(
            "".join(cell.get("source", []))
            for cell in self.cells
            if cell["cell_type"] == "markdown"
        )
        for heading in (
            "What source data exists?",
            "history long and coherent enough?",
            "What do the atomic events add?",
            "When does the target become knowable?",
            "Provisional feature hypotheses",
        ):
            with self.subTest(heading=heading):
                self.assertIn(heading, markdown)

    def test_sql_cells_do_not_use_rows_as_an_alias(self) -> None:
        for cell in self.cells:
            source = "".join(cell.get("source", []))
            if source.startswith("%%sql -r "):
                self.assertIsNone(re.search(r"\bAS\s+ROWS\b", source, re.IGNORECASE))

    def test_snowpark_pandas_analysis_protects_held_out_period(self) -> None:
        code = "\n".join(
            "".join(cell.get("source", []))
            for cell in self.cells
            if cell["cell_type"] == "code"
        )
        self.assertIn('holdout_cutoff = pd.Timestamp(config["data"]["drift_start_date"])', code)
        self.assertIn('(observations["OBSERVATION_DATE"] < holdout_cutoff)', code)
        self.assertNotIn('observations.groupby("OBSERVATION_DATE")["DEFAULT_WITHIN_90D"]', code)

    def test_notebook_contains_required_source_eda(self) -> None:
        notebook_text = NOTEBOOK_PATH.read_text()
        for expected in (
            "fact_contracts",
            "DUPLICATE_GRAIN_KEYS",
            "ORPHAN_RECORDS",
            "NULL_COUNT",
            "history_coverage",
            "trajectory_monthly",
            "payment_profile",
            "contact_profile",
            "label_coverage",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, notebook_text)

    def test_source_eda_does_not_use_model_ready_relations(self) -> None:
        notebook_text = NOTEBOOK_PATH.read_text()
        for prohibited in ("TRAINING_BASE", "ACCOUNT_SNAPSHOT", "ACCOUNT_MASTER"):
            self.assertNotIn(prohibited, notebook_text)

    def test_notebook_avoids_known_brittle_snowpark_pandas_operations(self) -> None:
        notebook_text = NOTEBOOK_PATH.read_text()
        for prohibited in (
            ".ngroups",
            ".transform(\"sum\")",
            ".clip(lower=",
            ".clip(upper=",
            "quantile([",
            "filterwarnings",
            ".agg(\n    lambda",
        ):
            with self.subTest(prohibited=prohibited):
                self.assertNotIn(prohibited, notebook_text)

    def test_all_sql_code_cells_use_workspace_magic(self) -> None:
        for cell in self.cells:
            if cell["cell_type"] != "code":
                continue
            source = "".join(cell.get("source", [])).lstrip()
            looks_like_sql = bool(re.match(r"(SELECT|WITH|DESCRIBE|SHOW|USE)\b", source, re.I))
            with self.subTest(cell_id=cell["id"]):
                self.assertFalse(looks_like_sql)


if __name__ == "__main__":
    unittest.main()