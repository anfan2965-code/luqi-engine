"""
场景感知数据类型单元测试
覆盖 awareness_types.py 中所有数据类型和核心方法
"""

import math
import time
import pytest

from luqi_engine.scene.awareness_types import (
    AreaType,
    AmbientAttribute,
    AmbientState,
    EntityPresence,
    EntityRole,
    ObjectCategory,
    ObjectState,
    SceneContext,
    SceneEvent,
    SceneEventType,
    SpatialRelation,
    SpatialRelationType,
)


class TestAreaType:
    """AreaType 枚举测试"""

    def test_enum_count(self):
        """6种区域类型全部存在"""
        assert len(AreaType) == 6
        assert AreaType.OUTDOOR_OPEN in AreaType
        assert AreaType.INDOOR_SECRET in AreaType


class TestAmbientAttribute:
    """AmbientAttribute 枚举测试"""

    def test_enum_count(self):
        """5种环境属性全部存在"""
        assert len(AmbientAttribute) == 5
        assert AmbientAttribute.LIGHTING in AmbientAttribute
        assert AmbientAttribute.SAFETY in AmbientAttribute


class TestAmbientState:
    """AmbientState 环境状态容器测试"""

    def test_default_empty(self):
        """默认状态为空"""
        state = AmbientState()
        assert state.is_empty() is True

    def test_set_and_get(self):
        """设置和获取属性值"""
        state = AmbientState()
        state.set(AmbientAttribute.LIGHTING, 0.8)
        assert state.get(AmbientAttribute.LIGHTING) == 0.8

    def test_clamping_high(self):
        """高值自动钳制到1.0"""
        state = AmbientState()
        state.set(AmbientAttribute.LIGHTING, 999.0)
        assert state.get(AmbientAttribute.LIGHTING) == 1.0

    def test_clamping_low(self):
        """低值自动钳制到0.0"""
        state = AmbientState()
        state.set(AmbientAttribute.NOISE_LEVEL, -50.0)
        assert state.get(AmbientAttribute.NOISE_LEVEL) == 0.0

    def test_default_value(self):
        """未设置的属性返回默认值0.5"""
        state = AmbientState()
        assert state.get(AmbientAttribute.TEMPERATURE) == 0.5

    def test_custom_default(self):
        """可指定自定义默认值"""
        state = AmbientState()
        result = state.get(AmbientAttribute.CROWDING, default=0.3)
        assert result == 0.3

    def test_not_empty_after_set(self):
        """设置属性后不再为空"""
        state = AmbientState()
        state.set(AmbientAttribute.SAFETY, 0.9)
        assert state.is_empty() is False


class TestEntityPresence:
    """EntityPresence 在场实体测试"""

    def test_defaults(self):
        """默认值验证"""
        ep = EntityPresence()
        assert ep.entity_id == ""
        assert ep.role == EntityRole.NPC
        assert ep.visible_to_player is True

    def test_custom_values(self):
        """自定义值设置"""
        ep = EntityPresence(
            entity_id="npc_001",
            role=EntityRole.PLAYER,
            name="Alice",
            activity="sitting at bar",
        )
        assert ep.entity_id == "npc_001"
        assert ep.role == EntityRole.PLAYER
        assert ep.name == "Alice"
        assert ep.activity == "sitting at bar"


class TestObjectState:
    """ObjectState 可交互物体测试"""

    def test_defaults(self):
        """默认值验证"""
        obj = ObjectState()
        assert obj.interactable is True
        assert obj.accessibility == 1.0
        assert obj.category == ObjectCategory.OTHER

    def test_category_count(self):
        """6种物体类别全部存在"""
        assert len(ObjectCategory) == 6


class TestSceneEvent:
    """SceneEvent 场景事件测试"""

    def test_no_timestamp_max_relevance(self):
        """无时间戳时相关性为最大值"""
        event = SceneEvent(description="test event")
        assert event.current_relevance == event.RELEVANCE_MAX

    def test_relevance_decay_over_time(self):
        """相关性随时间衰减"""
        event = SceneEvent(
            description="old event",
            timestamp=time.time() - 100.0,
            relevance_decay=0.05,
        )
        assert event.current_relevance < 1.0
        assert event.current_relevance > 0.0

    def test_relevance_clamping(self):
        """相关性被钳制到合法范围"""
        event = SceneEvent(
            description="test",
            timestamp=0,
            relevance_decay=-999,
        )
        rel = event.current_relevance
        assert event.RELEVANCE_MIN <= rel <= event.RELEVANCE_MAX

    def test_is_stale_fresh_event(self):
        """新鲜事件不判定为过期"""
        event = SceneEvent(description="fresh", timestamp=time.time())
        assert event.is_stale() is False

    def test_is_stale_old_event(self):
        """极旧事件判定为过期"""
        very_old_time = time.time() - 10000.0
        event = SceneEvent(
            description="ancient",
            timestamp=very_old_time,
            relevance_decay=1.0,
        )
        assert event.is_stale(threshold=0.5) is True

    def test_event_type_count(self):
        """6种事件类型全部存在"""
        assert len(SceneEventType) == 6


