import asyncio
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from luqi_engine.core.types import (
    DesireVector, SevenEmotions, SixDesires, SevenEmotionType,
    EventType, LLMRequest, LLMResponse, generate_entity_id,
)
from luqi_engine.core.chaos import LorenzAttractor, EmotionalFluctuation
from luqi_engine.core.rng import PCGRandom, SeededRNGManager, NarrativeSeedHierarchy
from luqi_engine.core.event_bus import EventBus, Event
from luqi_engine.core.config import (
    EngineConfig, CharacterConfig, CognitiveMemoryConfig, LocalLLMConfig,
)
from luqi_engine.llm.state_renderer import StateRenderer
from luqi_engine.llm.intent_classifier import IntentClassifier, IntentLevel
from luqi_engine.llm.fallback import LLMFallback, DegradationLevel
from luqi_engine.llm.local_llm_adapter import LocalLLMAdapter


class MockPersonality:
    def __init__(self, scores):
        self._scores = scores

    def get_score(self, dim):
        return self._scores.get(dim, 50)


class MockEmotion:
    def __init__(self, pleasure=0.0, arousal=0.0, dominance=0.0):
        self.pleasure = pleasure
        self.arousal = arousal
        self.dominance = dominance


class MockCharacter:
    def __init__(self, char_id, name, personality_scores, emotion=None, background=""):
        self.id = char_id
        self.name = name
        self.personality = MockPersonality(personality_scores)
        self.emotion = emotion or MockEmotion()
        self.background = background
        self.seven_emotions = None
        self.memories = {
            "short_term": [],
            "long_term": [],
            "emotional": [],
            "shared": [],
        }

    def store_memory(self, memory_type, content):
        if memory_type in self.memories:
            self.memories[memory_type].append({
                "content": content,
                "timestamp": time.time(),
                "importance": content.get("importance", 0.5),
            })

    def retrieve_memories(self, query="", memory_type=None, limit=10):
        if memory_type and memory_type in self.memories:
            return self.memories[memory_type][:limit]
        all_mems = []
        for mt in self.memories:
            all_mems.extend(self.memories[mt])
        return all_mems[:limit]


class TestMultiCharacterMemoryIsolation:
    def test_characters_have_independent_memories(self):
        char_a = MockCharacter("a", "小雪", {"openness": 72, "extraversion": 28, "agreeableness": 85})
        char_b = MockCharacter("b", "鹿栖", {"openness": 90, "extraversion": 65, "agreeableness": 70})

        char_a.store_memory("short_term", {"text": "今天和小明吵架了", "importance": 0.8})
        char_a.store_memory("emotional", {"text": "感到很委屈", "importance": 0.9})
        char_b.store_memory("short_term", {"text": "今天学了一首新歌", "importance": 0.5})

        a_mems = char_a.retrieve_memories(memory_type="short_term")
        b_mems = char_b.retrieve_memories(memory_type="short_term")
        assert len(a_mems) == 1
        assert len(b_mems) == 1
        assert a_mems[0]["content"]["text"] == "今天和小明吵架了"
        assert b_mems[0]["content"]["text"] == "今天学了一首新歌"

    def test_emotional_memory_does_not_leak(self):
        char_a = MockCharacter("a", "小雪", {"openness": 72, "extraversion": 28, "agreeableness": 85})
        char_b = MockCharacter("b", "鹿栖", {"openness": 90, "extraversion": 65, "agreeableness": 70})

        char_a.store_memory("emotional", {"text": "被老师批评了", "importance": 0.95})
        a_emotional = char_a.retrieve_memories(memory_type="emotional")
        b_emotional = char_b.retrieve_memories(memory_type="emotional")
        assert len(a_emotional) == 1
        assert len(b_emotional) == 0

    def test_shared_memory_between_characters(self):
        char_a = MockCharacter("a", "小雪", {"openness": 72, "extraversion": 28, "agreeableness": 85})
        char_b = MockCharacter("b", "鹿栖", {"openness": 90, "extraversion": 65, "agreeableness": 70})

        shared_event = {"text": "一起看了日落", "importance": 0.85, "participants": ["a", "b"]}
        char_a.store_memory("shared", shared_event)
        char_b.store_memory("shared", shared_event)

        a_shared = char_a.retrieve_memories(memory_type="shared")
        b_shared = char_b.retrieve_memories(memory_type="shared")
        assert len(a_shared) == 1
        assert len(b_shared) == 1
        assert a_shared[0]["content"]["text"] == b_shared[0]["content"]["text"]


