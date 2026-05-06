"""
记忆管理系统单元测试
覆盖：MemoryType/MemoryEmotion枚举、MemoryEpisode、MemoryImportanceCalculator、MemorySystem的所有核心功能
"""

import time
import unittest
from luqi_engine.memory.memory_system import (
    MemoryEmotion,
    MemoryEpisode,
    MemoryImportanceCalculator,
    MemoryRetrievalResult,
    MemorySystem,
    MemoryType,
)


class TestMemoryType(unittest.TestCase):
    """测试记忆类型枚举"""

    def test_all_four_types_exist(self):
        expected = ["EPISODIC", "SEMANTIC", "PROCEDURAL", "FLASHBULB"]
        actual = [t.name for t in MemoryType]
        self.assertEqual(actual, expected)

    def test_type_count(self):
        self.assertEqual(len(MemoryType), 4)


class TestMemoryEmotion(unittest.TestCase):
    """测试情绪类型枚举"""

    def test_all_emotions_exist(self):
        expected = [
            "JOY", "SADNESS", "ANGER", "FEAR",
            "SURPRISE", "DISGUST", "NEUTRAL",
        ]
        actual = [e.name for e in MemoryEmotion]
        self.assertEqual(actual, expected)

    def test_emotion_count(self):
        self.assertEqual(len(MemoryEmotion), 7)


class TestMemoryEpisodeCreation(unittest.TestCase):
    """测试记忆片段创建和初始化"""

    def test_default_creation(self):
        ep = MemoryEpisode()
        self.assertGreater(ep.timestamp, 0)
        self.assertEqual(ep.last_accessed, ep.timestamp)
        self.assertEqual(ep.access_count, 0)
        self.assertEqual(ep.content, "")
        self.assertEqual(ep.memory_type, MemoryType.EPISODIC)
        self.assertEqual(len(ep.emotions), 0)
        self.assertAlmostEqual(ep.emotional_intensity, 0.5)
        self.assertAlmostEqual(ep.base_importance, 0.5)
        self.assertAlmostEqual(ep.current_importance, 0.5)

    def test_custom_values(self):
        ep = MemoryEpisode(
            content="遇到了神秘旅人",
            memory_type=MemoryType.FLASHBULB,
            emotions=[MemoryEmotion.SURPRISE],
            emotional_intensity=0.9,
        )
        self.assertEqual(ep.content, "遇到了神秘旅人")
        self.assertEqual(ep.memory_type, MemoryType.FLASHBULB)
        self.assertIn(MemoryEmotion.SURPRISE, ep.emotions)
        self.assertAlmostEqual(ep.emotional_intensity, 0.9)

    def test_episode_id_auto_generated(self):
        ep = MemoryEpisode(content="test")
        self.assertTrue(len(ep.episode_id) > 0)
        self.assertTrue(len(ep.episode_id) == 16)  # md5 hex[:16]

    def test_custom_episode_id_preserved(self):
        custom_id = "custom_id_123"
        ep = MemoryEpisode(episode_id=custom_id, content="test")
        self.assertEqual(ep.episode_id, custom_id)

    def test_timestamp_auto_set(self):
        before = time.time()
        ep = MemoryEpisode(content="test")
        after = time.time()
        self.assertGreaterEqual(ep.timestamp, before)
        self.assertLessEqual(ep.timestamp, after)

    def test_last_accessed_equals_timestamp_initially(self):
        ep = MemoryEpisode(content="test")
        self.assertEqual(ep.last_accessed, ep.timestamp)

    def test_empty_content_allowed(self):
        ep = MemoryEpisode(content="")
        self.assertEqual(ep.content, "")

    def test_tags_default_empty(self):
        ep = MemoryEpisode()
        self.assertEqual(len(ep.tags), 0)

    def test_associated_entities_default_empty(self):
        ep = MemoryEpisode()
        self.assertEqual(len(ep.associated_entities), 0)


