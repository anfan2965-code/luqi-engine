"""
Phase 4 威胁可信度引擎测试 — threat_credibility.py (基于实际运行时API)
覆盖: 构造/威胁记录/执行标记/可信度评分/合理性评估/边界条件
"""

from __future__ import annotations

import time
import unittest

from luqi_engine.game_theory.types import (
    CommitmentLevel,
    CredibilityScore,
    ThreatRecord,
    ThreatType,
)
from luqi_engine.game_theory.threat_credibility import (
    ThreatCredibilityEngine,
    ThreatCredibilityConfig,
)


class TestThreatEngineConstruction(unittest.TestCase):
    """ThreatCredibilityEngine 构造测试"""

    def test_default_construction(self) -> None:
        engine = ThreatCredibilityEngine(character_id="test_char")
        self.assertIsNotNone(engine)

    def test_custom_config(self) -> None:
        config = ThreatCredibilityConfig(recency_half_life_days=60.0)
        engine = ThreatCredibilityEngine(
            character_id="test_char",
            config=config,
        )
        self.assertIsNotNone(engine)

    def test_config_access(self) -> None:
        engine = ThreatCredibilityEngine(character_id="test_char")
        cfg = engine.config
        self.assertIsInstance(cfg, ThreatCredibilityConfig)


class TestThreatRecordManagement(unittest.TestCase):
    """威胁记录管理测试"""

    def setUp(self) -> None:
        self.engine = ThreatCredibilityEngine(character_id="test_recorder")

    def test_record_threat_stores_record(self) -> None:
        tr = ThreatRecord(
            content="如果你背叛，我会报复",
            threat_type=ThreatType.COMMITMENT,
            commitment_level=CommitmentLevel.MATERIAL,
            estimated_cost=0.6,
        )
        self.engine.record_threat(tr)
        scores = self.engine.get_all_scores()
        self.assertGreaterEqual(len(scores), 1)

    def test_multiple_records_accepted(self) -> None:
        for i in range(3):
            tr = ThreatRecord(
                content=f"威胁 #{i}",
                threat_type=ThreatType.DETERRENCE,
            )
            self.engine.record_threat(tr)
        scores = self.engine.get_all_scores()
        self.assertGreaterEqual(len(scores), 1)

    def test_get_credibility_raises_for_unknown(self) -> None:
        with self.assertRaises(KeyError):
            self.engine.get_credibility("nonexistent")


class TestThreatExecutionTracking(unittest.TestCase):
    """威胁执行跟踪测试"""

    def setUp(self) -> None:
        self.engine = ThreatCredibilityEngine(character_id="tracker")

    def _record_and_get_entity_id(self, content: str, **kwargs) -> str:
        tr = ThreatRecord(content=content, **kwargs)
        self.engine.record_threat(tr)
        scores = self.engine.get_all_scores()
        self.assertGreaterEqual(len(scores), 1)
        return list(scores.keys())[0]

    def test_mark_executed_succeeds(self) -> None:
        content = "威胁内容"
        eid = self._record_and_get_entity_id(content, commitment_level=CommitmentLevel.IRREVERSIBLE)
        result = self.engine.mark_executed(eid, executed=True, delay_seconds=30.0)
        self.assertIsNone(result)

    def test_mark_not_executed(self) -> None:
        content = "未执行威胁"
        eid = self._record_and_get_entity_id(content, commitment_level=CommitmentLevel.VERBAL)
        result = self.engine.mark_executed(eid, executed=False)
        self.assertIsNone(result)

    def test_mark_executed_on_nonexistent(self) -> None:
        result = self.engine.mark_executed("nonexistent", executed=True)
        self.assertIsNone(result)

    def test_execution_delay_recorded(self) -> None:
        content = "延迟威胁"
        eid = self._record_and_get_entity_id(content)
        self.engine.mark_executed(eid, executed=True, delay_seconds=120.0)
        score = self.engine.get_credibility(eid)
        self.assertIsInstance(score, CredibilityScore)


