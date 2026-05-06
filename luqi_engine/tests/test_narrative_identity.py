"""
叙事身份模型单元测试
覆盖：LifeChapter、NarrativeEpisode、CoreNarrative的所有核心功能
"""

import time
import unittest
from luqi_engine.character.narrative_identity import (
    CoreNarrative,
    LifeChapter,
    NarrativeEpisode,
)


class TestLifeChapter(unittest.TestCase):
    """测试人生阶段枚举"""

    def test_all_chapters_exist(self):
        expected_chapters = [
            "ORIGIN", "TRIALS", "TRANSFORMATION", "MATURITY", "LEGACY"
        ]
        actual_chapters = [chapter.name for chapter in LifeChapter]
        self.assertEqual(actual_chapters, expected_chapters)

    def test_chapter_count(self):
        self.assertEqual(len(LifeChapter), 5)


class TestNarrativeEpisodeCreation(unittest.TestCase):
    """测试叙事片段创建和初始化"""

    def test_default_creation(self):
        episode = NarrativeEpisode()
        self.assertEqual(episode.episode_id, "")
        self.assertEqual(episode.title, "")
        self.assertEqual(episode.description, "")
        self.assertEqual(episode.chapter, LifeChapter.ORIGIN)
        self.assertAlmostEqual(episode.timestamp, -1.0)
        self.assertAlmostEqual(episode.significance, 0.5)
        self.assertEqual(episode.emotional_tags, [])
        self.assertIsNone(episode.learned_lesson)

    def test_custom_creation(self):
        episode = NarrativeEpisode(
            episode_id="ep_001",
            title="初次冒险",
            description="第一次离开家乡踏上旅程",
            chapter=LifeChapter.TRIALS,
            timestamp=1000.0,
            significance=0.8,
            emotional_tags=["兴奋", "恐惧"],
            learned_lesson="勇气源于行动",
        )
        self.assertEqual(episode.episode_id, "ep_001")
        self.assertEqual(episode.title, "初次冒险")
        self.assertEqual(episode.chapter, LifeChapter.TRIALS)
        self.assertAlmostEqual(episode.significance, 0.8)
        self.assertIn("兴奋", episode.emotional_tags)
        self.assertEqual(episode.learned_lesson, "勇气源于行动")

    def test_significance_clamping_high(self):
        episode = NarrativeEpisode(significance=1.5)
        self.assertAlmostEqual(episode.significance, 1.0)

    def test_significance_clamping_low(self):
        episode = NarrativeEpisode(significance=-0.3)
        self.assertAlmostEqual(episode.significance, 0.0)

    def test_significance_boundary_max(self):
        episode = NarrativeEpisode(significance=1.0)
        self.assertAlmostEqual(episode.significance, 1.0)

    def test_significance_boundary_min(self):
        episode = NarrativeEpisode(significance=0.0)
        self.assertAlmostEqual(episode.significance, 0.0)

    def test_defining_moment_detection(self):
        normal_episode = NarrativeEpisode(significance=0.5)
        defining_episode = NarrativeEpisode(significance=0.8)
        
        self.assertFalse(normal_episode.is_defining_moment)
        self.assertTrue(defining_episode.is_defining_moment)

    def test_boundary_defining_moment(self):
        boundary_episode = NarrativeEpisode(significance=0.7)
        self.assertFalse(boundary_episode.is_defining_moment)
        
        just_above = NarrativeEpisode(significance=0.71)
        self.assertTrue(just_above.is_defining_moment)