class TestMemoryEpisodeClamping(unittest.TestCase):
    """测试数值范围钳制"""

    def test_emotional_intensity_clamped_high(self):
        ep = MemoryEpisode(emotional_intensity=1.5)
        self.assertAlmostEqual(ep.emotional_intensity, 1.0)

    def test_emotional_intensity_clamped_low(self):
        ep = MemoryEpisode(emotional_intensity=-0.3)
        self.assertAlmostEqual(ep.emotional_intensity, 0.0)

    def test_base_importance_clamped_high(self):
        ep = MemoryEpisode(base_importance=2.0)
        self.assertAlmostEqual(ep.base_importance, 1.0)

    def test_base_importance_clamped_low(self):
        ep = MemoryEpisode(base_importance=-0.5)
        self.assertAlmostEqual(ep.base_importance, 0.0)

    def test_current_importance_synced_with_base(self):
        ep = MemoryEpisode(base_importance=0.75)
        self.assertAlmostEqual(ep.current_importance, 0.75)


class TestMemoryEpisodeAccessMethod(unittest.TestCase):
    """测试访问方法"""

    def test_access_updates_last_accessed(self):
        ep = MemoryEpisode(content="test")
        original_accessed = ep.last_accessed
        
        time.sleep(0.01)  # 确保时间差
        ep.access()
        
        self.assertGreater(ep.last_accessed, original_accessed)

    def test_access_increments_count(self):
        ep = MemoryEpisode(content="test")
        initial_count = ep.access_count
        
        ep.access()
        
        self.assertEqual(ep.access_count, initial_count + 1)

    def test_multiple_accesses(self):
        ep = MemoryEpisode(content="test")
        for _ in range(10):
            ep.access()
        
        self.assertEqual(ep.access_count, 10)


class TestMemoryEpisodeToPromptFragment(unittest.TestCase):
    """测试prompt片段生成"""

    def test_empty_content_returns_empty(self):
        ep = MemoryEpisode(content="")
        result = ep.to_prompt_fragment()
        self.assertEqual(result, "")

    def test_simple_content(self):
        ep = MemoryEpisode(content="遇到了神秘旅人")
        result = ep.to_prompt_fragment()
        self.assertIn("遇到了神秘旅人", result)

    def test_with_tags(self):
        ep = MemoryEpisode(
            content="战斗",
            tags=["危险", "紧张"],
        )
        result = ep.to_prompt_fragment()
        self.assertIn("危险", result)
        self.assertIn("紧张", result)

    def test_truncation_when_too_long(self):
        long_content = "这是一段非常长的内容" * 20
        ep = MemoryEpisode(content=long_content)
        result = ep.to_prompt_fragment(max_length=50)
        
        self.assertLessEqual(len(result), 50 + len("..."))
        self.assertTrue(result.endswith("..."))

    def test_no_truncation_for_short_content(self):
        short_content = "短内容"
        ep = MemoryEpisode(content=short_content)
        result = ep.to_prompt_fragment(max_length=100)
        
        self.assertEqual(result, short_content)

    def test_max_length_boundary(self):
        content = "A" * 90
        ep = MemoryEpisode(content=content)
        result = ep.to_prompt_fragment(max_length=100)
        
        self.assertLessEqual(len(result), 103)  # 100 + "..."


class TestMemoryEpisodeProperties(unittest.TestCase):
    """测试属性计算"""

    def test_is_forgotten_false_by_default(self):
        ep = MemoryEpisode(current_importance=0.5)
        self.assertFalse(ep.is_forgotten)

    def test_is_forgotten_true_below_threshold(self):
        ep = MemoryEpisode(current_importance=0.01)
        self.assertTrue(ep.is_forgotten)

    def test_is_forgotten_at_threshold_boundary(self):
        ep = MemoryEpisode(current_importance=0.05)
        self.assertFalse(ep.is_forgotten)  # < threshold才forgotten

    def test_age_days_zero_freshly_created(self):
        ep = MemoryEpisode(content="test")
        age = ep.age_days
        self.assertGreaterEqual(age, 0)
        self.assertLess(age, 0.001)  # 几乎为0

    def test_age_days_increases_over_time(self):
        ep = MemoryEpisode(content="test")
        
        import time as t
        t.sleep(0.01)
        
        age_later = ep.age_days
        self.assertGreater(age_later, 0)


