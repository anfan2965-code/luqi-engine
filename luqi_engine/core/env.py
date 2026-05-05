"""环境变量模块 - 管理环境变量读取"""

from __future__ import annotations

import os
import logging
from typing import Optional

_logger = logging.getLogger(__name__)

_ENV_KEY_API_KEY = "LUQI_API_KEY"
_ENV_KEY_BASE_URL = "LUQI_BASE_URL"
_ENV_KEY_MODEL = "LUQI_MODEL"


def get_env_key(key_name: str, default: str = "", warn_if_missing: bool = True) -> str:
    value = os.environ.get(key_name, default)
    if not value and warn_if_missing and not default:
        _logger.warning("Environment variable %s is not set", key_name)
    return value


def get_api_key() -> str:
    return get_env_key(_ENV_KEY_API_KEY, warn_if_missing=True)


def get_base_url() -> str:
    return get_env_key(_ENV_KEY_BASE_URL, default="", warn_if_missing=False)


def get_model() -> str:
    return get_env_key(_ENV_KEY_MODEL, default="", warn_if_missing=False)