class TestNarrativeEpisodeToPrompt(unittest.TestCase):
    """测试叙事片段转换为prompt格式"""

    def test_full_episode_to_prompt(self):
        episode = NarrativeEpisode(
            title="战斗",
            description="在战场上与敌人激战",
            significance=0.9,
            emotional_tags=["愤怒", "悲伤"],
            learned_lesson="战争没有赢家",
        )
        prompt = episode.to_narrative_prompt()
        
        self.assertIn("[战斗]", prompt)
        self.assertIn("在战场上与敌人激战", prompt)
        self.assertIn("情感:", prompt)
        self.assertIn("愤怒", prompt)
        self.assertIn("战争没有赢家", prompt)

    def test_title_only_episode(self):
        episode = NarrativeEpisode(title="出生")
        prompt = episode.to_narrative_prompt()
        
        self.assertIn("[出生]", prompt)

    def test_description_only_episode(self):
        episode = NarrativeEpisode(description="某件事发生了")
        prompt = episode.to_narrative_prompt()
        
        self.assertIn("某件事发生了", prompt)

    def test_empty_episode_returns_empty(self):
        episode = NarrativeEpisode()
        prompt = episode.to_narrative_prompt()
        
        self.assertEqual(prompt, "")

    def test_emotional_tags_limit(self):
        episode = NarrativeEpisode(
            title="复杂事件",
            emotional_tags=["喜", "怒", "哀", "惧", "爱", "恶"],
        )
        prompt = episode.to_narrative_prompt()
        
        tags_part = prompt.split("(情感: ")[1] if "(情感: " in prompt else ""
        if tags_part:
            displayed_tags = tags_part.split(")")[0].split("、")
            self.assertLessEqual(len(displayed_tags), 3)

    def test_no_learned_lesson(self):
        episode = NarrativeEpisode(
            title="事件",
            description="描述",
            learned_lesson=None,
        )
        prompt = episode.to_narrative_prompt()
        
        self.assertNotIn("—", prompt)


class TestCoreNarrativeCreation(unittest.TestCase):
    """测试核心叙事创建和初始化"""

    def test_default_creation(self):
        narrative = CoreNarrative()
        self.assertEqual(narrative.origin_story, "")
        self.assertEqual(narrative.central_conflict, "")
        self.assertEqual(narrative.unfulfilled_destiny, "")
        self.assertEqual(narrative.fear_of_becoming, "")
        self.assertEqual(narrative.core_values, [])
        self.assertEqual(narrative.defining_moments, [])
        self.assertEqual(narrative.current_chapter, LifeChapter.MATURITY)

    def test_custom_creation(self):
        narrative = CoreNarrative(
            origin_story="出生于贵族家庭",
            central_conflict="责任vs自由",
            unfulfilled_destiny="改变世界",
            fear_of_becoming="像父亲一样冷酷",
            core_values=["正义", "勇气"],
            current_chapter=LifeChapter.TRANSFORMATION,
        )
        self.assertEqual(narrative.origin_story, "出生于贵族家庭")
        self.assertEqual(narrative.central_conflict, "责任vs自由")
        self.assertEqual(narrative.current_chapter, LifeChapter.TRANSFORMATION)
        self.assertIn("正义", narrative.core_values)

    def test_is_empty_true(self):
        narrative = CoreNarrative()
        self.assertTrue(narrative.is_empty)

    def test_is_empty_false_with_origin(self):
        narrative = CoreNarrative(origin_story="有背景")
        self.assertFalse(narrative.is_empty)

    def test_is_empty_false_with_episodes(self):
        narrative = CoreNarrative()
        narrative.add_episode(NarrativeEpisode(episode_id="ep1"))
        self.assertFalse(narrative.is_empty)


class TestEpisodeManagement(unittest.TestCase):
    """测试叙事片段管理"""

    def setUp(self):
        self.narrative = CoreNarrative()

    def test_add_single_episode(self):
        episode = NarrativeEpisode(episode_id="ep_001", timestamp=100.0)
        self.narrative.add_episode(episode)
        
        self.assertEqual(len(self.narrative.defining_moments), 1)
        self.assertEqual(self.narrative.defining_moments[0].episode_id, "ep_001")

    def test_add_multiple_episodes(self):
        for i in range(5):
            ep = NarrativeEpisode(episode_id=f"ep_{i:03d}", timestamp=float(i * 100))
            self.narrative.add_episode(ep)
        
        self.assertEqual(len(self.narrative.defining_moments), 5)

    def test_add_non_episode_raises_type_error(self):
        with self.assertRaises(TypeError):
            self.narrative.add_episode("not an episode")

    def test_remove_existing_episode(self):
        self.narrative.add_episode(NarrativeEpisode(episode_id="to_remove"))
        removed = self.narrative.remove_episode("to_remove")
        
        self.assertIsNotNone(removed)
        self.assertEqual(removed.episode_id, "to_remove")
        self.assertEqual(len(self.narrative.defining_moments), 0)

    def test_remove_nonexistent_episode(self):
        removed = self.narrative.remove_episode("nonexistent")
        self.assertIsNone(removed)

    def test_episodes_sorted_by_timestamp(self):
        self.narrative.add_episode(NarrativeEpisode(episode_id="ep_c", timestamp=300.0))
        self.narrative.add_episode(NarrativeEpisode(episode_id="ep_a", timestamp=100.0))
        self.narrative.add_episode(NarrativeEpisode(episode_id="ep_b", timestamp=200.0))
        
        ids = [ep.episode_id for ep in self.narrative.defining_moments]
        self.assertEqual(ids, ["ep_a", "ep_b", "ep_c"])

    def test_episode_limit_enforcement(self):
        limit = CoreNarrative._episode_limit
        for i in range(limit + 10):
            ep = NarrativeEpisode(
                episode_id=f"ep_{i:03d}",
                timestamp=float(i),
            )
            self.narrative.add_episode(ep)
        
        self.assertLessEqual(len(self.narrative.defining_moments), limit)


