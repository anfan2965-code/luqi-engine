"""
ConfigLoader 统一配置文件加载器测试
覆盖所有核心功能：加载、保存、序列化、错误处理
"""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from luqi_engine.core.config import (
    ChaosConfig,
    EngineConfig,
    LLMConfig,
    NarrativeConfig,
)
from luqi_engine.core.config_loader import ConfigLoadError, load_config, save_config


class TestLoadFullYaml:
    """测试1: 加载完整YAML文件"""

    def test_load_full_yaml_all_fields(self, tmp_path):
        full_config = {
            "performance": {"target_fps": 60},
            "llm": {
                "model": "gpt-4",
                "temperature": 0.9,
                "fallback_thresholds": {"degraded": 5},
            },
            "narrative": {"max_branch_depth": 20},
            "chaos": {"sigma": 15.0},
            "debug_mode": True,
        }
        yaml_file = tmp_path / "full_config.yaml"
        with open(yaml_file, "w", encoding="utf-8") as f:
            yaml.dump(full_config, f)

        config = load_config(str(yaml_file))

        assert config.performance.target_fps == 60
        assert config.llm.model == "gpt-4"
        assert config.llm.temperature == 0.9
        assert config.llm.fallback_thresholds["degraded"] == 5
        assert config.narrative.max_branch_depth == 20
        assert config.chaos.sigma == 15.0
        assert config.debug_mode is True


class TestLoadPartialYaml:
    """测试2: 只包含部分节，其他使用默认值"""

    def test_load_partial_yaml_only_llm(self, tmp_path):
        partial_config = {
            "llm": {
                "model": "custom-model",
                "temperature": 0.5,
            }
        }
        yaml_file = tmp_path / "partial.yaml"
        with open(yaml_file, "w", encoding="utf-8") as f:
            yaml.dump(partial_config, f)

        config = load_config(str(yaml_file))

        assert config.llm.model == "custom-model"
        assert config.llm.temperature == 0.5
        assert config.chaos.sigma == 10.0  # 使用默认值
        assert config.scene.max_elements_per_scene == 500  # 使用默认值

    def test_load_partial_yaml_only_narrative(self, tmp_path):
        partial_config = {
            "narrative": {
                "max_branch_depth": 15,
                "elasticity_coefficient": 75.0,
            }
        }
        yaml_file = tmp_path / "partial_narrative.yaml"
        with open(yaml_file, "w", encoding="utf-8") as f:
            yaml.dump(partial_config, f)

        config = load_config(str(yaml_file))

        assert config.narrative.max_branch_depth == 15
        assert config.narrative.elasticity_coefficient == 75.0
        assert config.llm.model in ("deepseek-chat", "qwen2-0.5b-lora-merged")  # 默认值


class TestLoadNonexistentFile:
    """测试3: 文件不存在时返回默认配置（不报错）"""

    def test_load_nonexistent_returns_default(self):
        config = load_config("/nonexistent/path/config.yaml")

        assert isinstance(config, EngineConfig)
        assert config.performance.target_fps == 30
        assert config.llm.model in ("deepseek-chat", "qwen2-0.5b-lora-merged")

    def test_load_none_returns_default(self):
        config = load_config(None)

        assert isinstance(config, EngineConfig)
        assert config.performance.target_fps == 30


class TestLoadInvalidYaml:
    """测试4: 格式错误的YAML抛出 ConfigLoadError"""

    def test_invalid_yaml_syntax(self, tmp_path):
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text(
            "key:\n  - item1\n  bad indent: value\n: invalid",
            encoding="utf-8",
        )

        with pytest.raises(ConfigLoadError) as exc_info:
            load_config(str(yaml_file))

        assert "格式错误" in str(exc_info.value)

    def test_non_dict_root(self, tmp_path):
        yaml_file = tmp_path / "list_root.yaml"
        yaml_file.write_text("- item1\n- item2\n", encoding="utf-8")

        with pytest.raises(ConfigLoadError) as exc_info:
            load_config(str(yaml_file))

        assert "根节点必须是字典" in str(exc_info.value)


class TestSaveAndReload:
    """测试5: save→load 往返一致性"""

    def test_save_and_reload_roundtrip(self, tmp_path):
        original = EngineConfig()
        original.llm.model = "test-model"
        original.llm.temperature = 0.85
        original.chaos.sigma = 12.0
        original.debug_mode = True

        save_path = str(tmp_path / "saved_config.yaml")
        save_config(original, save_path)

        loaded = load_config(save_path)

        assert loaded.llm.model == "test-model"
        assert loaded.llm.temperature == 0.85
        assert loaded.chaos.sigma == 12.0
        assert loaded.debug_mode is True

    def test_save_preserves_defaults(self, tmp_path):
        original = EngineConfig()
        save_path = str(tmp_path / "defaults.yaml")
        save_config(original, save_path)

        loaded = load_config(save_path)

        default_config = EngineConfig()
        assert loaded.to_dict() == default_config.to_dict()


