import math
import pytest
from luqi_engine.core.types import (
    DesireVector, SevenEmotions, SixDesires,
    SevenEmotionType, SixDesireType, MaslowNeedType, FrommNeedType,
    Vector3, BoundingBox, WorldState, EventType, generate_entity_id,
)


class TestDesireVector:
    def test_default_dimensions_count(self):
        dv = DesireVector()
        assert len(dv.dimensions) == 17

    def test_all_default_dimensions_present(self):
        dv = DesireVector()
        assert len(dv.dimensions) == 17
        for dim_name in dv.dimensions:
            assert isinstance(dim_name, str)

    def test_default_values_zero(self):
        dv = DesireVector()
        for val in dv.dimensions.values():
            assert val == 0.0

    def test_set_dimension_clamps_high(self):
        dv = DesireVector()
        dv.set_dimension("physiological", 5.0)
        assert dv.get_dimension("physiological") == 1.0

    def test_set_dimension_clamps_low(self):
        dv = DesireVector()
        dv.set_dimension("safety", -1.0)
        assert dv.get_dimension("safety") == 0.0

    def test_set_dimension_valid(self):
        dv = DesireVector()
        dv.set_dimension("belonging", 0.7)
        assert abs(dv.get_dimension("belonging") - 0.7) < 1e-9

    def test_get_dimension_missing_returns_zero(self):
        dv = DesireVector()
        assert dv.get_dimension("nonexistent") == 0.0

    def test_add_dimension(self):
        dv = DesireVector()
        dv.add_dimension("custom_hunger", 0.5)
        assert dv.get_dimension("custom_hunger") == 0.5
        assert len(dv.dimensions) == 18

    def test_remove_dimension(self):
        dv = DesireVector()
        dv.remove_dimension("physiological")
        assert "physiological" not in dv.dimensions
        assert len(dv.dimensions) == 16

    def test_magnitude_zero(self):
        dv = DesireVector()
        assert dv.magnitude() == 0.0

    def test_magnitude_single(self):
        dv = DesireVector()
        dv.set_dimension("esteem", 1.0)
        assert abs(dv.magnitude() - 1.0) < 1e-9

    def test_magnitude_multiple(self):
        dv = DesireVector()
        dv.set_dimension("physiological", 1.0)
        dv.set_dimension("safety", 1.0)
        assert abs(dv.magnitude() - math.sqrt(2.0)) < 1e-9

    def test_normalize_zero_vector(self):
        dv = DesireVector()
        normed = dv.normalize()
        assert normed.magnitude() == 0.0

    def test_normalize_unit_vector(self):
        dv = DesireVector()
        dv.set_dimension("esteem", 1.0)
        normed = dv.normalize()
        assert abs(normed.get_dimension("esteem") - 1.0) < 1e-9
        assert abs(normed.magnitude() - 1.0) < 1e-9

    def test_normalize_general(self):
        dv = DesireVector()
        dv.set_dimension("physiological", 3.0)
        dv.set_dimension("safety", 4.0)
        normed = dv.normalize()
        assert abs(normed.magnitude() - 1.0) < 1e-9

    def test_maslows_hierarchy(self):
        dv = DesireVector()
        dv.set_dimension("physiological", 0.9)
        dv.set_dimension("safety", 0.7)
        dv.set_dimension("belonging", 0.5)
        dv.set_dimension("esteem", 0.3)
        dv.set_dimension("cognitive", 0.1)
        dv.set_dimension("self_actualization", 0.05)
        assert dv.get_dimension("physiological") > dv.get_dimension("self_actualization")

    def test_six_desires_integration(self):
        dv = DesireVector()
        for dim in ("sight", "hearing", "smell", "taste", "touch", "mind"):
            dv.set_dimension(dim, 0.5)
        for dim in ("sight", "hearing", "smell", "taste", "touch", "mind"):
            assert abs(dv.get_dimension(dim) - 0.5) < 1e-9

    def test_fromm_needs_integration(self):
        dv = DesireVector()
        for dim in ("relatedness", "transcendence", "rootedness", "identity", "orientation"):
            dv.set_dimension(dim, 0.3)
        for dim in ("relatedness", "transcendence", "rootedness", "identity", "orientation"):
            assert abs(dv.get_dimension(dim) - 0.3) < 1e-9


class TestSevenEmotions:
    def test_default_weights_zero(self):
        se = SevenEmotions()
        for src in SevenEmotionType:
            for tgt in SevenEmotionType:
                assert se.get_weight(src.name, tgt.name) == 0.0

    def test_default_active_emotions_zero(self):
        se = SevenEmotions()
        for emo in SevenEmotionType:
            assert se.get_emotion(emo.name) == 0.0

    def test_set_get_emotion(self):
        se = SevenEmotions()
        se.set_emotion("joy", 0.8)
        assert abs(se.get_emotion("joy") - 0.8) < 1e-9

    def test_dominant_emotion(self):
        se = SevenEmotions()
        se.set_emotion("joy", 0.1)
        se.set_emotion("anger", 0.9)
        assert se.dominant_emotion() == "anger"

    def test_dominant_emotion_all_zero(self):
        se = SevenEmotions()
        assert se.dominant_emotion() is None

    def test_set_weight(self):
        se = SevenEmotions()
        se.set_weight("joy", "sadness", -0.5)
        assert abs(se.get_weight("joy", "sadness") - (-0.5)) < 1e-9

    def test_emotion_interaction_joy_sadness(self):
        se = SevenEmotions()
        se.set_weight("joy", "sadness", -0.6)
        se.set_emotion("joy", 0.8)
        se.set_emotion("sadness", 0.3)
        w = se.get_weight("joy", "sadness")
        assert w < 0

    def test_all_seven_emotions_present(self):
        se = SevenEmotions()
        for emo in SevenEmotionType:
            se.set_emotion(emo.value, 0.5)
        expected_values = {e.value for e in SevenEmotionType}
        assert set(se.active_emotions.keys()) == expected_values

    def test_multiple_emotions_dominant(self):
        se = SevenEmotions()
        se.set_emotion("joy", 0.5)
        se.set_emotion("love", 0.5)
        se.set_emotion("fear", 0.9)
        assert se.dominant_emotion() == "fear"