class TestRecentEpisodes(unittest.TestCase):
    """测试获取最近叙事片段"""

    def setUp(self):
        self.narrative = CoreNarrative()
        base_time = 1000.0
        
        episodes_data = [
            ("oldest", base_time),
            ("older", base_time + 100.0),
            ("recent", base_time + 200.0),
            ("newer", base_time + 300.0),
            ("newest", base_time + 400.0),
        ]
        
        for ep_id, ts in episodes_data:
            self.narrative.add_episode(
                NarrativeEpisode(episode_id=ep_id, timestamp=ts)
            )

    def test_default_recent_count(self):
        recent = self.narrative.get_recent_episodes()
        self.assertEqual(len(recent), 3)

    def test_recent_order_newest_first(self):
        recent = self.narrative.get_recent_episodes()
        ids = [ep.episode_id for ep in recent]
        
        self.assertEqual(ids[0], "newest")
        self.assertEqual(ids[1], "newer")
        self.assertEqual(ids[2], "recent")

    def test_custom_recent_count(self):
        recent = self.narrative.get_recent_episodes(count=2)
        self.assertEqual(len(recent), 2)

    def test_count_larger_than_available(self):
        recent = self.narrative.get_recent_episodes(count=100)
        self.assertEqual(len(recent), 5)

    def test_empty_narrative_recent_episodes(self):
        empty = CoreNarrative()
        recent = empty.get_recent_episodes()
        self.assertEqual(recent, [])


class TestDefiningMoments(unittest.TestCase):
    """测试决定性时刻筛选"""

    def setUp(self):
        self.narrative = CoreNarrative()
        
        significant_episodes = [
            ("major_battle", 0.9),
            ("first_love", 0.8),
            ("great_loss", 0.75),
        ]
        
        normal_episodes = [
            ("daily_routine", 0.5),
            ("minor_event", 0.3),
        ]
        
        for ep_id, sig in significant_episodes + normal_episodes:
            self.narrative.add_episode(
                NarrativeEpisode(episode_id=ep_id, significance=sig)
            )

    def test_only_defining_moments_returned(self):
        defining = self.narrative.get_defining_moments()
        
        for ep in defining:
            self.assertGreater(ep.significance, 0.7)

    def test_defining_moments_sorted_by_significance(self):
        defining = self.narrative.get_defining_moments()
        
        significances = [ep.significance for ep in defining]
        self.assertEqual(significances, sorted(significances, reverse=True))

    def test_correct_count(self):
        defining = self.narrative.get_defining_moments()
        self.assertEqual(len(defining), 3)

    def test_no_defining_moments(self):
        narrative = CoreNarrative()
        narrative.add_episode(NarrativeEpisode(episode_id="normal", significance=0.4))
        
        defining = narrative.get_defining_moments()
        self.assertEqual(defining, [])


