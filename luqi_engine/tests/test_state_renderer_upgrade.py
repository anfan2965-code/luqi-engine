"""
StateRenderer v2 升级 + TokenBudgetProfile 测试 — Phase 3 深度聚合层
覆盖: TokenBudgetProfile / render_deep_state / estimate_tokens / 场景优化配置
"""

from __future__ import annotations

import unittest

from luqi_engine.character.deep_character import (
    DeepCharacterState,
    MotivationDominance,
    NarrativeArcPhase,
    PsychologicalTensionLevel,
    ShadowActivationState,
)
from luqi_engine.llm.state_renderer import (
    StateRenderer,
    TokenBudgetProfile,
)


class TestTokenBudgetProfileConstruction(unittest.TestCase):
    """TokenBudgetProfile 构造和默认值测试"""

    def test_default_construction(self) -> None:
        profile = TokenBudgetProfile()
        
        self.assertEqual(profile.total_budget, 2000)
        self.assertIn("personality_core", profile.section_weights)
        self.assertIn("existential_state", profile.section_weights)
        self.assertIn("memory", profile.section_weights)
        self.assertEqual(profile.min_section_tokens, 20)
        self.assertEqual(profile.overflow_strategy, "truncate_tail")

    def test_custom_total_budget(self) -> None:
        profile = TokenBudgetProfile(total_budget=5000)
        
        self.assertEqual(profile.total_budget, 5000)

    def test_custom_section_weights(self) -> None:
        custom_weights = {
            "personality_core": 0.40,
            "motivation": 0.30,
            "memory": 0.20,
            "social": 0.10,
        }
        profile = TokenBudgetProfile(section_weights=custom_weights)
        
        self.assertAlmostEqual(profile.section_weights["personality_core"], 0.40, places=5)

    def test_empty_weights_fallback_to_defaults(self) -> None:
        profile = TokenBudgetProfile(total_budget=1500, section_weights={})
        
        self.assertGreater(len(profile.section_weights), 0)
        self.assertIn("personality_core", profile.section_weights)

    def test_weights_sum_reasonable(self) -> None:
        profile = TokenBudgetProfile()
        
        total = sum(profile.section_weights.values())
        self.assertGreater(total, 0.9)
        self.assertLessEqual(total, 1.2)


class TestTokenBudgetProfileFactoryMethods(unittest.TestCase):
    """TokenBudgetProfile 工厂方法测试"""

    def test_dialogue_optimized_profile(self) -> None:
        profile = TokenBudgetProfile.dialogue_optimized()
        
        self.assertGreater(profile.section_weights.get("memory", 0),
                          profile.section_weights.get("narrative_identity", 0))
        self.assertGreater(profile.section_weights.get("social", 0),
                          profile.section_weights.get("scene_instruction", 0))

    def test_narrative_optimized_profile(self) -> None:
        profile = TokenBudgetProfile.narrative_optimized()
        
        self.assertGreater(profile.section_weights.get("narrative_identity", 0),
                          profile.section_weights.get("social", 0))
        self.assertGreater(profile.section_weights.get("motivation", 0),
                          profile.section_weights.get("response_hint", 0))

    def test_conflict_optimized_profile(self) -> None:
        profile = TokenBudgetProfile.conflict_optimized()
        
        self.assertGreater(profile.section_weights.get("existential_state", 0),
                          profile.section_weights.get("memory", 0))

    def test_factory_methods_return_token_budget_profiles(self) -> None:
        for factory in [
            TokenBudgetProfile.dialogue_optimized,
            TokenBudgetProfile.narrative_optimized,
            TokenBudgetProfile.conflict_optimized,
        ]:
            result = factory()
            self.assertIsInstance(result, TokenBudgetProfile)


class TestEstimateTokens(unittest.TestCase):
    """estimate_tokens() token估算测试"""

    def test_empty_string_zero_tokens(self) -> None:
        tokens = StateRenderer.estimate_tokens("")
        self.assertEqual(tokens, 0)

    def test_none_like_empty_string_zero_tokens(self) -> None:
        tokens = StateRenderer.estimate_tokens("")
        self.assertEqual(tokens, 0)

    def test_chinese_text_estimation(self) -> None:
        text = "这是一个测试文本"
        tokens = StateRenderer.estimate_tokens(text)
        
        expected = int(len(text) / 1.5) + 1
        self.assertEqual(tokens, expected)

    def test_english_text_estimation(self) -> None:
        text = "Hello world this is a test"
        tokens = StateRenderer.estimate_tokens(text)
        
        expected = int(len(text) / 4) + 1
        self.assertEqual(tokens, expected)

    def test_mixed_language_estimation(self) -> None:
        text = "Hello世界Test中文123"
        chinese_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff")
        other_count = len(text) - chinese_count
        expected = int(chinese_count / 1.5 + other_count / 4) + 1
        
        tokens = StateRenderer.estimate_tokens(text)
        self.assertEqual(tokens, expected)

    def test_single_character(self) -> None:
        tokens = StateRenderer.estimate_tokens("中")
        self.assertGreaterEqual(tokens, 1)

    def test_long_text_larger_estimate(self) -> None:
        short = "短文本"
        long_text = "这是一段非常长的文本" * 100
        
        short_tokens = StateRenderer.estimate_tokens(short)
        long_tokens = StateRenderer.estimate_tokens(long_text)
        
        self.assertGreater(long_tokens, short_tokens)