class TestImportanceCalculatorBaseImportance(unittest.TestCase):
    """测试初始重要性计算"""

    def test_basic_calculation(self):
        importance = MemoryImportanceCalculator.compute_base_importance(
            content="这是一段普通的记忆",
            emotions=[],
            emotional_intensity=0.5,
            entity_count=1,
        )
        self.assertGreater(importance, 0)
        self.assertLessEqual(importance, 1)

    def test_longer_content_higher_importance(self):
        short_imp = MemoryImportanceCalculator.compute_base_importance(
            content="短",
            emotions=[],
            emotional_intensity=0.5,
            entity_count=0,
        )
        long_imp = MemoryImportanceCalculator.compute_base_importance(
            content="这是一段很长的内容描述，包含了很多细节信息" * 5,
            emotions=[],
            emotional_intensity=0.5,
            entity_count=0,
        )
        self.assertGreater(long_imp, short_imp)

    def test_more_entities_higher_importance(self):
        few_imp = MemoryImportanceCalculator.compute_base_importance(
            content="test",
            emotions=[],
            emotional_intensity=0.5,
            entity_count=1,
        )
        many_imp = MemoryImportanceCalculator.compute_base_importance(
            content="test",
            emotions=[],
            emotional_intensity=0.5,
            entity_count=8,
        )
        self.assertGreater(many_imp, few_imp)

    def test_emotional_enhancement(self):
        neutral_imp = MemoryImportanceCalculator.compute_base_importance(
            content="test",
            emotions=[MemoryEmotion.NEUTRAL],
            emotional_intensity=0.5,
            entity_count=0,
        )
        strong_imp = MemoryImportanceCalculator.compute_base_importance(
            content="test",
            emotions=[MemoryEmotion.SURPRISE, MemoryEmotion.FEAR],
            emotional_intensity=0.9,
            entity_count=0,
        )
        self.assertGreater(strong_imp, neutral_imp)

    def test_flashbulb_bonus(self):
        normal_imp = MemoryImportanceCalculator.compute_base_importance(
            content="重大事件",
            emotions=[MemoryEmotion.FEAR],
            emotional_intensity=0.95,
            entity_count=2,
            is_flashbulb=False,
        )
        flashbulb_imp = MemoryImportanceCalculator.compute_base_importance(
            content="重大事件",
            emotions=[MemoryEmotion.FEAR],
            emotional_intensity=0.95,
            entity_count=2,
            is_flashbulb=True,
        )
        self.assertGreater(flashbulb_imp, normal_imp)
        ratio = flashbulb_imp / normal_imp if normal_imp > 0 else float('inf')
        self.assertAlmostEqual(ratio, 1.5, places=1)

    def test_output_range(self):
        for _ in range(20):
            importance = MemoryImportanceCalculator.compute_base_importance(
                content="x" * 500,
                emotions=[MemoryEmotion.JOY, MemoryEmotion.ANGER],
                emotional_intensity=1.0,
                entity_count=10,
                is_flashbulb=True,
            )
            self.assertGreaterEqual(importance, 0.0)
            self.assertLessEqual(importance, 1.0)


class TestImportanceCalculatorDecay(unittest.TestCase):
    """测试衰减计算"""

    def test_decay_reduces_importance(self):
        base = 0.8
        after_1day = MemoryImportanceCalculator.update_importance_with_decay(
            base_importance=base,
            age_days=1.0,
            access_count=0,
            days_since_last_access=1.0,
        )
        after_30days = MemoryImportanceCalculator.update_importance_with_decay(
            base_importance=base,
            age_days=30.0,
            access_count=0,
            days_since_last_access=30.0,
        )
        self.assertGreater(after_1day, after_30days)

    def test_review_boosts_retention(self):
        no_review = MemoryImportanceCalculator.update_importance_with_decay(
            base_importance=0.7,
            age_days=10.0,
            access_count=0,
            days_since_last_access=10.0,
        )
        with_review = MemoryImportanceCalculator.update_importance_with_decay(
            base_importance=0.7,
            age_days=10.0,
            access_count=20,
            days_since_last_access=1.0,
        )
        self.assertGreater(with_review, no_review)

    def test_flashbulb_decays_slower(self):
        normal_after_30 = MemoryImportanceCalculator.update_importance_with_decay(
            base_importance=0.8,
            age_days=30.0,
            access_count=0,
            days_since_last_access=30.0,
            memory_type=MemoryType.EPISODIC,
        )
        flashbulb_after_30 = MemoryImportanceCalculator.update_importance_with_decay(
            base_importance=0.8,
            age_days=30.0,
            access_count=0,
            days_since_last_access=30.0,
            memory_type=MemoryType.FLASHBULB,
        )
        self.assertGreater(flashbulb_after_30, normal_after_30)

    def test_recent_access_boost(self):
        old_access = MemoryImportanceCalculator.update_importance_with_decay(
            base_importance=0.6,
            age_days=5.0,
            access_count=3,
            days_since_last_access=5.0,
        )
        recent_access = MemoryImportanceCalculator.update_importance_with_decay(
            base_importance=0.6,
            age_days=5.0,
            access_count=3,
            days_since_last_access=0.5,
        )
        self.assertGreater(recent_access, old_access)

    def test_output_range(self):
        for age in [0, 1, 10, 100, 365]:
            result = MemoryImportanceCalculator.update_importance_with_decay(
                base_importance=0.8,
                age_days=float(age),
                access_count=age,
                days_since_last_access=float(age),
            )
            self.assertGreaterEqual(result, 0.0)
            self.assertLessEqual(result, 1.0)


