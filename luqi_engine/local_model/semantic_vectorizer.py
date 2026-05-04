"""
BGE语义嵌入引擎 - 基于bge-small-zh-v1.5的文本向量化和语义比较
解决TF-IDF密集矩阵方案的根本缺陷：相似度分布不合理、无法区分无关文本

技术选型依据:
  模型: BAAI/bge-small-zh-v1.5 (北京智源人工智能研究院)
  参数: ~33M, 输出维度: 512, 模型大小: ~95MB(ONNX)
  推理: 80-120ms/句(CPU), 内存: ~180MB峰值
  中文MTEB: 61.8分 (STS任务49.11分，检索61.77分)
  核心优势: v1.5版本修复了相似度集中在[0.6,1]的问题

架构:
  文本 → BGE编码器 → 512维归一化向量 → 余弦相似度比较
       ├─ check_consistency()    → 角色OOC/世界观矛盾检测
       ├─ detect_repetition()   → 重复/近似内容检测
       └─ find_semantic_drift() → 语义漂移监控

用法:
  engine = BGESemanticEngine(model_name="BAAI/bge-small-zh-v1.5")
  vec_a = engine.encode("角色性格坚毅果敢")
  vec_b = engine.encode("他低下头颤抖着说不敢")
  sim = engine.similarity(vec_a, vec_b)  # 应该 < 0.3 (低相似度)
"""

from __future__ import annotations

import os
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.config import LocalModelConfig
from luqi_engine.core.logging_config import get_logger

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

_logger = get_logger(__name__)


@dataclass
class SimilarityResult:
    similarity: float = 0.0
    is_consistent: bool = True
    confidence: float = 0.0
    drift_score: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RepetitionMatch:
    index: int = 0
    similarity: float = 0.0
    is_duplicate: bool = False
    overlap_type: str = ""


@dataclass
class ConsistencyReport:
    is_consistent: bool = True
    consistency_score: float = 1.0
    drift_magnitude: float = 0.0
    contradictions: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestion: str = ""


