"""
统一配置文件加载器
支持 YAML 格式的全局配置文件，提供：
- EngineConfig.load(path) 从YAML加载
- EngineConfig.save(path) 导出为YAML
- 自动回退：文件不存在时返回默认配置
- 部分覆盖：仅存在的节被覆盖
"""

import logging
from pathlib import Path
from typing import Optional

import yaml

from .config import EngineConfig

logger = logging.getLogger(__name__)


class ConfigLoadError(Exception):
    """配置文件加载错误"""
    pass


def load_config(path: Optional[str] = None) -> EngineConfig:
    """
    从YAML文件加载引擎配置。

    Args:
        path: YAML文件路径。None时返回默认配置。

    Returns:
        EngineConfig 实例

    行为：
        - 文件不存在 → 返回默认 EngineConfig()
        - 文件存在但格式错误 → 抛出 ConfigLoadError
        - 文件部分内容 → 仅覆盖提到的字段，其余用默认值
        - 完整文件 → 全部字段从YAML加载
    """
    if path is None:
        logger.debug("未指定配置路径，使用默认配置")
        return EngineConfig()

    config_path = Path(path)

    if not config_path.exists():
        error_msg = f"配置文件不存在: {path}"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        error_msg = f"配置文件格式错误: {path}\n详情: {e}"
        logger.error(error_msg)
        raise ConfigLoadError(error_msg) from e
    except IOError as e:
        error_msg = f"无法读取配置文件: {path}\n详情: {e}"
        logger.error(error_msg)
        raise ConfigLoadError(error_msg) from e

    if data is None:
        logger.warning(f"配置文件为空: {path}，使用默认配置")
        return EngineConfig()

    if not isinstance(data, dict):
        error_msg = f"配置文件根节点必须是字典/映射类型，实际类型: {type(data).__name__}"
        logger.error(error_msg)
        raise ConfigLoadError(error_msg)

    try:
        config = EngineConfig.from_dict(data)
        logger.info(f"成功加载配置文件: {path}")
        return config
    except Exception as e:
        error_msg = f"配置文件解析失败: {path}\n详情: {e}"
        logger.error(error_msg)
        raise ConfigLoadError(error_msg) from e


def save_config(config: EngineConfig, path: str) -> None:
    """
    将配置导出为YAML文件。

    Args:
        config: 要保存的 EngineConfig 实例
        path: 输出路径
    """
    config_path = Path(path)

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        error_msg = f"无法创建配置目录: {config_path.parent}\n详情: {e}"
        logger.error(error_msg)
        raise ConfigLoadError(error_msg) from e

    try:
        data = config.to_dict()
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(
                data,
                f,
                default_flow_style=False,
                allow_unicode=True,
                sort_keys=False,
                indent=2
            )
        logger.info(f"配置已保存到: {path}")
    except (IOError, OSError) as e:
        error_msg = f"无法写入配置文件: {path}\n详情: {e}"
        logger.error(error_msg)
        raise ConfigLoadError(error_msg) from e