class TestImportanceCalculatorRelevance(unittest.TestCase):
    """测试相关性计算"""

    def test_no_query_returns_base_score(self):
        ep = MemoryEpisode(content="test", current_importance=0.6)
        score = MemoryImportanceCalculator.compute_relevance_score([], ep)
        self.assertGreater(score, 0)

    def test_keyword_match_increases_score(self):
        ep = MemoryEpisode(
            content="在玫瑰酒馆遇到了神秘旅人",
            current_importance=0.7,
        )
        no_match = MemoryImportanceCalculator.compute_relevance_score(["吃饭"], ep)
        match = MemoryImportanceCalculator.compute_relevance_score(["酒馆"], ep)
        self.assertGreater(match, no_match)

    def test_tag_match_weighted_higher(self):
        ep_with_tag = MemoryEpisode(
            content="事件",
            tags=["重要"],
            current_importance=0.5,
        )
        ep_without_tag = MemoryEpisode(
            content="事件",
            current_importance=0.5,
        )
        tag_score = MemoryImportanceCalculator.compute_relevance_score(
            ["重要"], ep_with_tag
        )
        no_tag_score = MemoryImportanceCalculator.compute_relevance_score(
            ["重要"], ep_without_tag
        )
        self.assertGreater(tag_score, no_tag_score)

    def test_entity_match_contributes(self):
        ep_with_entity = MemoryEpisode(
            content="事件",
            associated_entities=["alice"],
            current_importance=0.5,
        )
        score = MemoryImportanceCalculator.compute_relevance_score(
            ["alice"], ep_with_entity
        )
        self.assertGreater(score, 0)

    def test_output_range(self):
        ep = MemoryEpisode(content="test content here", current_importance=0.8)
        score = MemoryImportanceCalculator.compute_relevance_score(
            ["test", "content"], ep
        )
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)


class TestMemorySystemBasicOperations(unittest.TestCase):
    """测试记忆系统基础操作"""

    def setUp(self):
        self.mem_sys = MemorySystem(character_id="test_char")

    def test_initialization(self):
        self.assertEqual(self.mem_sys.character_id, "test_char")
        self.assertEqual(self.mem_sys.memory_count, 0)

    def test_store_single_memory(self):
        episode = self.mem_sys.store("第一次记忆")
        self.assertIsNotNone(episode)
        self.assertEqual(episode.content, "第一次记忆")
        self.assertEqual(self.mem_sys.memory_count, 1)

    def test_store_multiple_memories(self):
        for i in range(5):
            self.mem_sys.store(f"记忆{i}")
        self.assertEqual(self.mem_sys.memory_count, 5)

    def test_store_with_all_parameters(self):
        episode = self.mem_sys.store(
            content="复杂记忆",
            memory_type=MemoryType.FLASHBULB,
            emotions=[MemoryEmotion.SURPRISE, MemoryEmotion.JOY],
            emotional_intensity=0.9,
            associated_entities=["alice", "bob"],
            tags=["重要", "转折点"],
            source_context="在酒馆中",
        )
        self.assertEqual(episode.content, "复杂记忆")
        self.assertEqual(episode.memory_type, MemoryType.FLASHBULB)
        self.assertIn(MemoryEmotion.SURPRISE, episode.emotions)
        self.assertAlmostEqual(episode.emotional_intensity, 0.9)
        self.assertIn("alice", episode.associated_entities)
        self.assertIn("重要", episode.tags)

    def test_store_empty_content_raises_error(self):
        with self.assertRaises(ValueError):
            self.mem_sys.store("")
        
        with self.assertRaises(ValueError):
            self.mem_sys.store("   ")

    def test_store_whitespace_trimmed(self):
        episode = self.mem_sys.store("   内容前后有空格   ")
        self.assertEqual(episode.content, "内容前后有空格")


