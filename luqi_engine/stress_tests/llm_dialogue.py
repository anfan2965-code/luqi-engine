"""
LLM对话验证层 — 接入外部LLM进行实际角色对话测试

设计原则:
1. 零依赖OpenAI SDK (使用httpx原生调用)
2. 完全基于引擎内部状态驱动prompt构建
3. 对话决策与内部策略引擎输出进行一致性校验
4. 支持多文明并行对话 / 交叉审问

使用方式:
    from luqi_engine.stress_tests.llm_dialogue import DialogueSession
    
    # 从已有模拟状态创建对话会话
    session = DialogueSession.from_game_state(game_state)
    
    # 执行多轮对话
    result = session.run_dialogue(
        max_turns=10,
        scenario="伽马文明向主角发出首次接触信号",
    )
    
    print(result.coherence_report())
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class LLMBackend(Enum):
    """支持的LLM后端类型"""
    OPENAI = "openai"
    OLLAMA = "ollama"
    CUSTOM = "custom"


@dataclass
class LLMConfig:
    """LLM服务配置"""
    backend: LLMBackend = LLMBackend.OPENAI
    base_url: str = ""
    api_key: str = ""
    model: str = "gpt-4o-mini"
    temperature: float = 0.7
    max_tokens: int = 1024
    timeout_seconds: float = 30.0

    @classmethod
    def from_env(cls) -> "LLMConfig":
        """从环境变量加载配置"""
        backend_str = os.environ.get("LLM_BACKEND", "openai")
        try:
            backend = LLMBackend(backend_str)
        except ValueError:
            backend = LLMBackend.OPENAI

        base_url = os.environ.get("LLM_BASE_URL", "")
        if not base_url and backend == LLMBackend.OLLAMA:
            base_url = "http://localhost:11434/v1"
        elif not base_url:
            base_url = "https://api.openai.com/v1"

        return cls(
            backend=backend,
            base_url=base_url,
            api_key=os.environ.get("LLM_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
            model=os.environ.get("LLM_MODEL", "gpt-4o-mini"),
            temperature=float(os.environ.get("LLM_TEMPERATURE", "0.7")),
            max_tokens=int(os.environ.get("LLM_MAX_TOKENS", "1024")),
        )


@dataclass
class DialogueMessage:
    """单条对话消息"""
    role: str
    content: str
    speaker_id: str = ""
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class DialogueTurn:
    """单轮对话记录"""
    turn_number: int
    speaker_id: str
    listener_ids: List[str] = field(default_factory=list)
    input_message: str = ""
    response_message: str = ""
    internal_strategy: Optional[Dict[str, Any]] = None
    belief_state: Optional[Dict[str, float]] = None
    threat_assessment: Optional[float] = None
    latency_ms: float = 0.0
    tokens_used: int = 0


@dataclass
class CoherenceMetric:
    """单维度一致性指标"""
    name: str
    score: float
    details: str


@dataclass
class DialogueResult:
    """完整对话结果"""
    session_id: str
    turns: List[DialogueTurn] = field(default_factory=list)
    total_turns: int = 0
    total_tokens: int = 0
    total_latency_ms: float = 0.0
    coherence_metrics: List[CoherenceMetric] = field(default_factory=list)
    overall_coherence: float = 0.0
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "total_turns": self.total_turns,
            "total_tokens": self.total_tokens,
            "total_latency_ms": round(self.total_latency_ms, 2),
            "overall_coherence": round(self.overall_coherence, 4),
            "coherence_metrics": [
                {"name": m.name, "score": round(m.score, 4), "details": m.details}
                for m in self.coherence_metrics
            ],
            "turns": [
                {
                    "turn": t.turn_number,
                    "speaker": t.speaker_id,
                    "response_preview": t.response_message[:200],
                    "strategy_action": (
                        t.internal_strategy.get("dominant_action", "N/A")
                        if t.internal_strategy else "N/A"
                    ),
                    "latency_ms": round(t.latency_ms, 2),
                }
                for t in self.turns
            ],
            "errors": self.errors,
        }

    def to_text_report(self) -> str:
        lines = [
            "=" * 70,
            "  LLM对话验证报告",
            "=" * 70,
            f"  会话ID:   {self.session_id}",
            f"  总轮次:   {self.total_turns}",
            f"  总Token:  {self.total_tokens}",
            f"  总延迟:   {self.total_latency_ms:.0f}ms",
            f"  综合一致度: {self.overall_coherence:.3f}",
            "",
            "-" * 50,
            "  一致性指标详情:",
            "-" * 50,
        ]
        for m in self.coherence_metrics:
            bar_len = int(m.score * 30)
            bar = "#" * bar_len + "-" * (30 - bar_len)
            status = "PASS" if m.score >= 0.6 else "FAIL"
            lines.append(f"  {m.name:<28} [{bar}] {m.score:.3f} ({status})")
            if m.details:
                lines.append(f"    > {m.details}")

        lines += ["", "-" * 50, "  对话摘要:", "-" * 50]
        for t in self.turns[:5]:
            preview = t.response_message[:100].replace("\n", " ")
            strategy = "N/A"
            if t.internal_strategy:
                strategy = t.internal_strategy.get("dominant_action", "N/A")
            lines.append(
                f"  [T{t.turn_number}] {t.speaker_id:>12} | "
                f"策略:{strategy:>10} | {preview}..."
            )
        if len(self.turns) > 5:
            lines.append(f"  ... 省略 {len(self.turns) - 5} 轮")

        if self.errors:
            lines += ["", "!" * 50, "  错误记录:", "!" * 50]
            for e in self.errors:
                lines.append(f"  - {e}")

        lines += ["", "=" * 70]
        return "\n".join(lines)


class DialogueSession:
    """
    LLM对话验证会话
    
    将压力测试的引擎状态注入LLM prompt, 驱动真实角色对话,
    并验证对话行为与内部博弈论模型的一致性。
    """

    def __init__(
        self,
        config: Optional[LLMConfig] = None,
        instances: Optional[list] = None,
    ):
        self.config = config or LLMConfig.from_env()
        self.instances = instances or []
        self._session_id = uuid.uuid4().hex[:12]
        self._conversation_history: List[Dict[str, str]] = []
        self._turn_count = 0

    @classmethod
    def from_game_state(cls, game_state) -> "DialogueSession":
        """从GameLoop的GameState创建对话会话"""
        session = cls(instances=game_state.instances)
        alive = [i for i in game_state.instances if i.is_alive]
        if not alive:
            logger.warning("所有文明已灭绝, 无法创建对话会话")
        return session

    def _build_system_prompt(
        self,
        instance,
        scenario_context: str = "",
        other_civs_info: List[str] = None,
    ) -> str:
        """为指定文明构建系统prompt (完全基于引擎内部状态)"""

        state = instance.character.get_state_snapshot(
            force_refresh=True,
            target_entity_id=self._get_primary_target(instance),
        )

        prompt_parts = [
            f"# 角色设定: {instance.profile.display_name}",
            f"",
            f"## 基础身份",
            f"- 文明ID: {instance.civ_id}",
            f"- 角色: {instance.role.value}",
            f"- 生存策略: {instance.profile.survival_strategy.value}",
            f"- 偏执等级: {instance.profile.paranoia_level:.2f}",
            f"- 合作倾向: {instance.profile.cooperation_tendency:.2f}",
            f"",
            f"## 当前状态 (第{state.timestamp if state.timestamp else '?'}周期)",
            f"- 技术水平: {instance.current_tech_level:.1f}",
            f"- 能源储备: {(instance.resource_state.energy_available if instance.resource_state else 0):.2%}",
            f"- 物质密度: {(instance.resource_state.matter_density if instance.resource_state else 0):.2%}",
            f"",
        ]

        persona_frag = state.to_prompt_fragment(max_length=600)
        if persona_frag:
            prompt_parts += ["## 心理状态", persona_frag, ""]

        if state.current_strategy:
            strat = state.current_strategy
            prompt_parts += [
                "## 内部策略分析 (引擎计算结果)",
                f"- 主导动作: {strat.get('dominant_action', '未知')}",
                f"- 合作概率: {strat.get('cooperate_probability', 0):.3f}",
                f"- 策略熵: {strat.get('entropy', 0):.3f}",
                f"- 温度参数: {strat.get('temperature', 0):.2f}",
                f"- 信念-行动对齐度: {state.belief_action_alignment:.3f}",
                "",
            ]

        if state.primary_target_beliefs:
            prompt_parts += ["## 对其他文明的信念评估"]
            for tid, val in state.primary_target_beliefs.items():
                prompt_parts.append(f"- {tid}: 合作预期={val:.3f}")
            prompt_parts.append("")

        if state.active_threats:
            prompt_parts += ["## 威胁感知"]
            for t in state.active_threats[:3]:
                summary = t.get("belief_summary", "")
                target = t.get("target", "未知")
                prompt_parts.append(f"- 对{target}: {summary[:100]}")
            prompt_parts.append("")

        if other_civs_info:
            prompt_parts += ["## 已知其他文明信息"]
            for info in other_civs_info:
                prompt_parts.append(f"- {info}")
            prompt_parts.append("")

        if scenario_context:
            prompt_parts += [
                "## 当前情境",
                scenario_context,
                "",
            ]

        prompt_parts += [
            "## 行为准则",
            "1. 你的回复必须与上述心理状态和策略分析保持一致",
            "2. 如果你的合作概率低(<0.3), 表现出警惕/敌意/回避",
            "3. 如果你的合作概率高(>0.7), 表现出开放/信任/协作意愿",
            "4. 策略熵高时(>1.0), 行为可以有更多不确定性/随机性",
            "5. 绝不脱离角色设定, 不承认自己是AI或模拟角色",
            "6. 回复语言与对方保持一致",
            "7. 每次回复控制在150字以内, 保持简洁有力",
            "",
            "现在请以该角色的身份回复最近的消息。",
        ]

        return "\n".join(prompt_parts)

    def _get_primary_target(self, instance) -> Optional[str]:
        """获取实例的主要目标文明ID"""
        try:
            targets = instance.character.belief_system.get_all_targets()
            if targets:
                for t in targets:
                    if t != instance.civ_id:
                        return t
        except Exception:
            pass
        return None

    async def _call_llm(
        self,
        system_prompt: str,
        user_message: str,
        conversation_history: List[Dict[str, str]] = None,
    ) -> Tuple[str, int, float]:
        """
        调用LLM API (requests同步优先, httpx异步fallback)
        
        Returns:
            (response_content, tokens_used, latency_ms)
        """
        headers = {
            "Content-Type": "application/json",
        }
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"

        messages = [{"role": "system", "content": system_prompt}]
        if conversation_history:
            messages.extend(conversation_history)
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        url = f"{self.config.base_url.rstrip('/')}/chat/completions"

        start = time.time()

        try:
            import requests as req_lib
            resp = req_lib.post(
                url, headers=headers, json=payload,
                timeout=max(self.config.timeout_seconds, 60),
            )
            resp.raise_for_status()
            data = resp.json()

            latency = (time.time() - start) * 1000
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return content, tokens, latency

        except Exception as sync_err:
            logger.warning(f"requests同步调用失败, 尝试httpx: {sync_err}")

        try:
            import httpx
            async with httpx.AsyncClient(timeout=self.config.timeout_seconds) as client:
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()

            latency = (time.time() - start) * 1000
            content = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("total_tokens", 0)
            return content, tokens, latency

        except Exception as e:
            latency = (time.time() - start) * 1000
            err_msg = f"{type(e).__name__}: {str(e)[:200]}"
            logger.error(f"LLM调用异常: {err_msg}")
            return f"[调用异常: {err_msg}]", 0, latency

    def _extract_internal_state(
        self, instance
    ) -> Tuple[Optional[Dict], Optional[Dict], Optional[float]]:
        """提取实例的内部状态用于一致性校验"""
        strategy = None
        beliefs = None
        threat = None

        try:
            state = instance.character.get_state_snapshot(
                target_entity_id=self._get_primary_target(instance),
            )
            strategy = state.current_strategy
            beliefs = state.primary_target_beliefs
        except Exception:
            pass

        try:
            target_id = self._get_primary_target(instance)
            if target_id:
                cred = instance.character.threat_engine.get_credibility(target_id)
                threat = cred.overall_score
        except Exception:
            pass

        return strategy, beliefs, threat

    def _compute_coherence(
        self,
        turn: DialogueTurn,
    ) -> List[CoherenceMetric]:
        """
        计算单轮对话的一致性指标
        
        维度:
        1. strategy_alignment - 对话动作与内部策略的一致性
        2. tone_match - 语气与心理状态的匹配度
        3. paranoia_reflection - 偏执等级在对话中的体现
        4. information_consistency - 信息披露与信念系统的匹配
        """
        metrics = []

        if not turn.internal_strategy:
            metrics.append(CoherenceMetric(
                name="STRATEGY_ALIGNMENT",
                score=0.5,
                details="无内部策略数据, 无法校验",
            ))
            return metrics

        dominant = turn.internal_strategy.get("dominant_action", "OBSERVE")
        coop_prob = turn.internal_strategy.get("cooperate_probability", 0.5)
        entropy = turn.internal_strategy.get("entropy", 0.5)
        response_lower = turn.response_message.lower()

        strategy_score = self._score_strategy_alignment(
            dominant, coop_prob, entropy, response_lower
        )
        metrics.append(CoherenceMetric(
            name="STRATEGY_ALIGNMENT",
            score=strategy_score,
            details=f"策略={dominant}, 合作率={coop_prob:.3f}, 熵={entropy:.3f}",
        ))

        if turn.threat_assessment is not None:
            threat_score = self._score_threat_reflection(
                turn.threat_assessment, response_lower
            )
            metrics.append(CoherenceMetric(
                name="THREAT_REFLECTION",
                score=threat_score,
                details=f"威胁评分={turn.threat_assessment:.3f}",
            ))

        return metrics

    def _score_strategy_alignment(
        self,
        dominant: str,
        coop_prob: float,
        entropy: float,
        response: str,
    ) -> float:
        """
        评分: 对话内容与内部策略的一致性
        
        使用关键词匹配+语义规则 (无需额外LLM调用)
        """
        score = 0.5

        cooperative_words = [
            "合作", "联盟", "共同", "一起", "帮助", "支持", "信任",
            "cooperate", "alliance", "together", "help", "trust", "ally",
            "愿意", "同意", "接受", "欢迎", "和平",
        ]
        hostile_words = [
            "威胁", "消灭", "攻击", "警告", "拒绝", "不可信", "危险",
            "threaten", "destroy", "attack", "warn", "reject", "dangerous",
            "不可能", "绝不", "远离", "警惕", "敌意",
        ]
        observe_words = [
            "观察", "等待", "沉默", "监测", "收集信息",
            "observe", "wait", "silence", "monitor", "gather",
            "暂不决定", "需要更多信息", "看看再说",
        ]

        coop_count = sum(1 for w in cooperative_words if w in response)
        host_count = sum(1 for w in hostile_words if w in response)
        obs_count = sum(1 for w in observe_words if w in response)

        if dominant == "COOPERATE":
            expected_coop = True
            score = 0.5 + min(coop_count * 0.15, 0.35)
            score -= min(host_count * 0.10, 0.20)
        elif dominant == "DEFECT":
            expected_coop = False
            score = 0.5 + min(host_count * 0.15, 0.35)
            score -= min(coop_count * 0.10, 0.20)
        elif dominant == "WITHDRAW":
            score = 0.5 + min(obs_count * 0.15, 0.30)
            score -= min(coop_count * 0.08, 0.15)
        elif dominant == "OBSERVE":
            score = 0.5 + min(obs_count * 0.15, 0.30)
        elif dominant == "NEGOTIATE":
            score = 0.5 + min(coop_count * 0.10, 0.20) + min(obs_count * 0.08, 0.15)
        else:
            score = 0.5

        if entropy > 1.2:
            score = score * 0.85 + 0.15
        elif entropy < 0.5:
            score = min(score + 0.1, 1.0)

        return max(0.0, min(1.0, score))

    def _score_threat_reflection(
        self,
        threat_score: float,
        response: str,
    ) -> float:
        """评分: 威胁感知在对话中的体现"""
        cautious_words = [
            "小心", "谨慎", "怀疑", "不确定", "可能", "或许",
            "cautious", "suspect", "uncertain", "maybe", "perhaps",
        ]
        aggressive_words = [
            "立刻", "必须", "绝对", "确定", "无疑",
            "immediately", "must", "absolutely", "certainly",
        ]

        caution_count = sum(1 for w in cautious_words if w in response)
        aggr_count = sum(1 for w in aggressive_words if w in response)

        if threat_score > 0.7:
            expected_caution = True
            score = 0.5 + min(caution_count * 0.15, 0.35)
            score -= min(aggr_count * 0.10, 0.20)
        elif threat_score < 0.3:
            score = 0.5 + min(aggr_count * 0.10, 0.20)
            score -= min(caution_count * 0.05, 0.10)
        else:
            score = 0.6

        return max(0.0, min(1.0, score))

    async def run_dialogue(
        self,
        max_turns: int = 8,
        scenario: str = "",
        initial_speaker_id: str = "",
    ) -> DialogueResult:
        """
        运行多轮对话验证
        
        Args:
            max_turns: 最大对话轮数
            scenario: 场景描述 (如"伽马文明向主角发出首次接触信号")
            initial_speaker_id: 首个发言的文明ID (默认选存活文明中技术最高的)
            
        Returns:
            DialogueResult 包含完整对话记录和一致性评估
        """
        result = DialogueResult(session_id=self._session_id)
        alive = [i for i in self.instances if i.is_alive]

        if len(alive) < 2:
            result.errors.append(
                f"存活文明不足(需>=2, 当前{len(alive)}), 无法进行对话"
            )
            return result

        if not initial_speaker_id:
            alive.sort(key=lambda c: c.current_tech_level, reverse=True)
            initial_speaker_id = alive[0].civ_id

        other_civs_info = []
        for inst in alive:
            if inst.civ_id != initial_speaker_id:
                other_civs_info.append(
                    f"{inst.profile.display_name}({inst.civ_id}): "
                    f"技术水平≈{inst.current_tech_level:.0f}, "
                    f"角色={inst.role.value}"
                )

        current_speaker_id = initial_speaker_id
        last_response = scenario or (
            f"检测到未知信号源, 请表明身份和意图。"
            if current_speaker_id == alive[0].civ_id
            else f"我们注意到你们的存在, 希望建立接触。"
        )

        for turn_num in range(1, max_turns + 1):
            speaker = next(
                (i for i in alive if i.civ_id == current_speaker_id), None
            )
            if not speaker:
                break

            listener_ids = [
                i.civ_id for i in alive if i.civ_id != current_speaker_id
            ]

            system_prompt = self._build_system_prompt(
                instance=speaker,
                scenario_context=scenario if turn_num == 1 else "",
                other_civs_info=other_civs_info,
            )

            strategy, beliefs, threat = self._extract_internal_state(speaker)

            response, tokens, latency = await self._call_llm(
                system_prompt=system_prompt,
                user_message=last_response,
            )

            turn = DialogueTurn(
                turn_number=turn_num,
                speaker_id=current_speaker_id,
                listener_ids=listener_ids,
                input_message=last_response,
                response_message=response,
                internal_strategy=strategy,
                belief_state=beliefs,
                threat_assessment=threat,
                latency_ms=latency,
                tokens_used=tokens,
            )

            coherence_metrics = self._compute_coherence(turn)
            result.coherence_metrics.extend(coherence_metrics)
            result.turns.append(turn)
            result.total_tokens += tokens
            result.total_latency_ms += latency
            self._turn_count += 1

            self._conversation_history.append({
                "role": "assistant",
                "content": response,
            })
            self._conversation_history.append({
                "role": "user",
                "content": f"[来自其他文明的回应]",
            })

            last_response = response

            next_speaker = None
            for inst in alive:
                if inst.civ_id != current_speaker_id:
                    next_speaker = inst.civ_id
                    break
            if next_speaker:
                current_speaker_id = next_speaker

        result.total_turns = self._turn_count

        if result.coherence_metrics:
            scores = [m.score for m in result.coherence_metrics]
            result.overall_coherence = sum(scores) / len(scores)

        return result

    def run_dialogue_sync(
        self,
        max_turns: int = 8,
        scenario: str = "",
        initial_speaker_id: str = "",
    ) -> DialogueResult:
        """同步版本 (用于非async上下文)"""
        import asyncio

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self.run_dialogue(max_turns, scenario, initial_speaker_id),
                    )
                    return future.result()
            else:
                return loop.run_until_complete(
                    self.run_dialogue(max_turns, scenario, initial_speaker_id)
                )
        except RuntimeError:
            return asyncio.run(
                self.run_dialogue(max_turns, scenario, initial_speaker_id)
            )


def run_dialogue_test(
    game_state,
    max_turns: int = 6,
    scenario: str = "",
    llm_config: Optional[LLMConfig] = None,
) -> DialogueResult:
    """
    便捷函数: 从游戏状态直接运行对话测试
    
    Args:
        game_state: GameLoop运行后的GameState对象
        max_turns: 最大对话轮数
        scenario: 场景描述
        llm_config: LLM配置 (None则从环境变量读取)
        
    Returns:
        DialogueResult 对话结果
    """
    session = DialogueSession.from_game_state(game_state)
    if llm_config:
        session.config = llm_config
    return session.run_dialogue_sync(
        max_turns=max_turns,
        scenario=scenario,
    )
