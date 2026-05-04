"""
世界观渲染引导 - 要素提取、分类、关联、冲突检测
为LLM提供结构化引导，实现用户自定义世界观的沉浸式渲染
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple

from luqi_engine.core.interfaces import IWorldViewRenderer
from luqi_engine.core.snapshot import ISnapshotable
from luqi_engine.core.types import ConflictReport, EntityId, generate_entity_id

_CLASSIFICATION_DIMENSIONS: List[str] = [
    "geography", "society", "culture", "history",
    "magic_system", "technology", "politics", "religion", "ecology",
]

_DIMENSION_KEYWORDS: Dict[str, List[str]] = {
    "geography": ["地形", "山脉", "河流", "海洋", "城市", "地图", "地理", "大陆", "岛屿", "气候", "mountain", "river", "ocean", "city", "map"],
    "society": ["社会", "阶级", "组织", "公会", "家族", "部落", "人口", "职业", "society", "class", "guild", "clan"],
    "culture": ["文化", "语言", "艺术", "节日", "习俗", "传统", "信仰", "culture", "language", "art", "festival"],
    "history": ["历史", "战争", "纪元", "朝代", "事件", "传说", "过去", "history", "war", "era", "dynasty"],
    "magic_system": ["魔法", "法术", "咒语", "魔力", "元素", "符文", "炼金", "magic", "spell", "mana", "rune"],
    "technology": ["科技", "机械", "工程", "发明", "武器", "工具", "technology", "machine", "weapon"],
    "politics": ["政治", "王国", "帝国", "联盟", "条约", "权力", "统治", "politics", "kingdom", "empire"],
    "religion": ["宗教", "神", "神殿", "祭祀", "信仰", "教派", "神谕", "religion", "god", "temple"],
    "ecology": ["生态", "生物", "怪物", "植物", "动物", "物种", "ecology", "creature", "monster"],
}

_CONFLICT_PATTERNS: List[Dict[str, Any]] = [
    {"type": "temporal", "desc": "时间线矛盾", "check": "temporal_conflict"},
    {"type": "causal", "desc": "因果逻辑矛盾", "check": "causal_conflict"},
    {"type": "attribute", "desc": "属性冲突", "check": "attribute_conflict"},
]

_RELATION_WEIGHT_STRONG: float = 0.8
_RELATION_WEIGHT_MEDIUM: float = 0.5
_RELATION_WEIGHT_WEAK: float = 0.2

_RENDER_ITEMS_PER_DIMENSION: int = 10
_RENDER_MAX_SOURCES: int = 20
_RENDER_TARGETS_PER_SOURCE: int = 3
_MIN_SENTENCE_LENGTH: int = 3
_FALLBACK_NAME_MAX_LENGTH: int = 20
_JACCARD_STRONG_THRESHOLD: float = 0.3
_JACCARD_MEDIUM_THRESHOLD: float = 0.1
_JACCARD_WEAK_THRESHOLD: float = 0.05
_CONFLICT_SEVERITY_DEFAULT: float = 0.8


class WorldViewRenderer(IWorldViewRenderer, ISnapshotable):
    """
    世界观渲染引导器
    从用户输入提取要素、分类、建立关联、检测冲突
    生成给LLM的结构化渲染引导文本
    """

    def __init__(self) -> None:
        self._elements: Dict[str, List[Dict]] = {}
        self._relations: Dict[str, List[Dict]] = {}
        self._world_model: Dict[str, Any] = {}

    async def extract_elements(
        self, raw_content: str, content_type: str = "text"
    ) -> Dict[str, Any]:
        """
        从原始内容中提取世界观要素
        支持text/markdown/json/csv格式
        """
        if content_type == "json":
            return self._extract_from_json(raw_content)
        if content_type == "csv":
            return self._extract_from_csv(raw_content)
        return self._extract_from_text(raw_content)

    async def classify_elements(
        self, elements: Dict[str, Any]
    ) -> Dict[str, List[Dict]]:
        """
        将提取的要素分类到标准维度
        """
        classified: Dict[str, List[Dict]] = {
            dim: [] for dim in _CLASSIFICATION_DIMENSIONS
        }
        classified["unclassified"] = []

        all_elements = elements.get("elements", [])
        for elem in all_elements:
            text = elem.get("text", "") or elem.get("name", "")
            content = elem.get("content", "") or elem.get("description", "")
            combined = f"{text} {content}"

            best_dim = self._classify_text(combined)
            if best_dim:
                classified[best_dim].append(elem)
            else:
                classified["unclassified"].append(elem)

        self._elements = classified
        return classified

    async def build_relations(
        self, classified: Dict[str, List[Dict]]
    ) -> Dict[str, Any]:
        """
        建立要素间关联关系图
        邻接表形式
        """
        relations: Dict[str, List[Dict]] = {}
        all_items: List[Tuple[str, Dict]] = []

        for dim, items in classified.items():
            for item in items:
                name = item.get("text", "") or item.get("name", f"item_{len(all_items)}")
                all_items.append((name, item))

        for i, (name_a, item_a) in enumerate(all_items):
            if name_a not in relations:
                relations[name_a] = []
            for j, (name_b, item_b) in enumerate(all_items):
                if i >= j:
                    continue
                weight = self._compute_relation_weight(item_a, item_b)
                if weight > _RELATION_WEIGHT_WEAK:
                    relations[name_a].append(
                        {"target": name_b, "weight": weight, "type": "related"}
                    )
                    if name_b not in relations:
                        relations[name_b] = []
                    relations[name_b].append(
                        {"target": name_a, "weight": weight, "type": "related"}
                    )

        self._relations = relations
        return {"adjacency": relations, "node_count": len(all_items), "edge_count": sum(len(v) for v in relations.values()) // 2}

    async def render_guidance(
        self, world_model: Dict[str, Any]
    ) -> str:
        """
        生成给LLM的结构化渲染引导文本
        """
        sections: List[str] = ["# 世界观设定\n"]

        classified = world_model.get("classified", self._elements)
        for dim, items in classified.items():
            if not items or dim == "unclassified":
                continue
            dim_label = _CLASSIFICATION_DIMENSIONS[
                _CLASSIFICATION_DIMENSIONS.index(dim)
            ] if dim in _CLASSIFICATION_DIMENSIONS else dim
            sections.append(f"\n## {dim_label}\n")
            for item in items[:_RENDER_ITEMS_PER_DIMENSION]:
                name = item.get("text", "") or item.get("name", "")
                content = item.get("content", "") or item.get("description", "")
                if name and content:
                    sections.append(f"- **{name}**: {content}")
                elif name:
                    sections.append(f"- {name}")

        relations = world_model.get("relations", self._relations)
        if relations and isinstance(relations, dict):
            adj = relations.get("adjacency", relations)
            if adj:
                sections.append("\n## 要素关联\n")
                for source, targets in list(adj.items())[:_RENDER_MAX_SOURCES]:
                    for t in targets[:_RENDER_TARGETS_PER_SOURCE]:
                        sections.append(
                            f"- {source} ↔ {t['target']} (权重: {t['weight']:.1f})"
                        )

        return "\n".join(sections)

    async def detect_conflicts(
        self, world_model: Dict[str, Any]
    ) -> List[ConflictReport]:
        """
        检测世界观内部的逻辑矛盾
        """
        conflicts: List[ConflictReport] = []
        classified = world_model.get("classified", self._elements)

        all_items: List[Dict] = []
        for items in classified.values():
            all_items.extend(items)

        for i in range(len(all_items)):
            for j in range(i + 1, len(all_items)):
                conflict = self._check_pair_conflict(all_items[i], all_items[j])
                if conflict:
                    conflicts.append(conflict)

        return conflicts

    @staticmethod
    def _extract_from_text(text: str) -> Dict[str, Any]:
        elements: List[Dict] = []
        patterns = [
            re.compile(r"[-•*]\s*(.+?)(?:[:：]\s*(.+?))?(?:\n|$)", re.MULTILINE),
            re.compile(r"#{1,3}\s+(.+?)(?:\n|$)", re.MULTILINE),
        ]
        for pattern in patterns:
            for match in pattern.finditer(text):
                name = match.group(1).strip()
                content = match.group(2).strip() if match.lastindex and match.lastindex >= 2 and match.group(2) else ""
                if name:
                    elements.append({"name": name, "content": content})

        if not elements:
            sentences = re.split(r"[。！？\.\!\?]", text)
            for s in sentences:
                s = s.strip()
                if len(s) > _MIN_SENTENCE_LENGTH:
                    elements.append({"name": s[:_FALLBACK_NAME_MAX_LENGTH], "content": s})

        return {"elements": elements, "source_type": "text", "total": len(elements)}

    @staticmethod
    def _extract_from_json(text: str) -> Dict[str, Any]:
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return {"elements": [], "source_type": "json", "total": 0}

        elements: List[Dict] = []
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    elements.append({
                        "name": item.get("name", item.get("title", "")),
                        "content": item.get("description", item.get("content", "")),
                    })
        elif isinstance(data, dict):
            for key, value in data.items():
                if isinstance(value, str):
                    elements.append({"name": key, "content": value})
                elif isinstance(value, dict):
                    elements.append({
                        "name": value.get("name", key),
                        "content": value.get("description", str(value)),
                    })

        return {"elements": elements, "source_type": "json", "total": len(elements)}

    @staticmethod
    def _extract_from_csv(text: str) -> Dict[str, Any]:
        elements: List[Dict] = []
        lines = text.strip().split("\n")
        if len(lines) < 2:
            return {"elements": [], "source_type": "csv", "total": 0}

        headers = lines[0].split(",")
        for line in lines[1:]:
            values = line.split(",")
            name_idx = 0
            desc_idx = 1 if len(values) > 1 else -1
            name = values[name_idx].strip() if name_idx < len(values) else ""
            content = values[desc_idx].strip() if desc_idx >= 0 and desc_idx < len(values) else ""
            if name:
                elements.append({"name": name, "content": content})

        return {"elements": elements, "source_type": "csv", "total": len(elements)}

    @staticmethod
    def _classify_text(text: str) -> Optional[str]:
        text_lower = text.lower()
        best_dim: Optional[str] = None
        best_score: int = 0
        for dim, keywords in _DIMENSION_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text_lower)
            if score > best_score:
                best_score = score
                best_dim = dim
        return best_dim

    @staticmethod
    def _compute_relation_weight(item_a: Dict, item_b: Dict) -> float:
        text_a = f"{item_a.get('name', '')} {item_a.get('content', '')}".lower()
        text_b = f"{item_b.get('name', '')} {item_b.get('content', '')}".lower()
        if not text_a or not text_b:
            return 0.0

        words_a = set(text_a.split())
        words_b = set(text_b.split())
        overlap = len(words_a & words_b)
        union = len(words_a | words_b)
        if union == 0:
            return 0.0
        jaccard = overlap / union
        if jaccard > _JACCARD_STRONG_THRESHOLD:
            return _RELATION_WEIGHT_STRONG
        if jaccard > _JACCARD_MEDIUM_THRESHOLD:
            return _RELATION_WEIGHT_MEDIUM
        return _RELATION_WEIGHT_WEAK if jaccard > _JACCARD_WEAK_THRESHOLD else 0.0

    @staticmethod
    def _check_pair_conflict(
        item_a: Dict, item_b: Dict
    ) -> Optional[ConflictReport]:
        name_a = item_a.get("name", "")
        name_b = item_b.get("name", "")
        content_a = item_a.get("content", "").lower()
        content_b = item_b.get("content", "").lower()

        negation_words = ["不", "非", "无", "禁止", "不可能", "never", "not", "no", "impossible"]
        for neg in negation_words:
            if neg in content_a and name_b in content_a:
                return ConflictReport(
                    conflict_id=generate_entity_id("conflict"),
                    conflict_type="attribute",
                    description=f"'{name_a}'与'{name_b}'存在属性冲突",
                    severity=_CONFLICT_SEVERITY_DEFAULT,
                    involved_entities=[name_a, name_b],
                    suggested_resolutions=[
                        {"strategy": "保留", "description": f"保留{name_a}的设定"},
                        {"strategy": "修改", "description": f"修改{name_b}的描述以消除矛盾"},
                        {"strategy": "折中", "description": "添加例外条件使两者兼容"},
                    ],
                )
        return None

    def save_snapshot(self) -> Dict[str, Any]:
        elements_serialized = {}
        for dim, items in self._elements.items():
            elements_serialized[dim] = list(items)
        relations_serialized = {}
        for source, targets in self._relations.items():
            relations_serialized[source] = list(targets)
        return {
            "elements": elements_serialized,
            "relations": relations_serialized,
            "world_model": dict(self._world_model),
        }

    def load_snapshot(self, data: Dict[str, Any]) -> None:
        self._elements = {}
        for dim, items in data.get("elements", {}).items():
            self._elements[dim] = list(items)
        self._relations = {}
        for source, targets in data.get("relations", {}).items():
            self._relations[source] = list(targets)
        self._world_model = dict(data.get("world_model", {}))
