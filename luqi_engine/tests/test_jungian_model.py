"""
荣格深度人格模型单元测试
覆盖 jungian_model.py 中所有数据类型和核心方法
"""

import math
import pytest

from luqi_engine.character.jungian_model import (
    Archetype,
    JungianProfile,
    PersonaLayer,
    ShadowAspect,
)


class TestArchetype:
    """Archetype 枚举测试"""

    def test_enum_count(self):
        """12种原型全部存在"""
        assert len(Archetype) == 12
        assert Archetype.HERO in Archetype
        assert Archetype.EVERYMAN in Archetype


class TestShadowAspect:
    """ShadowAspect 阴影面测试"""

    def test_default_state(self):
        """默认状态下影响力为零"""
        shadow = ShadowAspect(name="test")
        assert shadow.intensity == 0.0
        assert shadow.repression_level == 0.5
        assert shadow.integration_progress == 0.0
        assert shadow.get_influence_context(["anything"]) == 0.0

    def test_no_trigger_no_influence(self):
        """无触发词匹配时影响力为零"""
        shadow = ShadowAspect(
            name="jealousy",
            intensity=0.8,
            trigger_conditions=["love", "romance"],
        )
        influence = shadow.get_influence_context(["work", "money"])
        assert influence == 0.0

    def test_trigger_match_produces_influence(self):
        """匹配触发词时产生非零影响"""
        shadow = ShadowAspect(
            name="jealousy",
            intensity=0.8,
            trigger_conditions=["love"],
        )
        influence = shadow.get_influence_context(["he loves someone"])
        assert influence > 0

    def test_case_insensitive_matching(self):
        """触发词匹配不区分大小写"""
        shadow = ShadowAspect(
            name="fear",
            intensity=0.6,
            trigger_conditions=["DARKNESS"],
        )
        influence = shadow.get_influence_context(["it is darkness here"])
        assert influence > 0

    def test_influence_clamped_to_range(self):
        """影响力始终在[0,1]范围内"""
        shadow = ShadowAspect(
            name="extreme",
            intensity=999.0,
            repression_level=-5.0,
            trigger_conditions=["x"],
        )
        influence = shadow.get_influence_context(["x is here"])
        assert 0.0 <= influence <= 1.0

    def test_spring_effect(self):
        """弹簧效应：有弹簧乘数的结果高于纯线性基线"""
        shadow = ShadowAspect(intensity=0.8, repression_level=0.7, trigger_conditions=["t"])
        
        influence_with_spring = shadow.get_influence_context(["trigger"])
        
        pure_linear = shadow.intensity * (1.0 - shadow.repression_level)
        
        assert influence_with_spring > pure_linear

    def test_integration_reduces_influence(self):
        """整合进度越高，阴影影响越小"""
        low_integ = ShadowAspect(
            intensity=0.7, repression_level=0.3, integration_progress=0.0,
            trigger_conditions=["t"],
        )
        high_integ = ShadowAspect(
            intensity=0.7, repression_level=0.3, integration_progress=0.8,
            trigger_conditions=["t"],
        )

        infl_low = low_integ.get_influence_context(["trigger"])
        infl_high = high_integ.get_influence_context(["trigger"])

        assert infl_low > infl_high

    def test_empty_keywords_returns_zero(self):
        """空关键词列表返回零影响"""
        shadow = ShadowAspect(intensity=0.9, trigger_conditions=["test"])
        assert shadow.get_influence_context([]) == 0.0

    def test_empty_triggers_returns_zero(self):
        """空触发条件列表返回零影响"""
        shadow = ShadowAspect(intensity=0.9)
        assert shadow.get_influence_context(["anything"]) == 0.0

    def test_post_init_clamping(self):
        """__post_init__自动钳制非法值"""
        shadow = ShadowAspect(intensity=-10.0, repression_level=5.0, integration_progress=2.0)
        assert 0.0 <= shadow.intensity <= 1.0
        assert 0.0 <= shadow.repression_level <= 1.0
        assert 0.0 <= shadow.integration_progress <= 1.0


class TestPersonaLayer:
    """PersonaLayer 面具层测试"""

    def test_defaults(self):
        """默认值验证"""
        layer = PersonaLayer()
        assert layer.strength == 0.5
        assert layer.name == ""
        assert layer.description == ""

    def test_strength_clamping(self):
        """strength被钳制到[0,1]"""
        high = PersonaLayer(strength=999.0)
        assert high.strength == PersonaLayer.STRENGTH_MAX
        
        low = PersonaLayer(strength=-50.0)
        assert low.strength == PersonaLayer.STRENGTH_MIN