class TestIdentitySummaryGeneration(unittest.TestCase):
    """测试身份摘要生成"""

    def test_empty_narrative_summary(self):
        narrative = CoreNarrative()
        summary = narrative.get_identity_summary()
        self.assertEqual(summary, "")

    def test_origin_story_included(self):
        narrative = CoreNarrative(origin_story="孤儿出身")
        summary = narrative.get_identity_summary()
        self.assertIn("背景：孤儿出身", summary)

    def test_central_conflict_included(self):
        narrative = CoreNarrative(central_conflict="正义vs复仇")
        summary = narrative.get_identity_summary()
        self.assertIn("内心矛盾：正义vs复仇", summary)

    def test_unfulfilled_destiny_included(self):
        narrative = CoreNarrative(unfulfilled_destiny="成为英雄")
        summary = narrative.get_identity_summary()
        self.assertIn("追求：成为英雄", summary)

    def test_fear_of_becoming_included(self):
        narrative = CoreNarrative(fear_of_becoming="变得冷血")
        summary = narrative.get_identity_summary()
        self.assertIn("最深恐惧：变得冷血", summary)

    def test_recent_episodes_included(self):
        narrative = CoreNarrative()
        narrative.add_episode(NarrativeEpisode(
            episode_id="recent_ep",
            title="最近事件",
            description="重要的事情",
            timestamp=time.time(),
        ))
        summary = narrative.get_identity_summary()
        self.assertIn("近期经历", summary)
        self.assertIn("[最近事件]", summary)

    def test_full_summary_format(self):
        narrative = CoreNarrative(
            origin_story="出生于战士家族",
            central_conflict="和平vs战斗",
            unfulfilled_destiny="结束战争",
            fear_of_becoming="失去人性",
        )
        narrative.add_episode(NarrativeEpisode(
            episode_id="key_event",
            title="关键战役",
            description="改变了看法",
            timestamp=time.time(),
            significance=0.85,
        ))
        
        summary = narrative.get_identity_summary()
        
        self.assertIn("背景：", summary)
        self.assertIn("内心矛盾：", summary)
        self.assertIn("追求：", summary)
        self.assertIn("最深恐惧：", summary)
        self.assertIn("近期经历：", summary)

    def test_summary_order_priority(self):
        narrative = CoreNarrative(
            origin_story="A",
            central_conflict="B",
            unfulfilled_destiny="C",
            fear_of_becoming="D",
        )
        summary = narrative.get_identity_summary()
        
        pos_origin = summary.find("背景：")
        pos_conflict = summary.find("内心矛盾：")
        pos_destiny = summary.find("追求：")
        pos_fear = summary.find("最深恐惧：")
        
        self.assertLess(pos_origin, pos_conflict)
        self.assertLess(pos_conflict, pos_destiny)
        self.assertLess(pos_destiny, pos_fear)

    def test_recent_episodes_limit(self):
        narrative = CoreNarrative(origin_story="有背景")
        
        for i in range(6):
            narrative.add_episode(NarrativeEpisode(
                episode_id=f"ep_{i}",
                title=f"事件{i}",
                timestamp=float(1000 + i * 100),
            ))
        
        summary = narrative.get_identity_summary()
        
        recent_section = summary.split("近期经历：")[-1] if "近期经历：" in summary else ""
        if recent_section:
            episodes_in_summary = recent_section.split("；")
            self.assertLessEqual(len(episodes_in_summary), 3)

    def test_max_length_respected(self):
        long_text = "A" * 600
        narrative = CoreNarrative(origin_story=long_text)
        summary = narrative.get_identity_summary()
        
        self.assertLessEqual(len(summary), 503)


class TestNarrativeContextExport(unittest.TestCase):
    """测试结构化导出功能"""

    def test_empty_narrative_export(self):
        narrative = CoreNarrative()
        context = narrative.to_narrative_context()
        
        self.assertIsInstance(context, dict)
        self.assertEqual(context["origin_story"], "")
        self.assertEqual(context["episode_count"], 0)
        self.assertEqual(context["defining_moment_count"], 0)

    def test_populated_narrative_export(self):
        narrative = CoreNarrative(
            origin_story="有背景",
            core_values=["价值1", "价值2"],
            current_chapter=LifeChapter.TRANSFORMATION,
        )
        narrative.add_episode(NarrativeEpisode(
            episode_id="test_ep",
            title="测试",
            significance=0.8,
            timestamp=100.0,
        ))
        
        context = narrative.to_narrative_context()
        
        self.assertEqual(context["origin_story"], "有背景")
        self.assertIn("价值1", context["core_values"])
        self.assertEqual(context["current_chapter"], "TRANSFORMATION")
        self.assertEqual(context["episode_count"], 1)
        self.assertEqual(context["defining_moment_count"], 1)

    def test_recent_episodes_in_export(self):
        narrative = CoreNarrative()
        narrative.add_episode(NarrativeEpisode(
            episode_id="export_test",
            title="导出测试",
            timestamp=time.time(),
        ))
        
        context = narrative.to_narrative_context()
        
        self.assertIn("recent_episodes", context)
        self.assertEqual(len(context["recent_episodes"]), 1)
        self.assertEqual(context["recent_episodes"][0]["id"], "export_test")


