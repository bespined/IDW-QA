#!/usr/bin/env python3
"""Centralized logging for IDW QA (SCOUT ULTRA).

Provides persistent file logging + console output for all scripts.
Log files are stored in ~/.idw/logs/ with daily rotation.

Usage in any script:
    from idw_logger import get_logger
    logger = get_logger("canvas_api")
    logger.info("Connected to Canvas")
    logger.error("Failed to update page: %s", slug)
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path


LOG_DIR = Path.home() / ".idw" / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Daily log file
LOG_FILE = LOG_DIR / f"idw_{datetime.now().strftime('%Y-%m-%d')}.log"

# Session tracking
_SESSION_ID = datetime.now().strftime("%H%M%S")

# Module-level cache to avoid duplicate handlers
_loggers = {}


def get_logger(name="idw"):
    """Get a named logger with file + console handlers.

    Args:
        name: Logger name (typically the script name without .py)

    Returns:
        logging.Logger configured with file and console output.
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(f"idw.{name}")
    logger.setLevel(logging.DEBUG)

    # Avoid adding handlers if they already exist (e.g., reimport)
    if logger.handlers:
        _loggers[name] = logger
        return logger

    # File handler — DEBUG and above, persistent
    file_fmt = logging.Formatter(
        f"%(asctime)s [{_SESSION_ID}] %(name)s %(levelname)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh = logging.FileHandler(str(LOG_FILE), encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(file_fmt)
    logger.addHandler(fh)

    # Console handler — INFO and above (matches current print behavior)
    console_fmt = logging.Formatter("%(message)s")
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(console_fmt)
    logger.addHandler(ch)

    _loggers[name] = logger
    return logger


def get_session_id():
    """Return the current session ID for correlation."""
    return _SESSION_ID


def get_log_path():
    """Return path to today's log file."""
    return str(LOG_FILE)
