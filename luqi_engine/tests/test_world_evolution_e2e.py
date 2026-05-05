"""世界演化端到端测试"""

import asyncio
import pytest
from luqi_engine.worldview.renderer import WorldViewRenderer
from luqi_engine.narrative.controller import NarrativeController, NodeType, RegressionMethod
from luqi_engine.scene.builder import SceneBuilder, WeatherState
from luqi_engine.interaction.coordinator import InteractionCoordinator, SocialRule, SocialRuleType
from luqi_engine.character.personality import OceanPersonality
from luqi_engine.character.emotion import PADState, ExtendedPAD, ocean_to_pad_baseline
from luqi_engine.character.desire import DesireEngine
from luqi_engine.character.memory import MemoryStore, MemoryEntry, MemoryType
from luqi_engine.character.goap import GOAPPlanner, GOAPWorldState, GOAPAction
from luqi_engine.character.utility import UtilityBasedAI, CEMPlanner, BehaviorOption, Consideration, ResponseCurve
from luqi_engine.character.social_perception import SocialPerception
from luqi_engine.core.config import (
    EngineConfig, NarrativeConfig, SceneConfig, InteractionConfig,
    CharacterConfig, DesireConfig,
)
from luqi_engine.core.types import SevenEmotionType
from luqi_engine.core.rng import PCGRandom


class TestWorldEvolutionEndToEnd:
    def test_full_world_creation_and_evolution(self):
        rng = PCGRandom(seed=42)
        config = EngineConfig(
            narrative=NarrativeConfig(max_branch_depth=10, elasticity_coefficient=50.0),
            scene=SceneConfig(max_elements_per_scene=500, time_scale=1.0),
            interaction=InteractionConfig(max_concurrent_characters=50, dialogue_max_rounds=20),
        )

        renderer = WorldViewRenderer()
        controller = NarrativeController(config=config.narrative, rng=rng)
        builder = SceneBuilder(config=config.scene)
        coordinator = InteractionCoordinator(config=config.interaction, rng=rng)

        world_text = "# 世界设定\n- 大陆：艾尔兰德，被海洋环绕\n- 王国：北境王国，位于大陆北方\n- 魔法体系：元素魔法，基于火水风土\n- 禁魔区：王都中心不允许使用魔法"
        elements = asyncio.run(renderer.extract_elements(world_text, content_type="text"))
        assert elements.get("total", 0) > 0

        classified = asyncio.run(renderer.classify_elements(elements))
        assert isinstance(classified, dict)

        relations = asyncio.run(renderer.build_relations(classified))
        assert isinstance(relations, dict)

        guidance = asyncio.run(renderer.render_guidance({"classified": classified}))
        assert isinstance(guidance, str)
        assert len(guidance) > 0

        scene_id = asyncio.run(builder.create_scene({
            "name": "北境王国",
            "description": "位于大陆北方的王国",
            "initial_weather": "CLOUDY",
            "temperature": 0.3,
            "humidity": 0.6,
        }))
        assert scene_id is not None

        elem_ids = []
        for elem_data in [
            {"name": "王城", "position": {"x": 0, "y": 0, "z": 0}, "bounds": {"half_x": 10, "half_y": 20, "half_z": 10}},
            {"name": "魔法塔", "position": {"x": 50, "y": 0, "z": 0}, "bounds": {"half_x": 5, "half_y": 15, "half_z": 5}},
            {"name": "禁魔区", "position": {"x": 5, "y": 0, "z": 0}, "bounds": {"half_x": 3, "half_y": 3, "half_z": 3}},
        ]:
            eid = asyncio.run(builder.add_element(scene_id, elem_data))
            elem_ids.append(eid)

        conflicts = asyncio.run(builder.check_spatial_conflicts(scene_id))
        assert isinstance(conflicts, list)

        for _ in range(10):
            asyncio.run(builder.update_environment(scene_id, delta_time=3600.0))
        env = builder.get_environment(scene_id)
        assert env is not None

        root = controller.add_story_node("序章", NodeType.KEY_EVENT, "世界介绍", None, 1.0)
        ch1 = controller.add_story_node("第一章", NodeType.KEY_EVENT, "主角出发", root, 0.95)
        choice = controller.add_story_node("抉择", NodeType.TURNING_POINT, "面临选择", ch1, 0.9)
        controller.add_story_node("战斗路线", NodeType.TRANSITION, "正面战斗", choice, 0.7)
        controller.add_story_node("潜行路线", NodeType.TRANSITION, "暗中行动", choice, 0.6)
        controller.add_story_node("结局", NodeType.ENDING_CONDITION, "完成使命", ch1, 1.0)

        branch_a = controller.create_branch(choice, "勇敢路线")
        branch_b = controller.create_branch(choice, "谨慎路线")
        assert branch_a is not None
        assert branch_b is not None

        weights = asyncio.run(controller.compute_branch_weights(
            current_node={"node_id": choice, "core_relevance": 0.9},
            context={"characters": []},
        ))
        assert isinstance(weights, dict)

        dead_ends = asyncio.run(controller.detect_dead_ends({"root": root}))
        assert isinstance(dead_ends, list)

        elasticity = asyncio.run(controller.get_elasticity_coefficient())
        assert 0.0 <= elasticity <= 100.0

        state = controller.get_current_state()
        assert "current_node_id" in state
        assert "elasticity" in state


