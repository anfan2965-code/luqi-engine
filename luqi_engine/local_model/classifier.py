"""
内容分类器
支持从预训练资源加载类别质心和关键词，替代硬编码原型
"""

from __future__ import annotations

import math
from typing import Any, ClassVar, Dict, List, Optional

from luqi_engine.core.config import LocalModelConfig
from luqi_engine.core.logging_config import get_logger
from luqi_engine.core.types import LocalModelOutput
from luqi_engine.local_model.vectorizer import TFIDFVectorizer

_logger = get_logger(__name__)


class ContentClassifier:
    _PROBABILITY_SUM_TOLERANCE: ClassVar[float] = 1e-6
    _SOFTMAX_TEMPERATURE: ClassVar[float] = 1.0
    _DEFAULT_CATEGORY: ClassVar[str] = "normal"
    _ZERO_SIMILARITY: ClassVar[float] = 0.0
    _MIN_CONFIDENCE: ClassVar[float] = 0.0
    _MAX_CONFIDENCE: ClassVar[float] = 1.0

    _CATEGORY_KEYWORD_WEIGHTS: ClassVar[Dict[str, float]] = {
        "worldview_setting": 2.0,
        "plot_logic": 2.0,
        "character_consistency": 1.8,
        "spatial_relation": 1.5,
        "temporal_logic": 1.5,
        "dialogue_interaction": 1.8,
        "emotion_psychology": 1.8,
        "combat_action": 2.0,
        "social_politics": 1.8,
        "exploration_discovery": 1.8,
        "trade_economy": 1.8,
        "knowledge_lore": 1.8,
        "survival_crisis": 1.8,
        "unsafe_explicit": 3.0,
        "unsafe_implicit": 2.5,
        "unsafe_euphemism": 2.5,
        "unsafe_narrative_wrapped": 2.0,
        "content_safe": 1.0,
        "normal": 0.5,
    }

    _CATEGORY_PROTOTYPES: ClassVar[Dict[str, List[str]]] = {
        "worldview_setting": [
            "世界观", "设定", "规则", "体系", "魔法", "科技",
            "地理", "社会", "文化", "历史", "背景", "框架",
            "种族", "势力", "文明", "宗教", "政治",
        ],
        "plot_logic": [
            "剧情", "情节", "事件", "转折", "冲突", "发展",
            "结局", "伏笔", "叙事", "故事线", "高潮", "悬念",
            "铺垫", "呼应", "节奏",
        ],
        "character_consistency": [
            "角色", "性格", "行为", "动机", "关系", "一致性",
            "人设", "特征", "习惯", "态度", "信念", "目标",
        ],
        "spatial_relation": [
            "空间", "位置", "距离", "方向", "场景", "地点",
            "区域", "移动", "布局", "方位", "地形", "建筑",
        ],
        "temporal_logic": [
            "时间", "顺序", "因果", "先后", "同时", "延续",
            "变化", "时期", "年代", "纪元", "历法", "周期",
        ],
        "dialogue_interaction": [
            "对话", "交流", "互动", "语气", "态度", "表达",
            "沟通", "回应", "争论", "协商", "说服",
        ],
        "emotion_psychology": [
            "情感", "心理", "情绪", "感受", "内心", "心境",
            "恐惧", "愤怒", "喜悦", "悲伤", "焦虑", "矛盾",
        ],
        "combat_action": [
            "战斗", "攻击", "防御", "技能", "招式", "武器",
            "策略", "对抗", "搏斗", "交锋", "攻防",
        ],
        "social_politics": [
            "权力", "势力", "联盟", "政治", "阶层", "博弈",
            "统治", "反叛", "阴谋", "权谋", "立场",
        ],
        "exploration_discovery": [
            "探索", "发现", "秘密", "线索", "未知", "遗迹",
            "宝藏", "谜题", "探险", "揭示", "隐藏",
        ],
        "trade_economy": [
            "交易", "贸易", "价格", "资源", "财富", "商业",
            "谈判", "买卖", "市场", "经济", "利润",
        ],
        "knowledge_lore": [
            "知识", "传说", "典籍", "历史", "禁忌", "古老",
            "秘辛", "文献", "记载", "传承", "智慧",
        ],
        "survival_crisis": [
            "危机", "危险", "生存", "困境", "绝境", "威胁",
            "匮乏", "灾难", "求生", "险境", "紧迫",
        ],
        "unsafe_explicit": [
            "裸露", "暴露", "色情", "淫秽", "猥亵", "下流",
            "性暗示", "挑逗", "诱惑", "不雅", "淫荡",
        ],
        "unsafe_implicit": [
            "暧昧", "缠绵", "亲昵", "温存", "耳鬓厮磨",
            "肌肤相亲", "私语", "暗香", "春色", "旖旎",
        ],
        "unsafe_euphemism": [
            "云雨", "巫山", "鱼水", "周公之礼", "洞房",
            "圆房", "同房", "翻云覆雨", "共度", "在一起",
        ],
        "unsafe_narrative_wrapped": [
            "情感描写", "亲密互动", "详细刻画", "身体描写",
            "互动过程", "逐步描写", "感官体验", "深入描写",
        ],
        "content_safe": [
            "安全", "正常", "合规", "健康", "适当", "适宜",
        ],
        "normal": [
            "正常", "普通", "标准", "默认", "一般", "常规",
        ],
    }

    def __init__(
        self,
        config: LocalModelConfig | None = None,
        vectorizer: TFIDFVectorizer | None = None,
        resource_loader: Optional[Any] = None,
    ) -> None:
        self._config = config or LocalModelConfig()
        self._vectorizer = vectorizer if vectorizer is not None else TFIDFVectorizer(self._config)
        self._resource_loader = resource_loader
        self._prototype_vectors: Dict[str, Dict[str, float]] = {}
        self._last_probability_distribution: Dict[str, float] = {}
        self._owns_vectorizer = vectorizer is None
        self._category_centroids: Dict[str, List[float]] = {}
        self._category_keywords: Dict[str, List[str]] = {}
        self._use_pretrained_centroids: bool = False
        self._initialize_prototypes()

    def _initialize_prototypes(self) -> None:
        if self._resource_loader is not None:
            params = self._resource_loader.load_classifier_params()
            if params:
                self._load_from_params(params)
                return
        prototype_docs: List[List[str]] = []
        category_order: List[str] = []
        for category, keywords in self._CATEGORY_PROTOTYPES.items():
            prototype_docs.append(keywords)
            category_order.append(category)
        prototype_results = self._vectorizer.fit_transform_sync(prototype_docs)
        for category, vector in zip(category_order, prototype_results):
            self._prototype_vectors[category] = vector

    def _load_from_params(self, params: Dict[str, Any]) -> None:
        categories = params.get("categories", [])
        category_keywords = params.get("category_keywords", {})
        category_centroids = params.get("category_centroids", {})
        if category_keywords:
            self._category_keywords = category_keywords
        if category_centroids:
            self._category_centroids = category_centroids
            self._use_pretrained_centroids = True
        if category_keywords:
            prototype_docs: List[List[str]] = []
            category_order: List[str] = []
            for cat in categories:
                kw = category_keywords.get(cat, [])
                if kw:
                    prototype_docs.append(kw)
                    category_order.append(cat)
            if prototype_docs:
                prototype_results = self._vectorizer.fit_transform_sync(prototype_docs)
                for category, vector in zip(category_order, prototype_results):
                    self._prototype_vectors[category] = vector
        if self._config.enable_debug_output:
            source = "pretrained_centroids" if self._use_pretrained_centroids else "pretrained_keywords"
            _logger.info(
                "Initialized from %s, categories=%d, centroids=%d",
                source, len(self._prototype_vectors), len(self._category_centroids),
            )

    async def classify(self, vector: Dict[str, float]) -> LocalModelOutput:
        if not vector:
            return LocalModelOutput(
                classification=self._DEFAULT_CATEGORY,
                confidence=self._MIN_CONFIDENCE,
            )

        similarities = self._compute_similarities(vector)
        probabilities = self._softmax(similarities)
        self._last_probability_distribution = probabilities

        best_category = self._DEFAULT_CATEGORY
        best_prob = self._MIN_CONFIDENCE
        for category, prob in probabilities.items():
            if prob > best_prob:
                best_prob = prob
                best_category = category

        suggestions = self._generate_suggestions(best_category, best_prob)

        if self._config.enable_debug_output:
            _logger.debug(
                "classification=%s, confidence=%.4f",
                best_category, best_prob,
            )

        return LocalModelOutput(
            classification=best_category,
            confidence=best_prob,
            correction_suggestions=suggestions,
        )

    def _compute_similarities(self, vector: Dict[str, float]) -> Dict[str, float]:
        keyword_scores: Dict[str, float] = {}
        max_keyword_score = 0.0

        for category, proto_vector in self._prototype_vectors.items():
            keyword_weight = self._CATEGORY_KEYWORD_WEIGHTS.get(category, 1.0)
            keyword_hits = sum(1.0 for k in proto_vector.keys() if k in vector)
            score = keyword_hits * keyword_weight
            keyword_scores[category] = score
            if score > max_keyword_score:
                max_keyword_score = score

        similarities: Dict[str, float] = {}

        if max_keyword_score > 0.0:
            for category in self._prototype_vectors:
                similarities[category] = keyword_scores.get(category, 0.0) / max_keyword_score
        else:
            for category, proto_vector in self._prototype_vectors.items():
                sim = self._cosine_similarity(vector, proto_vector)
                similarities[category] = sim

        if self._use_pretrained_centroids and self._category_centroids:
            centroid_sims = self._compute_centroid_similarities(vector)
            for cat, sim in centroid_sims.items():
                if cat in similarities and sim > 0.0:
                    similarities[cat] = similarities[cat] * 0.6 + sim * 0.4
                elif cat in similarities:
                    pass
                else:
                    similarities[cat] = sim * 0.4

        return similarities

    def _compute_centroid_similarities(
        self, vector: Dict[str, float],
    ) -> Dict[str, float]:
        if self._resource_loader is None:
            return {}
        vocab = self._resource_loader.load_vocabulary()
        inv_vocab = {idx: word for word, idx in vocab.items()}
        centroid_dim = len(next(iter(self._category_centroids.values()))) if self._category_centroids else 0
        if centroid_dim == 0:
            return {}
        vec_list: List[float] = [0.0] * centroid_dim
        for i in range(min(centroid_dim, max(vocab.values()) + 1)):
            word = inv_vocab.get(i, "")
            if word in vector:
                vec_list[i] = vector[word]
        similarities: Dict[str, float] = {}
        for cat, centroid in self._category_centroids.items():
            c_len = min(len(centroid), centroid_dim)
            dot = sum(centroid[i] * vec_list[i] for i in range(c_len))
            norm_a = sum(c * c for c in centroid[:c_len]) ** 0.5
            norm_b = sum(v * v for v in vec_list[:c_len]) ** 0.5
            if norm_a > 1e-10 and norm_b > 1e-10:
                similarities[cat] = dot / (norm_a * norm_b)
            else:
                similarities[cat] = 0.0
        return similarities

    @staticmethod
    def _cosine_similarity(vec_a: Dict[str, float], vec_b: Dict[str, float]) -> float:
        common_keys = set(vec_a.keys()) & set(vec_b.keys())
        if not common_keys:
            return ContentClassifier._ZERO_SIMILARITY
        dot_product = sum(vec_a[k] * vec_b[k] for k in common_keys)
        norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
        norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
        if norm_a == 0 or norm_b == 0:
            return ContentClassifier._ZERO_SIMILARITY
        return dot_product / (norm_a * norm_b)

    def _softmax(self, scores: Dict[str, float]) -> Dict[str, float]:
        if not scores:
            return {}
        temperature = self._SOFTMAX_TEMPERATURE
        max_score = max(scores.values())
        exp_scores: Dict[str, float] = {}
        for category, score in scores.items():
            exp_scores[category] = math.exp((score - max_score) / temperature)
        total = sum(exp_scores.values())
        if total == 0:
            n = len(scores)
            return {k: self._MAX_CONFIDENCE / n for k in scores}
        return {k: v / total for k, v in exp_scores.items()}

    def _generate_suggestions(self, category: str, confidence: float) -> List[str]:
        suggestions: List[str] = []
        if confidence < self._config.classification_threshold:
            suggestions.append(
                f"分类置信度({confidence:.4f})低于阈值({self._config.classification_threshold})，建议人工审核"
            )
        if category != self._DEFAULT_CATEGORY and category in self._prototype_vectors:
            suggestions.append(f"内容涉及{category}领域，建议进行专项一致性校验")
        return suggestions

    def validate_output(self, output: LocalModelOutput) -> bool:
        if not output.classification:
            return False
        if not (self._MIN_CONFIDENCE <= output.confidence <= self._MAX_CONFIDENCE):
            return False
        if self._last_probability_distribution:
            prob_sum = sum(self._last_probability_distribution.values())
            if abs(prob_sum - self._MAX_CONFIDENCE) > self._PROBABILITY_SUM_TOLERANCE:
                return False
        return True

    def get_probability_distribution(self) -> Dict[str, float]:
        return dict(self._last_probability_distribution)