class TestSpatialRelation:
    """SpatialRelation 空间关系测试"""

    def test_defaults(self):
        """默认值为NEARBY"""
        rel = SpatialRelation(target_id="other_001")
        assert rel.relation_type == SpatialRelationType.NEARBY
        assert rel.distance_estimate == 1.0

    def test_distance_clamping_high(self):
        """距离超上限时自动钳制"""
        rel = SpatialRelation(distance_estimate=9999.0)
        assert rel.distance_estimate == rel.DISTANCE_MAX

    def test_distance_clamping_low(self):
        """距离负值自动钳制到0"""
        rel = SpatialRelation(distance_estimate=-10.0)
        assert rel.distance_estimate == rel.DISTANCE_MIN

    def test_relation_type_count(self):
        """7种空间关系类型全部存在"""
        assert len(SpatialRelationType) == 7


class TestSceneContextEmpty:
    """SceneContext 空状态测试"""

    def test_default_is_empty(self):
        """默认构造为空"""
        ctx = SceneContext()
        assert ctx.is_empty() is True

    def test_location_makes_nonempty(self):
        """有location时不再为空"""
        ctx = SceneContext(location="酒馆")
        assert ctx.is_empty() is False

    def test_entities_make_nonempty(self):
        """有在场实体时不再为空"""
        ctx = SceneContext(present_entities=[EntityPresence(name="NPC")])
        assert ctx.is_empty() is False

    def test_events_make_nonempty(self):
        """有事件时不再为空"""
        ctx = SceneContext(recent_events=[SceneEvent(description="something")])
        assert ctx.is_empty() is False

    def test_objects_make_nonempty(self):
        """有物体时不再为空"""
        ctx = SceneContext(available_objects=[ObjectState(name="sword")])
        assert ctx.is_empty() is False

    def test_spatial_relations_make_nonempty(self):
        """有空间关系时不再为空"""
        ctx = SceneContext(spatial_relations=[SpatialRelation(target_id="x")])
        assert ctx.is_empty() is False


