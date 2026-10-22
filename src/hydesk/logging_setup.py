"""Structured logging setup.

A single entry point (``configure_logging``) wires a rotating file handler
and a console handler with a consistent, parseable line format. Called once
from the application entry point; the rest of the code just uses
``logging.getLogger(__name__)``.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import Config

_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S%z"


def configure_logging(config: Config) -> logging.Logger:
    """Configure root logging from the application config.

    Idempotent: clears existing handlers so repeated calls (e.g. in tests)
    do not duplicate log lines.
    """
    log_path: Path = config.log_path
    log_path.parent.mkdir(parents=True, exist_ok=True)

    level = getattr(logging, config.logging.level.upper(), logging.INFO)
    formatter = logging.Formatter(_LOG_FORMAT, datefmt=_DATE_FORMAT)

    root = logging.getLogger()
    root.setLevel(level)
    for handler in list(root.handlers):
        root.removeHandler(handler)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=config.logging.max_bytes,
        backupCount=config.logging.backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    logging.getLogger(__name__).info("Logging configured (level=%s)", config.logging.level)
    return root
