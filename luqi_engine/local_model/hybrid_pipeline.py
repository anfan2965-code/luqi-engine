"""
HybridLocalModelPipeline - 混合本地模型流水线
结合TF-IDF规则模型(分类+安全) + BGE语义引擎(纠正/一致性)

架构:
  输入文本
    ├── TF-IDF Pipeline: 预处理→分词→向量化→ContentClassifier(19类)→ContextSafetyChecker(4级)
    └── BGE Semantic Engine: 一致性检测→重复检测→OOC检测→语义漂移监控

对外接口与LocalModelPipeline完全兼容
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional

from luqi_engine.core.config import LocalModelConfig
from luqi_engine.core.interfaces import ILocalModel
from luqi_engine.core.logging_config import get_logger
from luqi_engine.core.types import LocalModelOutput

from luqi_engine.local_model.classifier import ContentClassifier
from luqi_engine.local_model.corrector import ContentCorrector
from luqi_engine.local_model.data_exporter import TrainingDataExporter
from luqi_engine.local_model.preprocessor import TextPreprocessor
from luqi_engine.local_model.tokenizer import CustomTokenizer
from luqi_engine.local_model.vectorizer import TFIDFVectorizer
from luqi_engine.local_model.resource_loader import NLPResourceLoader
from luqi_engine.local_model.safety_checker import ContextSafetyChecker

try:
    from luqi_engine.local_model.semantic_vectorizer import BGESemanticEngine
    _HAS_BGE_ENGINE = True
except ImportError:
    _HAS_BGE_ENGINE = False

_logger = get_logger(__name__)

_ENV_SITE = str(Path(__file__).parent.parent / "env" / "Lib" / "site-packages")
if os.path.isdir(_ENV_SITE) and _ENV_SITE not in sys.path:
    sys.path.insert(0, _ENV_SITE)


class HybridLocalModelPipeline(ILocalModel):
    _HYBRID_STAGES: ClassVar[List[str]] = [
        "preprocess", "tokenize", "vectorize", "classify", "safety", "semantic"
    ]

    def __init__(
        self,
        config: LocalModelConfig | None = None,
        resource_loader: Optional[NLPResourceLoader] = None,
    ) -> None:
        self._config = config or LocalModelConfig()
        self._resource_loader = resource_loader or NLPResourceLoader(self._config)

        self._preprocessor = TextPreprocessor(self._config)
        self._tokenizer = CustomTokenizer(self._config)
        self._vectorizer = TFIDFVectorizer(self._config, self._resource_loader)

        self._classifier = ContentClassifier(
            self._config,
            vectorizer=self._vectorizer,
            resource_loader=self._resource_loader,
        )

        self._bge_engine: Any = None
        if _HAS_BGE_ENGINE:
            try:
                self._bge_engine = BGESemanticEngine(config=self._config)
                if self._bge_engine.is_initialized:
                    _logger.info(
                        "BGESemanticEngine initialized: "
                        "model=%s, dim=%s",
                        self._bge_engine.model_name,
                        self._bge_engine.vector_dimension,
                    )
            except Exception as e:
                _logger.error("BGESemanticEngine initialization failed: %s", e)
                self._bge_engine = None

        self._corrector = ContentCorrector(
            self._config, semantic_engine=self._bge_engine
        )
        self._exporter = TrainingDataExporter(self._config)
        self._safety_checker = ContextSafetyChecker(self._config)

        self._validation_errors: List[Dict[str, Any]] = []

    async def preprocess(self, text: str) -> str:
        result = await self._preprocessor.process(text)
        if not self._preprocessor.validate_output(result):
            self._record_validation_error("preprocess", f"empty or too short (len={len(result)})")
        return result

    async def tokenize(self, text: str) -> List[str]:
        result = await self._tokenizer.tokenize(text)
        if not self._tokenizer.validate_output(result):
            self._record_validation_error("tokenize", f"no valid tokens (count={len(result)})")
        return result

    async def vectorize(self, tokens: List[str]) -> Any:
        result = await self._vectorizer.transform(tokens)
        if not self._vectorizer.validate_output(result):
            self._record_validation_error("vectorize", f"invalid vector")
        return result

    async def classify(self, vector: Any) -> LocalModelOutput:
        if not isinstance(vector, dict):
            self._record_validation_error("classify", f"expected dict, got {type(vector).__name__}")
            return LocalModelOutput(
                classification=ContentClassifier._DEFAULT_CATEGORY,
                confidence=ContentClassifier._MIN_CONFIDENCE,
            )
        result = await self._classifier.classify(vector)
        if not self._classifier.validate_output(result):
            self._record_validation_error("classify", f"validation failed: {result.classification}")
        return result

    async def correct(self, content: Dict[str, Any]) -> Dict[str, Any]:
        return await self._corrector.correct(content)

    async def export_training_data(self, since: float) -> List[Dict[str, Any]]:
        return await self._exporter.export(since)

    async def run_pipeline(self, text: str) -> LocalModelOutput:
        preprocessed = await self.preprocess(text)
        if not preprocessed:
            return LocalModelOutput(
                classification=ContentClassifier._DEFAULT_CATEGORY,
                confidence=ContentClassifier._MIN_CONFIDENCE,
                correction_suggestions=["预处理后文本为空"],
            )

        tokens = await self.tokenize(preprocessed)
        if not tokens:
            return LocalModelOutput(
                classification=ContentClassifier._DEFAULT_CATEGORY,
                confidence=ContentClassifier._MIN_CONFIDENCE,
                correction_suggestions=["分词后无有效token"],
            )

        vector = await self.vectorize(tokens)
        result = await self.classify(vector)

        safety_verdict = self._safety_checker.check(text)
        correction_suggestions = []
        if not safety_verdict.is_safe:
            correction_suggestions.append(
                f"安全审核: {safety_verdict.level.value}, "
                f"类别={safety_verdict.category.value}, "
                f"风险={safety_verdict.confidence:.2f}"
            )
            for factor in safety_verdict.risk_factors:
                correction_suggestions.append(f"  风险因素: {factor}")

        if correction_suggestions:
            result.correction_suggestions = correction_suggestions

        if self._config.enable_debug_output:
            info = f"classify={result.classification}({result.confidence:.3f})"
            info += f" safety={safety_verdict.level.value}"
            if self.is_bge_available:
                info += f" bge=ready"
            _logger.debug("%s", info)

        return result

    async def run_full_correction(
        self,
        content: Dict[str, Any],
        text_field: str = "text",
    ) -> Dict[str, Any]:
        corrected = await self.correct(content)
        text_value = corrected.get(text_field, "")
        if text_value and isinstance(text_value, str):
            classification_result = await self.run_pipeline(text_value)
            corrections = corrected.get(ContentCorrector._REPAIR_KEY_CORRECTIONS, [])
            self._exporter.add_correction_case(
                original_content=content,
                corrected_content=corrected,
                classification=classification_result.classification,
                confidence=classification_result.confidence,
                corrections=corrections,
            )
            corrected["_classification"] = classification_result.classification
            corrected["_classification_confidence"] = classification_result.confidence
        return corrected

    def compute_semantic_similarity(self, word_a: str, word_b: str) -> float:
        return self._resource_loader.compute_semantic_similarity(word_a, word_b)

    def get_resource_stats(self) -> Dict[str, Any]:
        stats = self._resource_loader.get_resource_stats()
        stats["bge_available"] = self.is_bge_available
        if self.is_bge_available:
            stats["bge_model"] = self._bge_engine.model_name
            stats["bge_vector_dim"] = self._bge_engine.vector_dimension
        return stats

    def _record_validation_error(self, stage: str, message: str) -> None:
        self._validation_errors.append({"stage": stage, "message": message})
        _logger.warning("Validation error at %s: %s", stage, message)

    def get_validation_errors(self) -> List[Dict[str, Any]]:
        return list(self._validation_errors)

    def clear_validation_errors(self) -> None:
        self._validation_errors.clear()

    @property
    def preprocessor(self) -> TextPreprocessor:
        return self._preprocessor

    @property
    def tokenizer(self) -> CustomTokenizer:
        return self._tokenizer

    @property
    def vectorizer(self) -> TFIDFVectorizer:
        return self._vectorizer

    @property
    def classifier_instance(self) -> ContentClassifier:
        return self._classifier

    @property
    def corrector(self) -> ContentCorrector:
        return self._corrector

    @property
    def resource_loader(self) -> NLPResourceLoader:
        return self._resource_loader

    @property
    def safety_checker(self) -> ContextSafetyChecker:
        return self._safety_checker

    @property
    def bge_engine(self) -> Any:
        return self._bge_engine

    @property
    def is_bge_available(self) -> bool:
        return self._bge_engine is not None and self._bge_engine.is_initialized