class BGESemanticEngine:
    _DEFAULT_MODEL: ClassVar[str] = "BAAI/bge-small-zh-v1.5"
    _FALLBACK_MODEL: ClassVar[str] = "shibing624/text2vec-base-chinese"
    _VECTOR_DIM: ClassVar[int] = 512
    _COSINE_EPSILON: ClassVar[float] = 1e-10
    _L2_EPSILON: ClassVar[float] = 1e-10

    _CONSISTENCY_STRONG: ClassVar[float] = 0.65
    _CONSISTENCY_WEAK: ClassVar[float] = 0.30
    _DRIFT_WARNING: ClassVar[float] = 0.30

    _DUPLICATE_THRESHOLD: ClassVar[float] = 0.92
    _NEAR_DUPLICATE_THRESHOLD: ClassVar[float] = 0.80
    _IRRELEVANT_CEILING: ClassVar[float] = 0.30

    _MAX_CACHE_SIZE: ClassVar[int] = 500
    _MODEL_INIT_TIMEOUT: ClassVar[float] = 60.0
    _CACHE_KEY_PREFIX_LENGTH: ClassVar[int] = 200

    _HF_CACHE_SUBDIR: ClassVar[str] = "_hf_cache"
    _TMP_SUBDIR: ClassVar[str] = "_tmp"

    @classmethod
    def _resolve_project_root(cls) -> str:
        current = Path(__file__).resolve()
        for parent in current.parents:
            if (parent / "luqi_engine").is_dir() and (parent / "config").is_dir():
                return str(parent)
        return str(current.parent.parent.parent)

    def __init__(
        self,
        model_name: Optional[str] = None,
        config: Optional[LocalModelConfig] = None,
        cache_size: int = _MAX_CACHE_SIZE,
        model_dir: Optional[Path] = None,
    ) -> None:
        self._model_name = model_name or self._DEFAULT_MODEL
        self._config = config or LocalModelConfig()
        self._cache_size = cache_size
        self._model_dir = model_dir

        self._ensure_hf_cache_on_g_drive()

        self._model: Any = None
        self._tokenizer: Any = None
        self._vector_dim: int = self._VECTOR_DIM
        self._encode_fn: Any = None

        self._vector_cache: OrderedDict[str, np.ndarray] = OrderedDict()

        self._is_initialized: bool = False
        self._init_error: Optional[str] = None
        self._init_duration: float = 0.0
        self._model_info: Dict[str, Any] = {}

        self._initialize_model()

    @classmethod
    def _ensure_hf_cache_on_g_drive(cls) -> None:
        if os.environ.get("HF_HOME"):
            return
        project_root = cls._resolve_project_root()
        hf_cache = os.path.join(project_root, cls._HF_CACHE_SUBDIR)
        tmp_dir = os.path.join(project_root, cls._TMP_SUBDIR)
        os.makedirs(hf_cache, exist_ok=True)
        os.makedirs(tmp_dir, exist_ok=True)
        os.environ["HF_HOME"] = hf_cache
        os.environ["TRANSFORMERS_CACHE"] = os.path.join(hf_cache, "transformers")
        os.environ["TMP"] = tmp_dir
        os.environ["TEMP"] = tmp_dir

    def _initialize_model(self) -> None:
        start_time = time.time()
        try:
            self._try_load_sentence_transformers()
            if self._model is not None:
                self._is_initialized = True
                self._init_duration = time.time() - start_time
                _logger.info(
                    "BGESemanticEngine initialized: model=%s, dim=%d, duration=%.1fs, info=%s",
                    self._model_name, self._vector_dim, self._init_duration, self._model_info,
                )
                return

            self._try_load_flag_embedding()
            if self._model is not None:
                self._is_initialized = True
                self._init_duration = time.time() - start_time
                _logger.info(
                    "FlagEmbedding fallback initialized: duration=%.1fs",
                    self._init_duration,
                )
                return

            self._init_error = "所有加载方式均失败(sentence-transformers/FlagEmbedding均不可用)"

        except Exception as e:
            self._init_error = str(e)
            _logger.error("BGESemanticEngine initialization failed: %s", e)

    def _try_load_sentence_transformers(self) -> None:
        try:
            from sentence_transformers import SentenceTransformer

            if self._model_dir and self._model_dir.exists():
                local_path = str(self._model_dir / self._model_name.replace("/", "_"))
                if Path(local_path).exists():
                    self._model = SentenceTransformer(local_path)
                else:
                    self._model = SentenceTransformer(str(self._model_dir))
            else:
                self._model = SentenceTransformer(self._model_name)

            self._encode_fn = self._model.encode
            dim_fn = getattr(self._model, 'get_embedding_dimension', None) or getattr(self._model, 'get_sentence_embedding_dimension', None)
            if dim_fn:
                self._vector_dim = dim_fn()
            self._model_info = {
                "backend": "sentence-transformers",
                "max_seq_length": getattr(self._model, 'max_seq_length', 512),
                "model_name": self._model_name,
            }
        except ImportError:
            pass
        except Exception as e:
            _logger.warning("sentence-transformers loading failed: %s", e)

    def _try_load_flag_embedding(self) -> None:
        try:
            from FlagEmbedding import FlagModel

            use_fp16 = True
            self._model = FlagModel(
                self._model_name,
                query_instruction_for_retrieval="",
                use_fp16=use_fp16,
            )

            def flag_encode(texts, **kwargs):
                if isinstance(texts, str):
                    texts = [texts]
                embeddings = self._model.encode(texts)
                if hasattr(embeddings, 'astype'):
                    embeddings = np.array(embeddings, dtype=np.float32)
                norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
                norms = np.where(norms > self._L2_EPSILON, norms, 1.0)
                return (embeddings / norms).squeeze()

            self._encode_fn = flag_encode
            self._vector_dim = 512
            self._model_info = {
                "backend": "FlagEmbedding",
                "model_name": self._model_name,
                "use_fp16": use_fp16,
            }

        except ImportError:
            pass
        except Exception as e:
            _logger.warning("FlagEmbedding loading failed: %s", e)

    def encode(self, text: str) -> np.ndarray:
        if not self._is_initialized or self._encode_fn is None:
            return np.zeros(self._vector_dim, dtype=np.float32)

        cache_key = text[:200]
        cached = self._vector_cache.get(cache_key)
        if cached is not None:
            return cached.copy()

        try:
            result = self._encode_fn(text)
            if result.ndim > 1:
                result = result.flatten()

            norm = np.linalg.norm(result)
            if norm > self._L2_EPSILON:
                result = result / norm

            result = np.asarray(result, dtype=np.float32)
            self._cache_vector(cache_key, result)
            return result
        except Exception as e:
            _logger.error("Encoding failed: %s", e)
            return np.zeros(self._vector_dim, dtype=np.float32)

    def encode_batch(self, texts: List[str]) -> np.ndarray:
        if not texts or not self._is_initialized or self._encode_fn is None:
            return np.zeros((len(texts), self._vector_dim), dtype=np.float32)

        uncached_texts = []
        uncached_indices = []
        results = np.zeros((len(texts), self._vector_dim), dtype=np.float32)

        for i, text in enumerate(texts):
            cache_key = text[:200]
            cached = self._vector_cache.get(cache_key)
            if cached is not None:
                results[i] = cached
            else:
                uncached_texts.append(text)
                uncached_indices.append(i)

        if uncached_texts:
            try:
                batch_result = self._encode_fn(uncached_texts)
                if batch_result.ndim == 1:
                    batch_result = batch_result.reshape(1, -1)

                for j, idx in enumerate(uncached_indices):
                    vec = batch_result[j]
                    norm = np.linalg.norm(vec)
                    if norm > self._L2_EPSILON:
                        vec = vec / norm
                    results[idx] = np.asarray(vec, dtype=np.float32)
                    cache_key = uncached_texts[j][:self._CACHE_KEY_PREFIX_LENGTH]
                    self._cache_vector(cache_key, results[idx])

            except Exception as e:
                _logger.error("Batch encoding failed: %s", e)

        return results

    @staticmethod
    def similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
        if not _HAS_NUMPY:
            return 0.0
        norm_a = np.linalg.norm(vec_a)
        norm_b = np.linalg.norm(vec_b)
        if norm_a < 1e-10 or norm_b < 1e-10:
            return 0.0
        dot = float(np.dot(vec_a, vec_b))
        return max(0.0, min(1.0, dot / (norm_a * norm_b)))

    _MIN_TEXT_LENGTH_FOR_ENCODING: ClassVar[int] = 6
    _SHORT_TEXT_BOOST: ClassVar[float] = 0.15

    def check_consistency(
        self,
        reference_text: str,
        candidate_text: str,
        context_label: str = "",
    ) -> ConsistencyReport:
        ref_vec = self.encode(reference_text)
        cand_vec = self.encode(candidate_text)

        sim = self.similarity(ref_vec, cand_vec)

        ref_is_short = len(reference_text) < self._MIN_TEXT_LENGTH_FOR_ENCODING
        cand_is_short = len(candidate_text) < self._MIN_TEXT_LENGTH_FOR_ENCODING
        if ref_is_short or cand_is_short:
            sim = min(1.0, sim + self._SHORT_TEXT_BOOST)

        drift = 1.0 - sim

        is_consistent = sim >= self._CONSISTENCY_WEAK
        contradictions: List[str] = []
        warnings: List[str] = []
        suggestion = ""

        if sim < self._CONSISTENCY_WEAK:
            label_prefix = f"[{context_label}] " if context_label else ""
            contradictions.append(f"{label_prefix}与参考内容显著偏离(相似度={sim:.3f})")
            suggestion = "建议LLM重新审视此内容的合理性"

        elif sim < self._CONSISTENCY_STRONG:
            label_prefix = f"[{context_label}] " if context_label else ""
            warnings.append(f"{label_prefix}与参考内容存在一定偏差(相似度={sim:.3f})")
            suggestion = "可接受但建议关注后续发展"

        elif drift > self._DRIFT_WARNING and len(warnings) == 0:
            warnings.append(f"检测到轻微语义漂移(漂移度={drift:.3f})")

        return ConsistencyReport(
            is_consistent=is_consistent,
            consistency_score=sim,
            drift_magnitude=drift,
            contradictions=contradictions,
            warnings=warnings,
            suggestion=suggestion,
        )

    def detect_repetition(
        self,
        new_text: str,
        existing_texts: List[Tuple[str, str]],
        threshold: Optional[float] = None,
    ) -> List[RepetitionMatch]:
        dup_threshold = threshold or self._DUPLICATE_THRESHOLD
        near_dup_threshold = threshold or self._NEAR_DUPLICATE_THRESHOLD

        new_vec = self.encode(new_text)
        matches: List[RepetitionMatch] = []

        for idx, (label, existing_text) in enumerate(existing_texts):
            existing_vec = self.encode(existing_text)
            sim = self.similarity(new_vec, existing_vec)

            is_duplicate = sim >= dup_threshold
            overlap_type = "duplicate" if is_duplicate else ("near_duplicate" if sim >= near_dup_threshold else "")

            if sim >= near_dup_threshold:
                matches.append(RepetitionMatch(
                    index=idx,
                    similarity=sim,
                    is_duplicate=is_duplicate,
                    overlap_type=overlap_type,
                ))

        matches.sort(key=lambda m: m.similarity, reverse=True)
        return matches

    _DRIFT_CONSISTENT_THRESHOLD: ClassVar[float] = 0.50
    _DRIFT_SEVERE_THRESHOLD: ClassVar[float] = 0.35

    def find_semantic_drift(
        self,
        original_text: str,
        evolved_text: str,
        history_texts: Optional[List[str]] = None,
    ) -> SimilarityResult:
        orig_vec = self.encode(original_text)
        evolved_vec = self.encode(evolved_text)

        sim = self.similarity(orig_vec, evolved_vec)
        drift = 1.0 - sim

        is_consistent = sim >= self._DRIFT_CONSISTENT_THRESHOLD
        confidence = min(sim, 1.0 - drift * 0.5)

        trend = 0.0
        if history_texts and len(history_texts) >= 2:
            orig_vec_cached = orig_vec
            recent_sims = [
                self.similarity(orig_vec_cached, self.encode(t))
                for t in history_texts[-5:]
            ]
            if len(recent_sims) >= 2:
                trend = recent_sims[-1] - recent_sims[0]

        return SimilarityResult(
            similarity=sim,
            is_consistent=is_consistent,
            confidence=confidence,
            drift_score=drift,
            details={
                "trend": round(trend, 4),
                "history_points": len(history_texts) if history_texts else 0,
                "severity": "severe" if sim < self._DRIFT_SEVERE_THRESHOLD else (
                    "moderate" if sim < self._DRIFT_CONSISTENT_THRESHOLD else "stable"
                ),
            },
        )

    def find_most_similar(
        self,
        query_text: str,
        candidate_texts: List[str],
        top_k: int = 5,
    ) -> List[Tuple[int, float]]:
        query_vec = self.encode(query_text)
        cand_vecs = self.encode_batch(candidate_texts)

        similarities: List[Tuple[int, float]] = []
        for i, cand_vec in enumerate(cand_vecs):
            sim = self.similarity(query_vec, cand_vec)
            similarities.append((i, sim))

        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def _cache_vector(self, key: str, vector: np.ndarray) -> None:
        if len(self._vector_cache) >= self._cache_size:
            self._vector_cache.popitem(last=False)
        self._vector_cache[key] = vector.copy()

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized

    @property
    def initialization_error(self) -> Optional[str]:
        return self._init_error

    @property
    def vector_dimension(self) -> int:
        return self._vector_dim

    @property
    def model_name(self) -> str:
        return self._model_name

    @property
    def initialization_duration(self) -> float:
        return self._init_duration

    def get_stats(self) -> Dict[str, Any]:
        return {
            "is_initialized": self._is_initialized,
            "model_name": self._model_name,
            "vector_dim": self._vector_dim,
            "cache_size": len(self._vector_cache),
            "max_cache_size": self._cache_size,
            "init_duration": self._init_duration,
            "model_info": self._model_info,
            "has_error": self._init_error is not None,
        }

    def clear_cache(self) -> None:
        self._vector_cache.clear()
