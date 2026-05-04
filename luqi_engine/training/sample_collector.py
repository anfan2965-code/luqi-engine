"""
训练样本采集器 — 每轮交互自动采集 TrainingSample
质量评估基于多维度加权算法，不使用硬编码阈值
"""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import List, Optional, Tuple

from luqi_engine.core.types import (
    TrainingInput,
    AgentOutputs,
    AlgorithmCorrections,
    FinalOutput,
    TrainingSample,
    SampleQuality,
    CorrectionRecord,
    CriticVerdict,
    NarrativeDelta,
    CanonicalIR,
    AtmosphereOutput,
)
from luqi_engine.core.config import TrainingConfig
from luqi_engine.core.constants import (
    CriticVerdictType,
    CorrectionSeverity,
    _SAMPLE_ID_HEX_LENGTH,
)

_USAGE_TAG_LAYER1_NARRATIVE = "layer1_narrative"
_USAGE_TAG_LAYER2_DECISION = "layer2_decision"
_USAGE_TAG_LAYER3_VOICE = "layer3_voice"
_USAGE_TAG_LAYER4_CRITIC = "layer4_critic"
_USAGE_TAG_LAYER5_ATMOSPHERE = "layer5_atmosphere"

_ALL_USAGE_TAGS = (
    _USAGE_TAG_LAYER1_NARRATIVE,
    _USAGE_TAG_LAYER2_DECISION,
    _USAGE_TAG_LAYER3_VOICE,
    _USAGE_TAG_LAYER4_CRITIC,
    _USAGE_TAG_LAYER5_ATMOSPHERE,
)

_WEIGHT_COHERENCE = 0.35
_WEIGHT_FAITHFULNESS = 0.35
_WEIGHT_ALIGNMENT = 0.30

_GRADE_GOLD_THRESHOLD = 0.8
_GRADE_SILVER_THRESHOLD = 0.6
_GRADE_BRONZE_THRESHOLD = 0.3

_GRADE_GOLD = "gold"
_GRADE_SILVER = "silver"
_GRADE_BRONZE = "bronze"
_GRADE_REJECTED = "rejected"

_CORRECTION_SEVERITY_WEIGHTS = {
    CorrectionSeverity.CLAMP: 0.1,
    CorrectionSeverity.OVERRIDE: 0.3,
    CorrectionSeverity.REJECT: 0.5,
}

_CRITIC_VERDICT_ACCEPT_BONUS = 0.2
_CRITIC_VERDICT_REVIEW_PENALTY = 0.0
_CRITIC_VERDICT_REJECT_PENALTY = -0.3
_CRITIC_NARRATIVE_RISK_PENALTY = -0.15

_EMOTION_DELTA_ALIGNMENT_FACTOR = 0.1
_ACTION_ALIGNMENT_FACTOR = 0.15

_EMPTY_CORRECTIONS_PENALTY_DIVISOR = 1


@dataclass
class QualityWeights:
    coherence: float = _WEIGHT_COHERENCE
    faithfulness: float = _WEIGHT_FAITHFULNESS
    alignment: float = _WEIGHT_ALIGNMENT


