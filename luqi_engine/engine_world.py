"""
EngineWorld - 世界观模块
负责世界观创建、场景创建、角色创建、多角色对话
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

from luqi_engine.core.types import EntityId
from luqi_engine.llm.dialogue_modes import DialogueMode
from luqi_engine.core.constants import (
    AtmosphereMode,
    CriticMode,
    NovelMode,
    _DEFAULT_DOMINANT_EMOTION,
)


class EngineWorld:
    """
    世界观模块
    负责世界观创建、场景创建、角色创建、多角色对话
    """

    async def create_world(
        self,
        raw_content: str,
        content_type: str = "text",
    ) -> Dict[str, Any]:
        """
        从用户输入创建世界观
        """
        self._ensure_initialized()
        if self._worldview is None:
            raise RuntimeError("世界观渲染器未初始化")
        elements = await self._worldview.extract_elements(raw_content, content_type)
        classified = await self._worldview.classify_elements(elements)
        relations = await self._worldview.build_relations(classified)
        conflicts = await self._worldview.detect_conflicts({"classified": classified})
        if conflicts and self._local_model is not None:
            for conflict in conflicts:
                correction = await self._local_model.correct({
                    "conflict": {
                        "id": conflict.conflict_id,
                        "type": conflict.conflict_type,
                        "description": conflict.description,
                    },
                    "classified": classified,
                })
                if correction.get("suggestions"):
                    conflict.suggested_resolutions.extend(correction["suggestions"])
        guidance = await self._worldview.render_guidance({
            "classified": classified,
            "relations": relations,
        })
        self._world_guidance = guidance

        try:
            if self._narrative_doc is not None and self._novelist_agent is not None and self._llm_bridge is not None:
                novel_context = {
                    "narrative_context": str(classified),
                    "recent_facts": [],
                    "open_questions": [],
                }
                novel_delta = await self._novelist_agent.run(novel_context, self._llm_bridge, mode=NovelMode.INCREMENTAL)
                if novel_delta is not None:
                    self._narrative_doc.apply_delta(novel_delta)

            if self._critic_agent is not None and self._llm_bridge is not None:
                critic_context = {
                    "canonical_ir": None,
                    "narrative_context": self._narrative_doc.to_prompt_context() if self._narrative_doc else "",
                }
                await self._critic_agent.run(critic_context, self._llm_bridge, mode=CriticMode.LIGHT)

            if self._atmosphere_agent is not None and self._llm_bridge is not None:
                atm_context = {
                    "scene_name": self._narrative_doc.current_scene if self._narrative_doc else "",
                    "dominant_emotion": _DEFAULT_DOMINANT_EMOTION,
                }
                await self._atmosphere_agent.run(atm_context, self._llm_bridge, mode=AtmosphereMode.LIGHT)
        except Exception as exc:
            self._logger.warning("create_world 同步初始化流程失败（不影响世界观创建）: %s", exc)

        return {
            "elements": elements,
            "classified": classified,
            "relations": relations,
            "conflicts": [self._conflict_to_dict(c) for c in conflicts],
            "guidance": guidance,
        }

    async def create_scene(self, scene_config: Dict[str, Any]) -> EntityId:
        """
        创建场景
        """
        self._ensure_initialized()
        if self._scene_builder is None:
            raise RuntimeError("场景构建器未初始化")
        return await self._scene_builder.create_scene(scene_config)

    async def create_character(self, character_config: Dict[str, Any]) -> EntityId:
        """
        创建角色
        """
        self._ensure_initialized()
        if self._character_manager is None:
            raise RuntimeError("角色管理器未初始化")
        char_id = await self._character_manager.create_character(character_config)
        if self._interaction_coordinator is not None:
            character = self._character_manager.get_character(char_id)
            if character is not None:
                self._interaction_coordinator.register_character(
                    char_id,
                    {
                        "name": character.name,
                        "extraversion": character.personality.get_score("extraversion"),
                        "authority_rank": character_config.get("authority_rank", 0),
                    },
                )
        return char_id

    async def start_dialogue(
        self,
        participants: List[EntityId],
        topic: str,
        mode: DialogueMode = DialogueMode.MULTI_CHARACTER,
        max_rounds: int = 20,
    ) -> List[Dict[str, Any]]:
        """
        启动多角色对话
        """
        self._ensure_initialized()
        if self._interaction_coordinator is None:
            raise RuntimeError("交互协调器未初始化")
        if mode == DialogueMode.SINGLE_CHARACTER and len(participants) == 1:
            char_id = participants[0]
            character = self._character_manager.get_character(char_id) if self._character_manager else None
            if character is None:
                return []
            return [{
                "round": 0,
                "speaker_id": char_id,
                "priority_score": 1.0,
                "topic": topic,
                "mode": "single_character",
            }]
        return await self._interaction_coordinator.coordinate_dialogue(
            participants=participants,
            topic=topic,
            max_rounds=max_rounds,
        )

    @staticmethod
    def _conflict_to_dict(conflict: Any) -> Dict[str, Any]:
        return {
            "conflict_id": conflict.conflict_id,
            "conflict_type": conflict.conflict_type,
            "description": conflict.description,
            "severity": conflict.severity,
            "involved_entities": conflict.involved_entities,
            "suggested_resolutions": conflict.suggested_resolutions,
        }
