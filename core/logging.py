"""
MedScript Structured Logging Setup
"""

import logging
import sys


def setup_logging(app):
    """Configure structured logging for MedScript."""
    log_level = app.config.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, log_level, logging.INFO)

    log_format = "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
    formatter = logging.Formatter(log_format)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    handler.setLevel(level)

    root_logger = logging.getLogger()
    # Avoid duplicate handlers if already configured
    if not root_logger.handlers:
        root_logger.addHandler(handler)
    root_logger.setLevel(level)

    app.logger.setLevel(level)
