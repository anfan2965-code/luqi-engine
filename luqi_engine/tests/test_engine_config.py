"""
LuqiEngine 配置初始化增强功能测试
覆盖三种初始化方式：config对象、config_path、默认值
以及优先级、优雅降级、属性访问等场景
"""

import tempfile
from pathlib import Path

import pytest
import yaml

from luqi_engine import LuqiEngine
from luqi_engine.core.config import EngineConfig


class TestInitWithConfigObject:
    """测试1: 传入 EngineConfig 实例"""

    def test_init_with_custom_config(self):
        custom_config = EngineConfig()
        custom_config.llm.model = "gpt-4o"
        custom_config.narrative.max_branch_depth = 15

        engine = LuqiEngine(config=custom_config)

        assert engine.config is custom_config
        assert engine.config.llm.model == "gpt-4o"
        assert engine.config.narrative.max_branch_depth == 15


class TestInitWithConfigPath:
    """测试2: 从 YAML 文件路径加载"""

    def test_init_with_valid_yaml_path(self, tmp_path):
        yaml_data = {
            "llm": {"model": "deepseek-chat", "temperature": 0.9},
            "narrative": {"max_branch_depth": 20},
        }
        yaml_file = tmp_path / "test_config.yaml"
        with open(yaml_file, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f)

        engine = LuqiEngine(config_path=str(yaml_file))

        assert engine.config.llm.model == "deepseek-chat"
        assert engine.config.llm.temperature == 0.9
        assert engine.config.narrative.max_branch_depth == 20


class TestInitWithBothConfigAndPath:
    """测试3: 同时传 config 和 config_path，验证 config 优先"""

    def test_config_takes_priority_over_path(self, tmp_path):
        yaml_data = {
            "llm": {"model": "yaml-model", "temperature": 0.5},
        }
        yaml_file = tmp_path / "priority_test.yaml"
        with open(yaml_file, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f)

        custom_config = EngineConfig()
        custom_config.llm.model = "config-object-model"

        engine = LuqiEngine(config=custom_config, config_path=str(yaml_file))

        assert engine.config.llm.model == "config-object-model"
        assert engine.config is custom_config


class TestInitDefault:
    """测试4: 不传任何参数，使用默认配置"""

    def test_init_with_no_args(self):
        engine = LuqiEngine()

        assert isinstance(engine.config, EngineConfig)
        assert engine.config.llm.model == "deepseek-chat"
        assert engine.config.performance.target_fps == 30


class TestInitInvalidConfigPath:
    """测试5: 无效路径，优雅降级到默认配置"""

    def test_nonexistent_path_falls_back_to_default(self):
        engine = LuqiEngine(config_path="/nonexistent/path/config.yaml")

        assert isinstance(engine.config, EngineConfig)

    def test_invalid_yaml_syntax_falls_back_to_default(self, tmp_path):
        invalid_yaml = tmp_path / "invalid.yaml"
        invalid_yaml.write_text("key:\n  - item1\n  bad indent: value\n: invalid", encoding="utf-8")

        engine = LuqiEngine(config_path=str(invalid_yaml))

        assert isinstance(engine.config, EngineConfig)


class TestConfigPropertyReadonly:
    """测试6: config 属性返回正确实例"""

    def test_config_returns_engine_config_instance(self):
        engine = LuqiEngine()

        assert isinstance(engine.config, EngineConfig)

    def test_config_returns_same_object(self):
        custom_config = EngineConfig()
        engine = LuqiEngine(config=custom_config)

        assert engine.config is custom_config


class TestConfigPathProperty:
    """测试7: config_path 属性返回正确值"""

    def test_config_path_when_loaded_from_file(self, tmp_path):
        yaml_data = {"llm": {"model": "test"}}
        yaml_file = tmp_path / "path_test.yaml"
        with open(yaml_file, "w", encoding="utf-8") as f:
            yaml.dump(yaml_data, f)

        engine = LuqiEngine(config_path=str(yaml_file))

        assert engine.config_path == str(yaml_file)

    def test_config_path_is_none_when_using_config_object(self):
        custom_config = EngineConfig()
        engine = LuqiEngine(config=custom_config)

        assert engine.config_path is None

    def test_config_path_is_none_when_using_defaults(self):
        engine = LuqiEngine()

        assert engine.config_path is None


class TestInitWithPartialYaml:
    """测试8: 部分 YAML 配置，未提及字段用默认值"""

    def test_partial_yaml_uses_defaults_for_missing_fields(self, tmp_path):
        partial_data = {
            "llm": {"model": "partial-model"},
        }
        yaml_file = tmp_path / "partial.yaml"
        with open(yaml_file, "w", encoding="utf-8") as f:
            yaml.dump(partial_data, f)

        engine = LuqiEngine(config_path=str(yaml_file))

        assert engine.config.llm.model == "partial-model"
        assert engine.config.llm.temperature == 0.7  # 默认值
        assert engine.config.chaos.sigma == 10.0  # 默认值
        assert engine.config.narrative.max_branch_depth == 10  # 默认值
