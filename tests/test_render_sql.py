import io
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

PROJECT_DIR = Path(__file__).resolve().parents[1]
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
        template = (PROJECT_DIR / "deployment" / "bootstrap.sql").read_text()
        rendered = render(template, tokens)

        for metric in (
            "SNAPSHOT_ROWS",
            "FINALISED_DEFAULT_RATE",
            "TRAINING_ROWS",
            "SCORING_ROWS",
            "AVG_UTILISATION_RATIO",
            "ARREARS_RATE_30D",
            "OUTCOME_STATUS",
        ):
            with self.subTest(metric=metric):
                self.assertIn(metric, rendered)

    def test_sql_templates_do_not_use_rows_as_an_alias(self) -> None:
        for template_path in (PROJECT_DIR / "deployment").glob("*.sql"):
            with self.subTest(template=template_path.name):
                self.assertNotIn(" AS ROWS", template_path.read_text().upper())

    def test_inventory_covers_phase_one_object_categories(self) -> None:
        inventory_sql = (PROJECT_DIR / "deployment" / "inventory.sql").read_text()

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
        setup_sql = (PROJECT_DIR / "workspace_setup.sql").read_text()

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
                {"bootstrap.sql", "inventory.sql", "teardown.sql", "verify_data.sql"},
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

            self.assertTrue((output_dir / "bootstrap.sql").exists())
            self.assertIn("Rendered", output.getvalue())


if __name__ == "__main__":
    unittest.main()