class TestMultiSessionMemoryAccumulation:
    def test_memories_accumulate_across_sessions(self):
        char = MockCharacter("a", "小雪", {"openness": 72, "extraversion": 28, "agreeableness": 85})

        for i in range(5):
            char.store_memory("short_term", {"text": "会话{}的对话".format(i), "importance": 0.5 + i * 0.1})

        mems = char.retrieve_memories(memory_type="short_term")
        assert len(mems) == 5

    def test_long_term_memory_survives_multiple_sessions(self):
        char = MockCharacter("a", "小雪", {"openness": 72, "extraversion": 28, "agreeableness": 85})

        important_memories = [
            {"text": "第一次来到这个城市", "importance": 0.95},
            {"text": "认识了最好的朋友", "importance": 0.9},
            {"text": "考上了理想的学校", "importance": 0.85},
        ]
        for mem in important_memories:
            char.store_memory("long_term", mem)

        long_mems = char.retrieve_memories(memory_type="long_term")
        assert len(long_mems) == 3
        texts = [m["content"]["text"] for m in long_mems]
        assert "第一次来到这个城市" in texts

    def test_emotional_memory_tracks_sentiment(self):
        char = MockCharacter("a", "小雪", {"openness": 72, "extraversion": 28, "agreeableness": 85})

        emotional_events = [
            {"text": "被表扬了", "importance": 0.7, "valence": 0.8},
            {"text": "被误解了", "importance": 0.9, "valence": -0.6},
            {"text": "收到礼物", "importance": 0.6, "valence": 0.9},
        ]
        for evt in emotional_events:
            char.store_memory("emotional", evt)

        emos = char.retrieve_memories(memory_type="emotional")
        assert len(emos) == 3
        negative = [m for m in emos if m["content"].get("valence", 0) < 0]
        assert len(negative) == 1


class TestEmotionalStateAcrossSessions:
    def test_emotion_evolution_with_chaos(self):
        ef = EmotionalFluctuation(coupling=0.1, decay=0.95)
        emotion = (0.5, 0.3, 0.2)
        trajectory = []
        for _ in range(50):
            emotion = ef.update(emotion)
            trajectory.append(emotion)
        first = trajectory[0]
        last = trajectory[-1]
        assert first != last

    def test_emotion_stays_bounded(self):
        ef = EmotionalFluctuation(coupling=0.3, decay=0.9)
        emotion = (0.8, 0.9, 0.7)
        for _ in range(1000):
            emotion = ef.update(emotion)
            p, a, d = emotion
            assert -1.0 <= p <= 1.0
            assert -1.0 <= a <= 1.0
            assert -1.0 <= d <= 1.0

    def test_different_characters_different_emotional_trajectories(self):
        la_a = LorenzAttractor(initial_state=(1.0, 1.0, 1.0))
        la_b = LorenzAttractor(initial_state=(5.0, 5.0, 25.0))

        ef_a = EmotionalFluctuation(attractor=la_a, coupling=0.05, decay=0.95)
        ef_b = EmotionalFluctuation(attractor=la_b, coupling=0.05, decay=0.95)

        emo_a = (0.0, 0.0, 0.0)
        emo_b = (0.0, 0.0, 0.0)

        for _ in range(20):
            emo_a = ef_a.update(emo_a)
            emo_b = ef_b.update(emo_b)

        assert emo_a != emo_b

    def test_perturbation_creates_divergence(self):
        rng_a = PCGRandom(seed=42)
        rng_b = PCGRandom(seed=99)

        la_a = LorenzAttractor(initial_state=(1.0, 1.0, 1.0))
        la_b = LorenzAttractor(initial_state=(1.0, 1.0, 1.0))

        ef_a = EmotionalFluctuation(attractor=la_a, coupling=0.05, decay=0.95)
        ef_b = EmotionalFluctuation(attractor=la_b, coupling=0.05, decay=0.95)

        emo_a = (0.0, 0.0, 0.0)
        emo_b = (0.0, 0.0, 0.0)

        for _ in range(5):
            la_a.perturb(rng_a, magnitude=0.1)
            la_b.perturb(rng_b, magnitude=0.1)
            emo_a = ef_a.update(emo_a)
            emo_b = ef_b.update(emo_b)

        assert emo_a != emo_b


