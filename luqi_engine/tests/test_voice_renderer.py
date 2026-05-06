from typing import Any, Dict, Optional

import pytest

from luqi_engine.core.types import CanonicalIR, EmotionDelta
from luqi_engine.voice.voice_renderer import VoiceRenderer, _SeededRNG


class TestSeededRNGDeterminism:
    def test_same_seed_same_sequence(self):
        rng1 = _SeededRNG(42)
        rng2 = _SeededRNG(42)
        seq1 = [rng1.next_int(100) for _ in range(20)]
        seq2 = [rng2.next_int(100) for _ in range(20)]
        assert seq1 == seq2

    def test_different_seed_different_sequence(self):
        rng1 = _SeededRNG(42)
        rng2 = _SeededRNG(99)
        seq1 = [rng1.next_int(100) for _ in range(10)]
        seq2 = [rng2.next_int(100) for _ in range(10)]
        assert seq1 != seq2

    def test_next_int_zero_max(self):
        rng = _SeededRNG(42)
        assert rng.next_int(0) == 0

    def test_next_int_negative_max(self):
        rng = _SeededRNG(42)
        assert rng.next_int(-1) == 0

    def test_shuffle_deterministic(self):
        items1 = list(range(10))
        items2 = list(range(10))
        rng1 = _SeededRNG(42)
        rng2 = _SeededRNG(42)
        rng1.shuffle(items1)
        rng2.shuffle(items2)
        assert items1 == items2

    def test_shuffle_different_seed(self):
        items1 = list(range(10))
        items2 = list(range(10))
        rng1 = _SeededRNG(42)
        rng2 = _SeededRNG(99)
        rng1.shuffle(items1)
        rng2.shuffle(items2)
        assert items1 != items2

    def test_shuffle_does_not_lose_elements(self):
        items = list(range(10))
        rng = _SeededRNG(42)
        rng.shuffle(items)
        assert sorted(items) == list(range(10))


class TestVoiceRendererDeterminism:
    def test_same_ir_same_seed_identical_output(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            intent="greet",
            action="smile_nod",
            emotion_delta=EmotionDelta(),
            key_points=["你好", "很高兴见到你", "最近怎么样"],
            tone="casual",
            length_hint="medium",
        )
        profile = {"name": "小明"}
        output1 = renderer.render(ir, voice_profile=profile, seed=42)
        output2 = renderer.render(ir, voice_profile=profile, seed=42)
        assert output1 == output2

    def test_same_ir_different_seed_different_output(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            intent="greet",
            action="smile_nod",
            emotion_delta=EmotionDelta(),
            key_points=["你好", "很高兴见到你", "最近怎么样"],
            tone="casual",
            length_hint="medium",
        )
        profile = {"name": "小明"}
        output1 = renderer.render(ir, voice_profile=profile, seed=42)
        output2 = renderer.render(ir, voice_profile=profile, seed=99)
        assert output1 != output2

    def test_determinism_across_100_calls(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            intent="greet",
            action="smile_nod",
            key_points=["你好", "世界", "测试"],
            tone="casual",
            length_hint="short",
        )
        profile = {"name": "角色A"}
        first_output = renderer.render(ir, voice_profile=profile, seed=12345)
        for _ in range(100):
            output = renderer.render(ir, voice_profile=profile, seed=12345)
            assert output == first_output


class TestVoiceRendererToneTemplates:
    def test_casual_tone(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            action="idle",
            key_points=["你好"],
            tone="casual",
            length_hint="tiny",
        )
        profile = {"name": "小明"}
        output = renderer.render(ir, voice_profile=profile, seed=0)
        assert "小明说道：「" in output
        assert "你好" in output

    def test_angry_tone(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            action="idle",
            key_points=["你太过分了"],
            tone="angry",
            length_hint="tiny",
        )
        profile = {"name": "小红"}
        output = renderer.render(ir, voice_profile=profile, seed=0)
        assert "小红怒道：「" in output

    def test_sad_tone(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            action="idle",
            key_points=["再见"],
            tone="sad",
            length_hint="tiny",
        )
        profile = {"name": "小蓝"}
        output = renderer.render(ir, voice_profile=profile, seed=0)
        assert "小蓝黯然道：「" in output

    def test_unknown_tone_falls_back_to_neutral(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            action="idle",
            key_points=["嗯"],
            tone="unknown_tone",
            length_hint="tiny",
        )
        profile = {"name": "小绿"}
        output = renderer.render(ir, voice_profile=profile, seed=0)
        assert "小绿：「" in output


