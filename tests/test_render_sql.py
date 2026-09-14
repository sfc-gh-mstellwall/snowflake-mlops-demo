from pathlib import Path

import pytest

from scripts.render_sql import build_tokens, load_config, render


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