"""Centralised application configuration.

Configuration is loaded from TOML and exposed as a typed, immutable
``Config`` object. The database and log files live in a per-user data
directory *outside* the installation folder, as required by the brief.

Resolution order (later overrides earlier):
    1. Shipped defaults: ``config/default.toml`` next to the package.
    2. User override file, if present:
       ``<app_data_dir>/config.toml``.

Keeping this in one module means no other layer needs to know where
settings come from.
"""

from __future__ import annotations

import os
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

APP_NAME = "HyDesk"


def app_data_dir() -> Path:
    """Return the per-user data directory, creating it if necessary.

    On Windows this is ``%LOCALAPPDATA%\\HyDesk``; elsewhere it falls back
    to ``~/.local/share/HyDesk`` so the code remains testable off-Windows.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    else:
        base = os.environ.get("XDG_DATA_HOME") or str(Path.home() / ".local" / "share")
    directory = Path(base) / APP_NAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def _default_config_path() -> Path:
    """Path to the shipped default.toml (dev tree or frozen bundle)."""
    from .resources import resource_path

    return resource_path("config", "default.toml")


@dataclass(frozen=True)
class DatabaseConfig:
    filename: str = "hydesk.db"
    path: str = ""

    def resolve_path(self, data_dir: Path) -> Path:
        """Return the absolute database file path.

        If ``path`` is set it is used verbatim; otherwise the file lives in
        the per-user data directory.
        """
        if self.path:
            return Path(self.path).expanduser()
        return data_dir / self.filename


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    filename: str = "hydesk.log"
    max_bytes: int = 1_048_576
    backup_count: int = 5

    def resolve_path(self, data_dir: Path) -> Path:
        return data_dir / self.filename


@dataclass(frozen=True)
class UIConfig:
    default_page_size: int = 50
    page_size_options: tuple[int, ...] = (25, 50, 100, 200)


@dataclass(frozen=True)
class Config:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    ui: UIConfig = field(default_factory=UIConfig)
    data_dir: Path = field(default_factory=app_data_dir)

    @property
    def database_path(self) -> Path:
        return self.database.resolve_path(self.data_dir)

    @property
    def log_path(self) -> Path:
        return self.logging.resolve_path(self.data_dir)

    @property
    def database_url(self) -> str:
        """SQLAlchemy URL for the configured SQLite database."""
        return f"sqlite:///{self.database_path.as_posix()}"


def _read_toml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open("rb") as handle:
        return tomllib.load(handle)


def _merge(base: dict, override: dict) -> dict:
    """Shallow-per-section merge of two config dicts."""
    result = {k: dict(v) if isinstance(v, dict) else v for k, v in base.items()}
    for section, values in override.items():
        if isinstance(values, dict) and isinstance(result.get(section), dict):
            result[section].update(values)
        else:
            result[section] = values
    return result


def load_config(data_dir: Path | None = None) -> Config:
    """Load configuration from shipped defaults plus optional user override."""
    resolved_dir = data_dir if data_dir is not None else app_data_dir()

    merged = _read_toml(_default_config_path())
    user_override = _read_toml(resolved_dir / "config.toml")
    if user_override:
        merged = _merge(merged, user_override)

    db = merged.get("database", {})
    log = merged.get("logging", {})
    ui = merged.get("ui", {})

    return Config(
        database=DatabaseConfig(
            filename=db.get("filename", "hydesk.db"),
            path=db.get("path", ""),
        ),
        logging=LoggingConfig(
            level=log.get("level", "INFO"),
            filename=log.get("filename", "hydesk.log"),
            max_bytes=int(log.get("max_bytes", 1_048_576)),
            backup_count=int(log.get("backup_count", 5)),
        ),
        ui=UIConfig(
            default_page_size=int(ui.get("default_page_size", 50)),
            page_size_options=tuple(ui.get("page_size_options", [25, 50, 100, 200])),
        ),
        data_dir=resolved_dir,
    )
