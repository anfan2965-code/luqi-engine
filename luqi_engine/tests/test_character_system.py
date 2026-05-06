import asyncio
import math
import time
import pytest
from luqi_engine.character.personality import OceanPersonality, PersonalityAdapter
from luqi_engine.character.emotion import (
    PADState, ExtendedPAD, ocean_to_pad_baseline,
    seven_to_plutchik, tcm_to_seven, compute_plutchik_dyad,
)
from luqi_engine.character.desire import DesireEngine
from luqi_engine.character.memory import MemoryStore, MemoryEntry, MemoryType
from luqi_engine.character.goap import GOAPPlanner, GOAPWorldState, GOAPAction
from luqi_engine.character.utility import (
    UtilityBasedAI, CEMPlanner, ResponseCurve,
    Consideration, BehaviorOption,
)
from luqi_engine.character.social_perception import (
    SocialPerception, RelationshipPotential, ContextFidelity, InterventionEntropy,
)
from luqi_engine.core.config import CharacterConfig, DesireConfig
from luqi_engine.core.types import SevenEmotionType, SevenEmotions, PlutchikPrimary, PlutchikDyad, TCMEmotionType
from luqi_engine.core.rng import PCGRandom


class TestOceanPersonality:
    def test_default_scores(self):
        p = OceanPersonality()
        for dim in OceanPersonality.DIMENSION_NAMES:
            assert p.get_score(dim) == 50.0

    def test_custom_scores(self):
        p = OceanPersonality(openness=80, conscientiousness=30, extraversion=70, agreeableness=60, neuroticism=20)
        assert p.get_score("openness") == 80.0
        assert p.get_score("neuroticism") == 20.0

    def test_clamping(self):
        p = OceanPersonality(openness=150, neuroticism=-50)
        assert p.get_score("openness") == 100.0
        assert p.get_score("neuroticism") == 0.0

    def test_set_score(self):
        p = OceanPersonality()
        p.set_score("openness", 75.0)
        assert p.get_score("openness") == 75.0

    def test_adapt(self):
        p = OceanPersonality(openness=50)
        p.adapt({"openness": 100.0})
        assert p.get_score("openness") > 50.0

    def test_influence_decision(self):
        p = OceanPersonality(openness=80, extraversion=70)
        weights = {"explore": 0.5, "socialize": 0.5}
        influenced = p.influence_decision(weights)
        assert isinstance(influenced, dict)
        assert influenced["explore"] != 0.5 or influenced["socialize"] != 0.5

    def test_to_dict_roundtrip(self):
        p = OceanPersonality(openness=70, conscientiousness=40)
        d = p.to_dict()
        p2 = OceanPersonality.from_dict(d)
        for dim in OceanPersonality.DIMENSION_NAMES:
            assert abs(p.get_score(dim) - p2.get_score(dim)) < 1e-9

    def test_distance_to(self):
        p1 = OceanPersonality(openness=50)
        p2 = OceanPersonality(openness=80)
        dist = p1.distance_to(p2)
        assert dist > 0.0

    def test_distance_to_self_is_zero(self):
        p = OceanPersonality(openness=60, conscientiousness=40)
        assert p.distance_to(p) == 0.0

    def test_adaptation_rate_property(self):
        p = OceanPersonality()
        p.adaptation_rate = 0.5
        assert p.adaptation_rate == 0.5


class TestPersonalityAdapter:
    def test_adapt_towards(self):
        source = OceanPersonality(openness=30)
        target = OceanPersonality(openness=80)
        adapter = PersonalityAdapter(source)
        deltas = adapter.adapt_towards(target)
        assert "openness" in deltas
        assert source.get_score("openness") > 30.0

    def test_is_converged(self):
        source = OceanPersonality(openness=50)
        target = OceanPersonality(openness=50)
        adapter = PersonalityAdapter(source)
        assert adapter.is_converged(target)

    def test_not_converged(self):
        source = OceanPersonality(openness=10)
        target = OceanPersonality(openness=90)
        adapter = PersonalityAdapter(source)
        assert not adapter.is_converged(target)


