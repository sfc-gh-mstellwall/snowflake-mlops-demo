import json
import tempfile
import unittest
from pathlib import Path
import sys

PROJECT_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_DIR))

from scripts.build_release import build_release, collect_payload_files


class CodeBundleReleaseTests(unittest.TestCase):
    def test_payload_excludes_notebooks_and_live_workspace_state(self) -> None:
        files = [path.relative_to(PROJECT_DIR).as_posix() for path in collect_payload_files(PROJECT_DIR)]
        self.assertIn("jobs/train.py", files)
        self.assertIn("code_bundle.yml", files)
        self.assertIn("config/workflow.yaml", files)
        self.assertNotIn("notebooks/03_credit_default_model_experiment.ipynb", files)
        joined = " ".join(files)
        self.assertNotIn("versions/live", joined)

    def test_build_release_records_payload_digest(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            output_dir = Path(temporary_directory)
            manifest = build_release(PROJECT_DIR, output_dir, "R_TEST_1")
            payload_dir = output_dir / "R_TEST_1"
            self.assertTrue((payload_dir / "jobs" / "train.py").is_file())
            self.assertTrue((payload_dir / "code_bundle.yml").is_file())
            self.assertTrue((payload_dir / "release_manifest.json").is_file())
            self.assertEqual(len(manifest["payload_digest"]), 64)
            self.assertFalse(manifest["execute_from_notebook_cell"])
            self.assertFalse(manifest["create_from_workspace_live"])
            written = json.loads((payload_dir / "release_manifest.json").read_text())
            self.assertEqual(written["release_id"], "R_TEST_1")

    def test_specification_uses_compute_pool_not_warehouse(self) -> None:
        specification = (PROJECT_DIR / "code_bundle.yml").read_text()
        self.assertIn("compute_type: compute_pool", specification)
        self.assertIn("runtime_version: V2.9-CPU-PY3.11", specification)
        self.assertNotIn("compute_type: warehouse", specification)
        self.assertNotIn("requirements.txt", specification)
        self.assertNotIn("requirements-file", specification)
        self.assertNotIn("requirements_file", specification)

    def test_sql_forbids_notebook_cell_execution(self) -> None:
        sql = (PROJECT_DIR / "deployment" / "05_code_bundle.sql").read_text()
        self.assertIn("never a notebook cell", sql)
        self.assertIn("EXECUTE CODE BUNDLE", sql)
        self.assertIn("ARGUMENTS = (", sql)
        self.assertIn(
            "Do not create a production release from Workspace versions/live",
            sql,
        )
        self.assertNotRegex(sql, r"FROM\s+'[^']*versions/live")
        self.assertNotIn("SHOW CODE BUNDLES IN SCHEMA", sql)


if __name__ == "__main__":
    unittest.main()