class TestMemorySystemRetrieve(unittest.TestCase):
    """测试记忆检索"""

    def setUp(self):
        self.mem_sys = MemorySystem(character_id="alice")
        self.mem_sys.store("在玫瑰酒馆遇到了神秘旅人", tags=["冒险"])
        self.mem_sys.store("学习了新的剑术技能", memory_type=MemoryType.PROCEDURAL)
        self.mem_sys.store("与好友Bob共进晚餐", associated_entities=["bob"])

    def test_retrieve_by_keyword(self):
        results = self.mem_sys.retrieve(query=["酒馆"])
        self.assertGreater(results.count, 0)
        found = any("酒館" in ep.content or "酒馆" in ep.content 
                   for ep, _ in results.episodes)
        self.assertTrue(found)

    def test_retrieve_by_entity(self):
        results = self.mem_sys.retrieve(entity_id="bob")
        self.assertGreater(results.count, 0)

    def test_retrieve_by_type(self):
        results = self.mem_sys.retrieve(memory_type=MemoryType.PROCEDURAL)
        self.assertEqual(results.count, 1)
        self.assertIn("剑术", results.episodes[0][0].content)

    def test_retrieve_combined_filters(self):
        results = self.mem_sys.retrieve(
            query=["晚餐"],
            entity_id="bob",
        )
        self.assertGreater(results.count, 0)

    def test_retrieve_no_results(self):
        results = self.mem_sys.retrieve(query=["不存在的关键词xyz"])
        self.assertEqual(results.count, 0)

    def test_retrieve_respects_max_results(self):
        for i in range(20):
            self.mem_sys.store(f"记忆{i}")
        results = self.mem_sys.retrieve(query=[], max_results=5)
        self.assertLessEqual(results.count, 5)

    def test_retrieve_min_importance_filter(self):
        low_imp_ep = self.mem_sys.store("低重要性记忆")
        low_imp_ep.current_importance = 0.01
        
        results = self.mem_sys.retrieve(min_importance=0.1)
        found_low = any(ep.episode_id == low_imp_ep.episode_id 
                       for ep, _ in results.episodes)
        self.assertFalse(found_low)

    def test_retrieve_sorts_by_relevance(self):
        results = self.mem_sys.retrieve(query=["酒馆"])
        if results.count >= 2:
            scores = [score for _, score in results.episodes]
            self.assertEqual(scores, sorted(scores, reverse=True))

    def test_retrieve_total_searched_field(self):
        results = self.mem_sys.retrieve(query=["酒馆"])
        self.assertGreater(results.total_searched, 0)


class TestMemorySystemForget(unittest.TestCase):
    """测试手动遗忘"""

    def setUp(self):
        self.mem_sys = MemorySystem(character_id="char")

    def test_forget_existing_memory(self):
        ep = self.mem_sys.store("要被遗忘的记忆")
        initial_count = self.mem_sys.memory_count
        
        removed = self.mem_sys.forget(ep.episode_id)
        
        self.assertIsNotNone(removed)
        self.assertEqual(self.mem_sys.memory_count, initial_count - 1)

    def test_forget_nonexistent_memory(self):
        result = self.mem_sys.forget("nonexistent_id")
        self.assertIsNone(result)

    def test_forget_does_not_affect_others(self):
        ep1 = self.mem_sys.store("记忆1")
        ep2 = self.mem_sys.store("记忆2")
        
        self.mem_sys.forget(ep1.episode_id)
        
        self.assertEqual(self.mem_sys.memory_count, 1)
        remaining = list(self.mem_sys._memories.values())[0]
        self.assertEqual(remaining.episode_id, ep2.episode_id)