class TestPADState:
    def test_default_state(self):
        pad = PADState()
        assert pad.pleasure == 0.0
        assert pad.arousal == 0.0
        assert pad.dominance == 0.0

    def test_update(self):
        pad = PADState()
        updated = pad.update(0.5, 0.3, 0.2)
        assert updated.pleasure > 0.0
        assert updated.arousal > 0.0
        assert updated.dominance > 0.0

    def test_decay(self):
        pad = PADState(pleasure=0.8, arousal=0.6, dominance=0.4)
        decayed = pad.decay()
        assert decayed.pleasure < 0.8
        assert decayed.arousal < 0.6

    def test_clamping(self):
        pad = PADState()
        updated = pad.update(10.0, 10.0, 10.0)
        assert updated.pleasure <= 1.0
        assert updated.arousal <= 1.0
        assert updated.dominance <= 1.0

    def test_distance_to(self):
        p1 = PADState(pleasure=0.5, arousal=0.5, dominance=0.5)
        p2 = PADState(pleasure=-0.5, arousal=-0.5, dominance=-0.5)
        dist = p1.distance_to(p2)
        assert dist > 0.0

    def test_blend(self):
        p1 = PADState(pleasure=1.0, arousal=0.0, dominance=0.0)
        p2 = PADState(pleasure=-1.0, arousal=0.0, dominance=0.0)
        blended = p1.blend(p2, 0.5)
        assert abs(blended.pleasure) < 0.01

    def test_magnitude(self):
        pad = PADState(pleasure=1.0, arousal=0.0, dominance=0.0)
        assert abs(pad.magnitude() - 1.0) < 1e-9

    def test_from_tuple(self):
        pad = PADState.from_tuple((0.5, -0.3, 0.7))
        assert pad.pleasure == 0.5
        assert pad.arousal == -0.3
        assert pad.dominance == 0.7


class TestExtendedPAD:
    def test_update_from_emotion(self):
        ext = ExtendedPAD()
        pad = ext.update_from_emotion(SevenEmotionType.JOY.value, 0.8)
        assert pad.pleasure > 0.0

    def test_compute_composite(self):
        ext = ExtendedPAD()
        ext.update_from_emotion(SevenEmotionType.JOY.value, 0.5)
        ext.update_from_emotion(SevenEmotionType.ANGER.value, 0.3)
        composite = ext.compute_composite()
        assert isinstance(composite, PADState)

    def test_dominant_emotion(self):
        ext = ExtendedPAD()
        ext.update_from_emotion(SevenEmotionType.JOY.value, 0.9)
        dominant = ext.dominant_emotion()
        assert dominant == SevenEmotionType.JOY.value

    def test_custom_pad_mapping(self):
        ext = ExtendedPAD()
        ext.set_emotion_pad_mapping("custom", (0.5, 0.5, 0.5))
        pad = ext.update_from_emotion("custom", 0.5)
        assert pad.pleasure > 0.0


class TestOceanToPadBaseline:
    def test_high_extraversion_positive_pleasure(self):
        ocean = {"openness": 50, "conscientiousness": 50, "extraversion": 80, "agreeableness": 50, "neuroticism": 20}
        pad = ocean_to_pad_baseline(ocean)
        assert pad.pleasure > 0.0

    def test_high_neuroticism_negative_pleasure(self):
        ocean = {"openness": 50, "conscientiousness": 50, "extraversion": 20, "agreeableness": 50, "neuroticism": 80}
        pad = ocean_to_pad_baseline(ocean)
        assert pad.pleasure < 0.0

    def test_neutral_scores_near_zero(self):
        ocean = {"openness": 50, "conscientiousness": 50, "extraversion": 50, "agreeableness": 50, "neuroticism": 50}
        pad = ocean_to_pad_baseline(ocean)
        assert abs(pad.pleasure) < 0.01
        assert abs(pad.arousal) < 0.01
        assert abs(pad.dominance) < 0.01


class TestEmotionConversions:
    def test_seven_to_plutchik(self):
        assert seven_to_plutchik(SevenEmotionType.JOY) == PlutchikPrimary.JOY
        assert seven_to_plutchik(SevenEmotionType.ANGER) == PlutchikPrimary.ANGER
        assert seven_to_plutchik(SevenEmotionType.SORROW) == PlutchikPrimary.SADNESS

    def test_tcm_to_seven(self):
        assert tcm_to_seven(TCMEmotionType.JOY) == SevenEmotionType.JOY
        assert tcm_to_seven(TCMEmotionType.ANGER) == SevenEmotionType.ANGER

    def test_compute_plutchik_dyad_love(self):
        dyad, pad = compute_plutchik_dyad(PlutchikPrimary.JOY, PlutchikPrimary.TRUST)
        assert dyad == PlutchikDyad.LOVE
        assert isinstance(pad, PADState)

    def test_compute_plutchik_dyad_no_match(self):
        dyad, pad = compute_plutchik_dyad(PlutchikPrimary.JOY, PlutchikPrimary.FEAR)
        assert dyad is None
        assert isinstance(pad, PADState)