class TestStateRendererMultiCharacter:
    def test_different_characters_different_prompts(self):
        renderer = StateRenderer()

        char_a = MockCharacter("a", "小雪", {"openness": 72, "conscientiousness": 45, "extraversion": 28, "agreeableness": 85, "neuroticism": 62})
        char_b = MockCharacter("b", "鹿栖", {"openness": 90, "conscientiousness": 80, "extraversion": 65, "agreeableness": 70, "neuroticism": 30})

        prompt_a = renderer.render_system_prompt(
            character_name=char_a.name,
            personality={"openness": 72, "conscientiousness": 45, "extraversion": 28, "agreeableness": 85, "neuroticism": 62},
            pad_emotion={"pleasure": -0.3, "arousal": 0.5, "dominance": -0.2},
            seven_emotions={"joy": 0.1, "anger": 0.7, "sadness": 0.5, "fear": 0.2, "love": 0.1, "disgust": 0.0, "desire": 0.1},
            scene="教室",
            behavior_instruction="表达不满",
            memories=[{"person": "小明", "event": "吵架"}],
            background="转学生",
            output_requirements="第一人称回复",
        )

        prompt_b = renderer.render_system_prompt(
            character_name=char_b.name,
            personality={"openness": 90, "conscientiousness": 80, "extraversion": 65, "agreeableness": 70, "neuroticism": 30},
            pad_emotion={"pleasure": 0.6, "arousal": 0.3, "dominance": 0.4},
            seven_emotions={"joy": 0.8, "anger": 0.0, "sadness": 0.0, "fear": 0.0, "love": 0.5, "disgust": 0.0, "desire": 0.3},
            scene="公园",
            behavior_instruction="分享快乐",
            memories=[{"person": "小雪", "event": "一起看日落"}],
            background="本地学生",
            output_requirements="第一人称回复",
        )

        assert "[角色]小雪" in prompt_a
        assert "[角色]鹿栖" in prompt_b
        assert prompt_a != prompt_b

    def test_prompt_includes_memory(self):
        renderer = StateRenderer()
        prompt = renderer.render_system_prompt(
            character_name="小雪",
            personality={"openness": 50, "conscientiousness": 50, "extraversion": 50, "agreeableness": 50, "neuroticism": 50},
            pad_emotion={"pleasure": 0.0, "arousal": 0.0, "dominance": 0.0},
            seven_emotions={"joy": 0.5, "anger": 0.0, "sadness": 0.0, "fear": 0.0, "love": 0.0, "disgust": 0.0, "desire": 0.0},
            scene="",
            behavior_instruction="",
            memories=[
                {"who": "小明", "what": "吵架"},
                {"who": "老师", "what": "被表扬"},
                {"who": "妈妈", "what": "打电话"},
            ],
            background="",
            output_requirements="",
        )
        assert "小明" in prompt

    def test_prompt_within_token_limit(self):
        renderer = StateRenderer()
        prompt = renderer.render_system_prompt(
            character_name="小雪",
            personality={"openness": 72, "conscientiousness": 45, "extraversion": 28, "agreeableness": 85, "neuroticism": 62},
            pad_emotion={"pleasure": -0.3, "arousal": 0.5, "dominance": -0.2},
            seven_emotions={"joy": 0.1, "anger": 0.7, "sadness": 0.5, "fear": 0.2, "love": 0.1, "disgust": 0.0, "desire": 0.1},
            scene="学校教室，下午的阳光透过窗户",
            behavior_instruction="表达对朋友的不满但又不忍心",
            memories=[
                {"person": "小明", "event": "今天吵架了"},
                {"person": "小红", "event": "安慰了我"},
                {"person": "老师", "event": "表扬了我"},
            ],
            background="从外地转来的学生，性格内向但很善良",
            output_requirements="第一人称回复，保持角色风格",
        )
        estimated_tokens = len(prompt) / 2
        assert estimated_tokens <= 300


class TestIntentClassifierMultiCharacter:
    def test_multi_character_indicators_trigger_complex(self):
        ic = IntentClassifier()
        assert ic.classify("让小雪和鹿栖一起讨论这个问题", num_characters=2) == IntentLevel.COMPLEX

    def test_single_character_emotion_is_moderate(self):
        ic = IntentClassifier()
        result = ic.classify("我今天很难过，你能陪我说说话吗")
        assert result == IntentLevel.MODERATE

    def test_narrative_request_is_complex(self):
        ic = IntentClassifier()
        result = ic.classify("给我讲一个关于冒险的故事吧")
        assert result == IntentLevel.COMPLEX

    def test_short_greeting_is_simple(self):
        ic = IntentClassifier()
        result = ic.classify("你好")
        assert result == IntentLevel.SIMPLE

    def test_offline_mode_downgrades_complex(self):
        ic = IntentClassifier(offline_mode=True)
        result = ic.classify("让小雪和鹿栖一起讨论这个问题", num_characters=2)
        assert result == IntentLevel.MODERATE


