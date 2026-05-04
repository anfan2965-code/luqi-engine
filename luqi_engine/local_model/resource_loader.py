"""
NLP资源加载器 - 从磁盘加载预训练矩阵
支持内存映射（mmap）和懒加载，与ResourceManager集成
"""

from __future__ import annotations

import json
import struct
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from luqi_engine.core.config import LocalModelConfig
from luqi_engine.core.logging_config import get_logger

try:
    import numpy as np
    _HAS_NUMPY = True
except ImportError:
    _HAS_NUMPY = False

_logger = get_logger(__name__)

_BINARY_HEADER_FORMAT = "<II"
_BINARY_HEADER_SIZE = struct.calcsize(_BINARY_HEADER_FORMAT)
_FLOAT32_SIZE = 4
_FLOAT32_STRUCT = struct.Struct("<f")

_RESOURCE_DIR_NAME = "nlp"
_TFIDF_MATRIX_FILENAME = "tfidf_dense_matrix.bin"
_EMBEDDINGS_FILENAME = "context_embeddings.bin"
_JIEBA_DICT_FILENAME = "jieba_dict.json"
_TFIDF_WEIGHTS_FILENAME = "tfidf_weights.json"
_CLASSIFIER_PARAMS_FILENAME = "classifier_params.json"
_STOPWORDS_FILENAME = "stopwords.json"
_SYNONYM_FOREST_FILENAME = "synonym_forest.json"
_BIGRAM_DICT_FILENAME = "bigram_dict.json"
_SEMANTIC_RELATION_FILENAME = "semantic_relation_matrix.bin"
_VOCAB_TRUNCATION_MAX: int = 100000
_DEFAULT_TOPK_VOCAB_SIZE: int = 100000