class TestVoiceRendererActionTemplates:
    def test_action_smile_nod(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            action="smile_nod",
            key_points=["好的"],
            tone="neutral",
            length_hint="tiny",
        )
        profile = {"name": "小明"}
        output = renderer.render(ir, voice_profile=profile, seed=0)
        assert "小明微笑着点了点头。" in output

    def test_action_step_back_draw_weapon(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            action="step_back_draw_weapon",
            key_points=["退后"],
            tone="angry",
            length_hint="tiny",
        )
        profile = {"name": "战士"}
        output = renderer.render(ir, voice_profile=profile, seed=0)
        assert "战士猛地后退一步" in output

    def test_action_idle_no_action_text(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            action="idle",
            key_points=["嗯"],
            tone="neutral",
            length_hint="tiny",
        )
        profile = {"name": "小明"}
        output = renderer.render(ir, voice_profile=profile, seed=0)
        lines = output.split("\n")
        assert len(lines) == 1

    def test_unknown_action_no_action_text(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            action="fly_away",
            key_points=["走"],
            tone="neutral",
            length_hint="tiny",
        )
        profile = {"name": "小明"}
        output = renderer.render(ir, voice_profile=profile, seed=0)
        lines = output.split("\n")
        assert len(lines) == 1


class TestVoiceRendererLengthHint:
    def test_tiny_only_one_keypoint(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            action="idle",
            key_points=["第一", "第二", "第三"],
            tone="neutral",
            length_hint="tiny",
        )
        profile = {"name": "角色"}
        output = renderer.render(ir, voice_profile=profile, seed=0)
        assert "第二" not in output or "第一" not in output or "第三" not in output

    def test_long_includes_more_keypoints(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            action="idle",
            key_points=["一", "二", "三", "四", "五", "六"],
            tone="neutral",
            length_hint="long",
        )
        profile = {"name": "角色"}
        output = renderer.render(ir, voice_profile=profile, seed=0)
        content_start = output.find("「") + 1
        content_end = output.rfind("」")
        content = output[content_start:content_end]
        assert len(content) > 0


class TestVoiceRendererNoKeyPoints:
    def test_no_key_points_only_action(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            action="smile_nod",
            key_points=[],
            tone="neutral",
        )
        profile = {"name": "小明"}
        output = renderer.render(ir, voice_profile=profile, seed=0)
        assert "小明微笑着点了点头。" == output


class TestVoiceRendererProfileDefaults:
    def test_no_voice_profile_uses_default_name(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            action="idle",
            key_points=["你好"],
            tone="neutral",
            length_hint="tiny",
        )
        output = renderer.render(ir, voice_profile=None, seed=0)
        assert "角色：「" in output

    def test_empty_voice_profile_uses_default_name(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            action="idle",
            key_points=["你好"],
            tone="neutral",
            length_hint="tiny",
        )
        output = renderer.render(ir, voice_profile={}, seed=0)
        assert "角色：「" in output

    def test_custom_name_from_profile(self):
        renderer = VoiceRenderer()
        ir = CanonicalIR(
            action="idle",
            key_points=["你好"],
            tone="neutral",
            length_hint="tiny",
        )
        profile = {"name": "张三"}
        output = renderer.render(ir, voice_profile=profile, seed=0)
        assert "张三：「" in output


class TestVoiceRendererNoMutation:
    def test_render_does_not_mutate_ir_key_points(self):
        renderer = VoiceRenderer()
        original_points = ["你好", "世界", "测试"]
        ir = CanonicalIR(
            action="idle",
            key_points=list(original_points),
            tone="neutral",
            length_hint="medium",
        )
        renderer.render(ir, voice_profile={"name": "角色"}, seed=42)
        assert ir.key_points == original_points
