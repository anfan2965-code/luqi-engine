"""
上下文语义安全审核器
检测显式/隐晦/隐喻/谐音/叙事包装的不当内容
基于语义模式匹配+上下文分析，不依赖硬编码关键词黑名单
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

from luqi_engine.core.config import LocalModelConfig


class SafetyLevel(Enum):
    SAFE = "safe"
    SUSPICIOUS = "suspicious"
    UNSAFE = "unsafe"
    CRITICAL = "critical"


class UnsafeCategory(Enum):
    EXPLICIT = "unsafe_explicit"
    IMPLICIT = "unsafe_implicit"
    EUPHEMISM = "unsafe_euphemism"
    NARRATIVE_WRAPPED = "unsafe_narrative_wrapped"
    NONE = "content_safe"


@dataclass
class SafetyVerdict:
    level: SafetyLevel = SafetyLevel.SAFE
    category: UnsafeCategory = UnsafeCategory.NONE
    confidence: float = 0.0
    risk_factors: List[str] = field(default_factory=list)
    context_evidence: List[str] = field(default_factory=list)

    @property
    def is_safe(self) -> bool:
        return self.level == SafetyLevel.SAFE


_SEMANTIC_FIELD_BODY: Tuple[str, ...] = (
    "身体", "肌肤", "皮肤", "嘴唇", "脖颈", "锁骨", "腰肢",
    "胸膛", "背脊", "大腿", "手臂", "手指", "面颊", "耳垂",
    "肩头", "小腹", "脚踝", "手腕",
    "衣襟", "衣领", "衣带", "衣衫", "衣摆", "裙摆",
    "内衣", "内衬", "腰际", "腿间", "胸口", "胸前",
    "后背", "脊背", "腰线", "臀线", "脚心", "掌心",
)

_SEMANTIC_FIELD_ACTION: Tuple[str, ...] = (
    "抚摸", "亲吻", "拥抱", "贴近", "缠绕", "摩挲", "舔舐",
    "咬", "含", "吮", "揉", "按压", "摩擦", "探索",
    "侵入", "深入", "贯穿", "挺进", "冲撞",
    "伸进", "滑入", "探入", "解开", "褪去", "剥落",
    "游走", "攀上", "钻入", "抚过", "掠过", "捏住",
    "掐住", "攥住", "扣住", "箍住", "搂住", "抱紧",
    "贴上", "压住", "覆上", "盖住", "遮住", "掀起",
)

_SEMANTIC_FIELD_SENSATION: Tuple[str, ...] = (
    "喘息", "呻吟", "颤抖", "酥麻", "灼热", "湿润", "潮红",
    "痉挛", "失神", "迷离", "沉沦", "沦陷", "失控",
    "情动", "动情", "欲火", "春情",
    "弓起", "蜷缩", "绷紧", "发软", "发烫", "滚烫",
    "战栗", "抽搐", "窒息", "闷哼", "低喘", "娇喘",
    "泛红", "绯红", "殷红", "苍白", "惨白",
    "心跳加速", "呼吸急促", "浑身发软", "意乱情迷",
)

_SEMANTIC_FIELD_EUPHEMISM: Tuple[str, ...] = (
    "做", "来", "那个", "那种事", "在一起", "要你",
    "开车", "上车", "翻云覆雨", "巫山", "云雨", "共度",
    "鱼水", "周公之礼", "洞房", "圆房", "同房",
    "办事", "正事", "那种意思", "你懂的",
)

_SEMANTIC_FIELD_NARRATIVE_WRAP: Tuple[str, ...] = (
    "描写", "刻画", "细节", "详细", "过程", "一步步",
    "慢慢", "逐渐", "从上到下", "每个部位",
    "情感描写", "亲密描写", "互动描写",
)

_SEMANTIC_FIELD_HARMONY: Tuple[str, ...] = (
    "做AI", "造爱", "坐爱", "做唉",
    "啪", "打扑克", "打牌", "修车",
    "吃豆腐", "揩油", "咸猪手",
    "约炮", "约P", "开房", "滚床单",
    "色色", "涩涩", "搞黄色", "搞颜色",
)


@dataclass
class _FieldScore:
    body: float = 0.0
    action: float = 0.0
    sensation: float = 0.0
    euphemism: float = 0.0
    narrative_wrap: float = 0.0
    harmony: float = 0.0


class ContextSafetyChecker:
    _FIELD_WEIGHTS: ClassVar[Dict[str, float]] = {
        "body": 0.12,
        "action": 0.20,
        "sensation": 0.20,
        "euphemism": 0.20,
        "narrative_wrap": 0.13,
        "harmony": 0.15,
    }

    _CATEGORY_RULES: ClassVar[List[Tuple[UnsafeCategory, Dict[str, float]]]] = [
        (UnsafeCategory.EXPLICIT, {
            "body": 0.3, "action": 0.4, "sensation": 0.3,
            "euphemism": 0.0, "narrative_wrap": 0.0, "harmony": 0.0,
        }),
        (UnsafeCategory.IMPLICIT, {
            "body": 0.2, "action": 0.2, "sensation": 0.3,
            "euphemism": 0.2, "narrative_wrap": 0.1, "harmony": 0.0,
        }),
        (UnsafeCategory.EUPHEMISM, {
            "body": 0.0, "action": 0.0, "sensation": 0.0,
            "euphemism": 0.5, "narrative_wrap": 0.0, "harmony": 0.5,
        }),
        (UnsafeCategory.NARRATIVE_WRAPPED, {
            "body": 0.1, "action": 0.1, "sensation": 0.1,
            "euphemism": 0.1, "narrative_wrap": 0.5, "harmony": 0.1,
        }),
    ]

    _SUSPICIOUS_THRESHOLD: ClassVar[float] = 0.08
    _UNSAFE_THRESHOLD: ClassVar[float] = 0.18
    _CRITICAL_THRESHOLD: ClassVar[float] = 0.40

    _CONTEXT_WINDOW_SIZE: ClassVar[int] = 3

    def __init__(self, config: Optional[LocalModelConfig] = None) -> None:
        self._config = config or LocalModelConfig()
        self._field_sets: Dict[str, Set[str]] = {
            "body": set(_SEMANTIC_FIELD_BODY),
            "action": set(_SEMANTIC_FIELD_ACTION),
            "sensation": set(_SEMANTIC_FIELD_SENSATION),
            "euphemism": set(_SEMANTIC_FIELD_EUPHEMISM),
            "narrative_wrap": set(_SEMANTIC_FIELD_NARRATIVE_WRAP),
            "harmony": set(_SEMANTIC_FIELD_HARMONY),
        }

    def check(self, text: str, context: Optional[List[str]] = None) -> SafetyVerdict:
        if not text or not text.strip():
            return SafetyVerdict()

        full_text = text
        if context:
            full_text = " ".join(context[-self._CONTEXT_WINDOW_SIZE:]) + " " + text

        field_score = self._compute_field_scores(full_text)
        risk_score = self._compute_risk_score(field_score)
        category = self._determine_category(field_score)
        level = self._determine_level(risk_score)
        risk_factors = self._extract_risk_factors(field_score)
        evidence = self._extract_evidence(full_text)

        return SafetyVerdict(
            level=level,
            category=category,
            confidence=round(risk_score, 4),
            risk_factors=risk_factors,
            context_evidence=evidence,
        )

    def _compute_field_scores(self, text: str) -> _FieldScore:
        import re
        chars = re.sub(r'[^\u4e00-\u9fff\u3400-\u4dbf]', '', text)
        score = _FieldScore()

        for field_name, field_set in self._field_sets.items():
            hit_count = 0
            total_weight = 0.0
            for term in field_set:
                count = text.count(term)
                if count > 0:
                    term_weight = math.log2(len(term) + 1)
                    hit_count += count
                    total_weight += count * term_weight

            if hit_count > 0:
                raw = total_weight / max(len(chars) * 0.005, 1.0)
                normalized = 1.0 - math.exp(-raw * 1.5)
            else:
                normalized = 0.0

            setattr(score, field_name, normalized)

        return score

    def _compute_risk_score(self, score: _FieldScore) -> float:
        total = 0.0
        for field_name, weight in self._FIELD_WEIGHTS.items():
            total += getattr(score, field_name) * weight
        return min(total, 1.0)

    def _determine_category(self, score: _FieldScore) -> UnsafeCategory:
        best_category = UnsafeCategory.NONE
        best_similarity = 0.0

        for category, profile in self._CATEGORY_RULES:
            similarity = self._cosine_profile(score, profile)
            if similarity > best_similarity:
                best_similarity = similarity
                best_category = category

        return best_category

    @staticmethod
    def _cosine_profile(score: _FieldScore, profile: Dict[str, float]) -> float:
        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0
        for field_name, profile_val in profile.items():
            score_val = getattr(score, field_name, 0.0)
            dot += score_val * profile_val
            norm_a += score_val * score_val
            norm_b += profile_val * profile_val
        norm_a = math.sqrt(norm_a)
        norm_b = math.sqrt(norm_b)
        if norm_a < 1e-10 or norm_b < 1e-10:
            return 0.0
        return dot / (norm_a * norm_b)

    def _determine_level(self, risk_score: float) -> SafetyLevel:
        if risk_score >= self._CRITICAL_THRESHOLD:
            return SafetyLevel.CRITICAL
        if risk_score >= self._UNSAFE_THRESHOLD:
            return SafetyLevel.UNSAFE
        if risk_score >= self._SUSPICIOUS_THRESHOLD:
            return SafetyLevel.SUSPICIOUS
        return SafetyLevel.SAFE

    def _extract_risk_factors(self, score: _FieldScore) -> List[str]:
        factors: List[str] = []
        thresholds = {
            "body": 0.15,
            "action": 0.15,
            "sensation": 0.15,
            "euphemism": 0.10,
            "narrative_wrap": 0.10,
            "harmony": 0.10,
        }
        labels = {
            "body": "身体部位描述",
            "action": "亲密动作描述",
            "sensation": "感官反应描述",
            "euphemism": "委婉/隐喻表达",
            "narrative_wrap": "叙事性包装",
            "harmony": "谐音/变体词",
        }
        for field_name, threshold in thresholds.items():
            val = getattr(score, field_name, 0.0)
            if val >= threshold:
                factors.append(f"{labels[field_name]}({val:.2f})")
        return factors

    def _extract_evidence(self, text: str) -> List[str]:
        evidence: List[str] = []
        for field_name, field_set in self._field_sets.items():
            for term in field_set:
                if term in text:
                    idx = text.index(term)
                    start = max(0, idx - 4)
                    end = min(len(text), idx + len(term) + 4)
                    snippet = text[start:end]
                    evidence.append(snippet)
                    if len(evidence) >= 5:
                        return evidence
        return evidence
