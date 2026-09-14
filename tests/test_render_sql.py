from pathlib import Path

import pytest

import scripts.render_sql as render_sql_module
from scripts.render_sql import (
    DEFAULT_CONFIG_PATH,
    DEFAULT_OUTPUT_DIR,
    build_tokens,
    load_config,
    render,
    render_project,
)


PROJECT_DIR = Path(__file__).resolve().parents[1]


def test_default_config_is_safe_and_complete() -> None:
    tokens = build_tokens(load_config(PROJECT_DIR / "project.yaml"))
    assert tokens["PREFIX"] == "CRISK_DEMO"
    assert tokens["DATABASE"] == "CRISK_DEMO_DB"
    assert tokens["ACCOUNT_COUNT"] == "5000"


def test_prefix_must_identify_demo_resources() -> None:
    config = load_config(PROJECT_DIR / "project.yaml")
    config["project"]["prefix"] = "PRODUCTION"
    with pytest.raises(ValueError, match="must end with '_DEMO'"):
        build_tokens(config)


def test_destructive_names_must_use_protected_prefix() -> None:
    config = load_config(PROJECT_DIR / "project.yaml")
    config["snowflake"]["database"] = "PRODUCTION"
    with pytest.raises(ValueError, match="must start with the protected prefix"):
        build_tokens(config)


def test_invalid_date_is_rejected() -> None:
    config = load_config(PROJECT_DIR / "project.yaml")
    config["data"]["as_of_date"] = "2026-02-30"
    with pytest.raises(ValueError, match="valid YYYY-MM-DD"):
        build_tokens(config)


def test_invalid_compute_pool_bounds_are_rejected() -> None:
    config = load_config(PROJECT_DIR / "project.yaml")
    config["compute"]["pool_min_nodes"] = 2
    config["compute"]["pool_max_nodes"] = 1
    with pytest.raises(ValueError, match="cannot exceed"):
        build_tokens(config)


def test_render_rejects_unknown_token() -> None:
    with pytest.raises(ValueError, match="Missing template tokens"):
        render("SELECT '{{UNKNOWN}}'", {})


def test_all_sql_templates_render_without_tokens_left() -> None:
    tokens = build_tokens(load_config(PROJECT_DIR / "project.yaml"))
    for template_path in (PROJECT_DIR / "deployment").glob("*.sql"):
        rendered = render(template_path.read_text(), tokens)
        assert "{{" not in rendered
        assert "}}" not in rendered


def test_workspace_defaults_are_relative_to_project_root() -> None:
    assert DEFAULT_CONFIG_PATH == PROJECT_DIR / "project.yaml"
    assert DEFAULT_OUTPUT_DIR == PROJECT_DIR / "build"


def test_workspace_setup_matches_default_compute_pool() -> None:
    tokens = build_tokens(load_config(DEFAULT_CONFIG_PATH))
    setup_sql = (PROJECT_DIR / "workspace_setup.sql").read_text()

    assert f"CREATE COMPUTE POOL IF NOT EXISTS {tokens['COMPUTE_POOL']}" in setup_sql
    assert f"INSTANCE_FAMILY = {tokens['POOL_INSTANCE_FAMILY']}" in setup_sql
    assert f"MIN_NODES = {tokens['POOL_MIN_NODES']}" in setup_sql
    assert f"MAX_NODES = {tokens['POOL_MAX_NODES']}" in setup_sql
    assert f"AUTO_SUSPEND_SECS = {tokens['POOL_AUTO_SUSPEND']}" in setup_sql
    assert "AUTO_RESUME = TRUE" in setup_sql


def test_render_project_supports_an_explicit_output_directory(tmp_path: Path) -> None:
    output_paths = render_project(PROJECT_DIR / "project.yaml", tmp_path)

    assert {path.name for path in output_paths} == {
        "bootstrap.sql",
        "inventory.sql",
        "teardown.sql",
        "verify_data.sql",
    }
    assert all(path.parent == tmp_path for path in output_paths)


def test_render_project_rejects_stale_sql(tmp_path: Path) -> None:
    (tmp_path / "obsolete.sql").write_text("SELECT 1")

    with pytest.raises(ValueError, match="remove stale files"):
        render_project(PROJECT_DIR / "project.yaml", tmp_path)


def test_main_uses_workspace_defaults(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setattr(render_sql_module, "DEFAULT_OUTPUT_DIR", tmp_path)
    monkeypatch.setattr("sys.argv", ["render_sql.py"])

    render_sql_module.main()

    assert (tmp_path / "bootstrap.sql").exists()
    assert "Rendered" in capsys.readouterr().out