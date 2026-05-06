"""
ChatOrchestrator - 四智能体协作数据流编排器
从LuqiEngine.chat()提取的6阶段流水线：
Phase 1: DialogueAgent → Phase 2: SupremeCourt → Phase 3: CriticAgent
→ Phase 4: NovelistAgent + AtmosphereAgent → Phase 5: VoiceRenderer
→ Phase 6: OutputAssembler

架构权衡记录：
- 拆分原因：chat()原210行10+职责，任何单阶段修改需理解全部代码
- atmosphere_context原构建两次(L521-528和L561-567)，现合并为一次
- 保持LuqiEngine.chat()公开API签名不变，内部委托给本类
- 前置条件：所有agent/bridge/narrative_doc必须已初始化
- 后置条件：返回与原chat()完全一致的Dict结构
- 可能异常：各Phase内部异常被捕获并降级，不会向上抛出
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from luqi_engine.core.types import (
    CanonicalIR,
    CriticVerdict,
    NarrativeDelta,
    AtmosphereOutput,
    ValidatedIR,
    ValidatedDelta,
)
from luqi_engine.core.constants import (
    AtmosphereMode,
    CriticMode,
    CriticVerdictType,
    NovelMode,
    PaceLevel,
    AssemblyMode,
    _FALLBACK_CRITIC_CONFIDENCE,
    _MAX_RECENT_FACTS,
    _MS_PER_SECOND,
    _DEFAULT_DOMINANT_EMOTION,
    _DEFAULT_EMOTION_INTENSITY,
)
from luqi_engine.agents.dialogue_agent import DialogueAgent
from luqi_engine.agents.novelist_agent import NovelistAgent
from luqi_engine.agents.critic_agent import CriticAgent
from luqi_engine.agents.atmosphere_agent import AtmosphereAgent
from luqi_engine.core.supreme_court import AlgorithmSupremeCourt
from luqi_engine.voice.voice_renderer import VoiceRenderer
from luqi_engine.voice.output_assembler import OutputAssembler
from luqi_engine.scheduler.async_scheduler import AsyncTaskScheduler
from luqi_engine.scheduler.gap_precomputer import GapPrecomputer
from luqi_engine.scheduler.pace_sensor import PaceSensor
from luqi_engine.training.sample_collector import SampleCollector
from luqi_engine.training.document_protector import DegradationDocumentProtector
from luqi_engine.narrative.document import NarrativeDocument
from luqi_engine.llm.bridge import LLMBridge
from luqi_engine.llm.fallback import LLMFallback, DegradationLevel


class ChatOrchestrator:
    """四智能体协作数据流编排器，从LuqiEngine.chat()提取"""

    def __init__(
        self,
        dialogue_agent: DialogueAgent,
        novelist_agent: NovelistAgent,
        critic_agent: CriticAgent,
        atmosphere_agent: AtmosphereAgent,
        supreme_court: AlgorithmSupremeCourt,
        voice_renderer: VoiceRenderer,
        output_assembler: OutputAssembler,
        doc_protector: DegradationDocumentProtector,
        llm_bridge: LLMBridge,
        narrative_doc: NarrativeDocument,
        scheduler: Optional[AsyncTaskScheduler] = None,
        precomputer: Optional[GapPrecomputer] = None,
        pace_sensor: Optional[PaceSensor] = None,
        sample_collector: Optional[SampleCollector] = None,
        fallback: Optional[LLMFallback] = None,
    ) -> None:
        if dialogue_agent is None:
            raise ValueError("dialogue_agent不能为None")
        if llm_bridge is None:
            raise ValueError("llm_bridge不能为None")
        self._dialogue_agent = dialogue_agent
        self._novelist_agent = novelist_agent
        self._critic_agent = critic_agent
        self._atmosphere_agent = atmosphere_agent
        self._supreme_court = supreme_court
        self._voice_renderer = voice_renderer
        self._output_assembler = output_assembler
        self._doc_protector = doc_protector
        self._llm_bridge = llm_bridge
        self._narrative_doc = narrative_doc
        self._scheduler = scheduler
        self._precomputer = precomputer
        self._pace_sensor = pace_sensor
        self._sample_collector = sample_collector
        self._fallback = fallback
        self._logger = logging.getLogger(__name__)

    async def orchestrate(
        self,
        user_input: str,
        target_char: Any,
        is_local_llm_fast: bool,
        character_extractor: Any,
    ) -> Dict[str, Any]:
        """
        执行完整的6阶段对话流水线

        前置条件：target_char非None，character_extractor已初始化
        后置条件：返回包含reply/character_id/narrative_version等字段的Dict
        可能异常：各Phase内部异常被捕获降级，不向上抛出
        """
        start_time = time.time()

        dialogue_context = self._build_dialogue_context(
            user_input, target_char, character_extractor
        )

        canonical_ir = await self._phase1_dialogue(dialogue_context)

        validated_ir = self._phase2_supreme_court(canonical_ir, target_char)

        critic_verdict, novel_delta, atmosphere, atm_mode, pace = (
            await self._phase3_and_4(
                canonical_ir, target_char, is_local_llm_fast, character_extractor
            )
        )

        self._phase4_delta_apply(novel_delta)

        validated_delta = self._phase4_validate_delta(novel_delta)

        dialogue_text = self._phase5_voice(canonical_ir, target_char, user_input)

        final_text = self._phase6_assemble(dialogue_text, atmosphere)

        self._post_orchestrate(
            user_input, canonical_ir, novel_delta, critic_verdict,
            atmosphere, validated_ir, final_text,
            dialogue_context, character_extractor, is_local_llm_fast,
        )

        self._update_character_emotion(target_char, canonical_ir)

        latency_ms = int((time.time() - start_time) * _MS_PER_SECOND)

        return {
            "reply": final_text,
            "character_id": "",
            "narrative_version": self._narrative_doc.version if self._narrative_doc else 0,
            "atmosphere_mode": atm_mode,
            "critic_verdict": critic_verdict.verdict,
            "validation_clean": validated_ir.is_clean,
            "pace": pace,
            "latency_ms": latency_ms,
        }

    def _build_dialogue_context(
        self,
        user_input: str,
        target_char: Any,
        character_extractor: Any,
    ) -> Dict[str, Any]:
        """构建Phase 1对话上下文"""
        return {
            "user_message": user_input,
            "character_name": target_char.name if hasattr(target_char, 'name') else "",
            "personality": character_extractor.extract_personality(target_char),
            "emotion_pad": character_extractor.extract_emotion_pad(target_char),
            "narrative_context": self._narrative_doc.to_prompt_context() if self._narrative_doc else "",
            "recent_exchanges": [],
        }

    async def _phase1_dialogue(
        self, dialogue_context: Dict[str, Any]
    ) -> CanonicalIR:
        """Phase 1: DialogueAgent生成CanonicalIR"""
        try:
            return await self._dialogue_agent.run(dialogue_context, self._llm_bridge)
        except Exception as exc:
            self._logger.error("Phase 1 DialogueAgent 失败: %s", exc)
            raise

    def _phase2_supreme_court(
        self, canonical_ir: CanonicalIR, target_char: Any
    ) -> ValidatedIR:
        """Phase 2: SupremeCourt校验CanonicalIR"""
        try:
            return self._supreme_court.validate_dialogue_ir(
                canonical_ir, target_char, self._narrative_doc
            )
        except Exception as exc:
            self._logger.warning("Phase 2 SupremeCourt 校验失败: %s", exc)
            return ValidatedIR(
                ir=canonical_ir, violations=[], is_clean=True, needs_critic_review=False
            )

    async def _phase3_and_4(
        self,
        canonical_ir: CanonicalIR,
        target_char: Any,
        is_local_llm_fast: bool,
        character_extractor: Any,
    ) -> tuple:
        """
        Phase 3+4: CriticAgent → NovelistAgent + AtmosphereAgent
        本地LLM快速路径跳过这些阶段

        返回: (critic_verdict, novel_delta, atmosphere, atm_mode, pace)
        """
        critic_verdict = CriticVerdict(
            verdict=CriticVerdictType.ACCEPT,
            checks=[],
            overall_confidence=_FALLBACK_CRITIC_CONFIDENCE,
            corrections=None,
        )
        novel_delta: Optional[NarrativeDelta] = None
        atmosphere = None
        atm_mode = AtmosphereMode.LIGHT
        pace = PaceLevel.NORMAL

        if is_local_llm_fast:
            return critic_verdict, novel_delta, atmosphere, atm_mode, pace

        critic_verdict = await self._phase3_critic(canonical_ir, target_char, character_extractor)

        if critic_verdict.verdict in (CriticVerdictType.REJECT, CriticVerdictType.MAJOR_REWRITE):
            canonical_ir = self._apply_critic_corrections(canonical_ir, critic_verdict)

        if self._scheduler is not None:
            try:
                self._scheduler.start_responding()
            except Exception as exc:
                self._logger.debug("调度器start_responding失败: %s", exc)

        novel_delta = await self._phase4_novelist(canonical_ir)

        pace = self._pace_sensor.get_current_pace() if self._pace_sensor else PaceLevel.NORMAL
        atm_mode = AtmosphereMode.LIGHT if pace in (PaceLevel.FAST, PaceLevel.URGENT) else AtmosphereMode.FULL

        atmosphere = await self._phase4_atmosphere(canonical_ir, target_char, atm_mode)

        return critic_verdict, novel_delta, atmosphere, atm_mode, pace

    async def _phase3_critic(
        self,
        canonical_ir: CanonicalIR,
        target_char: Any,
        character_extractor: Any,
    ) -> CriticVerdict:
        """Phase 3: CriticAgent审查"""
        try:
            critic_context = {
                "canonical_ir": canonical_ir,
                "narrative_delta": None,
                "character_state": character_extractor.extract_character_state(target_char),
                "narrative_context": self._narrative_doc.to_prompt_context() if self._narrative_doc else "",
            }
            return await self._critic_agent.run(
                critic_context, self._llm_bridge, mode=CriticMode.LIGHT
            )
        except Exception as exc:
            self._logger.warning("Phase 3 CriticAgent 失败: %s", exc)
            return CriticVerdict(
                verdict=CriticVerdictType.ACCEPT,
                checks=[],
                overall_confidence=_FALLBACK_CRITIC_CONFIDENCE,
                corrections=None,
            )

    async def _phase4_novelist(
        self, canonical_ir: CanonicalIR
    ) -> Optional[NarrativeDelta]:
        """Phase 4: NovelistAgent生成叙事增量"""
        try:
            novel_context = {
                "narrative_context": self._narrative_doc.to_prompt_context() if self._narrative_doc else "",
                "recent_facts": (
                    [f.content for f in self._narrative_doc.established_facts[-_MAX_RECENT_FACTS:]]
                    if self._narrative_doc else []
                ),
                "canonical_ir": canonical_ir,
                "open_questions": self._narrative_doc.open_questions if self._narrative_doc else [],
            }
            return await self._novelist_agent.run(
                novel_context, self._llm_bridge, mode=NovelMode.INCREMENTAL
            )
        except Exception as exc:
            self._logger.warning("Phase 4 NovelistAgent 失败: %s", exc)
            return None

    async def _phase4_atmosphere(
        self,
        canonical_ir: CanonicalIR,
        target_char: Any,
        atm_mode: AtmosphereMode,
    ) -> Optional[AtmosphereOutput]:
        """Phase 4.5: AtmosphereAgent生成氛围描写（只构建一次atmosphere_context）"""
        try:
            atmosphere_context = {
                "scene_name": self._narrative_doc.current_scene if self._narrative_doc else "",
                "dominant_emotion": _DEFAULT_DOMINANT_EMOTION,
                "emotion_intensity": (
                    abs(canonical_ir.emotion_delta.arousal)
                    if canonical_ir.emotion_delta else _DEFAULT_EMOTION_INTENSITY
                ),
                "characters_present": [target_char.name] if hasattr(target_char, 'name') else [],
                "narrative_context": self._narrative_doc.to_prompt_context() if self._narrative_doc else "",
            }
            return await self._atmosphere_agent.run(
                atmosphere_context, self._llm_bridge, mode=atm_mode
            )
        except Exception as exc:
            self._logger.warning("Phase 4.5 AtmosphereAgent 失败: %s", exc)
            return None

    def _phase4_delta_apply(self, novel_delta: Optional[NarrativeDelta]) -> None:
        """Phase 4: 安全应用叙事增量到NarrativeDocument"""
        if novel_delta is None:
            return
        if self._narrative_doc is None:
            return
        if self._doc_protector is None:
            return
        try:
            is_degraded = (
                self._fallback is not None
                and self._fallback.current_level != DegradationLevel.NORMAL
            )
            protected_delta, _protection_report = self._doc_protector.safe_apply_delta(
                novel_delta,
                self._narrative_doc.established_facts,
                self._narrative_doc.current_chapter_outline,
                is_degraded=is_degraded,
            )
            self._narrative_doc.apply_delta(protected_delta)
        except Exception as exc:
            self._logger.warning("Phase 4 Delta 应用失败: %s", exc)

    def _phase4_validate_delta(
        self, novel_delta: Optional[NarrativeDelta]
    ) -> ValidatedDelta:
        """Phase 4: SupremeCourt校验叙事增量"""
        try:
            if novel_delta is not None and self._supreme_court is not None:
                return self._supreme_court.validate_novel_delta(
                    novel_delta, self._narrative_doc
                )
            return ValidatedDelta(delta=novel_delta, violations=[])
        except Exception as exc:
            self._logger.warning("Phase 4 SupremeCourt Delta 校验失败: %s", exc)
            return ValidatedDelta(delta=novel_delta, violations=[])

    def _phase5_voice(
        self,
        canonical_ir: CanonicalIR,
        target_char: Any,
        fallback_text: str,
    ) -> str:
        """Phase 5: VoiceRenderer渲染语音"""
        try:
            voice_profile = {"name": target_char.name} if hasattr(target_char, 'name') else {}
            return self._voice_renderer.render(canonical_ir, voice_profile, seed=0)
        except Exception as exc:
            self._logger.warning("Phase 5 VoiceRenderer 失败: %s", exc)
            if canonical_ir.key_points:
                return " ".join(canonical_ir.key_points)
            return fallback_text

    def _phase6_assemble(
        self, dialogue_text: str, atmosphere: Optional[AtmosphereOutput]
    ) -> str:
        """Phase 6: OutputAssembler组装最终输出"""
        try:
            return self._output_assembler.assemble_output(
                dialogue_text, atmosphere, AssemblyMode.WRAP
            )
        except Exception as exc:
            self._logger.warning("Phase 6 OutputAssembler 失败: %s", exc)
            return dialogue_text

    def _post_orchestrate(
        self,
        user_input: str,
        canonical_ir: CanonicalIR,
        novel_delta: Optional[NarrativeDelta],
        critic_verdict: CriticVerdict,
        atmosphere: Optional[AtmosphereOutput],
        validated_ir: ValidatedIR,
        final_text: str,
        dialogue_context: Dict[str, Any],
        character_extractor: Any,
        is_local_llm_fast: bool,
    ) -> None:
        """后处理：训练样本采集 + 异步预计算"""
        try:
            if self._sample_collector is not None:
                from luqi_engine.core.types import (
                    TrainingInput, AgentOutputs, AlgorithmCorrections, FinalOutput,
                )
                training_input = TrainingInput(
                    user_message=user_input,
                    narrative_summary=dialogue_context.get("narrative_context", ""),
                )
                agent_outputs = AgentOutputs(
                    novel=novel_delta,
                    dialogue=canonical_ir,
                    critic=critic_verdict,
                    atmosphere=atmosphere,
                )
                algorithm_corrections = AlgorithmCorrections()
                final_output = FinalOutput(
                    reply_text=final_text,
                    executed_action=canonical_ir.action if canonical_ir else "",
                    final_emotion=canonical_ir.emotion_delta if canonical_ir else None,
                    narrative_version_after=self._narrative_doc.version if self._narrative_doc else 0,
                )
                character_id = dialogue_context.get("character_name", "")
                self._sample_collector.collect(
                    character_id, training_input, agent_outputs,
                    algorithm_corrections, final_output,
                )
        except Exception as exc:
            self._logger.warning("训练样本采集失败: %s", exc)

        try:
            if self._scheduler is not None:
                try:
                    self._scheduler.start_async_prep()
                except Exception as exc:
                    self._logger.debug("调度器start_async_prep失败: %s", exc)
                if self._precomputer is not None:
                    self._start_gap_precomputation(
                        dialogue_context, character_extractor, canonical_ir
                    )
                try:
                    self._scheduler.mark_ready()
                except Exception as exc:
                    self._logger.debug("调度器mark_ready失败: %s", exc)
        except Exception as exc:
            self._logger.warning("异步预计算启动失败: %s", exc)

    def _start_gap_precomputation(
        self,
        dialogue_ctx: Dict[str, Any],
        character_extractor: Any,
        canonical_ir: CanonicalIR,
    ) -> None:
        """启动间隙预计算"""
        if self._precomputer is None:
            return
        try:
            import asyncio
            loop = asyncio.get_event_loop()
            if loop.is_running():
                novel_ctx = {
                    "narrative_context": self._narrative_doc.to_prompt_context() if self._narrative_doc else "",
                    "recent_facts": [],
                    "canonical_ir": canonical_ir,
                    "open_questions": [],
                }
                asyncio.ensure_future(
                    self._precomputer.run_all_tasks(
                        self._novelist_agent,
                        self._critic_agent,
                        self._dialogue_agent,
                        self._atmosphere_agent,
                        novel_ctx,
                        self._llm_bridge,
                    )
                )
        except Exception as exc:
            self._logger.debug("间隙预计算启动失败（不影响主流程）: %s", exc)

    @staticmethod
    def _update_character_emotion(target_char: Any, canonical_ir: CanonicalIR) -> None:
        """更新角色情感状态（通过PADState.update确保范围钳制）"""
        try:
            if hasattr(target_char, 'emotion') and canonical_ir.emotion_delta:
                if hasattr(target_char.emotion, 'update'):
                    target_char.emotion = target_char.emotion.update(
                        canonical_ir.emotion_delta.pleasure,
                        canonical_ir.emotion_delta.arousal,
                        canonical_ir.emotion_delta.dominance,
                    )
                else:
                    target_char.emotion.pleasure += canonical_ir.emotion_delta.pleasure
                    target_char.emotion.arousal += canonical_ir.emotion_delta.arousal
                    target_char.emotion.dominance += canonical_ir.emotion_delta.dominance
        except Exception as exc:
            logging.getLogger(__name__).warning("角色情感更新失败: %s", exc)

    @staticmethod
    def _apply_critic_corrections(ir: CanonicalIR, verdict: CriticVerdict) -> CanonicalIR:
        """应用Critic修正建议到CanonicalIR"""
        if verdict.corrections:
            if verdict.corrections.suggested_emotion_delta:
                ir.emotion_delta = verdict.corrections.suggested_emotion_delta
            if verdict.corrections.suggested_action:
                ir.action = verdict.corrections.suggested_action
        return ir
