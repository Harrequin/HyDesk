"""Tests for configuration loading and path resolution."""

from __future__ import annotations

from pathlib import Path

from hydesk.config import Config, load_config


def test_load_defaults(tmp_path: Path):
    config = load_config(data_dir=tmp_path)
    assert config.database.filename == "hydesk.db"
    assert config.ui.default_page_size == 50
    assert config.logging.level == "INFO"


def test_database_path_in_data_dir(tmp_path: Path):
    config = load_config(data_dir=tmp_path)
    assert config.database_path == tmp_path / "hydesk.db"


def test_database_url_is_sqlite(tmp_path: Path):
    config = load_config(data_dir=tmp_path)
    assert config.database_url.startswith("sqlite:///")


def test_log_path_in_data_dir(tmp_path: Path):
    config = load_config(data_dir=tmp_path)
    assert config.log_path == tmp_path / "hydesk.log"


def test_user_override_takes_precedence(tmp_path: Path):
    override = tmp_path / "config.toml"
    override.write_text(
        "[ui]\ndefault_page_size = 100\n\n[logging]\nlevel = \"DEBUG\"\n",
        encoding="utf-8",
    )
    config = load_config(data_dir=tmp_path)
    assert config.ui.default_page_size == 100
    assert config.logging.level == "DEBUG"
    # Unspecified values still come from shipped defaults.
    assert config.database.filename == "hydesk.db"


def test_explicit_database_path_override(tmp_path: Path):
    override = tmp_path / "config.toml"
    custom = tmp_path / "custom" / "mydb.sqlite"
    override.write_text(
        f"[database]\npath = \"{custom.as_posix()}\"\n", encoding="utf-8"
    )
    config = load_config(data_dir=tmp_path)
    assert config.database_path == custom