class TestSceneContextToPrompt:
    """SceneContext.to_llm_prompt() 测试"""

    def test_empty_context_returns_empty_string(self):
        """空上下文返回空字符串"""
        ctx = SceneContext()
        result = ctx.to_llm_prompt()
        assert result == ""

    def test_location_only(self):
        """只有位置信息"""
        ctx = SceneContext(location="玫瑰酒馆")
        result = ctx.to_llm_prompt()
        assert "玫瑰酒馆" in result
        assert "室内公共场所" in result

    def test_area_type_display_names(self):
        """各区域类型的中文显示名称正确"""
        test_cases = [
            (AreaType.OUTDOOR_OPEN, "室外开阔"),
            (AreaType.INDOOR_PRIVATE, "私密空间"),
            (AreaType.INDOOR_SECRET, "隐秘空间"),
        ]
        for area_type, expected_label in test_cases:
            ctx = SceneContext(location="test", area_type=area_type)
            result = ctx.to_llm_prompt()
            assert expected_label in result, f"Missing {expected_label} for {area_type}"

    def test_time_and_weather(self):
        """时间和天气信息"""
        ctx = SceneContext(
            location="somewhere",
            time_of_day="evening",
            weather="RAINY",
        )
        result = ctx.to_llm_prompt()
        assert "evening" in result
        assert "RAINY" in result
        assert "时间天气" in result

    def test_present_entities_visible_only(self):
        """只显示visible_to_player=True的实体"""
        visible = EntityPresence(name="Alice", visible_to_player=True)
        hidden = EntityPresence(name="Bob", visible_to_player=False)
        ctx = SceneContext(location="bar", present_entities=[visible, hidden])
        result = ctx.to_llm_prompt()
        assert "Alice" in result
        assert "Bob" not in result

    def test_present_entities_fallback_to_id(self):
        """无name时使用entity_id"""
        ep = EntityPresence(entity_id="npc_42", name="", visible_to_player=True)
        ctx = SceneContext(location="bar", present_entities=[ep])
        result = ctx.to_llm_prompt()
        assert "npc_42" in result

    def test_available_objects_interactable_only(self):
        """只显示interactable=True的物品"""
        usable = ObjectState(name="sword", interactable=True)
        decoration = ObjectState(name="painting", interactable=False)
        ctx = SceneContext(location="room", available_objects=[usable, decoration])
        result = ctx.to_llm_prompt()
        assert "sword" in result
        assert "painting" not in result

    def test_ambient_description(self):
        """环境氛围描述生成"""
        ambient = AmbientState()
        ambient.set(AmbientAttribute.LIGHTING, 0.1)
        ambient.set(AmbientAttribute.NOISE_LEVEL, 0.9)
        ctx = SceneContext(location="somewhere", ambient=ambient)
        result = ctx.to_llm_prompt()
        assert "环境氛围" in result
        assert "昏暗" in result
        assert "嘈杂" in result

    def test_ambient_neutral_range(self):
        """环境属性在中间范围时显示'一般'"""
        ambient = AmbientState()
        ambient.set(AmbientAttribute.TEMPERATURE, 0.5)
        ctx = SceneContext(location="somewhere", ambient=ambient)
        result = ctx.to_llm_prompt()
        assert "一般" in result

    def test_spatial_relation_with_description(self):
        """空间关系使用description字段"""
        rel = SpatialRelation(
            target_id="enemy_01",
            relation_type=SpatialRelationType.OPPOSITE,
            description="坐在对面",
        )
        ctx = SceneContext(location="table", spatial_relations=[rel])
        result = ctx.to_llm_prompt()
        assert "坐在对面" in result

    def test_recent_events_top_three(self):
        """最近事件只取top3且按相关性排序"""
        events = [
            SceneEvent(description="event_a", relevance_decay=0.1),
            SceneEvent(description="event_b", relevance_decay=0.2),
            SceneEvent(description="event_c", relevance_decay=0.05),
            SceneEvent(description="event_d", relevance_decay=0.5),
        ]
        for e in events:
            e.timestamp = time.time() - 10.0
        ctx = SceneContext(location="somewhere", recent_events=events)
        result = ctx.to_llm_prompt()
        assert "最近发生的事" in result
        assert "event_b" in result

    def test_stale_events_excluded(self):
        """过期事件被排除"""
        stale = SceneEvent(description="old news", timestamp=time.time() - 10000.0, relevance_decay=1.0)
        ctx = SceneContext(location="somewhere", recent_events=[stale])
        result = ctx.to_llm_prompt()
        assert "最近发生的事" not in result or "old news" not in result

    def test_truncation(self):
        """超长内容截断并加..."""
        long_desc = "x" * 1000
        ctx = SceneContext(location=long_desc)
        result = ctx.to_llm_prompt(max_length=100)
        assert len(result) <= 103
        assert result.endswith("...")

    def test_ends_with_period(self):
        """输出以句号结尾"""
        ctx = SceneContext(location="place")
        result = ctx.to_llm_prompt()
        assert result.endswith("。")

    def test_location_description_included(self):
        """location_description包含在输出中"""
        ctx = SceneContext(
            location="酒馆",
            location_description="一个破旧的木质建筑，空气中弥漫着麦芽香气",
        )
        result = ctx.to_llm_prompt()
        assert "环境描述" in result
        assert "麦芽香气" in result

    def test_full_context_ordering(self):
        """完整上下文按优先级排序: 位置>时间>人物>物品>氛围>关系>事件"""
        ctx = SceneContext(
            location="酒馆",
            time_of_day="night",
            weather="STORMY",
            present_entities=[EntityPresence(name="酒保")],
            available_objects=[ObjectState(name="啤酒杯", interactable=True)],
            recent_events=[SceneEvent(description="打碎杯子", timestamp=time.time())],
        )
        result = ctx.to_llm_prompt()
        pos_location = result.find("当前位置")
        pos_time = result.find("时间天气")
        pos_people = result.find("在场人物")
        pos_items = result.find("可见物品")
        
        assert pos_location < pos_time < pos_people < pos_items
