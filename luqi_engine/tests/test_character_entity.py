"""角色实体测试"""

import asyncio
import pytest
from luqi_engine.character.character_entity import (
    CharacterEntity, Motive, MotivationEngine,
)
from luqi_engine.character.personality import OceanPersonality
from luqi_engine.character.emotion import PADState
from luqi_engine.character.memory import MemoryEntry, MemoryType
from luqi_engine.character.goap import GOAPAction, GOAPWorldState
from luqi_engine.core.config import CharacterConfig


class TestMotive:
    def test_default_values(self):
        m = Motive(motive_id="hunger", name="饥饿", layer=1, base_intensity=0.8)
        assert m.current_satisfaction == 0.5
        assert m.decay_rate == 0.001

    def test_custom_satisfaction(self):
        m = Motive(motive_id="thirst", name="口渴", layer=1, base_intensity=0.9, current_satisfaction=0.1)
        assert m.current_satisfaction == 0.1


class TestMotivationEngine:
    def test_add_motive(self):
        engine = MotivationEngine()
        engine.add_motive(Motive("m1", "M1", 1, 0.8))
        assert "m1" in engine.motives

    def test_get_prioritized_motives(self):
        engine = MotivationEngine([
            Motive("low", "Low", 3, 0.2),
            Motive("high", "High", 1, 0.9),
            Motive("mid", "Mid", 2, 0.5),
        ])
        prioritized = engine.get_prioritized_motives()
        assert len(prioritized) == 3
        assert prioritized[0][0] == "high"
        assert prioritized[0][1] >= prioritized[1][1]

    def test_update_satisfaction(self):
        engine = MotivationEngine()
        engine.add_motive(Motive("m1", "M1", 1, 0.8))
        engine.update_satisfaction("m1", 0.3)
        assert abs(engine.motives["m1"].current_satisfaction - 0.8) < 1e-9

    def test_decay_all(self):
        engine = MotivationEngine([Motive("m1", "M1", 1, 0.8)])
        engine.decay_all(100.0)
        assert engine.motives["m1"].current_satisfaction < 0.5

    def test_drive_strength_clamped(self):
        engine = MotivationEngine([Motive("m1", "M1", 1, 10.0)])
        strength = engine.calculate_drive_strength(engine.motives["m1"])
        assert 0.0 <= strength <= 1.0

    def test_context_danger_modifier(self):
        engine = MotivationEngine([Motive("survival", "生存", 1, 0.8)])
        strength_normal = engine.calculate_drive_strength(engine.motives["survival"], {})
        strength_danger = engine.calculate_drive_strength(engine.motives["survival"], {"danger_level": 0.9})
        # 修复弱断言：验证危险情境下的驱动力强度
        # 在危险情境下，驱动力应该增强或至少保持非负
        assert strength_danger >= 0, "Drive strength should be non-negative even in danger context"
        # 验证危险情境下的驱动力不小于正常情境
        assert strength_danger >= strength_normal, \
            f"Danger strength ({strength_danger}) should be >= normal strength ({strength_normal})"


class TestCharacterEntityCreation:
    def test_default_creation(self):
        entity = CharacterEntity(name="TestChar")
        assert entity.name == "TestChar"
        assert entity.entity_id.startswith("char")
        assert isinstance(entity.personality, OceanPersonality)
        assert isinstance(entity.emotion, PADState)

    def test_custom_personality(self):
        p = OceanPersonality(openness=80)
        e = CharacterEntity(name="OpenChar", personality=p)
        assert e.personality.get_score("openness") == 80.0

    def test_to_dict_roundtrip(self):
        e = CharacterEntity(name="DictChar")
        d = e.to_dict()
        assert d["name"] == "DictChar"
        assert "entity_id" in d
        restored = CharacterEntity.from_dict(d)
        assert restored.name == "DictChar"


class TestCharacterEntityDecide:
    def test_decide_no_motives_returns_empty_dict(self):
        e = CharacterEntity(name="Empty")
        result = asyncio.run(e.decide({}))
        assert isinstance(result, dict)
        assert result.get("dominant_desire") == ""
        assert result.get("goap_plan") == []

    def test_decide_with_motive_no_actions_returns_dict(self):
        e = CharacterEntity(name="NoActions")
        e.motivation.add_motive(Motive("goal", "Goal", 1, 0.9))
        result = asyncio.run(e.decide({}))
        assert isinstance(result, dict)
        assert "dominant_desire" in result
        assert "utility_scores" in result

    def test_decide_with_actions(self):
        e = CharacterEntity(name="Planner")
        e.motivation.add_motive(Motive("survive", "生存", 1, 0.9))
        actions = [
            GOAPAction(name="eat", preconditions={"hungry": True}, effects={"hungry": False}, cost=1.0),
        ]
        result = asyncio.run(e.decide({}, available_actions=actions))
        assert isinstance(result, dict)
        assert "selected_action" in result
        assert "goap_plan" in result

    def test_decide_sets_current_goal(self):
        e = CharacterEntity(name="GoalSetter")
        e.motivation.add_motive(Motive("primary", "主目标", 1, 0.9))
        asyncio.run(e.decide({}))
        assert e._current_goal == "primary"


class TestCharacterEntityConsistency:
    def test_consistent_action_high_score(self):
        e = CharacterEntity(name="Consistent")
        is_consistent, score = e.validate_behavior_consistency({"type": "careful"})
        assert isinstance(is_consistent, bool)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0


class TestCharacterEntityEventHandling:
    def test_on_event_stores_memory(self):
        e = CharacterEntity(name="EventListener")
        entry = MemoryEntry(who="小雪", what="遇到了鹿栖", where="森林", why="探险")
        e.memory.store(entry)
        results = e.memory.retrieve("鹿栖")
        assert len(results) > 0

    def test_on_event_updates_emotion(self):
        e = CharacterEntity(name="EmoHandler")
        original_pleasure = e.emotion.pleasure
        updated = e.emotion.update(0.5, 0.3, 0.1)
        assert updated.pleasure != original_pleasure


class TestCharacterEntityMultiCharacter:
    def test_two_entities_independent_memory(self):
        e1 = CharacterEntity(name="A")
        e2 = CharacterEntity(name="B")
        e1.memory.store(MemoryEntry(who="A", what="A的专属记忆"))
        e2.memory.store(MemoryEntry(who="B", what="B的专属记忆"))
        a_results = e1.memory.retrieve("A的专属记忆")
        b_results = e2.memory.retrieve("B的专属记忆")
        assert len(a_results) > 0
        assert len(b_results) > 0