class TestThreeCharacterWorldInteraction:
    def test_three_characters_interact_in_world(self):
        rng = PCGRandom(seed=42)
        config = EngineConfig(
            interaction=InteractionConfig(max_concurrent_characters=50, dialogue_max_rounds=10),
            narrative=NarrativeConfig(max_branch_depth=10, elasticity_coefficient=50.0),
        )

        coordinator = InteractionCoordinator(config=config.interaction, rng=rng)
        controller = NarrativeController(config=config.narrative, rng=rng)
        perception = SocialPerception()

        personalities = {
            "xiaoxue": OceanPersonality(openness=70, conscientiousness=60, extraversion=28, agreeableness=75, neuroticism=40),
            "luqi": OceanPersonality(openness=85, conscientiousness=45, extraversion=65, agreeableness=55, neuroticism=25),
            "teacher": OceanPersonality(openness=50, conscientiousness=80, extraversion=40, agreeableness=60, neuroticism=30),
        }

        for cid, personality in personalities.items():
            coordinator.register_character(cid, {
                "name": cid,
                "extraversion": personality.get_score("extraversion"),
                "authority_rank": 5 if cid == "teacher" else 1,
            })

        extended_pads = {cid: ExtendedPAD() for cid in personalities}
        for cid, ext_pad in extended_pads.items():
            ocean_scores = personalities[cid].to_dict()
            baseline = ocean_to_pad_baseline(ocean_scores)
            ext_pad.pad_state = baseline

        desire_engine = DesireEngine()
        for cid in personalities:
            asyncio.run(desire_engine.update_desires(cid, {"joy": 0.3, "fear": -0.1}))

        memory_stores = {cid: MemoryStore() for cid in personalities}

        root = controller.add_story_node("课堂", NodeType.KEY_EVENT, "魔法课堂开始", None, 1.0)
        ch1 = controller.add_story_node("提问", NodeType.TURNING_POINT, "老师提问", root, 0.9)
        ch2 = controller.add_story_node("回答", NodeType.TRANSITION, "学生回答", ch1, 0.7)
        controller.add_story_node("课后", NodeType.ENDING_CONDITION, "课堂结束", ch2, 1.0)

        asyncio.run(coordinator.update_relationship("xiaoxue", "luqi", {"friendship": 0.4, "trust": 0.3}))
        asyncio.run(coordinator.update_relationship("xiaoxue", "teacher", {"respect": 0.3}))
        asyncio.run(coordinator.update_relationship("luqi", "teacher", {"respect": 0.2}))

        dist_xl = coordinator.get_social_distance("xiaoxue", "luqi")
        dist_xt = coordinator.get_social_distance("xiaoxue", "teacher")
        assert 0.0 <= dist_xl <= 1.0
        assert 0.0 <= dist_xt <= 1.0

        perception.update_potential("xiaoxue", "luqi", 0.5)
        perception.update_potential("xiaoxue", "teacher", 0.2)
        score_xl = perception.compute_perception_score("xiaoxue", "luqi")
        score_xt = perception.compute_perception_score("xiaoxue", "teacher")
        assert 0.0 <= score_xl <= 1.0
        assert 0.0 <= score_xt <= 1.0

        priorities = asyncio.run(coordinator.compute_speaking_priority(
            participants=["xiaoxue", "luqi", "teacher"],
            context={"topic": "魔法课堂", "formality_level": 0.7},
        ))
        assert isinstance(priorities, list)
        assert len(priorities) == 3

        turns = asyncio.run(coordinator.coordinate_dialogue(
            participants=["xiaoxue", "luqi", "teacher"],
            topic="元素魔法讨论",
            max_rounds=5,
        ))
        assert isinstance(turns, list)

        for cid in personalities:
            memory_stores[cid].store(MemoryEntry(
                who=cid,
                what="参加了魔法课堂讨论",
                where="魔法学院",
                why="学习元素魔法",
                importance=0.7,
            ))

        for cid in personalities:
            results = memory_stores[cid].retrieve("魔法")
            assert len(results) > 0

        for cid, ext_pad in extended_pads.items():
            ext_pad.update_from_emotion(SevenEmotionType.JOY.value, 0.3)
            pad = ext_pad.pad_state
            assert -1.0 <= pad.pleasure <= 1.0

        for cid in personalities:
            chain = asyncio.run(desire_engine.compute_drive_chain(cid, {"situation": "classroom"}))
            assert isinstance(chain, dict)
            assert "dominant_desire" in chain

        weights = asyncio.run(controller.compute_branch_weights(
            current_node={"node_id": ch1, "core_relevance": 0.9},
            context={"character_priorities": {"xiaoxue": 0.3, "luqi": 0.5, "teacher": 0.8}},
        ))
        assert isinstance(weights, dict)

        dead_ends = asyncio.run(controller.detect_dead_ends({"root": root}))
        assert isinstance(dead_ends, list)

        state = controller.get_current_state()
        assert state["total_nodes"] > 0


