"""本地模型管线测试"""

import asyncio
import pytest
from luqi_engine.local_model.pipeline import LocalModelPipeline
from luqi_engine.core.config import LocalModelConfig


class TestLocalModelPipelineCreation:
    def test_default_creation(self):
        pipeline = LocalModelPipeline()
        assert pipeline is not None

    def test_creation_with_config(self):
        cfg = LocalModelConfig(classification_threshold=0.9)
        pipeline = LocalModelPipeline(cfg)
        assert pipeline is not None


class TestLocalModelPipelineTokenize:
    def test_tokenize_text(self):
        pipeline = LocalModelPipeline()
        tokens = asyncio.run(pipeline.tokenize("你好世界"))
        assert tokens is not None
        assert isinstance(tokens, list)

    def test_tokenize_empty_string(self):
        pipeline = LocalModelPipeline()
        tokens = asyncio.run(pipeline.tokenize(""))
        assert tokens == []


class TestLocalModelPipelineClassify:
    def test_classify_basic_input(self):
        pipeline = LocalModelPipeline()
        result = asyncio.run(pipeline.classify({"text": "这是一个测试句子"}))
        assert result is not None
        assert hasattr(result, 'classification') or hasattr(result, 'label')


class TestLocalModelPipelineComponents:
    def test_tokenizer_component(self):
        pipeline = LocalModelPipeline()
        tokenizer = pipeline.tokenizer
        assert tokenizer is not None
