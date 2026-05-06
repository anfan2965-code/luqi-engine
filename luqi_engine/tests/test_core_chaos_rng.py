import math
import pytest
from luqi_engine.core.rng import PCGRandom, SeededRNGManager, NarrativeSeedHierarchy
from luqi_engine.core.chaos import LorenzAttractor, EmotionalFluctuation
from luqi_engine.core.distributions import DistributionToolkit


class TestPCGRandom:
    def test_deterministic_same_seed(self):
        a = PCGRandom(seed=42, stream=0)
        b = PCGRandom(seed=42, stream=0)
        for _ in range(100):
            assert a.next_uint32() == b.next_uint32()

    def test_different_seed_different_output(self):
        a = PCGRandom(seed=42)
        b = PCGRandom(seed=99)
        assert a.next_uint32() != b.next_uint32()

    def test_different_stream_different_output(self):
        a = PCGRandom(seed=42, stream=0)
        b = PCGRandom(seed=42, stream=1)
        assert a.next_uint32() != b.next_uint32()

    def test_uniform_range(self):
        rng = PCGRandom(seed=12345)
        for _ in range(1000):
            val = rng.uniform(0.0, 1.0)
            assert 0.0 <= val < 1.0

    def test_uniform_custom_range(self):
        rng = PCGRandom(seed=12345)
        for _ in range(1000):
            val = rng.uniform(10.0, 20.0)
            assert 10.0 <= val < 20.0

    def test_gaussian_mean(self):
        rng = PCGRandom(seed=42)
        samples = [rng.gaussian(mean=0.0, stddev=1.0) for _ in range(10000)]
        avg = sum(samples) / len(samples)
        assert abs(avg) < 0.1

    def test_gaussian_stddev(self):
        rng = PCGRandom(seed=42)
        samples = [rng.gaussian(mean=0.0, stddev=1.0) for _ in range(10000)]
        variance = sum((x ** 2) for x in samples) / len(samples)
        assert abs(variance - 1.0) < 0.2

    def test_weighted_choice(self):
        rng = PCGRandom(seed=42)
        weights = [0.0, 0.0, 1.0, 0.0, 0.0]
        for _ in range(100):
            idx = rng.weighted_choice(weights)
            assert idx == 2

    def test_weighted_choice_distribution(self):
        rng = PCGRandom(seed=42)
        weights = [0.5, 0.3, 0.2]
        counts = [0, 0, 0]
        for _ in range(10000):
            idx = rng.weighted_choice(weights)
            counts[idx] += 1
        total = sum(counts)
        ratios = [c / total for c in counts]
        assert abs(ratios[0] - 0.5) < 0.05
        assert abs(ratios[1] - 0.3) < 0.05
        assert abs(ratios[2] - 0.2) < 0.05

    def test_state_save_restore(self):
        rng = PCGRandom(seed=42)
        rng.next_uint32()
        rng.next_uint32()
        saved = rng.state
        val_a = rng.next_uint32()
        rng.state = saved
        val_b = rng.next_uint32()
        assert val_a == val_b


class TestSeededRNGManager:
    def test_same_stream_deterministic(self):
        mgr_a = SeededRNGManager(master_seed=42)
        mgr_b = SeededRNGManager(master_seed=42)
        a = mgr_a.get_stream("char_xiaoxue")
        b = mgr_b.get_stream("char_xiaoxue")
        vals_a = [a.next_uint32() for _ in range(10)]
        vals_b = [b.next_uint32() for _ in range(10)]
        assert vals_a == vals_b

    def test_different_streams_independent(self):
        mgr = SeededRNGManager(master_seed=42)
        a = mgr.get_stream("char_xiaoxue")
        b = mgr.get_stream("char_luqi")
        assert a.next_uint32() != b.next_uint32()

    def test_active_streams(self):
        mgr = SeededRNGManager(master_seed=42)
        mgr.get_stream("a")
        mgr.get_stream("b")
        mgr.get_stream("c")
        assert set(mgr.active_streams) == {"a", "b", "c"}

    def test_remove_stream(self):
        mgr = SeededRNGManager(master_seed=42)
        mgr.get_stream("temp")
        mgr.remove_stream("temp")
        assert "temp" not in mgr.active_streams

    def test_master_seed_preserved(self):
        mgr = SeededRNGManager(master_seed=42)
        assert mgr.master_seed == 42