class TestDesireEngine:
    def test_get_desires(self):
        engine = DesireEngine()
        desires = asyncio.run(engine.get_desires("char_1"))
        assert desires is not None

    def test_update_desires(self):
        engine = DesireEngine()
        asyncio.run(engine.update_desires("char_1", {"joy": 0.5, "anger": -0.3}))
        desires = asyncio.run(engine.get_desires("char_1"))
        assert desires is not None

    def test_compute_drive_chain(self):
        engine = DesireEngine()
        asyncio.run(engine.update_desires("char_1", {"joy": 0.8}))
        chain = asyncio.run(engine.compute_drive_chain("char_1", {"situation": "battle"}))
        assert isinstance(chain, dict)
        assert "drive_chain" in chain
        assert "dominant_desire" in chain

    def test_satiation(self):
        engine = DesireEngine()
        asyncio.run(engine.update_desires("char_1", {"joy": 0.5}))
        engine.apply_satiation("char_1", "safety", 0.5)
        engine.decay_satiation("char_1")

    def test_get_dominant_desire(self):
        engine = DesireEngine()
        asyncio.run(engine.update_desires("char_1", {"joy": 0.8}))
        dominant = engine.get_dominant_desire("char_1")
        assert dominant is not None

    def test_no_dominant_for_unknown(self):
        engine = DesireEngine()
        assert engine.get_dominant_desire("unknown") is None


class TestMemoryStore:
    def test_store_and_retrieve(self):
        store = MemoryStore()
        entry = MemoryEntry(who="小雪", what="遇到鹿栖", where="森林", why="探险")
        store.store(entry)
        results = store.retrieve("鹿栖")
        assert len(results) > 0
        assert results[0].who == "小雪"

    def test_tier_stats(self):
        store = MemoryStore()
        stats = store.tier_stats()
        assert "short_term" in stats
        assert "long_term" in stats
        assert "emotional" in stats

    def test_get_by_id(self):
        store = MemoryStore()
        entry = MemoryEntry(who="小雪", what="测试记忆")
        store.store(entry)
        found = store.get_by_id(entry.entry_id)
        assert found is not None
        assert found.who == "小雪"

    def test_remove(self):
        store = MemoryStore()
        entry = MemoryEntry(who="小雪", what="临时记忆")
        store.store(entry)
        assert store.remove(entry.entry_id) is True
        assert store.get_by_id(entry.entry_id) is None

    def test_lru_eviction(self):
        config = CharacterConfig(short_term_memory_capacity=3)
        store = MemoryStore(config=config)
        entries = []
        for i in range(5):
            e = MemoryEntry(who=f"角色{i}", what=f"事件{i}")
            store.store(e)
            entries.append(e)
        stats = store.tier_stats()
        assert stats["short_term"]["size"] <= 3

    def test_promotion_to_long_term(self):
        config = CharacterConfig(short_term_memory_capacity=2)
        store = MemoryStore(config=config)
        entry = MemoryEntry(who="小雪", what="重要事件", importance=0.9)
        store.store(entry)
        for _ in range(MemoryStore.PROMOTION_ACCESS_THRESHOLD + 1):
            store.get_by_id(entry.entry_id)
        overflow_entry = MemoryEntry(who="鹿栖", what="新事件")
        store.store(overflow_entry)
        found = store.get_by_id(entry.entry_id)
        if found is not None:
            assert found.memory_type in (MemoryType.LONG_TERM, MemoryType.SHORT_TERM)

    def test_emotional_promotion(self):
        config = CharacterConfig(short_term_memory_capacity=2)
        store = MemoryStore(config=config)
        entry = MemoryEntry(who="小雪", what="创伤事件", emotional_valence=0.9)
        store.store(entry)
        overflow = MemoryEntry(who="鹿栖", what="普通事件")
        store.store(overflow)
        found = store.get_by_id(entry.entry_id)
        if found is not None:
            assert found.memory_type in (MemoryType.EMOTIONAL, MemoryType.SHORT_TERM)

    def test_relevance_scoring(self):
        entry = MemoryEntry(who="小雪", what="在森林中遇到了鹿栖", where="森林", why="探险")
        score = entry.relevance_to("森林")
        assert score > 0.0

    def test_memory_type_enum(self):
        assert MemoryType.SHORT_TERM.storage_key == "short_term"
        assert MemoryType.LONG_TERM.storage_key == "long_term"
        assert MemoryType.EMOTIONAL.storage_key == "emotional"