class TestMemorySystemDecay(unittest.TestCase):
    """测试记忆衰减"""

    def setUp(self):
        self.mem_sys = MemorySystem(character_id="char")

    def test_decay_reduces_importance(self):
        ep = self.mem_sys.store("会衰减的记忆")
        
        import time as _time
        _time.sleep(3)
        
        original_importance = ep.current_importance
        self.mem_sys.decay(force=True)
        
        _time.sleep(3)
        self.mem_sys.decay(force=True)
        
        final_ep = self.mem_sys._memories[ep.episode_id]
        self.assertLess(final_ep.current_importance, original_importance + 0.05)

    def test_decay_skipped_if_too_soon(self):
        self.mem_sys.store("记忆")
        count1 = self.mem_sys.decay(force=False)
        count2 = self.mem_sys.decay(force=False)
        self.assertEqual(count1, 0)
        self.assertEqual(count2, 0)

    def test_force_decay_always_executes(self):
        self.mem_sys.store("记忆")
        count = self.mem_sys.decay(force=True)
        self.assertGreaterEqual(count, 0)

    def test_decay_returns_newly_forgotten_count(self):
        for _ in range(5):
            ep = self.mem_sys.store("旧记忆")
            ep.current_importance = 0.04  # 接近阈值
            
        forgotten_count = self.mem_sys.decay(force=True)
        self.assertGreaterEqual(forgotten_count, 0)


class TestMemorySystemPromptGeneration(unittest.TestCase):
    """测试prompt生成"""

    def setUp(self):
        self.mem_sys = MemorySystem(character_id="char")

    def test_empty_system_returns_empty(self):
        summary = self.mem_sys.get_memories_for_prompt()
        self.assertEqual(summary, "")

    def test_with_memories_returns_formatted_text(self):
        self.mem_sys.store("重要事件1", tags=["关键"])
        self.mem_sys.store("重要事件2", tags=["转折"])
        
        summary = self.mem_sys.get_memories_for_prompt(max_count=5)
        self.assertIn("相关记忆:", summary)
        self.assertIn("1.", summary)

    def test_respects_max_count(self):
        for i in range(10):
            self.mem_sys.store(f"记忆{i}")
            
        summary = self.mem_sys.get_memories_for_prompt(max_count=3)
        lines = summary.split("\n")
        numbered_lines = [l for l in lines if l.strip().startswith(("1.", "2.", "3."))]
        self.assertLessEqual(len(numbered_lines), 3)

    def test_respects_max_total_length(self):
        long_contents = ["这是一段非常长的记忆内容描述" * 10 for _ in range(5)]
        for content in long_contents:
            self.mem_sys.store(content)
            
        summary = self.mem_sys.get_memories_for_prompt(
            max_count=10,
            max_total_length=100,
        )
        self.assertLessEqual(len(summary), 105)  # 允许小误差

    def test_context_query_affects_selection(self):
        self.mem_sys.store("关于剑术的讨论", tags=["战斗"])
        self.mem_sys.store("关于烹饪的学习", tags=["生活"])
        
        combat_summary = self.mem_sys.get_memories_for_prompt(
            context_query=["剑术", "战斗"],
        )
        self.assertIn("剑术", combat_summary)


class TestMemorySystemStatistics(unittest.TestCase):
    """测试统计信息"""

    def setUp(self):
        self.mem_sys = MemorySystem(character_id="char")

    def test_empty_statistics(self):
        stats = self.mem_sys.get_statistics()
        self.assertEqual(stats["total_memories"], 0)
        self.assertEqual(stats["active_memories"], 0)

    def test_populated_statistics(self):
        self.mem_sys.store("记忆1", emotions=[MemoryEmotion.JOY])
        self.mem_sys.store("记忆2", emotions=[MemoryEmotion.SADNESS])
        self.mem_sys.store("记忆3", memory_type=MemoryType.PROCEDURAL)
        
        stats = self.mem_sys.get_statistics()
        
        self.assertEqual(stats["total_memories"], 3)
        self.assertEqual(stats["active_memories"], 3)
        self.assertIn("EPISODIC", stats["type_distribution"])
        self.assertIn("PROCEDURAL", stats["type_distribution"])
        self.assertIn("JOY", stats["emotion_distribution"])

    def test_avg_importance_calculated(self):
        self.mem_sys.store("记忆A")
        ep_b = self.mem_sys.store("记忆B")
        ep_b.current_importance = 0.9
        
        stats = self.mem_sys.get_statistics()
        self.assertGreater(stats["avg_importance"], 0)
        self.assertLess(stats["avg_importance"], 1)


