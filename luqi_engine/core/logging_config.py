"""日志配置模块 - 配置日志系统"""

from __future__ import annotations

import logging
import re
import sys
from typing import Optional

_DEFAULT_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_root_logger_name = "luqi_engine"


class SensitiveDataFilter(logging.Filter):
    """
    日志脱敏过滤器
    
    过滤敏感信息如API密钥、Bearer token等，防止泄露到日志中
    """
    
    # 敏感信息模式
    _PATTERNS = [
        # Bearer token
        (re.compile(r'Bearer\s+\S+', re.IGNORECASE), 'Bearer ***'),
        # API密钥（api_key=xxx 或 api_key: xxx）
        (re.compile(r'api_key[=:]\s*\S+', re.IGNORECASE), 'api_key=***'),
        # 通用密钥模式（key=xxx 或 key: xxx）
        (re.compile(r'(?:secret|password|token)[=:]\s*\S+', re.IGNORECASE), '***'),
        # 长字符串（可能是哈希值或token）
        (re.compile(r'\b[A-Za-z0-9+/]{40,}={0,2}\b'), '***'),
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        """
        过滤日志记录，脱敏敏感信息
        
        Args:
            record: 日志记录
            
        Returns:
            True表示允许日志通过，False表示过滤掉
        """
        if record.msg and isinstance(record.msg, str):
            for pattern, replacement in self._PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        
        # 处理args（如果有格式化参数）
        if record.args and isinstance(record.args, dict):
            for key, value in record.args.items():
                if isinstance(value, str):
                    for pattern, replacement in self._PATTERNS:
                        record.args[key] = pattern.sub(replacement, value)
        
        return True


def configure_logging(
    level: int = logging.INFO,
    format_string: Optional[str] = None,
    date_format: Optional[str] = None,
    handler: Optional[logging.Handler] = None,
    enable_sensitive_filter: bool = True,
) -> None:
    """
    配置日志系统
    
    Args:
        level: 日志级别
        format_string: 日志格式字符串
        date_format: 日期格式字符串
        handler: 日志处理器
        enable_sensitive_filter: 是否启用敏感信息过滤
    """
    fmt = format_string or _DEFAULT_FORMAT
    datefmt = date_format or _DEFAULT_DATE_FORMAT
    logger = logging.getLogger(_root_logger_name)
    logger.setLevel(level)
    if not logger.handlers:
        target_handler = handler or logging.StreamHandler(sys.stderr)
        target_handler.setFormatter(logging.Formatter(fmt, datefmt))
        
        # 添加敏感信息过滤器
        if enable_sensitive_filter:
            target_handler.addFilter(SensitiveDataFilter())
        
        logger.addHandler(target_handler)


def get_logger(name: str) -> logging.Logger:
    """
    获取日志记录器
    
    Args:
        name: 日志记录器名称
        
    Returns:
        日志记录器实例
    """
    return logging.getLogger(f"{_root_logger_name}.{name}")