class TestSixDesires:
    def test_default_intensities_zero(self):
        sd = SixDesires()
        for desire in SixDesireType:
            assert sd.get_intensity(desire.name) == 0.0

    def test_set_intensity_clamps_high(self):
        sd = SixDesires()
        sd.set_intensity("eye", 2.0)
        assert sd.get_intensity("eye") == 1.0

    def test_set_intensity_clamps_low(self):
        sd = SixDesires()
        sd.set_intensity("ear", -1.0)
        assert sd.get_intensity("ear") == 0.0

    def test_set_intensity_valid(self):
        sd = SixDesires()
        sd.set_intensity("tongue", 0.6)
        assert abs(sd.get_intensity("tongue") - 0.6) < 1e-9

    def test_all_six_desires_present(self):
        sd = SixDesires()
        expected_values = {d.value for d in SixDesireType}
        assert set(sd.intensities.keys()) == expected_values

    def test_sensory_hierarchy(self):
        sd = SixDesires()
        sd.set_intensity("eye", 0.9)
        sd.set_intensity("ear", 0.7)
        sd.set_intensity("nose", 0.3)
        sd.set_intensity("tongue", 0.5)
        sd.set_intensity("body", 0.8)
        sd.set_intensity("mind", 0.6)
        assert sd.get_intensity("eye") > sd.get_intensity("nose")


class TestVector3:
    def test_creation(self):
        v = Vector3(x=1.0, y=2.0, z=3.0)
        assert v.x == 1.0 and v.y == 2.0 and v.z == 3.0

    def test_distance_to(self):
        a = Vector3(x=0.0, y=0.0, z=0.0)
        b = Vector3(x=3.0, y=4.0, z=0.0)
        assert abs(a.distance_to(b) - 5.0) < 1e-9

    def test_lerp(self):
        a = Vector3(x=0.0, y=0.0, z=0.0)
        b = Vector3(x=10.0, y=10.0, z=10.0)
        mid = a.lerp(b, 0.5)
        assert abs(mid.x - 5.0) < 1e-9

    def test_to_tuple(self):
        v = Vector3(x=1.0, y=2.0, z=3.0)
        assert v.to_tuple() == (1.0, 2.0, 3.0)


class TestBoundingBox:
    def test_contains(self):
        bb = BoundingBox(center=Vector3(x=5, y=5, z=5), half_extents=Vector3(x=5, y=5, z=5))
        p = Vector3(x=5, y=5, z=5)
        assert bb.contains(p)

    def test_not_contains(self):
        bb = BoundingBox(center=Vector3(x=5, y=5, z=5), half_extents=Vector3(x=5, y=5, z=5))
        p = Vector3(x=15, y=5, z=5)
        assert not bb.contains(p)

    def test_intersects(self):
        a = BoundingBox(center=Vector3(x=5, y=5, z=5), half_extents=Vector3(x=5, y=5, z=5))
        b = BoundingBox(center=Vector3(x=10, y=10, z=10), half_extents=Vector3(x=5, y=5, z=5))
        assert a.intersects(b)

    def test_not_intersects(self):
        a = BoundingBox(center=Vector3(x=2.5, y=2.5, z=2.5), half_extents=Vector3(x=2.5, y=2.5, z=2.5))
        b = BoundingBox(center=Vector3(x=12.5, y=12.5, z=12.5), half_extents=Vector3(x=2.5, y=2.5, z=2.5))
        assert not a.intersects(b)


class TestWorldState:
    def test_merge_flags(self):
        a = WorldState(flags={"alive": True, "visible": False})
        b = WorldState(flags={"visible": True, "moving": True})
        merged = a.merge(b)
        assert merged.flags["alive"] is True
        assert merged.flags["visible"] is True
        assert merged.flags["moving"] is True

    def test_merge_variables(self):
        a = WorldState(variables={"health": 100})
        b = WorldState(variables={"mana": 50})
        merged = a.merge(b)
        assert merged.variables["health"] == 100
        assert merged.variables["mana"] == 50


class TestGenerateEntityId:
    def test_unique(self):
        ids = {generate_entity_id() for _ in range(100)}
        assert len(ids) == 100

    def test_with_prefix(self):
        eid = generate_entity_id("char")
        assert eid.startswith("char")


class TestEventType:
    def test_all_types_exist(self):
        actual = {e.name for e in EventType}
        assert "ENTITY_SPAWNED" in actual
        assert "ENTITY_DESPAWNED" in actual
        assert "STATE_CHANGED" in actual
        assert "DIALOGUE_STARTED" in actual
        assert "DIALOGUE_ENDED" in actual
        assert "CHARACTER_ACTION" in actual
        assert "CONFLICT_DETECTED" in actual
        assert "CUSTOM" in actual