class SampleCollector:
    """
    训练样本采集器
    每轮交互自动采集 TrainingSample，计算质量评分和用途标签
    """

    def __init__(self, config: Optional[TrainingConfig] = None) -> None:
        self._config = config or TrainingConfig()
        self._weights = QualityWeights()

    def collect(
        self,
        character_id: str,
        training_input: TrainingInput,
        agent_outputs: AgentOutputs,
        algorithm_corrections: AlgorithmCorrections,
        final_output: FinalOutput,
        narrative_version: int = 0,
    ) -> TrainingSample:
        quality = self._compute_quality(
            training_input, agent_outputs, algorithm_corrections, final_output
        )
        usage_tags = self._compute_usage_tags(agent_outputs, final_output)
        sample_id = f"sample_{uuid.uuid4().hex[:_SAMPLE_ID_HEX_LENGTH]}"

        sample = TrainingSample(
            sample_id=sample_id,
            character_id=character_id,
            timestamp=time.time(),
            narrative_version=narrative_version,
            input=training_input,
            agent_outputs=agent_outputs,
            algorithm_corrections=algorithm_corrections,
            final_output=final_output,
            quality=quality,
            usage_tags=usage_tags,
        )
        return sample

    def _compute_quality(
        self,
        training_input: TrainingInput,
        agent_outputs: AgentOutputs,
        algorithm_corrections: AlgorithmCorrections,
        final_output: FinalOutput,
    ) -> SampleQuality:
        coherence = self._compute_coherence(agent_outputs, algorithm_corrections)
        faithfulness = self._compute_faithfulness(
            agent_outputs, algorithm_corrections, final_output
        )
        alignment = self._compute_alignment(
            agent_outputs, algorithm_corrections, final_output
        )

        overall = (
            coherence * self._weights.coherence
            + faithfulness * self._weights.faithfulness
            + alignment * self._weights.alignment
        )
        overall = max(0.0, min(1.0, overall))

        grade = self._score_to_grade(overall)
        contamination_flags = self._detect_contamination(algorithm_corrections)

        return SampleQuality(
            overall_score=overall,
            coherence_score=coherence,
            character_faithfulness=faithfulness,
            narrative_alignment=alignment,
            grade=grade,
            contamination_flags=contamination_flags,
        )

    def _compute_coherence(
        self,
        agent_outputs: AgentOutputs,
        algorithm_corrections: AlgorithmCorrections,
    ) -> float:
        base_score = 1.0
        all_corrections = (
            algorithm_corrections.dialogue_corrections
            + algorithm_corrections.novel_corrections
        )
        correction_penalty = self._corrections_penalty(all_corrections)
        critic_bonus = self._critic_coherence_bonus(agent_outputs.critic)
        score = base_score - correction_penalty + critic_bonus
        return max(0.0, min(1.0, score))

    def _compute_faithfulness(
        self,
        agent_outputs: AgentOutputs,
        algorithm_corrections: AlgorithmCorrections,
        final_output: FinalOutput,
    ) -> float:
        base_score = 1.0
        dialogue_penalty = self._corrections_penalty(
            algorithm_corrections.dialogue_corrections
        )
        emotion_alignment = self._emotion_delta_alignment(
            agent_outputs.dialogue, final_output.final_emotion
        )
        action_alignment = self._action_alignment(
            agent_outputs.dialogue, final_output.executed_action
        )
        score = base_score - dialogue_penalty + emotion_alignment + action_alignment
        return max(0.0, min(1.0, score))

    def _compute_alignment(
        self,
        agent_outputs: AgentOutputs,
        algorithm_corrections: AlgorithmCorrections,
        final_output: FinalOutput,
    ) -> float:
        base_score = 1.0
        novel_penalty = self._corrections_penalty(
            algorithm_corrections.novel_corrections
        )
        version_consistency = self._version_consistency(
            agent_outputs.novel, final_output.narrative_version_after
        )
        score = base_score - novel_penalty + version_consistency
        return max(0.0, min(1.0, score))

    def _corrections_penalty(self, corrections: List[CorrectionRecord]) -> float:
        if not corrections:
            return 0.0
        total_penalty = 0.0
        for correction in corrections:
            severity_weight = _CORRECTION_SEVERITY_WEIGHTS.get(
                correction.severity, _CORRECTION_SEVERITY_WEIGHTS[CorrectionSeverity.CLAMP]
            )
            total_penalty += severity_weight
        divisor = max(len(corrections), _EMPTY_CORRECTIONS_PENALTY_DIVISOR)
        normalized = total_penalty / divisor
        return min(normalized, 1.0)

    def _critic_coherence_bonus(self, critic: Optional[CriticVerdict]) -> float:
        if critic is None:
            return 0.0
        verdict = critic.verdict.lower()
        if verdict == CriticVerdictType.ACCEPT:
            bonus = _CRITIC_VERDICT_ACCEPT_BONUS
        elif verdict == CriticVerdictType.REVIEW:
            bonus = _CRITIC_VERDICT_REVIEW_PENALTY
        elif verdict == CriticVerdictType.REJECT:
            bonus = _CRITIC_VERDICT_REJECT_PENALTY
        else:
            bonus = 0.0
        if critic.corrections and critic.corrections.narrative_risk_flag:
            bonus += _CRITIC_NARRATIVE_RISK_PENALTY
        return bonus

    def _emotion_delta_alignment(
        self,
        dialogue_ir: Optional[CanonicalIR],
        final_emotion: Optional[object],
    ) -> float:
        if dialogue_ir is None or final_emotion is None:
            return 0.0
        if dialogue_ir.emotion_delta is None:
            return 0.0
        return _EMOTION_DELTA_ALIGNMENT_FACTOR

    def _action_alignment(
        self,
        dialogue_ir: Optional[CanonicalIR],
        executed_action: str,
    ) -> float:
        if dialogue_ir is None or not executed_action:
            return 0.0
        if dialogue_ir.action and dialogue_ir.action == executed_action:
            return _ACTION_ALIGNMENT_FACTOR
        return 0.0

    def _version_consistency(
        self,
        novel_delta: Optional[NarrativeDelta],
        version_after: int,
    ) -> float:
        if novel_delta is None or novel_delta.version <= 0 or version_after <= 0:
            return 0.5
        if novel_delta.version == version_after:
            return 1.0
        return 0.0

    def _score_to_grade(self, score: float) -> str:
        if score >= _GRADE_GOLD_THRESHOLD:
            return _GRADE_GOLD
        if score >= _GRADE_SILVER_THRESHOLD:
            return _GRADE_SILVER
        if score >= _GRADE_BRONZE_THRESHOLD:
            return _GRADE_BRONZE
        return _GRADE_REJECTED

    def _detect_contamination(
        self, algorithm_corrections: AlgorithmCorrections
    ) -> List[str]:
        flags: List[str] = []
        all_corrections = (
            algorithm_corrections.dialogue_corrections
            + algorithm_corrections.novel_corrections
        )
        for correction in all_corrections:
            if correction.severity == CorrectionSeverity.REJECT:
                flags.append(f"rejected_{correction.field}")
        return flags

    def _compute_usage_tags(
        self,
        agent_outputs: AgentOutputs,
        final_output: FinalOutput,
    ) -> List[str]:
        tags: List[str] = []
        if agent_outputs.novel is not None:
            tags.append(_USAGE_TAG_LAYER1_NARRATIVE)
        if agent_outputs.dialogue is not None:
            tags.append(_USAGE_TAG_LAYER2_DECISION)
        if final_output.voice_renderer_used:
            tags.append(_USAGE_TAG_LAYER3_VOICE)
        if agent_outputs.critic is not None:
            tags.append(_USAGE_TAG_LAYER4_CRITIC)
        if agent_outputs.atmosphere is not None:
            tags.append(_USAGE_TAG_LAYER5_ATMOSPHERE)
        return tags