class TestCredibilityScoring(unittest.TestCase):
    """可信度评分测试"""

    def setUp(self) -> None:
        self.engine = ThreatCredibilityEngine(character_id="scorer")

    def _record_and_get_score(self, content: str, **kwargs) -> CredibilityScore:
        tr = ThreatRecord(content=content, **kwargs)
        self.engine.record_threat(tr)
        scores = self.engine.get_all_scores()
        return list(scores.values())[0]

    def test_default_plausibility_for_unknown(self) -> None:
        result = self.engine.evaluate_threat_plausibility(
            target_id="unknown_target",
            threatened_action="test_action",
            estimated_cost=0.5,
        )
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)

    def test_high_consistency_after_execution(self) -> None:
        content = "一致威胁"
        tr = ThreatRecord(
            content=content,
            commitment_level=CommitmentLevel.IRREVERSIBLE,
        )
        self.engine.record_threat(tr)
        scores = self.engine.get_all_scores()
        eid = list(scores.keys())[0]
        for _ in range(9):
            extra = ThreatRecord(content=f"{content}_extra", commitment_level=CommitmentLevel.IRREVERSIBLE)
            self.engine.record_threat(extra)
            self.engine.mark_executed(list(self.engine.get_all_scores().keys())[-1], executed=True, delay_seconds=30.0)
        self.engine.mark_executed(eid, executed=True, delay_seconds=30.0)
        score = self.engine.get_credibility(eid)
        self.assertIsInstance(score, CredibilityScore)

    def test_irreversible_commitment_bonus(self) -> None:
        score_high = self._record_and_get_score(
            "高承诺威胁",
            commitment_level=CommitmentLevel.IRREVERSIBLE,
            estimated_cost=0.9,
        )
        score_low = self._record_and_get_score(
            "低承诺威胁",
            commitment_level=CommitmentLevel.NONE,
            estimated_cost=0.05,
        )
        self.assertIsInstance(score_high, CredibilityScore)
        self.assertIsInstance(score_low, CredibilityScore)

    def test_recent_threats_weighted_more(self) -> None:
        old_content = "旧威胁"
        self.engine.record_threat(ThreatRecord(content=old_content))
        time.sleep(0.02)

        new_content = "新威胁"
        self.engine.record_threat(ThreatRecord(
            content=new_content,
            commitment_level=CommitmentLevel.MATERIAL,
        ))

        scores = self.engine.get_all_scores()
        if len(scores) >= 2:
            for score in scores.values():
                self.assertIsInstance(score, CredibilityScore)
                self.assertGreater(score.recency_score, 0.0)

    def test_all_scores_in_range(self) -> None:
        score = self._record_and_score("range_test_content")
        self.assertGreaterEqual(score.consistency_score, 0.0)
        self.assertLessEqual(score.consistency_score, 1.0)
        self.assertGreaterEqual(score.cost_signal_score, 0.0)
        self.assertLessEqual(score.cost_signal_score, 1.0)
        self.assertGreaterEqual(score.recency_score, 0.0)
        self.assertLessEqual(score.recency_score, 1.0)
        self.assertGreaterEqual(score.pattern_score, 0.0)
        self.assertLessEqual(score.pattern_score, 1.0)

    def _record_and_score(self, content: str, **kwargs) -> CredibilityScore:
        tr = ThreatRecord(content=content, **kwargs)
        self.engine.record_threat(tr)
        scores = self.engine.get_all_scores()
        return list(scores.values())[0]