class TestFallbackMultiCharacter:
    def test_degradation_with_multiple_characters(self):
        fallback = LLMFallback()
        for _ in range(3):
            fallback.report_failure()
        assert fallback.current_level == DegradationLevel.DEGRADED

    def test_recovery_after_degradation(self):
        fallback = LLMFallback()
        for _ in range(3):
            fallback.report_failure()
        assert fallback.current_level == DegradationLevel.DEGRADED
        fallback.report_success()
        fallback.report_success()
        assert fallback.current_level == DegradationLevel.NORMAL

    def test_local_llm_fallback_for_multiple_chars(self):
        fallback = LLMFallback()
        mock_adapter = MagicMock(spec=LocalLLMAdapter)
        mock_adapter.chat = AsyncMock(return_value=LLMResponse(content="我在这里", role="assistant", finish_reason="stop", usage={}, tokens=5))
        renderer = StateRenderer()
        fallback.set_local_llm_adapter(mock_adapter, state_renderer=renderer)

        for _ in range(3):
            fallback.report_failure()
        assert fallback.current_level == DegradationLevel.DEGRADED
        assert fallback.has_local_llm is True


class TestDesireVectorMultiCharacter:
    def test_different_characters_different_desires(self):
        dv_a = DesireVector()
        dv_a.set_dimension("physiological", 0.9)
        dv_a.set_dimension("belonging", 0.8)
        dv_a.set_dimension("esteem", 0.3)

        dv_b = DesireVector()
        dv_b.set_dimension("physiological", 0.2)
        dv_b.set_dimension("cognitive", 0.9)
        dv_b.set_dimension("self_actualization", 0.8)

        assert dv_a.get_dimension("physiological") > dv_b.get_dimension("physiological")
        assert dv_b.get_dimension("cognitive") > dv_a.get_dimension("cognitive")

    def test_desire_drives_behavior_priority(self):
        dv = DesireVector()
        dv.set_dimension("belonging", 0.95)
        dv.set_dimension("esteem", 0.3)
        assert dv.get_dimension("belonging") > dv.get_dimension("esteem")


class TestSevenEmotionsMultiCharacter:
    def test_different_emotional_profiles(self):
        se_a = SevenEmotions()
        se_a.set_emotion("sadness", 0.8)
        se_a.set_emotion("fear", 0.5)

        se_b = SevenEmotions()
        se_b.set_emotion("joy", 0.9)
        se_b.set_emotion("love", 0.7)

        assert se_a.dominant_emotion() == "sadness"
        assert se_b.dominant_emotion() == "joy"

    def test_emotion_weights_affect_propagation(self):
        se = SevenEmotions()
        se.set_weight("joy", "sadness", -0.8)
        se.set_emotion("joy", 0.9)
        se.set_emotion("sadness", 0.5)
        w = se.get_weight("joy", "sadness")
        assert w == -0.8


class TestNarrativeSeedMultiCharacter:
    def test_each_character_gets_unique_seed(self):
        nsh = NarrativeSeedHierarchy(root_seed=42)
        seed_a = nsh.derive_character_seed("world_1", "小雪")
        seed_b = nsh.derive_character_seed("world_1", "鹿栖")
        assert seed_a != seed_b

    def test_same_character_same_seed_across_sessions(self):
        nsh = NarrativeSeedHierarchy(root_seed=42)
        seed_1 = nsh.derive_character_seed("world_1", "小雪")
        seed_2 = nsh.derive_character_seed("world_1", "小雪")
        assert seed_1 == seed_2

    def test_character_rng_deterministic(self):
        nsh = NarrativeSeedHierarchy(root_seed=42)
        rng_a1 = nsh.create_rng("world_1", "小雪")
        rng_a2 = nsh.create_rng("world_1", "小雪")
        assert rng_a1.next_uint32() == rng_a2.next_uint32()

    def test_character_rng_independent(self):
        nsh = NarrativeSeedHierarchy(root_seed=42)
        rng_a = nsh.create_rng("world_1", "小雪")
        rng_b = nsh.create_rng("world_1", "鹿栖")
        seq_a = [rng_a.next_uint32() for _ in range(10)]
        seq_b = [rng_b.next_uint32() for _ in range(10)]
        assert seq_a != seq_b