class TestRenderDeepState(unittest.TestCase):
    """render_deep_state() v2 API 渲染测试"""

    def setUp(self) -> None:
        self.renderer = StateRenderer()

    def test_render_empty_state_returns_empty_or_hint(self) -> None:
        state = DeepCharacterState()
        result = self.renderer.render_deep_state(state)
        
        self.assertIsInstance(result, str)

    def test_render_with_archetype(self) -> None:
        state = DeepCharacterState(dominant_archetype="HERO")
        result = self.renderer.render_deep_state(state)
        
        self.assertIn("[深层人格]", result)
        self.assertIn("原型:", result)

    def test_render_with_shadow_active(self) -> None:
        state = DeepCharacterState(
            dominant_archetype="HERO",
            shadow_state=ShadowActivationState.ACTIVE,
            active_shadow_aspects=["傲慢"],
        )
        result = self.renderer.render_deep_state(state)
        
        self.assertIn("活跃", result)
        self.assertIn("傲慢", result)

    def test_render_with_persona(self) -> None:
        state = DeepCharacterState(
            dominant_archetype="CREATOR",
            persona_active=True,
            persona_description="艺术家",
        )
        result = self.renderer.render_deep_state(state)
        
        self.assertIn("面具:艺术家", result)

    def test_render_with_existential_tension(self) -> None:
        state = DeepCharacterState(
            tension_level=PsychologicalTensionLevel.CRISIS,
            existential_anxiety=0.7,
            authenticity_score=0.3,
        )
        result = self.renderer.render_deep_state(state)
        
        self.assertIn("[存在状态]", result)
        self.assertIn("危机", result)

    def test_render_with_narrative(self) -> None:
        state = DeepCharacterState(
            narrative_phase=NarrativeArcPhase.ORDEAL,
            core_narrative="面对挑战",
            narrative_tension=0.8,
        )
        result = self.renderer.render_deep_state(state)
        
        self.assertIn("[叙事弧]", result)
        self.assertIn("严峻考验", result)

    def test_render_with_motivation(self) -> None:
        state = DeepCharacterState(
            dominant_need="SAFETY",
            need_satisfaction_map={"SAFETY": 0.25},
            urgency_level=1.6,
            current_conflict="生存vs自由",
        )
        result = self.renderer.render_deep_state(state)
        
        self.assertIn("[主导需求]", result)
        self.assertIn("冲突:生存vs自由", result)

    def test_render_with_memories(self) -> None:
        memories = [
            {"content": "第一次相遇在雨夜", "emotion": "紧张"},
            {"content": "他说会保护我", "emotion": "安心"},
        ]
        state = DeepCharacterState(relevant_memories=memories)
        result = self.renderer.render_deep_state(state)
        
        self.assertIn("[核心记忆]", result)
        self.assertIn("雨夜", result)

    def test_render_with_social(self) -> None:
        state = DeepCharacterState(
            relationship_summary="信任的盟友",
            social_role="伙伴",
            trust_level_current=0.9,
        )
        result = self.renderer.render_deep_state(state)
        
        self.assertIn("[社交关系]", result)
        self.assertIn("90%", result)

    def test_render_with_scene_context(self) -> None:
        state = DeepCharacterState(scene_context="废弃的城堡大厅")
        result = self.renderer.render_deep_state(state)
        
        self.assertIn("[场景]", result)
        self.assertIn("废弃的城堡大厅", result)

    def test_render_includes_style_hint(self) -> None:
        state = DeepCharacterState(response_style_hint="简短有力; 带有一丝疲惫")
        result = self.renderer.render_deep_state(state)
        
        self.assertIn("[回复风格]", result)
        self.assertIn("简短有力", result)

    def test_respects_max_tokens_limit(self) -> None:
        state = DeepCharacterState(
            dominant_archetype="HERO" * 50,
            active_shadow_aspects=[f"shadow_{i}" for i in range(20)],
            persona_active=True,
            persona_description="x" * 500,
            tension_level=PsychologicalTensionLevel.CRISIS,
            existential_anxiety=0.99,
            core_narrative="y" * 500,
            relevant_memories=[{"content": f"z{i}" * 100} for i in range(10)],
            relationship_summary="w" * 300,
            scene_context="v" * 400,
        )
        result = self.renderer.render_deep_state(state, max_tokens=100)
        
        estimated = StateRenderer.estimate_tokens(result)
        self.assertLessEqual(estimated, 120)

    def test_high_priority_sections_included_first(self) -> None:
        state = DeepCharacterState(
            dominant_archetype="SAGE",
            dominant_need="COGNITIVE",
            need_satisfaction_map={"COGNITIVE": 0.4},
        )
        result = self.renderer.render_deep_state(state, max_tokens=50)
        
        lines = [l.strip() for l in result.split("\n") if l.strip()]
        if len(lines) >= 2:
            first_line = lines[0]
            self.assertTrue(
                first_line.startswith("[深层人格]") or
                first_line.startswith("[主导需求]") or
                first_line.startswith("[回复风格]"),
            )


