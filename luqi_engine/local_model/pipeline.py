"""
本地模型管线 - ILocalModel接口实现
4层管线：预处理→分词→向量化→分类
支持从预训练资源加载，避免冷启动重新计算
"""

from __future__ import annotations

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
from luqi_engine.local_model.safety_checker import ContextSafetyChecker, SafetyVerdict, SafetyLevel

_logger = get_logger(__name__)


class LocalModelPipeline(ILocalModel):
    _PIPELINE_STAGE_PREPROCESS: ClassVar[str] = "preprocess"
    _PIPELINE_STAGE_TOKENIZE: ClassVar[str] = "tokenize"
    _PIPELINE_STAGE_VECTORIZE: ClassVar[str] = "vectorize"
    _PIPELINE_STAGE_CLASSIFY: ClassVar[str] = "classify"
    _PIPELINE_STAGE_SAFETY: ClassVar[str] = "safety"
    _CLASSIFICATION_KEY: ClassVar[str] = "_classification"
    _CLASSIFICATION_CONFIDENCE_KEY: ClassVar[str] = "_classification_confidence"
    _SAFETY_VERDICT_KEY: ClassVar[str] = "_safety_verdict"
    _DEFAULT_TEXT_FIELD: ClassVar[str] = "text"

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
        self._corrector = ContentCorrector(self._config)
        self._exporter = TrainingDataExporter(self._config)
        self._safety_checker = ContextSafetyChecker(self._config)
        self._validation_errors: List[Dict[str, Any]] = []

    async def preprocess(self, text: str) -> str:
        result = await self._preprocessor.process(text)
        if not self._preprocessor.validate_output(result):
            self._record_validation_error(
                self._PIPELINE_STAGE_PREPROCESS,
                f"Output validation failed: empty or too short (length={len(result)})",
            )
        return result

    async def tokenize(self, text: str) -> List[str]:
        result = await self._tokenizer.tokenize(text)
        if not self._tokenizer.validate_output(result):
            self._record_validation_error(
                self._PIPELINE_STAGE_TOKENIZE,
                f"Output validation failed: no valid tokens (count={len(result)})",
            )
        return result

    async def vectorize(self, tokens: List[str]) -> Any:
        result = await self._vectorizer.transform(tokens)
        if not self._vectorizer.validate_output(result):
            self._record_validation_error(
                self._PIPELINE_STAGE_VECTORIZE,
                f"Output validation failed: invalid vector (dims={len(result)})",
            )
        return result

    async def classify(self, vector: Any) -> LocalModelOutput:
        if not isinstance(vector, dict):
            self._record_validation_error(
                self._PIPELINE_STAGE_CLASSIFY,
                f"Input validation failed: expected dict, got {type(vector).__name__}",
            )
            return LocalModelOutput(
                classification=ContentClassifier._DEFAULT_CATEGORY,
                confidence=ContentClassifier._MIN_CONFIDENCE,
            )

        result = await self._classifier.classify(vector)
        if not self._classifier.validate_output(result):
            self._record_validation_error(
                self._PIPELINE_STAGE_CLASSIFY,
                f"Output validation failed: classification={result.classification}, "
                f"confidence={result.confidence}",
            )
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
                correction_suggestions=["预处理后文本为空，无法继续分类"],
            )

        tokens = await self.tokenize(preprocessed)
        if not tokens:
            return LocalModelOutput(
                classification=ContentClassifier._DEFAULT_CATEGORY,
                confidence=ContentClassifier._MIN_CONFIDENCE,
                correction_suggestions=["分词后无有效token，无法继续分类"],
            )

        vector = await self.vectorize(tokens)
        if not vector:
            return LocalModelOutput(
                classification=ContentClassifier._DEFAULT_CATEGORY,
                confidence=ContentClassifier._MIN_CONFIDENCE,
                correction_suggestions=["向量化结果为空，无法继续分类"],
            )

        result = await self.classify(vector)

        safety_verdict = self._safety_checker.check(text)
        if not safety_verdict.is_safe:
            result.correction_suggestions = result.correction_suggestions or []
            result.correction_suggestions.append(
                f"安全审核: {safety_verdict.level.value}, "
                f"类别={safety_verdict.category.value}, "
                f"风险={safety_verdict.confidence:.2f}"
            )
            for factor in safety_verdict.risk_factors:
                result.correction_suggestions.append(f"  风险因素: {factor}")

        if self._config.enable_debug_output:
            safety_info = f", safety={safety_verdict.level.value}" if not safety_verdict.is_safe else ""
            _logger.debug(
                "pipeline complete: text_len=%d -> preprocessed_len=%d -> "
                "tokens=%d -> vector_dims=%d -> classification=%s, confidence=%.4f%s",
                len(text), len(preprocessed), len(tokens), len(vector),
                result.classification, result.confidence, safety_info,
            )

        return result

    async def run_full_correction(
        self,
        content: Dict[str, Any],
        text_field: str = _DEFAULT_TEXT_FIELD,
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

            corrected[self._CLASSIFICATION_KEY] = classification_result.classification
            corrected[self._CLASSIFICATION_CONFIDENCE_KEY] = classification_result.confidence

        return corrected

    def compute_semantic_similarity(self, word_a: str, word_b: str) -> float:
        return self._resource_loader.compute_semantic_similarity(word_a, word_b)

    def get_resource_stats(self) -> Dict[str, Any]:
        return self._resource_loader.get_resource_stats()

    def _record_validation_error(self, stage: str, message: str) -> None:
        error_entry = {
            "stage": stage,
            "message": message,
        }
        self._validation_errors.append(error_entry)
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
    def exporter(self) -> TrainingDataExporter:
        return self._exporter

    @property
    def resource_loader(self) -> NLPResourceLoader:
        return self._resource_loader

    @property
    def safety_checker(self) -> ContextSafetyChecker:
        return self._safety_checker
