"""Logging setup. Logs contain events only - never camera frames or landmarks."""
from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .paths import logs_dir

_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)s | %(message)s"
VALID_LEVELS = ("DEBUG", "INFO", "WARNING", "ERROR")


def setup_logging(level: str = "INFO", log_dir: Path | None = None) -> logging.Logger:
    """Configure the root 'airwheel' logger (console + rotating file). Idempotent."""
    level = level.upper() if level.upper() in VALID_LEVELS else "INFO"
    logger = logging.getLogger("airwheel")
    logger.setLevel(getattr(logging, level))

    # Remove handlers from any earlier call so repeated setup doesn't duplicate output.
    for h in list(logger.handlers):
        logger.removeHandler(h)
        h.close()

    formatter = logging.Formatter(_FORMAT)
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    logger.addHandler(console)

    try:
        directory = Path(log_dir) if log_dir else logs_dir()
        directory.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            directory / "airwheel.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"
        )
        fh.setFormatter(formatter)
        logger.addHandler(fh)
    except OSError as exc:  # never crash because the log file is unwritable
        logger.warning("File logging unavailable: %s", exc)

    logger.propagate = False
    return logger