class NLPResourceLoader:
    """
    NLP资源加载器
    从config/resources/nlp/加载预训练矩阵、词典、分类器参数
    支持内存映射（移动端友好）和全量加载（服务端）
    """

    def __init__(
        self,
        config: Optional[LocalModelConfig] = None,
        resource_dir: Optional[Path] = None,
    ) -> None:
        self._config = config or LocalModelConfig()
        if resource_dir is not None:
            self._resource_dir = resource_dir
        else:
            self._resource_dir = self._resolve_resource_dir()
        self._vocab: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._dense_matrix: Any = None
        self._embeddings: Any = None
        self._embeddings_vocab: Dict[str, int] = {}
        self._stopwords: set = set()
        self._synonym_forest: Dict[str, List[str]] = {}
        self._bigram_dict: Dict[str, Dict[str, float]] = {}
        self._classifier_params: Dict[str, Any] = {}
        self._dense_matrix_shape: Tuple[int, int] = (0, 0)
        self._embeddings_shape: Tuple[int, int] = (0, 0)
        self._semantic_matrix: Any = None
        self._semantic_matrix_shape: Tuple[int, int] = (0, 0)
        self._dense_loaded: bool = False
        self._embeddings_loaded: bool = False
        self._semantic_loaded: bool = False

    def _resolve_resource_dir(self) -> Path:
        engine_root = Path(__file__).parent.parent.parent
        return engine_root / "config" / "resources" / _RESOURCE_DIR_NAME

    def load_vocabulary(self) -> Dict[str, int]:
        if self._vocab:
            return self._vocab
        dict_path = self._resource_dir / _JIEBA_DICT_FILENAME
        if not dict_path.exists():
            return {}
        with open(dict_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._vocab = {word: idx for idx, word in enumerate(data.keys())}
        return self._vocab

    def load_idf_weights(self) -> Dict[str, float]:
        if self._idf:
            return self._idf
        weights_path = self._resource_dir / _TFIDF_WEIGHTS_FILENAME
        if not weights_path.exists():
            return {}
        with open(weights_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._idf = {}
        for word, value in data.items():
            if isinstance(value, (int, float)):
                self._idf[word] = float(value)
            elif isinstance(value, list) and value:
                self._idf[word] = sum(value) / len(value)
        return self._idf

    def load_dense_matrix(self, use_memmap: bool = True) -> Any:
        if self._dense_loaded and self._dense_matrix is not None:
            return self._dense_matrix
        matrix_path = self._resource_dir / _TFIDF_MATRIX_FILENAME
        if not matrix_path.exists():
            return None
        with open(matrix_path, "rb") as f:
            header = f.read(_BINARY_HEADER_SIZE)
            vocab_size, n_topics = struct.unpack(_BINARY_HEADER_FORMAT, header)
        self._dense_matrix_shape = (vocab_size, n_topics)
        if _HAS_NUMPY:
            if use_memmap:
                self._dense_matrix = np.memmap(
                    matrix_path,
                    dtype=np.float32,
                    mode="r",
                    offset=_BINARY_HEADER_SIZE,
                    shape=(vocab_size, n_topics),
                )
            else:
                with open(matrix_path, "rb") as f:
                    f.seek(_BINARY_HEADER_SIZE)
                    raw = f.read()
                self._dense_matrix = np.frombuffer(
                    raw, dtype=np.float32,
                ).reshape(vocab_size, n_topics).copy()
        else:
            self._dense_matrix = _FallbackMatrix(
                matrix_path, vocab_size, n_topics,
            )
        self._dense_loaded = True
        if self._config.enable_debug_output:
            mode = "memmap" if use_memmap and _HAS_NUMPY else "full"
            _logger.info(
                "TF-IDF dense matrix loaded: %dx%d, mode=%s",
                vocab_size, n_topics, mode,
            )
        return self._dense_matrix

    def load_embeddings(self, use_memmap: bool = True) -> Any:
        if self._embeddings_loaded and self._embeddings is not None:
            return self._embeddings
        embed_path = self._resource_dir / _EMBEDDINGS_FILENAME
        if not embed_path.exists():
            return None
        with open(embed_path, "rb") as f:
            header = f.read(_BINARY_HEADER_SIZE)
            n_entries, dim = struct.unpack(_BINARY_HEADER_FORMAT, header)
        self._embeddings_shape = (n_entries, dim)
        if _HAS_NUMPY:
            if use_memmap:
                self._embeddings = np.memmap(
                    embed_path,
                    dtype=np.float32,
                    mode="r",
                    offset=_BINARY_HEADER_SIZE,
                    shape=(n_entries, dim),
                )
            else:
                with open(embed_path, "rb") as f:
                    f.seek(_BINARY_HEADER_SIZE)
                    raw = f.read()
                self._embeddings = np.frombuffer(
                    raw, dtype=np.float32,
                ).reshape(n_entries, dim).copy()
        else:
            self._embeddings = _FallbackMatrix(
                embed_path, n_entries, dim,
            )
        self._embeddings_loaded = True
        if self._config.enable_debug_output:
            mode = "memmap" if use_memmap and _HAS_NUMPY else "full"
            _logger.info(
                "Context embeddings loaded: %dx%d, mode=%s",
                n_entries, dim, mode,
            )
        return self._embeddings

    def load_semantic_matrix(self, use_memmap: bool = True) -> Any:
        if self._semantic_loaded and self._semantic_matrix is not None:
            return self._semantic_matrix
        matrix_path = self._resource_dir / _SEMANTIC_RELATION_FILENAME
        if not matrix_path.exists():
            return None
        with open(matrix_path, "rb") as f:
            header = f.read(_BINARY_HEADER_SIZE)
            n_concepts, dim = struct.unpack(_BINARY_HEADER_FORMAT, header)
        self._semantic_matrix_shape = (n_concepts, dim)
        if _HAS_NUMPY:
            if use_memmap:
                self._semantic_matrix = np.memmap(
                    matrix_path,
                    dtype=np.float32,
                    mode="r",
                    offset=_BINARY_HEADER_SIZE,
                    shape=(n_concepts, dim),
                )
            else:
                with open(matrix_path, "rb") as f:
                    f.seek(_BINARY_HEADER_SIZE)
                    raw = f.read()
                self._semantic_matrix = np.frombuffer(
                    raw, dtype=np.float32,
                ).reshape(n_concepts, dim).copy()
        else:
            self._semantic_matrix = _FallbackMatrix(
                matrix_path, n_concepts, dim,
            )
        self._semantic_loaded = True
        if self._config.enable_debug_output:
            mode = "memmap" if use_memmap and _HAS_NUMPY else "full"
            _logger.info(
                "Semantic relation matrix loaded: %dx%d, mode=%s",
                n_concepts, dim, mode,
            )
        return self._semantic_matrix

    def find_semantic_neighbors(
        self, concept_index: int, top_k: int = 10,
    ) -> List[Tuple[int, float]]:
        matrix = self.load_semantic_matrix()
        if matrix is None:
            return []
        if concept_index < 0 or concept_index >= self._semantic_matrix_shape[0]:
            return []
        if _HAS_NUMPY and isinstance(matrix, (np.memmap, np.ndarray)):
            query_vec = matrix[concept_index]
            norms = np.linalg.norm(matrix, axis=1)
            query_norm = norms[concept_index]
            if query_norm < 1e-10:
                return []
            similarities = matrix @ query_vec / (norms * query_norm + 1e-10)
            similarities[concept_index] = -1.0
            top_indices = np.argsort(similarities)[-top_k:][::-1]
            return [(int(idx), float(similarities[idx])) for idx in top_indices]
        return []

    def load_stopwords(self) -> set:
        if self._stopwords:
            return self._stopwords
        path = self._resource_dir / _STOPWORDS_FILENAME
        if not path.exists():
            return set()
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        self._stopwords = set(data)
        return self._stopwords

    def load_synonym_forest(self) -> Dict[str, List[str]]:
        if self._synonym_forest:
            return self._synonym_forest
        path = self._resource_dir / _SYNONYM_FOREST_FILENAME
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            self._synonym_forest = json.load(f)
        return self._synonym_forest

    def load_bigram_dict(self) -> Dict[str, Dict[str, float]]:
        if self._bigram_dict:
            return self._bigram_dict
        path = self._resource_dir / _BIGRAM_DICT_FILENAME
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            self._bigram_dict = json.load(f)
        return self._bigram_dict

    def load_classifier_params(self) -> Dict[str, Any]:
        if self._classifier_params:
            return self._classifier_params
        path = self._resource_dir / _CLASSIFIER_PARAMS_FILENAME
        if not path.exists():
            return {}
        with open(path, "r", encoding="utf-8") as f:
            self._classifier_params = json.load(f)
        return self._classifier_params

    def lookup_word_vector(self, word: str) -> Optional[Any]:
        vocab = self.load_vocabulary()
        idx = vocab.get(word)
        if idx is None:
            return None
        matrix = self.load_dense_matrix()
        if matrix is None:
            return None
        if _HAS_NUMPY and isinstance(matrix, np.memmap):
            return matrix[idx].copy()
        if _HAS_NUMPY and isinstance(matrix, np.ndarray):
            return matrix[idx].copy()
        if isinstance(matrix, _FallbackMatrix):
            return matrix.get_row(idx)
        return None

    def compute_semantic_similarity(
        self, word_a: str, word_b: str,
    ) -> float:
        vec_a = self.lookup_word_vector(word_a)
        vec_b = self.lookup_word_vector(word_b)
        if vec_a is not None and vec_b is not None:
            return self._cosine_similarity(vec_a, vec_b)

        fallback = self._fallback_similarity(word_a, word_b)
        if fallback is not None:
            return fallback

        return self._character_overlap_similarity(word_a, word_b)

    @staticmethod
    def _cosine_similarity(vec_a: Any, vec_b: Any) -> float:
        if _HAS_NUMPY:
            norm_a = np.linalg.norm(vec_a)
            norm_b = np.linalg.norm(vec_b)
            if norm_a < 1e-10 or norm_b < 1e-10:
                return 0.0
            return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = sum(a * a for a in vec_a) ** 0.5
        norm_b = sum(b * b for b in vec_b) ** 0.5
        if norm_a < 1e-10 or norm_b < 1e-10:
            return 0.0
        return dot / (norm_a * norm_b)

    def _fallback_similarity(self, word_a: str, word_b: str) -> Optional[float]:
        synonyms = self.load_synonym_forest()
        if not synonyms:
            return None
        for group_key, group_words in synonyms.items():
            a_in = word_a in group_words or word_a == group_key
            b_in = word_b in group_words or word_b == group_key
            if a_in and b_in:
                return 0.8
            if a_in or b_in:
                other = word_b if a_in else word_a
                for syn in (group_words if a_in else [group_key]):
                    if self._character_overlap_similarity(other, syn if isinstance(syn, str) else str(syn)) > 0.3:
                        return 0.5
        return None

    @staticmethod
    def _character_overlap_similarity(word_a: str, word_b: str) -> float:
        if not word_a or not word_b:
            return 0.0
        chars_a = set(word_a)
        chars_b = set(word_b)
        intersection = chars_a & chars_b
        union = chars_a | chars_b
        if not union:
            return 0.0
        jaccard = len(intersection) / len(union)
        len_diff = abs(len(word_a) - len(word_b))
        len_penalty = 1.0 / (1.0 + len_diff * 0.5)
        return jaccard * len_penalty

    def release_dense_matrix(self) -> None:
        if self._dense_matrix is not None:
            if _HAS_NUMPY and isinstance(self._dense_matrix, np.memmap):
                del self._dense_matrix
            self._dense_matrix = None
            self._dense_loaded = False

    def release_embeddings(self) -> None:
        if self._embeddings is not None:
            if _HAS_NUMPY and isinstance(self._embeddings, np.memmap):
                del self._embeddings
            self._embeddings = None
            self._embeddings_loaded = False

    def release_semantic_matrix(self) -> None:
        if self._semantic_matrix is not None:
            if _HAS_NUMPY and isinstance(self._semantic_matrix, np.memmap):
                del self._semantic_matrix
            self._semantic_matrix = None
            self._semantic_loaded = False

    def get_resource_stats(self) -> Dict[str, Any]:
        return {
            "vocab_size": len(self._vocab),
            "idf_size": len(self._idf),
            "stopwords_size": len(self._stopwords),
            "synonym_groups": len(self._synonym_forest),
            "bigram_entries": len(self._bigram_dict),
            "dense_matrix_shape": self._dense_matrix_shape,
            "dense_matrix_loaded": self._dense_loaded,
            "embeddings_shape": self._embeddings_shape,
            "embeddings_loaded": self._embeddings_loaded,
            "semantic_matrix_shape": self._semantic_matrix_shape,
            "semantic_matrix_loaded": self._semantic_loaded,
            "resource_dir": str(self._resource_dir),
        }

    def load_dense_matrix_aligned(self) -> Dict[str, Any]:
        matrix = self.load_dense_matrix(use_memmap=True)
        if matrix is None:
            return {}
        vocab = self.load_vocabulary()
        idf = self.load_idf_weights()
        vocab_size = len(vocab)
        top_k = min(100000, vocab_size) if vocab_size > 0 else 0
        is_memmap = False
        if _HAS_NUMPY:
            import numpy as np
            is_memmap = isinstance(matrix, np.memmap)
        return {
            "matrix": matrix,
            "shape": self._dense_matrix_shape,
            "vocab": vocab,
            "idf": idf,
            "topk_indices": set(range(top_k)),
            "is_memmap": is_memmap,
        }

    def get_topk_vocab_indices(self, k: int = _DEFAULT_TOPK_VOCAB_SIZE) -> Set[int]:
        vocab = self.load_vocabulary()
        vocab_size = len(vocab)
        actual_k = min(k, vocab_size) if vocab_size > 0 else 0
        return set(range(actual_k))

    def get_matrix_stats(self) -> Dict[str, Any]:
        dense_mb = 0.0
        if self._dense_matrix_shape[0] > 0 and self._dense_matrix_shape[1] > 0:
            dense_bytes = self._dense_matrix_shape[0] * self._dense_matrix_shape[1] * _FLOAT32_SIZE
            dense_mb = dense_bytes / (1024.0 * 1024.0)
        embed_mb = 0.0
        if self._embeddings_shape[0] > 0 and self._embeddings_shape[1] > 0:
            embed_bytes = self._embeddings_shape[0] * self._embeddings_shape[1] * _FLOAT32_SIZE
            embed_mb = embed_bytes / (1024.0 * 1024.0)
        semantic_mb = 0.0
        if self._semantic_matrix_shape[0] > 0 and self._semantic_matrix_shape[1] > 0:
            semantic_bytes = self._semantic_matrix_shape[0] * self._semantic_matrix_shape[1] * _FLOAT32_SIZE
            semantic_mb = semantic_bytes / (1024.0 * 1024.0)
        return {
            "dense_matrix_shape": self._dense_matrix_shape,
            "dense_matrix_mb": round(dense_mb, 2),
            "embeddings_shape": self._embeddings_shape,
            "embeddings_mb": round(embed_mb, 2),
            "semantic_matrix_shape": self._semantic_matrix_shape,
            "semantic_matrix_mb": round(semantic_mb, 2),
            "vocab_size": len(self._vocab),
            "idf_size": len(self._idf),
            "has_numpy": _HAS_NUMPY,
        }


class _FallbackMatrix:
    """
    无NumPy时的回退矩阵实现
    按行懒加载，避免全量读入内存
    """

    _ROW_CACHE_MAX: int = 1000

    def __init__(self, path: Path, rows: int, cols: int) -> None:
        self._path = path
        self._rows = rows
        self._cols = cols
        self._cache: Dict[int, List[float]] = {}

    def get_row(self, index: int) -> List[float]:
        if index in self._cache:
            return self._cache[index]
        offset = _BINARY_HEADER_SIZE + index * self._cols * _FLOAT32_SIZE
        row: List[float] = []
        with open(self._path, "rb") as f:
            f.seek(offset)
            for _ in range(self._cols):
                val_bytes = f.read(_FLOAT32_SIZE)
                val = _FLOAT32_STRUCT.unpack(val_bytes)[0]
                row.append(val)
        if len(self._cache) >= self._ROW_CACHE_MAX:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]
        self._cache[index] = row
        return row

    @property
    def shape(self) -> Tuple[int, int]:
        return (self._rows, self._cols)