class TestSaveCreatesDirectory:
    """测试6: 目录不存在时自动创建"""

    def test_save_creates_nested_directories(self, tmp_path):
        nested_path = tmp_path / "deep" / "nested" / "dir" / "config.yaml"
        config = EngineConfig()

        save_config(config, str(nested_path))

        assert nested_path.exists()
        loaded = load_config(str(nested_path))
        assert isinstance(loaded, EngineConfig)


class TestFromDictPartial:
    """测试7: from_dict 只接受部分字段"""

    def test_from_dict_partial_fields(self):
        data = {"sigma": 20.0}
        config = ChaosConfig.from_dict(data)

        assert config.sigma == 20.0
        assert config.rho == 28.0  # 默认值
        assert abs(config.beta - 8.0 / 3.0) < 1e-9  # 默认值

    def test_from_dict_ignores_unknown_fields(self):
        data = {"sigma": 15.0, "unknown_field": "should_be_ignored"}
        config = ChaosConfig.from_dict(data)

        assert config.sigma == 15.0
        assert not hasattr(config, "unknown_field")

    def test_from_dict_empty_returns_defaults(self):
        config = LLMConfig.from_dict({})

        assert config.sdk_type == "openai"
        assert config.model == "deepseek-chat"
        assert config.temperature == 0.7


class TestToDictRoundtrip:
    """测试8: to_dict→from_dict 数据一致性"""

    def test_chaos_roundtrip(self):
        original = ChaosConfig(sigma=12.0, rho=30.0, beta=3.0)
        data = original.to_dict()
        restored = ChaosConfig.from_dict(data)

        assert restored.sigma == original.sigma
        assert restored.rho == original.rho
        assert restored.beta == original.beta

    def test_engine_config_roundtrip(self):
        original = EngineConfig()
        original.llm.model = "roundtrip-test"
        original.narrative.max_branch_depth = 99
        original.debug_mode = True

        data = original.to_dict()
        restored = EngineConfig.from_dict(data)

        assert restored.llm.model == original.llm.model
        assert restored.narrative.max_branch_depth == original.narrative.max_branch_depth
        assert restored.debug_mode == original.debug_mode

    def test_to_dict_includes_all_fields(self):
        config = EngineConfig()
        data = config.to_dict()

        expected_keys = {
            "performance",
            "worldview",
            "scene",
            "character",
            "narrative",
            "interaction",
            "llm",
            "local_model",
            "desire",
            "mobile",
            "cognitive_memory",
            "local_llm",
            "chaos",
            "agent",
            "narrative_doc",
            "pace",
            "training",
            "seed",
            "debug_mode",
        }
        assert set(data.keys()) == expected_keys


class TestNestedConfigSerialization:
    """测试9: 嵌套配置(如 fallback_thresholds)正确序列化"""

    def test_fallback_thresholds_serialization(self):
        llm = LLMConfig(fallback_thresholds={"degraded": 10, "offline": 20})
        data = llm.to_dict()

        assert data["fallback_thresholds"]["degraded"] == 10
        assert data["fallback_thresholds"]["offline"] == 20

    def test_fallback_thresholds_deserialization(self):
        data = {"fallback_thresholds": {"severely_degraded": 8, "degraded": 3, "offline": 10}}
        llm = LLMConfig.from_dict(data)

        assert llm.fallback_thresholds["severely_degraded"] == 8
        assert llm.fallback_thresholds["degraded"] == 3
        assert llm.fallback_thresholds["offline"] == 10

    def test_nested_engine_config_roundtrip(self):
        original = EngineConfig()
        original.llm.fallback_thresholds = {"degraded": 7, "severely_degraded": 12}

        data = original.to_dict()
        restored = EngineConfig.from_dict(data)

        assert restored.llm.fallback_thresholds == original.llm.fallback_thresholds


class TestDefaultTemplateValid:
    """测试10: 默认 luqi_engine.yaml 可被正确加载"""

    def test_default_template_loads_successfully(self):
        template_path = Path(__file__).parent.parent / "config" / "luqi_engine.yaml"

        if not template_path.exists():
            pytest.skip("默认模板文件不存在")

        config = load_config(str(template_path))

        assert isinstance(config, EngineConfig)
        assert config.performance.target_fps == 30
        assert config.llm.model in ("deepseek-chat", "qwen2-0.5b-lora-merged")
        assert config.chaos.sigma == 10.0
        assert abs(config.chaos.beta - 2.6666666666666665) < 1e-9

    def test_default_template_all_sections_present(self):
        template_path = Path(__file__).parent.parent / "config" / "luqi_engine.yaml"

        if not template_path.exists():
            pytest.skip("默认模板文件不存在")

        with open(template_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        required_sections = [
            "performance",
            "llm",
            "narrative",
            "chaos",
            "character",
            "scene",
            "interaction",
            "intent_classifier",
        ]

        for section in required_sections:
            assert section in data, f"缺少必需的配置节: {section}"