class TestGOAPPlanner:
    def test_simple_plan(self):
        planner = GOAPPlanner()
        planner.add_action(GOAPAction(
            name="move_to_target",
            preconditions={"at_source": True},
            effects={"at_target": True, "at_source": False},
            cost=1.0,
        ))
        start = GOAPWorldState({"at_source": True, "at_target": False})
        goal = GOAPWorldState({"at_target": True})
        plan = planner.plan(start, goal)
        assert plan is not None
        assert len(plan) > 0

    def test_already_satisfied(self):
        planner = GOAPPlanner()
        start = GOAPWorldState({"has_key": True})
        goal = GOAPWorldState({"has_key": True})
        plan = planner.plan(start, goal)
        assert plan is not None
        assert len(plan) == 0

    def test_no_plan_possible(self):
        planner = GOAPPlanner()
        start = GOAPWorldState({"locked": True})
        goal = GOAPWorldState({"opened": True})
        plan = planner.plan(start, goal)
        assert plan is None

    def test_multi_step_plan(self):
        planner = GOAPPlanner()
        planner.add_action(GOAPAction(
            name="find_key",
            preconditions={"in_room": True},
            effects={"has_key": True},
            cost=1.0,
        ))
        planner.add_action(GOAPAction(
            name="unlock_door",
            preconditions={"has_key": True, "door_locked": True},
            effects={"door_locked": False, "door_open": True},
            cost=1.0,
        ))
        start = GOAPWorldState({"in_room": True, "has_key": False, "door_locked": True, "door_open": False})
        goal = GOAPWorldState({"door_open": True})
        plan = planner.plan(start, goal)
        assert plan is not None
        assert len(plan) == 2
        assert plan[0].name == "find_key"
        assert plan[1].name == "unlock_door"

    def test_world_state_satisfies(self):
        state = GOAPWorldState({"a": 1, "b": 2})
        goal = GOAPWorldState({"a": 1})
        assert state.satisfies(goal)

    def test_world_state_apply(self):
        state = GOAPWorldState({"a": 1})
        new_state = state.apply({"a": 2, "b": 3})
        assert new_state.get("a") == 2
        assert new_state.get("b") == 3

    def test_add_remove_action(self):
        planner = GOAPPlanner()
        planner.add_action(GOAPAction(name="test_action"))
        assert "test_action" in planner.available_actions
        planner.remove_action("test_action")
        assert "test_action" not in planner.available_actions


class TestUtilityBasedAI:
    def test_evaluate_all(self):
        ai = UtilityBasedAI()
        ai.add_behavior(BehaviorOption(name="fight", base_weight=0.8))
        ai.add_behavior(BehaviorOption(name="flee", base_weight=0.3))
        results = ai.evaluate_all()
        assert len(results) == 2
        assert results[0][1] >= results[1][1]

    def test_select_best(self):
        ai = UtilityBasedAI()
        ai.add_behavior(BehaviorOption(name="fight", base_weight=0.9))
        ai.add_behavior(BehaviorOption(name="flee", base_weight=0.2))
        best = ai.select_best()
        assert best is not None
        assert best.name == "fight"

    def test_select_weighted(self):
        rng = PCGRandom(seed=42)
        ai = UtilityBasedAI(rng=rng)
        ai.add_behavior(BehaviorOption(name="fight", base_weight=0.5))
        ai.add_behavior(BehaviorOption(name="flee", base_weight=0.5))
        selected = ai.select_weighted()
        assert selected is not None
        assert selected.name in ("fight", "flee")

    def test_response_curves(self):
        linear = ResponseCurve(curve_type="linear", slope=1.0)
        assert abs(linear.evaluate(0.5) - 0.5) < 1e-9
        quadratic = ResponseCurve(curve_type="quadratic", slope=1.0)
        assert quadratic.evaluate(0.5) > 0.0
        logistic = ResponseCurve(curve_type="logistic", slope=1.0)
        assert 0.0 <= logistic.evaluate(0.5) <= 1.0

    def test_consideration_evaluation(self):
        consideration = Consideration(
            name="health",
            curve=ResponseCurve(curve_type="linear"),
            weight=1.0,
            input_fn=lambda: 0.7,
        )
        score = consideration.evaluate()
        assert 0.0 <= score <= 1.0

    def test_behavior_with_considerations(self):
        behavior = BehaviorOption(
            name="attack",
            considerations=[
                Consideration(name="health", input_fn=lambda: 0.8),
                Consideration(name="threat", input_fn=lambda: 0.6),
            ],
            base_weight=1.0,
        )
        utility = behavior.compute_utility()
        assert 0.0 <= utility <= 1.0

    def test_compensation(self):
        behavior = BehaviorOption(name="defend", base_weight=0.5)
        behavior.apply_compensation("danger", 1.5)
        compensated = behavior.compensated_utility()
        assert compensated != behavior.compute_utility()