class TestRenderWithTokenBudget(unittest.TestCase):
    """render_with_token_budget() 自定义预算渲染测试"""

    def test_uses_budget_total(self) -> None:
        renderer = StateRenderer()
        budget = TokenBudgetProfile(total_budget=100)
        
        state = DeepCharacterState(dominant_archetype="HERO")
        result = renderer.render_with_token_budget(state, budget)
        
        estimated = StateRenderer.estimate_tokens(result)
        self.assertLessEqual(estimated, 130)

    def test_large_budget_allows_more_content(self) -> None:
        renderer = StateRenderer()
        small_budget = TokenBudgetProfile(total_budget=30)
        large_budget = TokenBudgetProfile(total_budget=500)
        
        state = DeepCharacterState(
            dominant_archetype="EXPLORER",
            shadow_state=ShadowActivationState.ACTIVE,
            active_shadow_aspects=["冲动"],
            persona_active=True,
            persona_description="冒险家",
            tension_level=PsychologicalTensionLevel.TENSE,
            existential_anxiety=0.6,
            narrative_phase=NarrativeArcPhase.INITIATION,
            core_narrative="踏上旅程",
            dominant_need="BELONGING",
            need_satisfaction_map={"BELONGING": 0.3},
            relevant_memories=[{"content": "出发的那天"}],
            relationship_summary="同伴",
            trust_level_current=0.7,
        )
        
        small_result = renderer.render_with_token_budget(state, small_budget)
        large_result = renderer.render_with_token_budget(state, large_budget)
        
        self.assertGreaterEqual(len(large_result), len(small_result))


class TestV1APICompatibility(unittest.TestCase):
    """v1 API 向后兼容性测试 (确保升级不破坏原有功能)"""

    def test_v1_construction_still_works(self) -> None:
        from luqi_engine.core.config import LLMConfig
        
        config = LLMConfig(system_token_budget=500)
        renderer = StateRenderer(config=config)
        
        self.assertIsNotNone(renderer)

    def test_v1_render_system_prompt_basic(self) -> None:
        renderer = StateRenderer()
        
        result = renderer.render_system_prompt(
            character_name="测试角色",
            background="一个勇敢的战士",
        )
        
        self.assertIsInstance(result, str)
        self.assertIn("测试角色", result)

    def test_v1_render_with_personality(self) -> None:
        renderer = StateRenderer()
        
        result = renderer.render_system_prompt(
            character_name="test",
            personality={
                "openness": 0.8,
                "conscientiousness": 0.3,
                "extraversion": 0.7,
                "agreeableness": 0.5,
                "neuroticism": 0.4,
            },
        )
        
        self.assertIsInstance(result, str)

    def test_v1_render_with_emotions(self) -> None:
        renderer = StateRenderer()
        
        result = renderer.render_system_prompt(
            pad_emotion={"pleasure": 0.7, "arousal": 0.6},
            seven_emotions={"喜": 0.8, "怒": 0.2, "忧": 0.5},
        )
        
        self.assertIsInstance(result, str)

    def test_v1_render_with_memories(self) -> None:
        renderer = StateRenderer()
        
        result = renderer.render_system_prompt(
            memories=[
                {"who": "Alice", "what": "说了你好"},
                {"who": "Bob", "what": "给了礼物"},
            ],
        )
        
        self.assertIn("记忆", result)

    def test_v1_compression_kicks_in_for_long_prompts(self) -> None:
        renderer = StateRenderer()
        
        long_name = "A" * 200
        long_bg = "B" * 200
        long_instr = "C" * 200
        
        result = renderer.render_system_prompt(
            character_name=long_name,
            background=long_bg,
            behavior_instruction=long_instr,
        )
        
        self.assertIsInstance(result, str)


if __name__ == "__main__":
    unittest.main()
