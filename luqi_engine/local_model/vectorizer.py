"""
TF-IDF向量化器
支持从预训练资源加载词汇表和IDF权重，避免冷启动重新计算
"""

from __future__ import annotations

import math
from typing import ClassVar, Dict, List, Optional, Set

from luqi_engine.core.config import LocalModelConfig
from luqi_engine.core.logging_config import get_logger

_logger = get_logger(__name__)


class TFIDFVectorizer:
    _IDF_SMOOTH_ADDEND: ClassVar[float] = 1.0
    _L2_NORM_ZERO_THRESHOLD: ClassVar[float] = 1e-10
    _L2_NORM_EXPECTED: ClassVar[float] = 1.0
    _L2_NORM_TOLERANCE: ClassVar[float] = 1e-4
    _DEFAULT_MAX_FEATURES: ClassVar[int] = 5000
    _DEFAULT_MIN_DF: ClassVar[int] = 1
    _UNSEEN_TERM_IDF_DEFAULT: ClassVar[float] = 1.0

    def __init__(
        self,
        config: LocalModelConfig | None = None,
        resource_loader: Optional[Any] = None,
    ) -> None:
        self._config = config or LocalModelConfig()
        self._resource_loader = resource_loader
        self._vocab: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._doc_freq: Dict[str, int] = {}
        self._n_docs: int = 0
        self._is_fitted: bool = False
        self._is_pretrained: bool = False
        self._max_features: int = self._DEFAULT_MAX_FEATURES
        self._min_df: int = self._DEFAULT_MIN_DF
        self._stopwords: Set[str] = set()
        self._bigram_dict: Dict[str, Dict[str, float]] = {}
        if self._resource_loader is not None:
            self._try_load_pretrained()

    def _try_load_pretrained(self) -> None:
        if self._resource_loader is None:
            return
        vocab = self._resource_loader.load_vocabulary()
        idf = self._resource_loader.load_idf_weights()
        stopwords = self._resource_loader.load_stopwords()
        bigram = self._resource_loader.load_bigram_dict()
        if vocab and idf:
            self._vocab = vocab
            self._idf = idf
            self._n_docs = max(len(vocab), 1)
            self._is_fitted = True
            self._is_pretrained = True
        if stopwords:
            self._stopwords = stopwords
        if bigram:
            self._bigram_dict = bigram
        if self._config.enable_debug_output:
            source = "pretrained" if self._is_pretrained else "empty"
            _logger.info(
                "Initialized from %s, vocab_size=%d, idf_size=%d, stopwords=%d, bigram=%d",
                source, len(self._vocab), len(self._idf),
                len(self._stopwords), len(self._bigram_dict),
            )

    @property
    def vocabulary_size(self) -> int:
        return len(self._vocab)

    @property
    def is_fitted(self) -> bool:
        return self._is_fitted

    @property
    def is_pretrained(self) -> bool:
        return self._is_pretrained

    @property
    def stopwords(self) -> Set[str]:
        return self._stopwords

    def fit(self, documents: List[List[str]]) -> None:
        if not documents:
            self._is_fitted = True
            return

        self._n_docs = len(documents)
        self._doc_freq = {}
        all_terms: Set[str] = set()

        for doc in documents:
            unique_terms = set(doc)
            for term in unique_terms:
                self._doc_freq[term] = self._doc_freq.get(term, 0) + 1
            all_terms.update(unique_terms)

        filtered_terms = [
            term for term in all_terms
            if self._doc_freq.get(term, 0) >= self._min_df
        ]

        if len(filtered_terms) > self._max_features:
            sorted_terms = sorted(
                filtered_terms,
                key=lambda t: self._doc_freq.get(t, 0),
                reverse=True,
            )
            filtered_terms = sorted_terms[:self._max_features]

        self._vocab = {term: idx for idx, term in enumerate(sorted(filtered_terms))}
        self._idf = {}
        for term in self._vocab:
            df = self._doc_freq.get(term, 0)
            self._idf[term] = math.log(
                (self._IDF_SMOOTH_ADDEND + self._n_docs)
                / (self._IDF_SMOOTH_ADDEND + df)
            ) + self._IDF_SMOOTH_ADDEND

        self._is_fitted = True
        self._is_pretrained = False

        if self._config.enable_debug_output:
            _logger.info("fit complete: n_docs=%d, vocab_size=%d", self._n_docs, len(self._vocab))

    async def transform(self, tokens: List[str]) -> Dict[str, float]:
        if not self._is_fitted:
            raise RuntimeError("TFIDFVectorizer must be fitted before transform. Call fit() first.")

        if not tokens:
            return {}

        filtered = [t for t in tokens if t not in self._stopwords] if self._stopwords else tokens
        if not filtered:
            filtered = tokens

        tf_counts: Dict[str, int] = {}
        for token in filtered:
            tf_counts[token] = tf_counts.get(token, 0) + 1

        total_terms = len(filtered)
        tfidf: Dict[str, float] = {}
        for term, count in tf_counts.items():
            tf_val = count / total_terms
            idf_val = self._idf.get(term, self._compute_unseen_term_idf())
            tfidf[term] = tf_val * idf_val

        if self._bigram_dict:
            tfidf = self._apply_bigram_boost(tfidf, filtered)

        tfidf = self._l2_normalize(tfidf)

        if self._config.enable_debug_output:
            _logger.debug("transform: input_tokens=%d, output_dims=%d", len(tokens), len(tfidf))

        return tfidf

    def fit_transform_sync(self, documents: List[List[str]]) -> List[Dict[str, float]]:
        if not self._is_pretrained:
            self.fit(documents)
        results: List[Dict[str, float]] = []
        for doc in documents:
            tf_counts: Dict[str, int] = {}
            for token in doc:
                tf_counts[token] = tf_counts.get(token, 0) + 1
            total_terms = len(doc)
            tfidf: Dict[str, float] = {}
            for term, count in tf_counts.items():
                tf_val = count / total_terms
                idf_val = self._idf.get(term, self._compute_unseen_term_idf())
                tfidf[term] = tf_val * idf_val
            results.append(self._l2_normalize(tfidf))
        return results

    def _apply_bigram_boost(
        self,
        tfidf: Dict[str, float],
        tokens: List[str],
    ) -> Dict[str, float]:
        if len(tokens) < 2:
            return tfidf
        for i in range(len(tokens) - 1):
            bigram_key = tokens[i]
            next_word = tokens[i + 1]
            transitions = self._bigram_dict.get(bigram_key)
            if transitions and next_word in transitions:
                boost = transitions[next_word]
                if next_word in tfidf:
                    tfidf[next_word] *= (1.0 + boost)
        return tfidf

    def _compute_unseen_term_idf(self) -> float:
        if self._n_docs == 0:
            return self._UNSEEN_TERM_IDF_DEFAULT
        return math.log(
            (self._IDF_SMOOTH_ADDEND + self._n_docs)
            / self._IDF_SMOOTH_ADDEND
        ) + self._IDF_SMOOTH_ADDEND

    @staticmethod
    def _l2_normalize(vector: Dict[str, float]) -> Dict[str, float]:
        norm = math.sqrt(sum(v * v for v in vector.values()))
        if norm < TFIDFVectorizer._L2_NORM_ZERO_THRESHOLD:
            return vector
        return {k: v / norm for k, v in vector.items()}

    def validate_output(self, vector: Dict[str, float]) -> bool:
        if not vector:
            return False
        for val in vector.values():
            if val < 0:
                return False
        norm = math.sqrt(sum(v * v for v in vector.values()))
        if norm > self._L2_NORM_ZERO_THRESHOLD:
            if abs(norm - self._L2_NORM_EXPECTED) > self._L2_NORM_TOLERANCE:
                return False
        return True

    def validate_dimension_consistency(self, vectors: List[Dict[str, float]]) -> bool:
        if not vectors:
            return True
        if not self._is_fitted:
            return True
        for vec in vectors:
            for term in vec:
                if term not in self._vocab:
                    return False
        return True