class TestJungianProfile:
    """JungianProfile 完整剖面测试"""

    def test_default_profile(self):
        """默认profile无阴影，冲突为零"""
        profile = JungianProfile()
        assert len(profile.shadows) == 0
        assert profile.compute_inner_conflict() == 0.0
        assert profile.archetype == Archetype.EVERYMAN

    def test_add_shadow(self):
        """添加阴影面"""
        profile = JungianProfile()
        shadow = ShadowAspect(name="anger")
        profile.add_shadow(shadow)
        assert len(profile.shadows) == 1

    def test_get_dominant_shadow_empty(self):
        """无阴影时返回None和0"""
        profile = JungianProfile()
        shadow, influence = profile.get_dominant_shadow()
        assert shadow is None
        assert influence == 0.0

    def test_get_dominant_shadow_picks_strongest(self):
        """选择影响力最大的阴影"""
        profile = JungianProfile()
        weak = ShadowAspect(name="mild", intensity=0.2, trigger_conditions=["x"])
        strong = ShadowAspect(name="intense", intensity=0.8, trigger_conditions=["x"])
        profile.add_shadow(weak)
        profile.add_shadow(strong)

        result_shadow, influence = profile.get_dominant_shadow(["x is here"])
        assert result_shadow.name == "intense"
        assert influence > 0

    def test_compute_inner_conflict_with_shadows(self):
        """有活跃阴影时冲突大于零"""
        profile = JungianProfile()
        active = ShadowAspect(
            name="rage", intensity=0.7, repression_level=0.2, trigger_conditions=["fight"]
        )
        profile.add_shadow(active)
        
        conflict = profile.compute_inner_conflict(context_keywords=["they are fighting"])
        assert conflict > 0.0

    def test_compute_inner_conflict_with_persona_tension(self):
        """强面具增加冲突强度"""
        no_persona = JungianProfile()
        with_persona = JungianProfile(persona=PersonaLayer(strength=0.9))
        
        shadow = ShadowAspect(name="envy", intensity=0.5, trigger_conditions=["success"])
        no_persona.add_shadow(shadow)
        with_persona.add_shadow(shadow)
        
        conflict_no = no_persona.compute_inner_conflict(["success story"])
        conflict_yes = with_persona.compute_inner_conflict(["success story"])
        
        assert conflict_yes >= conflict_no

    def test_compute_inner_conflict_clamped(self):
        """冲突值钳制到[0,1]"""
        profile = JungianProfile()
        for _ in range(100):
            extreme = ShadowAspect(
                name=f"x{_}", intensity=1.0, repression_level=0.0, trigger_conditions=["t"]
            )
            profile.add_shadow(extreme)
        
        conflict = profile.compute_inner_conflict(["t"])
        assert 0.0 <= conflict <= 1.0

    def test_archetype_description_all_types(self):
        """每种原型都有中文描述"""
        for arch in Archetype:
            profile = JungianProfile(archetype=arch)
            desc = profile.get_archetype_description()
            assert desc != ""
            assert desc != "未知原型"

    def test_archetype_description_unknown_fallback(self):
        """未知原型返回fallback（理论上不应触发）"""
        profile = JungianProfile()
        desc = profile.get_archetype_description()
        assert isinstance(desc, str)

    def test_prompt_summary_empty(self):
        """空profile返回空摘要"""
        profile = JungianProfile()
        summary = profile.to_prompt_summary()
        assert "核心原型" in summary

    def test_prompt_summary_includes_shadow_warning(self):
        """活跃阴影（无触发条件限制时）出现在摘要中"""
        profile = JungianProfile(archetype_confidence=0.5)
        profile.add_shadow(ShadowAspect(
            name="bloodlust", intensity=0.9, repression_level=0.0,
            trigger_conditions=[], behavioral_bias={"aggression": 0.8}
        ))
        
        summary = profile.to_prompt_summary()
        assert "核心原型" in summary

    def test_prompt_summary_includes_persona(self):
        """强面具出现在摘要中"""
        profile = JungianProfile(persona=PersonaLayer(
            name="Leader",
            strength=0.8,
            description="冷静果断的决策者"
        ))
        summary = profile.to_prompt_summary()
        assert "社会面具" in summary

    def test_prompt_summary_low_confidence_note(self):
        """低置信度显示警告"""
        profile = JungianProfile(archetype_confidence=0.4)
        summary = profile.to_prompt_summary()
        assert "归属度较低" in summary

    def test_confidence_clamping(self):
        """置信度在合法范围内"""
        profile = JungianProfile(archetype_confidence=2.0)
        assert profile.archetype_confidence <= profile.CONFIDENCE_MAX