class TestNarrativeComplexity(unittest.TestCase):
    """测试叙事复杂度评分"""

    def test_empty_complexity_zero(self):
        narrative = CoreNarrative()
        self.assertAlmostEqual(narrative.narrative_complexity, 0.0)

    def test_fields_contribute_to_complexity(self):
        narrative = CoreNarrative(
            origin_story="背景",
            central_conflict="冲突",
            unfulfilled_destiny="命运",
            fear_of_becoming="恐惧",
        )
        
        complexity = narrative.narrative_complexity
        self.assertGreater(complexity, 0.0)
        self.assertLessEqual(complexity, 1.0)

    def test_episodes_increase_complexity(self):
        narrative_with_eps = CoreNarrative(origin_story="背景")
        narrative_without = CoreNarrative(origin_story="背景")
        
        for i in range(5):
            narrative_with_eps.add_episode(NarrativeEpisode(
                episode_id=f"ep_{i}",
                significance=0.8,
            ))
        
        self.assertGreater(
            narrative_with_eps.narrative_complexity,
            narrative_without.narrative_complexity
        )

    def test_chapter_diversity_increases_complexity(self):
        single_chapter = CoreNarrative(origin_story="背景")
        multi_chapter = CoreNarrative(origin_story="背景")
        
        chapters = list(LifeChapter)
        for i, chapter in enumerate(chapters):
            multi_chapter.add_episode(NarrativeEpisode(
                episode_id=f"ep_{i}",
                chapter=chapter,
                significance=0.7,
            ))
            
            if i == 0:
                single_chapter.add_episode(NarrativeEpisode(
                    episode_id=f"ep_{i}",
                    chapter=chapter,
                    significance=0.7,
                ))
        
        self.assertGreater(
            multi_chapter.narrative_complexity,
            single_chapter.narrative_complexity
        )

    def test_complexity_clamped_to_range(self):
        narrative = CoreNarrative(
            origin_story="A",
            central_conflict="B",
            unfulfilled_destiny="C",
            fear_of_becoming="D",
        )
        
        for _ in range(20):
            narrative.add_episode(NarrativeEpisode(
                episode_id="high_sig",
                significance=0.95,
                chapter=LifeChapter.TRANSFORMATION,
            ))
        
        complexity = narrative.narrative_complexity
        self.assertGreaterEqual(complexity, 0.0)
        self.assertLessEqual(complexity, 1.0)


class TestEdgeCasesAndRobustness(unittest.TestCase):
    """边界条件和鲁棒性测试"""

    def test_unicode_content(self):
        narrative = CoreNarrative(
            origin_story="🏰 出生于城堡",
            central_conflict="⚔️ 和平 vs 战争",
        )

        summary = narrative.get_identity_summary()
        self.assertIn("🏰", summary)

    def test_very_long_descriptions(self):
        long_desc = "内容" * 200
        episode = NarrativeEpisode(
            title="长标题",
            description=long_desc,
        )
        
        prompt = episode.to_narrative_prompt()
        self.assertIn(long_desc[:50], prompt)

    def test_rapid_episode_addition(self):
        narrative = CoreNarrative()
        
        for i in range(50):
            narrative.add_episode(NarrativeEpisode(
                episode_id=f"rapid_{i}",
                timestamp=float(i),
            ))
        
        self.assertEqual(len(narrative.defining_moments), 50)

    def test_remove_all_episodes(self):
        narrative = CoreNarrative(origin_story="有背景")
        
        ids = [f"ep_{i}" for i in range(5)]
        for ep_id in ids:
            narrative.add_episode(NarrativeEpisode(episode_id=ep_id))
        
        for ep_id in ids:
            narrative.remove_episode(ep_id)
        
        self.assertEqual(len(narrative.defining_moments), 0)
        self.assertFalse(narrative.is_empty)  # 还有origin_story

    def test_timestamp_negative_for_ancient_events(self):
        ancient = NarrativeEpisode(
            episode_id="ancient",
            title="远古传说",
            timestamp=-1.0,
        )
        
        self.assertAlmostEqual(ancient.timestamp, -1.0)
        prompt = ancient.to_narrative_prompt()
        self.assertIn("[远古传说]", prompt)


if __name__ == "__main__":
    unittest.main()