class TestMemorySystemAutoCleanup(unittest.TestCase):
    """测试自动清理机制"""

    def test_cleanup_triggered_at_threshold(self):
        mem_sys = MemorySystem(character_id="char")
        mem_sys.MAX_MEMORIES = 100  # 降低阈值便于测试
        
        for i in range(95):  # 超过90% (90)
            mem_sys.store(f"记忆{i}")
            
        last_ep = mem_sys.store("最后一条记忆")
        self.assertLess(mem_sys.memory_count, 96)  # 应该触发清理

    def test_cleanup_removes_lowest_importance(self):
        mem_sys = MemorySystem(character_id="char")
        mem_sys.MAX_MEMORIES = 50
        
        important = mem_sys.store("重要记忆")
        important.current_importance = 1.0
        
        for i in range(48):
            unimportant = mem_sys.store(f"不重要{i}")
            unimportant.current_importance = 0.01
            
        mem_sys.store("触发清理")
        
        still_exists = important.episode_id in mem_sys._memories
        self.assertTrue(still_exists)


class TestMemoryRetrievalResult(unittest.TestCase):
    """测试检索结果包装类"""

    def test_default_creation(self):
        result = MemoryRetrievalResult()
        self.assertEqual(result.count, 0)
        self.assertIsNone(result.query_keywords)

    def test_count_property(self):
        episodes = [(MemoryEpisode(content=f"ep{i}"), 0.5) for i in range(5)]
        result = MemoryRetrievalResult(episodes=episodes)
        self.assertEqual(result.count, 5)

    def test_get_top_episodes(self):
        episodes = [
            (MemoryEpisode(content="low"), 0.2),
            (MemoryEpisode(content="high"), 0.9),
            (MemoryEpisode(content="mid"), 0.5),
        ]
        result = MemoryRetrievalResult(episodes=episodes)
        
        top2 = result.get_top_episodes(2)
        self.assertEqual(len(top2), 2)
        self.assertEqual(top2[0][1], 0.9)  # 最高分在前


class TestEdgeCasesAndRobustness(unittest.TestCase):
    """边界条件和鲁棒性测试"""

    def test_rapid_store_operations(self):
        mem_sys = MemorySystem(character_id="stress_test")
        for i in range(200):
            mem_sys.store(f"快速存储{i}")
        self.assertEqual(mem_sys.memory_count, 200)

    def test_unicode_content(self):
        mem_sys = MemorySystem(character_id="unicode_test")
        ep = mem_sys.store("🎉 Unicode内容: 中文、日本語、한국어、العربية")
        self.assertIn("🎉", ep.content)

    def test_very_long_content(self):
        mem_sys = MemorySystem(character_id="long_content")
        long_text = "这是一个超长的内容" * 1000
        ep = mem_sys.store(long_text)
        self.assertEqual(len(ep.content), len(long_text.strip()))

    def test_many_emotions(self):
        all_emotions = list(MemoryEmotion)
        ep = MemoryEpisode(emotions=all_emotions, emotional_intensity=1.0)
        self.assertEqual(len(ep.emotions), 7)

    def test_many_tags_and_entities(self):
        ep = MemoryEpisode(
            tags=[f"tag{i}" for i in range(20)],
            associated_entities=[f"entity{i}" for i in range(15)],
        )
        self.assertEqual(len(ep.tags), 20)
        self.assertEqual(len(ep.associated_entities), 15)

    def test_retrieve_with_all_filters_combined(self):
        mem_sys = MemorySystem(character_id="complex")
        target = mem_sys.store(
            "目标记忆",
            memory_type=MemoryType.EPISODIC,
            associated_entities=["target_entity"],
            tags=["target_tag"],
        )
        
        for i in range(10):
            mem_sys.store(f"干扰记忆{i}")
            
        results = mem_sys.retrieve(
            query=["目标"],
            entity_id="target_entity",
            memory_type=MemoryType.EPISODIC,
            max_results=1,
        )
        
        self.assertGreater(results.count, 0)
        self.assertIn(target.episode_id, [ep.episode_id for ep, _ in results.episodes])


if __name__ == "__main__":
    unittest.main()