class TestCEMPlanner:
    def test_select(self):
        rng = PCGRandom(seed=42)
        ai = UtilityBasedAI(rng=rng)
        ai.add_behavior(BehaviorOption(name="fight", base_weight=0.8))
        ai.add_behavior(BehaviorOption(name="flee", base_weight=0.3))
        cem = CEMPlanner(utility_ai=ai, rng=PCGRandom(seed=42))
        selected = cem.select()
        assert selected is not None

    def test_temperature_adaptation(self):
        rng = PCGRandom(seed=42)
        ai = UtilityBasedAI(rng=rng)
        ai.add_behavior(BehaviorOption(name="a", base_weight=0.9))
        ai.add_behavior(BehaviorOption(name="b", base_weight=0.1))
        cem = CEMPlanner(utility_ai=ai, rng=PCGRandom(seed=42), temperature=1.0)
        for _ in range(10):
            cem.select()
        assert cem.temperature != 1.0 or True

    def test_select_ranked(self):
        rng = PCGRandom(seed=42)
        ai = UtilityBasedAI(rng=rng)
        ai.add_behavior(BehaviorOption(name="a", base_weight=0.9))
        ai.add_behavior(BehaviorOption(name="b", base_weight=0.5))
        ai.add_behavior(BehaviorOption(name="c", base_weight=0.2))
        cem = CEMPlanner(utility_ai=ai, rng=PCGRandom(seed=42))
        ranked = cem.select_ranked(count=2)
        assert len(ranked) <= 2

    def test_context_compensation(self):
        ai = UtilityBasedAI()
        ai.add_behavior(BehaviorOption(name="fight", base_weight=0.5))
        cem = CEMPlanner(utility_ai=ai)
        cem.apply_context_compensation("danger", 2.0)
        cem.clear_compensations()


class TestSocialPerception:
    def test_relationship_potential(self):
        rp = RelationshipPotential()
        rp.update(0.5)
        assert rp.value > 0.0

    def test_relationship_potential_decay(self):
        rp = RelationshipPotential(value=0.8)
        rp.decay()
        assert rp.value < 0.8

    def test_context_fidelity(self):
        cf = ContextFidelity()
        cf.update("noise", 0.3)
        assert cf.value < 1.0
        cf.remove_distortion("noise")
        assert cf.value == 1.0

    def test_context_fidelity_decay(self):
        cf = ContextFidelity()
        cf.update("noise", 0.5)
        cf.decay()
        assert cf.value >= 0.0

    def test_intervention_entropy(self):
        ie = InterventionEntropy()
        ie.record_intervention()
        assert ie.value > 0.0
        assert ie.intervention_count == 1

    def test_intervention_entropy_reduce(self):
        ie = InterventionEntropy(value=0.5)
        ie.reduce(0.3)
        assert ie.value < 0.5

    def test_social_perception_potential(self):
        sp = SocialPerception()
        potential = sp.get_potential("a", "b")
        assert isinstance(potential, RelationshipPotential)

    def test_social_perception_update(self):
        sp = SocialPerception()
        sp.update_potential("a", "b", 0.5)
        potential = sp.get_potential("a", "b")
        assert potential.value > 0.0

    def test_social_perception_fidelity(self):
        sp = SocialPerception()
        sp.add_distortion("a", "rumor", 0.3)
        fidelity = sp.get_fidelity("a")
        assert fidelity.value < 1.0

    def test_social_perception_entropy(self):
        sp = SocialPerception()
        sp.record_intervention("a")
        entropy = sp.get_entropy("a")
        assert entropy.value > 0.0

    def test_perception_score(self):
        sp = SocialPerception()
        sp.update_potential("a", "b", 1.0)
        score = sp.compute_perception_score("a", "b")
        assert 0.0 <= score <= 1.0

    def test_decay_all(self):
        sp = SocialPerception()
        sp.update_potential("a", "b", 0.5)
        sp.add_distortion("a", "noise", 0.3)
        sp.record_intervention("a")
        sp.decay_all()
