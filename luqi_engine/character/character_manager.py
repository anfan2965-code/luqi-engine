"""
角色管理器 - ICharacterManager接口实现
NPCFactory工厂模式 + 角色状态序列化/反序列化
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from luqi_engine.core.interfaces import ICharacterManager
from luqi_engine.core.snapshot import ISnapshotable
from luqi_engine.core.types import EntityId, ActionResult, WorldState, generate_entity_id
from luqi_engine.core.config import CharacterConfig
from luqi_engine.character.character_entity import CharacterEntity, Motive, MotivationEngine
from luqi_engine.character.personality import OceanPersonality
from luqi_engine.character.memory import MemoryStore, MemoryType, MemoryEntry

_NPC_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "guard": {
        "personality": {
            "openness": 25, "conscientiousness": 85, "extraversion": 30,
            "agreeableness": 40, "neuroticism": 20,
        },
        "motives": [
            {"motive_id": "duty", "name": "职责", "layer": 2, "base_intensity": 0.9, "urgency_curve": "sigmoid"},
            {"motive_id": "survival", "name": "生存", "layer": 1, "base_intensity": 0.7, "urgency_curve": "exponential"},
            {"motive_id": "order", "name": "秩序", "layer": 2, "base_intensity": 0.6, "urgency_curve": "linear"},
        ],
    },
    "merchant": {
        "personality": {
            "openness": 50, "conscientiousness": 60, "extraversion": 75,
            "agreeableness": 70, "neuroticism": 40,
        },
        "motives": [
            {"motive_id": "profit", "name": "利润", "layer": 1, "base_intensity": 0.85, "urgency_curve": "sigmoid"},
            {"motive_id": "social", "name": "社交", "layer": 2, "base_intensity": 0.6, "urgency_curve": "linear"},
            {"motive_id": "safety", "name": "安全", "layer": 1, "base_intensity": 0.5, "urgency_curve": "exponential"},
        ],
    },
    "scholar": {
        "personality": {
            "openness": 90, "conscientiousness": 70, "extraversion": 25,
            "agreeableness": 65, "neuroticism": 45,
        },
        "motives": [
            {"motive_id": "knowledge", "name": "求知", "layer": 3, "base_intensity": 0.9, "urgency_curve": "sigmoid"},
            {"motive_id": "survival", "name": "生存", "layer": 1, "base_intensity": 0.4, "urgency_curve": "exponential"},
            {"motive_id": "recognition", "name": "认可", "layer": 2, "base_intensity": 0.5, "urgency_curve": "linear"},
        ],
    },
    "warrior": {
        "personality": {
            "openness": 30, "conscientiousness": 55, "extraversion": 65,
            "agreeableness": 35, "neuroticism": 25,
        },
        "motives": [
            {"motive_id": "combat", "name": "战斗", "layer": 1, "base_intensity": 0.85, "urgency_curve": "exponential"},
            {"motive_id": "honor", "name": "荣誉", "layer": 2, "base_intensity": 0.7, "urgency_curve": "sigmoid"},
            {"motive_id": "survival", "name": "生存", "layer": 1, "base_intensity": 0.6, "urgency_curve": "exponential"},
        ],
    },
    "mage": {
        "personality": {
            "openness": 95, "conscientiousness": 75, "extraversion": 20,
            "agreeableness": 55, "neuroticism": 50,
        },
        "motives": [
            {"motive_id": "arcane_power", "name": "奥术力量", "layer": 3, "base_intensity": 0.9, "urgency_curve": "sigmoid"},
            {"motive_id": "knowledge", "name": "知识", "layer": 3, "base_intensity": 0.8, "urgency_curve": "sigmoid"},
            {"motive_id": "safety", "name": "安全", "layer": 1, "base_intensity": 0.5, "urgency_curve": "exponential"},
        ],
    },
    "assassin": {
        "personality": {
            "openness": 45, "conscientiousness": 80, "extraversion": 15,
            "agreeableness": 20, "neuroticism": 35,
        },
        "motives": [
            {"motive_id": "mission", "name": "任务", "layer": 2, "base_intensity": 0.9, "urgency_curve": "sigmoid"},
            {"motive_id": "stealth", "name": "隐匿", "layer": 1, "base_intensity": 0.8, "urgency_curve": "exponential"},
            {"motive_id": "survival", "name": "生存", "layer": 1, "base_intensity": 0.7, "urgency_curve": "exponential"},
        ],
    },
}


class NPCFactory:
    """
    NPC工厂 - 模板化创建角色
    """

    @classmethod
    def create(
        cls,
        template_name: str,
        custom_overrides: Optional[Dict[str, Any]] = None,
        config: Optional[CharacterConfig] = None,
    ) -> CharacterEntity:
        """
        从模板创建NPC实例
        支持自定义覆盖
        """
        base = _NPC_TEMPLATES.get(template_name, _NPC_TEMPLATES["guard"])
        data = _deep_merge(base, custom_overrides or {})

        personality = OceanPersonality(**data.get("personality", {}))

        motivation = MotivationEngine()
        for m_data in data.get("motives", []):
            motivation.add_motive(Motive(**m_data))

        return CharacterEntity(
            name=data.get("name", template_name),
            personality=personality,
            motivation=motivation,
            config=config,
        )

    @classmethod
    def available_templates(cls) -> List[str]:
        return list(_NPC_TEMPLATES.keys())


class CharacterManager(ICharacterManager, ISnapshotable):
    """
    角色管理器
    实现ICharacterManager接口
    """

    def __init__(self, config: Optional[CharacterConfig] = None) -> None:
        self._config = config or CharacterConfig()
        self._characters: Dict[EntityId, CharacterEntity] = {}
        self._memory_service: Optional[Any] = None

    async def create_character(
        self, character_config: Dict[str, Any]
    ) -> EntityId:
        """
        创建角色
        支持模板创建和自定义创建
        """
        template = character_config.get("template")
        overrides = dict(character_config.get("overrides") or {})
        name = character_config.get("name")
        if name:
            overrides["name"] = name

        if template:
            entity = NPCFactory.create(
                template_name=template,
                custom_overrides=overrides if overrides else None,
                config=self._config,
            )
        else:
            personality_data = character_config.get("personality", {})
            personality = OceanPersonality(**personality_data) if personality_data else OceanPersonality()

            motivation = MotivationEngine()
            for m_data in character_config.get("motives", []):
                motivation.add_motive(Motive(**m_data))

            entity = CharacterEntity(
                name=character_config.get("name", ""),
                personality=personality,
                motivation=motivation,
                config=self._config,
            )

        self._characters[entity.entity_id] = entity
        return entity.entity_id

    async def get_personality(
        self, character_id: EntityId
    ) -> Dict[str, float]:
        """
        获取角色性格量化值（OCEAN模型，0-100分）
        """
        entity = self._get_entity(character_id)
        if entity is None:
            return {}
        return {
            "openness": entity.personality.get_score("openness"),
            "conscientiousness": entity.personality.get_score("conscientiousness"),
            "extraversion": entity.personality.get_score("extraversion"),
            "agreeableness": entity.personality.get_score("agreeableness"),
            "neuroticism": entity.personality.get_score("neuroticism"),
        }

    async def update_personality(
        self, character_id: EntityId, deltas: Dict[str, float]
    ) -> None:
        """
        根据经历微调角色性格
        """
        entity = self._get_entity(character_id)
        if entity is None:
            return
        for dim, delta in deltas.items():
            current = entity.personality.get_score(dim)
            new_val = max(0.0, min(100.0, current + delta * self._config.personality_adaptation_rate))
            entity.personality.set_score(dim, new_val)

    async def store_memory(
        self,
        character_id: EntityId,
        memory_type: str,
        content: Dict[str, Any],
    ) -> None:
        """
        存储记忆
        """
        entity = self._get_entity(character_id)
        if entity is None:
            return
        entry = MemoryEntry(
            who=content.get("who", ""),
            what=content.get("what", ""),
            when=content.get("when", time.time()),
            where=content.get("where", ""),
            why=content.get("why", ""),
            emotional_valence=content.get("emotional_valence", 0.0),
        )
        mtype = MemoryType(memory_type) if memory_type in [mt.value for mt in MemoryType] else MemoryType.SHORT_TERM
        entity.memory.store(entry, mtype)

    async def retrieve_memories(
        self,
        character_id: EntityId,
        query: str,
        memory_type: Optional[str] = None,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        检索相关记忆
        """
        entity = self._get_entity(character_id)
        if entity is None:
            return []
        mtype = None
        if memory_type:
            mtype = MemoryType(memory_type) if memory_type in [mt.value for mt in MemoryType] else None
        entries = entity.memory.retrieve(query=query, memory_type=mtype, limit=limit)
        return [
            {
                "who": e.who,
                "what": e.what,
                "when": e.when,
                "where": e.where,
                "why": e.why,
                "emotional_valence": e.emotional_valence,
            }
            for e in entries
        ]

    async def validate_behavior_consistency(
        self,
        character_id: EntityId,
        proposed_action: Dict[str, Any],
    ) -> Tuple[bool, float]:
        """
        验证行为是否符合性格设定
        返回: (是否一致, 一致性分数0-1)
        """
        entity = self._get_entity(character_id)
        if entity is None:
            return False, 0.0
        return entity.validate_behavior_consistency(proposed_action)

    def get_character(self, character_id: EntityId) -> Optional[CharacterEntity]:
        return self._characters.get(character_id)

    def list_characters(self) -> List[EntityId]:
        return list(self._characters.keys())

    def serialize_character(self, character_id: EntityId) -> Optional[Dict[str, Any]]:
        entity = self._get_entity(character_id)
        if entity is None:
            return None
        return entity.to_dict()

    def deserialize_character(self, data: Dict[str, Any]) -> EntityId:
        entity = CharacterEntity.from_dict(data)
        self._characters[entity.entity_id] = entity
        return entity.entity_id

    def _get_entity(self, character_id: EntityId) -> Optional[CharacterEntity]:
        return self._characters.get(character_id)

    def set_memory_service(self, service: Any) -> None:
        self._memory_service = service

    async def store_shared_memory(
        self,
        event_id: str,
        content: Dict[str, Any],
        participant_ids: List[str],
        emotional_valence: float = 0.0,
    ) -> None:
        if self._memory_service is None:
            return
        self._memory_service.store_shared_memory(event_id, content, participant_ids, emotional_valence)

    async def retrieve_temporal(
        self,
        character_id: EntityId,
        time_start: float,
        time_end: float,
        query: str = "",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        if self._memory_service is None:
            return []
        return self._memory_service.retrieve_temporal(character_id, time_start, time_end, query, limit)

    async def memory_tool_call(
        self,
        character_id: EntityId,
        tool_name: str,
        params: Dict[str, Any],
    ) -> Any:
        if self._memory_service is None:
            return None
        return self._memory_service.memory_tool_call(character_id, tool_name, params)

    async def load_memory_module(self, character_id: EntityId) -> None:
        if self._memory_service is None:
            return
        self._memory_service.load_memory_module(character_id)

    async def unload_memory_module(self, character_id: EntityId) -> None:
        if self._memory_service is None:
            return
        self._memory_service.unload_memory_module(character_id)

    def save_snapshot(self) -> Dict[str, Any]:
        characters_serialized = []
        for entity in self._characters.values():
            characters_serialized.append(entity.to_dict())
        return {
            "characters": characters_serialized,
        }

    def load_snapshot(self, data: Dict[str, Any]) -> None:
        self._characters = {}
        for char_data in data.get("characters", []):
            entity = CharacterEntity.from_dict(char_data)
            self._characters[entity.entity_id] = entity


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result