class TestCharacterDecisionLoop:
    def test_goap_utility_decision_pipeline(self):
        rng = PCGRandom(seed=42)

        planner = GOAPPlanner()
        planner.add_action(GOAPAction(
            name="greet",
            preconditions={"near_target": True, "social_energy": True},
            effects={"greeted": True},
            cost=1.0,
        ))
        planner.add_action(GOAPAction(
            name="approach",
            preconditions={"social_energy": True},
            effects={"near_target": True},
            cost=2.0,
        ))
        planner.add_action(GOAPAction(
            name="rest",
            preconditions={},
            effects={"social_energy": True},
            cost=0.5,
        ))

        start = GOAPWorldState({"near_target": False, "social_energy": False, "greeted": False})
        goal = GOAPWorldState({"greeted": True})
        plan = planner.plan(start, goal)
        assert plan is not None
        assert len(plan) >= 2

        ai = UtilityBasedAI(rng=rng)
        ai.add_behavior(BehaviorOption(
            name="socialize",
            considerations=[
                Consideration(name="extraversion", input_fn=lambda: 0.7, curve=ResponseCurve(curve_type="linear")),
            ],
            base_weight=0.8,
        ))
        ai.add_behavior(BehaviorOption(
            name="rest",
            considerations=[
                Consideration(name="fatigue", input_fn=lambda: 0.3, curve=ResponseCurve(curve_type="linear")),
            ],
            base_weight=0.5,
        ))

        cem = CEMPlanner(utility_ai=ai, rng=PCGRandom(seed=42), temperature=1.0)
        selected = cem.select()
        assert selected is not None
        assert selected.name in ("socialize", "rest")

        personality = OceanPersonality(openness=70, extraversion=65)
        influenced = personality.influence_decision({"socialize": 0.8, "rest": 0.5})
        assert influenced["socialize"] > influenced["rest"]

        ext_pad = ExtendedPAD()
        ocean_scores = personality.to_dict()
        baseline = ocean_to_pad_baseline(ocean_scores)
        ext_pad.pad_state = baseline
        assert baseline.pleasure > 0.0

        desire_engine = DesireEngine()
        asyncio.run(desire_engine.update_desires("char_1", {"joy": 0.5, "desire": 0.3}))
        chain = asyncio.run(desire_engine.compute_drive_chain("char_1", {"situation": "social"}))
        assert "dominant_desire" in chain

        memory = MemoryStore()
        memory.store(MemoryEntry(
            who="char_1",
            what="决定社交",
            where="广场",
            why="外向性格驱动",
            importance=0.8,
        ))
        results = memory.retrieve("社交")
        assert len(results) > 0


class TestWorldEvolutionOverTime:
    def test_scene_weather_narrative_evolution(self):
        rng = PCGRandom(seed=42)
        config = EngineConfig(
            scene=SceneConfig(time_scale=10.0),
            narrative=NarrativeConfig(max_branch_depth=10, elasticity_coefficient=50.0),
        )

        builder = SceneBuilder(config=config.scene)
        controller = NarrativeController(config=config.narrative, rng=rng)

        scene_id = asyncio.run(builder.create_scene({
            "name": "荒野",
            "initial_weather": "CLEAR",
            "temperature": 0.5,
            "humidity": 0.5,
        }))

        root = controller.add_story_node("出发", NodeType.KEY_EVENT, "冒险开始", None, 1.0)
        ch1 = controller.add_story_node("遭遇", NodeType.TURNING_POINT, "遭遇暴风雨", root, 0.8)
        ch2 = controller.add_story_node("避难", NodeType.TRANSITION, "寻找避难所", ch1, 0.6)
        ch3 = controller.add_story_node("发现", NodeType.KEY_EVENT, "发现遗迹", ch2, 0.9)
        controller.add_story_node("结局", NodeType.ENDING_CONDITION, "冒险结束", ch3, 1.0)

        weather_states = set()
        for i in range(50):
            asyncio.run(builder.update_environment(scene_id, delta_time=3600.0))
            env = builder.get_environment(scene_id)
            if env:
                weather_states.add(env["weather"])

        env_final = builder.get_environment(scene_id)
        assert env_final is not None
        assert "weather" in env_final
        assert "time_of_day" in env_final

        weights = asyncio.run(controller.compute_branch_weights(
            current_node={"node_id": ch1, "core_relevance": 0.8},
            context={"characters": []},
        ))
        assert isinstance(weights, dict)

        asyncio.run(controller.set_elasticity_coefficient(80.0))
        elasticity = asyncio.run(controller.get_elasticity_coefficient())
        assert elasticity == 80.0

        state = controller.get_current_state()
        assert state["total_nodes"] >= 5