class TestNarrativeSeedHierarchy:
    def test_derive_seed_deterministic(self):
        nsh = NarrativeSeedHierarchy(root_seed=42)
        a = nsh.derive_seed("world", "fantasy_realm")
        b = nsh.derive_seed("world", "fantasy_realm")
        assert a == b

    def test_different_paths_different_seeds(self):
        nsh = NarrativeSeedHierarchy(root_seed=42)
        a = nsh.derive_seed("world", "realm_a")
        b = nsh.derive_seed("world", "realm_b")
        assert a != b

    def test_create_rng(self):
        nsh = NarrativeSeedHierarchy(root_seed=42)
        rng = nsh.create_rng("world", "fantasy", stream=0)
        assert isinstance(rng, PCGRandom)

    def test_convenience_methods(self):
        nsh = NarrativeSeedHierarchy(root_seed=42)
        ws = nsh.derive_world_seed("earth")
        fs = nsh.derive_faction_seed("earth", "guild")
        cs = nsh.derive_character_seed("earth", "xiaoxue")
        ss = nsh.derive_scene_seed("earth", "classroom")
        es = nsh.derive_event_seed("earth", "first_meeting")
        seeds = [ws, fs, cs, ss, es]
        assert len(set(seeds)) == len(seeds)

    def test_clear_cache(self):
        nsh = NarrativeSeedHierarchy(root_seed=42)
        nsh.derive_seed("world", "test")
        nsh.clear_cache()


class TestLorenzAttractor:
    def test_initial_state(self):
        la = LorenzAttractor(initial_state=(1.0, 1.0, 1.0))
        assert la.state == (1.0, 1.0, 1.0)

    def test_step_advances(self):
        la = LorenzAttractor(initial_state=(1.0, 1.0, 1.0))
        s1 = la.step()
        assert s1 != (1.0, 1.0, 1.0)

    def test_step_count(self):
        la = LorenzAttractor(initial_state=(1.0, 1.0, 1.0))
        la.step()
        la.step()
        la.step()
        assert la.step_count == 3

    def test_normalized_range(self):
        la = LorenzAttractor(initial_state=(1.0, 1.0, 1.0))
        for _ in range(100):
            x, y, z = la.step_normalized()
            assert 0.0 <= x <= 1.0
            assert 0.0 <= y <= 1.0
            assert 0.0 <= z <= 1.0

    def test_advance_batch(self):
        la = LorenzAttractor(initial_state=(1.0, 1.0, 1.0))
        states = la.advance(50)
        assert len(states) == 50
        assert la.step_count == 50

    def test_perturb_changes_state(self):
        la = LorenzAttractor(initial_state=(1.0, 1.0, 1.0))
        rng = PCGRandom(seed=42)
        s_before = la.state
        la.perturb(rng, magnitude=0.01)
        s_after = la.state
        assert s_before != s_after

    def test_reset(self):
        la = LorenzAttractor(initial_state=(1.0, 1.0, 1.0))
        la.step()
        la.step()
        la.reset(initial_state=(1.0, 1.0, 1.0))
        assert la.state == (1.0, 1.0, 1.0)
        assert la.step_count == 0

    def test_chaos_butterfly_effect(self):
        la_a = LorenzAttractor(initial_state=(1.0, 1.0, 1.0))
        la_b = LorenzAttractor(initial_state=(1.001, 1.0, 1.0))
        for _ in range(5000):
            la_a.step()
            la_b.step()
        ax, ay, az = la_a.state
        bx, by, bz = la_b.state
        diff = math.sqrt((ax - bx) ** 2 + (ay - by) ** 2 + (az - bz) ** 2)
        assert diff > 0.1