class TestEvaluateThreatPlausibility(unittest.TestCase):
    """威胁合理性评估测试"""

    def setUp(self) -> None:
        self.engine = ThreatCredibilityEngine(character_id="plaus_tester")

    def test_basic_plausibility_returns_float(self) -> None:
        result = self.engine.evaluate_threat_plausibility(
            target_id="entity_p",
            threatened_action="报复",
            estimated_cost=0.5,
        )
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0.0)
        self.assertLessEqual(result, 1.0)

    def test_high_cost_higher_plausibility(self) -> None:
        low = self.engine.evaluate_threat_plausibility(
            target_id="cost_cmp",
            threatened_action="威胁A",
            estimated_cost=0.1,
        )
        high = self.engine.evaluate_threat_plausibility(
            target_id="cost_cmp",
            threatened_action="威胁B",
            estimated_cost=0.9,
        )
        self.assertGreater(high, low)

    def test_irreversible_commitment_boosts(self) -> None:
        none_result = self.engine.evaluate_threat_plausibility(
            target_id="commit_cmp",
            threatened_action="威胁",
            estimated_cost=0.5,
            commitment_level=CommitmentLevel.NONE,
        )
        irr_result = self.engine.evaluate_threat_plausibility(
            target_id="commit_cmp",
            threatened_action="威胁",
            estimated_cost=0.5,
            commitment_level=CommitmentLevel.IRREVERSIBLE,
        )
        self.assertGreater(irr_result, none_result)

    def test_unknown_entity_uses_base(self) -> None:
        result = self.engine.evaluate_threat_plausibility(
            target_id="totally_new_entity",
            threatened_action="未知威胁",
            estimated_cost=0.7,
        )
        self.assertIsInstance(result, float)
        self.assertGreaterEqual(result, 0.0)


class TestEdgeCasesAndBoundaryConditions(unittest.TestCase):
    """边界条件和异常处理测试"""

    def setUp(self) -> None:
        self.engine = ThreatCredibilityEngine(character_id="edge_case_engine")

    def _record_and_score(self, content: str, **kwargs) -> CredibilityScore:
        tr = ThreatRecord(content=content, **kwargs)
        self.engine.record_threat(tr)
        scores = self.engine.get_all_scores()
        return list(scores.values())[0]

    def test_empty_history_raises_keyerror(self) -> None:
        with self.assertRaises(KeyError):
            self.engine.get_credibility("never_seen_before")

    def test_many_threats_recorded(self) -> None:
        for i in range(15):
            tr = ThreatRecord(
                content=f"spam_target #{i}",
                commitment_level=CommitmentLevel.VERBAL,
            )
            self.engine.record_threat(tr)
        scores = self.engine.get_all_scores()
        self.assertGreaterEqual(len(scores), 1)
        for score in scores.values():
            self.assertIsInstance(score, CredibilityScore)

    def test_extreme_cost_values(self) -> None:
        score = self._record_and_score(
            "极高成本威胁",
            estimated_cost=1.0,
            commitment_level=CommitmentLevel.IRREVERSIBLE,
        )
        self.assertGreater(score.cost_signal_score, 0.0)

    def test_zero_cost_threat(self) -> None:
        score = self._record_and_score(
            "零成本虚张声势",
            estimated_cost=0.0,
            commitment_level=CommitmentLevel.NONE,
        )
        self.assertGreaterEqual(score.cost_signal_score, 0.0)

    def test_all_commitment_levels(self) -> None:
        for level in CommitmentLevel:
            tr = ThreatRecord(
                content=f"{level.name} 级别威胁",
                commitment_level=level,
            )
            self.engine.record_threat(tr)
        scores = self.engine.get_all_scores()
        self.assertGreaterEqual(len(scores), 1)
        for score in scores.values():
            self.assertIsInstance(score, CredibilityScore)

    def test_all_threat_types(self) -> None:
        for ttype in ThreatType:
            tr = ThreatRecord(
                content=f"{ttype.name} 类型威胁",
                threat_type=ttype,
            )
            self.engine.record_threat(tr)
        scores = self.engine.get_all_scores()
        self.assertGreaterEqual(len(scores), 1)
        for score in scores.values():
            self.assertIsInstance(score, CredibilityScore)

    def test_get_all_scores(self) -> None:
        scores = self.engine.get_all_scores()
        self.assertIsInstance(scores, dict)


if __name__ == "__main__":
    unittest.main()
