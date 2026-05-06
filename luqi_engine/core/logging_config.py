from __future__ import annotations

import logging
import sys
from typing import Optional

_DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_root_logger_name = "luqi_engine"


def configure_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    date_format: Optional[str] = None,
    handler: Optional[logging.Handler] = None,
) -> None:
    fmt = format_string or _DEFAULT_FORMAT
    datefmt = date_format or _DEFAULT_DATE_FORMAT
    logger = logging.getLogger(_root_logger_name)
    logger.setLevel(level)
    if not logger.handlers:
        target_handler = handler or logging.StreamHandler(sys.stderr)
        target_handler.setFormatter(logging.Formatter(fmt, datefmt))
        logger.addHandler(target_handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(f"{_root_logger_name}.{name}")