class TestEventBusMultiCharacterDialogue:
    def test_dialogue_lifecycle_events(self):
        bus = EventBus()
        events = []
        bus.subscribe_all(lambda e: events.append(e))

        bus.publish(Event(event_type=EventType.DIALOGUE_STARTED, source="system", payload={"participants": ["char_a", "char_b", "char_c"]}))
        bus.publish(Event(event_type=EventType.CHARACTER_ACTION, source="char_a", payload={"content": "大家好"}))
        bus.publish(Event(event_type=EventType.CHARACTER_ACTION, source="char_b", payload={"content": "你好"}))
        bus.publish(Event(event_type=EventType.CHARACTER_ACTION, source="char_c", payload={"content": "嗨"}))
        bus.publish(Event(event_type=EventType.DIALOGUE_ENDED, source="system"))

        assert len(events) == 5
        turn_events = [e for e in events if e.event_type == EventType.CHARACTER_ACTION]
        assert len(turn_events) == 3
        speakers = [e.source for e in turn_events]
        assert speakers == ["char_a", "char_b", "char_c"]

    def test_character_action_events_isolated(self):
        bus = EventBus()
        a_actions = []
        b_actions = []
        bus.subscribe(EventType.CHARACTER_ACTION, lambda e: a_actions.append(e) if e.source == "char_a" else None)
        bus.subscribe(EventType.CHARACTER_ACTION, lambda e: b_actions.append(e) if e.source == "char_b" else None)

        bus.publish(Event(event_type=EventType.CHARACTER_ACTION, source="char_a", payload={"action": "speak"}))
        bus.publish(Event(event_type=EventType.CHARACTER_ACTION, source="char_b", payload={"action": "listen"}))
        bus.publish(Event(event_type=EventType.CHARACTER_ACTION, source="char_a", payload={"action": "cry"}))

        assert len(a_actions) == 2
        assert len(b_actions) == 1

    def test_conflict_detection_between_characters(self):
        bus = EventBus()
        conflicts = []
        bus.subscribe(EventType.CONFLICT_DETECTED, lambda e: conflicts.append(e))

        bus.publish(Event(event_type=EventType.CONFLICT_DETECTED, source="system", payload={
            "characters": ["char_a", "char_b"],
            "type": "dialogue_interrupt",
            "severity": 0.5,
        }))

        assert len(conflicts) == 1
        assert "char_a" in conflicts[0].payload["characters"]


class TestCognitiveMemoryConfig:
    def test_default_values(self):
        cfg = CognitiveMemoryConfig()
        assert cfg.sensory_capacity == 1000
        assert cfg.working_capacity == 9
        assert cfg.short_term_capacity == 100
        assert cfg.long_term_capacity == 10000
        assert cfg.emotional_capacity == 500
        assert cfg.decay_lambda_short == 0.01
        assert cfg.decay_lambda_long == 0.001
        assert cfg.retrieval_bm25_weight + cfg.retrieval_vector_weight + cfg.retrieval_graph_weight == pytest.approx(1.0)

    def test_retrieval_weights_sum_to_one(self):
        cfg = CognitiveMemoryConfig()
        total = cfg.retrieval_bm25_weight + cfg.retrieval_vector_weight + cfg.retrieval_graph_weight
        assert abs(total - 1.0) < 1e-9

    def test_custom_values(self):
        cfg = CognitiveMemoryConfig(
            sensory_capacity=500,
            working_capacity=7,
            short_term_capacity=50,
            long_term_capacity=5000,
            emotional_capacity=200,
        )
        assert cfg.sensory_capacity == 500
        assert cfg.working_capacity == 7