class TestEmotionalFluctuation:
    def test_default_init(self):
        ef = EmotionalFluctuation()
        assert ef.accumulated == (0.0, 0.0, 0.0)

    def test_update_returns_clamped(self):
        ef = EmotionalFluctuation()
        result = ef.update((0.0, 0.0, 0.0))
        p, a, d = result
        assert -1.0 <= p <= 1.0
        assert -1.0 <= a <= 1.0
        assert -1.0 <= d <= 1.0

    def test_update_with_positive_emotion(self):
        ef = EmotionalFluctuation()
        result = ef.update((0.5, 0.3, 0.2))
        p, a, d = result
        assert isinstance(p, float)
        assert isinstance(a, float)
        assert isinstance(d, float)

    def test_accumulated_grows(self):
        ef = EmotionalFluctuation(coupling=0.5, decay=0.5)
        ef.update((0.0, 0.0, 0.0))
        acc1 = ef.accumulated
        ef.update((0.0, 0.0, 0.0))
        acc2 = ef.accumulated
        total1 = sum(abs(x) for x in acc1)
        total2 = sum(abs(x) for x in acc2)
        assert total2 > total1 or total2 > 0

    def test_reset(self):
        ef = EmotionalFluctuation()
        ef.update((0.5, 0.5, 0.5))
        ef.reset()
        assert ef.accumulated == (0.0, 0.0, 0.0)

    def test_long_term_stability(self):
        ef = EmotionalFluctuation(coupling=0.1, decay=0.95)
        emotion = (0.5, 0.3, 0.2)
        for _ in range(1000):
            emotion = ef.update(emotion)
            p, a, d = emotion
            assert -1.0 <= p <= 1.0
            assert -1.0 <= a <= 1.0
            assert -1.0 <= d <= 1.0

    def test_emotional_drift(self):
        ef = EmotionalFluctuation(coupling=0.1, decay=0.95)
        initial = (0.5, 0.5, 0.5)
        current = initial
        for _ in range(100):
            current = ef.update(current)
        diff = math.sqrt(sum((a - b) ** 2 for a, b in zip(initial, current)))
        assert diff > 0.001


class TestDistributionToolkit:
    def test_normal_range(self):
        dt = DistributionToolkit(rng=PCGRandom(seed=42))
        for _ in range(1000):
            val = dt.normal(mean=0.0, stddev=1.0)
            assert isinstance(val, float)

    def test_exponential_positive(self):
        dt = DistributionToolkit(rng=PCGRandom(seed=42))
        for _ in range(1000):
            val = dt.exponential(lam=1.0)
            assert val > 0

    def test_pareto_range(self):
        dt = DistributionToolkit(rng=PCGRandom(seed=42))
        for _ in range(1000):
            val = dt.pareto(alpha=2.0, xm=1.0)
            assert val >= 1.0

    def test_beta_range(self):
        dt = DistributionToolkit(rng=PCGRandom(seed=42))
        for _ in range(1000):
            val = dt.beta(a=2.0, b=5.0)
            assert 0.0 <= val <= 1.0

    def test_triangular_range(self):
        dt = DistributionToolkit(rng=PCGRandom(seed=42))
        for _ in range(1000):
            val = dt.triangular(low=0.0, high=1.0, mode_ratio=0.5)
            assert 0.0 <= val <= 1.0

    def test_sample_dispatch(self):
        dt = DistributionToolkit(rng=PCGRandom(seed=42))
        val = dt.sample("normal", mean=0.0, stddev=1.0)
        assert isinstance(val, float)

    def test_deterministic_with_same_seed(self):
        a = DistributionToolkit(rng=PCGRandom(seed=42))
        b = DistributionToolkit(rng=PCGRandom(seed=42))
        for _ in range(100):
            assert a.normal() == b.normal()