class TestEndToEndMultiCharacterScenario:
    def test_three_character_dialogue_flow(self):
        bus = EventBus()
        nsh = NarrativeSeedHierarchy(root_seed=42)
        renderer = StateRenderer()
        intent_clf = IntentClassifier()

        char_a = MockCharacter("a", "小雪", {"openness": 72, "conscientiousness": 45, "extraversion": 28, "agreeableness": 85, "neuroticism": 62}, emotion=MockEmotion(-0.3, 0.5, -0.2), background="转学生")
        char_b = MockCharacter("b", "鹿栖", {"openness": 90, "conscientiousness": 80, "extraversion": 65, "agreeableness": 70, "neuroticism": 30}, emotion=MockEmotion(0.6, 0.3, 0.4), background="本地学生")
        char_c = MockCharacter("c", "星河", {"openness": 60, "conscientiousness": 90, "extraversion": 40, "agreeableness": 75, "neuroticism": 50}, emotion=MockEmotion(0.1, 0.2, 0.1), background="学霸")

        bus.publish(Event(event_type=EventType.DIALOGUE_STARTED, source="system", payload={"participants": ["a", "b", "c"]}))

        user_msg = "小雪，你今天看起来不太开心，怎么了？"
        intent = intent_clf.classify(user_msg, num_characters=3)
        assert intent == IntentLevel.COMPLEX

        prompt_a = renderer.render_system_prompt(
            character_name=char_a.name,
            personality={"openness": 72, "conscientiousness": 45, "extraversion": 28, "agreeableness": 85, "neuroticism": 62},
            pad_emotion={"pleasure": char_a.emotion.pleasure, "arousal": char_a.emotion.arousal, "dominance": char_a.emotion.dominance},
            seven_emotions={"joy": 0.1, "anger": 0.3, "sadness": 0.7, "fear": 0.2, "love": 0.1, "disgust": 0.0, "desire": 0.1},
            scene="教室",
            behavior_instruction="坦诚地表达自己的感受",
            memories=[{"who": "鹿栖", "what": "是好朋友"}],
            background=char_a.background,
            output_requirements="第一人称回复",
        )
        assert "[角色]小雪" in prompt_a
        assert "[情绪]" in prompt_a

        char_a.store_memory("short_term", {"text": "被鹿栖关心了", "importance": 0.7, "valence": 0.3})
        char_a.store_memory("emotional", {"text": "被关心时感到温暖", "importance": 0.8, "valence": 0.5})

        bus.publish(Event(event_type=EventType.CHARACTER_ACTION, source="a", payload={"content": "其实...今天和小明吵架了"}))
        bus.publish(Event(event_type=EventType.CHARACTER_ACTION, source="b", payload={"content": "别难过了，我陪你去散散步吧"}))
        bus.publish(Event(event_type=EventType.CHARACTER_ACTION, source="c", payload={"content": "需要我帮忙调解吗？"}))

        a_short = char_a.retrieve_memories(memory_type="short_term")
        a_emotional = char_a.retrieve_memories(memory_type="emotional")
        assert len(a_short) == 1
        assert len(a_emotional) == 1

        bus.publish(Event(event_type=EventType.DIALOGUE_ENDED, source="system"))
        dialogue_events = bus.get_history(event_type=EventType.CHARACTER_ACTION)
        assert len(dialogue_events) >= 3

    def test_memory_persists_across_dialogues(self):
        char = MockCharacter("a", "小雪", {"openness": 72, "extraversion": 28, "agreeableness": 85})

        char.store_memory("long_term", {"text": "和鹿栖成为好朋友", "importance": 0.95})
        char.store_memory("long_term", {"text": "转学来到这个城市", "importance": 0.9})

        char.store_memory("short_term", {"text": "今天聊了天气", "importance": 0.3})
        char.store_memory("short_term", {"text": "讨论了作业", "importance": 0.4})

        long_mems = char.retrieve_memories(memory_type="long_term")
        short_mems = char.retrieve_memories(memory_type="short_term")
        assert len(long_mems) == 2
        assert len(short_mems) == 2

        all_mems = char.retrieve_memories()
        assert len(all_mems) == 4

    def test_emotional_evolution_affects_rendering(self):
        renderer = StateRenderer()
        ef = EmotionalFluctuation(coupling=0.1, decay=0.95)
        emotion = (0.5, 0.3, 0.2)

        prompts = []
        for _ in range(10):
            emotion = ef.update(emotion)
            p, a, d = emotion
            prompt = renderer.render_system_prompt(
                character_name="小雪",
                personality={"openness": 50, "conscientiousness": 50, "extraversion": 50, "agreeableness": 50, "neuroticism": 50},
                pad_emotion={"pleasure": p, "arousal": a, "dominance": d},
                seven_emotions=None,
                scene="",
                behavior_instruction="",
                memories=[],
                background="",
                output_requirements="",
            )
            prompts.append(prompt)

        unique_prompts = set(prompts)
        assert len(unique_prompts) > 1
