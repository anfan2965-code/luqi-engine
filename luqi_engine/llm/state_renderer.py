from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional

from luqi_engine.core.config import LLMConfig
from luqi_engine.core.constants import (
    OCEAN_HIGH_THRESHOLD,
    OCEAN_LOW_THRESHOLD,
    PAD_POSITIVE_THRESHOLD,
    PAD_NEGATIVE_THRESHOLD,
)

_OCEAN_TRAIT_MAP: Dict[str, Dict[str, str]] = {
    "openness": {"high": "开放/好奇/富有想象力", "low": "保守/传统/务实", "mid": "适度开放"},
    "conscientiousness": {"high": "尽责/自律/有条理", "low": "随性/灵活/不拘小节", "mid": "适度尽责"},
    "extraversion": {"high": "外向/热情/善交际", "low": "内向/安静/独处", "mid": "适度外向"},
    "agreeableness": {"high": "友善/合作/体贴", "low": "直率/独立/好辩", "mid": "适度友善"},
    "neuroticism": {"high": "敏感/易焦虑/情绪波动", "low": "稳定/冷静/从容", "mid": "适度敏感"},
}

_PAD_EMOTION_MAP: Dict[str, Dict[str, str]] = {
    "pleasure": {"high": "愉悦", "low": "不悦", "mid": "平淡"},
    "arousal": {"high": "激动", "low": "平静", "mid": "一般"},
    "dominance": {"high": "主导", "low": "顺从", "mid": "平等"},
}

_SEVEN_EMOTIONS: List[str] = ["喜", "怒", "忧", "思", "悲", "恐", "惊"]

_MAX_MEMORY_ITEMS: int = 5
_TOKEN_PER_CHAR_ESTIMATE: float = 0.6
_TRUNCATION_SUFFIX_V2: str = "..."
_MIN_SECTION_TOKENS: int = 20


@dataclass
class TokenBudgetProfile:
    """
    Token预算配置 — 控制Prompt各部分的token分配
    
    允许针对不同使用场景定制Prompt的信息分布:
    - 对话密集场景: 增加记忆和社交权重
    - 叙事推进场景: 增加叙事和动机权重
    - 冲突高潮场景: 增加存在主义和阴影权重
    """
    
    total_budget: int = 2000
    section_weights: Dict[str, float] = field(default_factory=dict)
    min_section_tokens: int = _MIN_SECTION_TOKENS
    overflow_strategy: str = "truncate_tail"
    
    _DEFAULT_WEIGHTS: ClassVar[Dict[str, float]] = {
        "personality_core": 0.18,
        "existential_state": 0.12,
        "narrative_identity": 0.12,
        "motivation": 0.12,
        "memory": 0.10,
        "social": 0.08,
        # === Phase 3 新增 ===
        "belief_state": 0.10,
        "threat_assessment": 0.08,
        "strategy_hint": 0.06,
        # === 基础 ===
        "scene_instruction": 0.06,
        "response_hint": 0.04,
    }
    
    def __post_init__(self) -> None:
        if not self.section_weights:
            self.section_weights = dict(self._DEFAULT_WEIGHTS)
    
    @classmethod
    def dialogue_optimized(cls) -> "TokenBudgetProfile":
        """对话密集场景: 强调记忆和社交"""
        profile = cls()
        profile.section_weights.update({
            "memory": 0.20,
            "social": 0.18,
            "personality_core": 0.20,
            "motivation": 0.15,
            "existential_state": 0.10,
            "narrative_identity": 0.10,
            "scene_instruction": 0.07,
        })
        return profile
    
    @classmethod
    def narrative_optimized(cls) -> "TokenBudgetProfile":
        """叙事推进场景: 强调叙事和动机"""
        profile = cls()
        profile.section_weights.update({
            "narrative_identity": 0.22,
            "motivation": 0.20,
            "personality_core": 0.18,
            "existential_state": 0.15,
            "memory": 0.12,
            "social": 0.08,
            "scene_instruction": 0.05,
        })
        return profile
    
    @classmethod
    def conflict_optimized(cls) -> "TokenBudgetProfile":
        """冲突高潮场景: 强调存在主义和阴影"""
        profile = cls()
        profile.section_weights.update({
            "existential_state": 0.25,
            "personality_core": 0.22,
            "motivation": 0.18,
            "narrative_identity": 0.15,
            "memory": 0.10,
            "social": 0.07,
            "scene_instruction": 0.03,
        })
        return profile


class StateRenderer:
    _MIN_SECTION_TOKENS: int = _MIN_SECTION_TOKENS
    
    def __init__(self, config: Optional[LLMConfig] = None) -> None:
        self._max_system_token_estimate: int = (
            config.system_token_budget if config else 300
        )

    def render_system_prompt(
        self,
        character_name: str = "",
        personality: Optional[Dict[str, float]] = None,
        pad_emotion: Optional[Dict[str, float]] = None,
        seven_emotions: Optional[Dict[str, float]] = None,
        scene: str = "",
        behavior_instruction: str = "",
        memories: Optional[List[Dict[str, Any]]] = None,
        background: str = "",
        output_requirements: str = "",
    ) -> str:
        parts: List[str] = []

        if character_name:
            parts.append("[角色]{}".format(character_name))

        if background:
            bg_summary = background
            if len(bg_summary) > 60:
                bg_summary = bg_summary[:57] + "..."
            parts.append("[背景]{}".format(bg_summary))

        if personality:
            traits = self._render_personality(personality)
            if traits:
                parts.append("[性格]{}".format(traits))

        if pad_emotion:
            emotion_str = self._render_pad_emotion(pad_emotion)
            if emotion_str:
                parts.append("[情绪]{}".format(emotion_str))

        if seven_emotions:
            emo_str = self._render_seven_emotions(seven_emotions)
            if emo_str:
                parts.append("[七情]{}".format(emo_str))

        if scene:
            parts.append("[场景]{}".format(scene))

        if behavior_instruction:
            parts.append("[指令]{}".format(behavior_instruction))

        if memories:
            mem_str = self._render_memories(memories)
            if mem_str:
                parts.append("[记忆]{}".format(mem_str))

        if output_requirements:
            parts.append("[要求]{}".format(output_requirements))

        result = " ".join(parts)

        estimated_tokens = len(result) * _TOKEN_PER_CHAR_ESTIMATE
        if estimated_tokens > self._max_system_token_estimate:
            result = self._compress_prompt(result)

        return result

    def _render_personality(self, personality: Dict[str, float]) -> str:
        traits: List[str] = []
        for dim, score in personality.items():
            dim_key = dim.lower()
            if dim_key not in _OCEAN_TRAIT_MAP:
                continue
            if score >= OCEAN_HIGH_THRESHOLD:
                traits.append(_OCEAN_TRAIT_MAP[dim_key]["high"].split("/")[0])
            elif score <= OCEAN_LOW_THRESHOLD:
                traits.append(_OCEAN_TRAIT_MAP[dim_key]["low"].split("/")[0])
            else:
                traits.append(_OCEAN_TRAIT_MAP[dim_key]["mid"].split("/")[0])
        return "/".join(traits)

    def _render_pad_emotion(self, pad: Dict[str, float]) -> str:
        parts: List[str] = []
        for dim, score in pad.items():
            dim_key = dim.lower()
            if dim_key not in _PAD_EMOTION_MAP:
                continue
            if score >= PAD_POSITIVE_THRESHOLD:
                parts.append("{}{:.1f}".format(_PAD_EMOTION_MAP[dim_key]["high"], abs(score)))
            elif score <= PAD_NEGATIVE_THRESHOLD:
                parts.append("{}{:.1f}".format(_PAD_EMOTION_MAP[dim_key]["low"], abs(score)))
        return "/".join(parts)

    def _render_seven_emotions(self, emotions: Dict[str, float]) -> str:
        parts: List[str] = []
        for emo_name in _SEVEN_EMOTIONS:
            score = emotions.get(emo_name, 0.0)
            if score >= 0.3:
                parts.append("{}{:.1f}".format(emo_name, score))
        return "/".join(parts)

    def _render_memories(self, memories: List[Dict[str, Any]]) -> str:
        items = memories[:_MAX_MEMORY_ITEMS]
        parts: List[str] = []
        for mem in items:
            who = mem.get("who", "")
            what = mem.get("what", "")
            if what:
                if who:
                    parts.append("{}:{}".format(who, what[:20]))
                else:
                    parts.append(what[:20])
        return "|".join(parts)

    def _compress_prompt(self, prompt: str) -> str:
        while len(prompt) * _TOKEN_PER_CHAR_ESTIMATE > self._max_system_token_estimate:
            parts = prompt.split(" ")
            if len(parts) <= 3:
                break
            mid = len(parts) // 2
            parts.pop(mid)
            prompt = " ".join(parts)
        return prompt

    # ================================================================
    # v2 API: DeepCharacter 状态渲染
    # ================================================================

    # v2 权重 (Phase 1-3)
    DEEP_SECTION_WEIGHTS: ClassVar[Dict[str, float]] = TokenBudgetProfile._DEFAULT_WEIGHTS

    def render_deep_state(
        self,
        deep_state: Any,
        max_tokens: int = 2000,
        include_v1_sections: bool = True,
    ) -> str:
        """
        渲染DeepCharacter状态为Prompt文本 (v2 API)
        
        流程:
        1. 将DeepCharacterState分解为各section
        2. 按权重排序section
        3. 渲染每个section
        4. 检查token预算, 必要时截断低优先级section
        
        Args:
            deep_state: DeepCharacterState对象
            max_tokens: 最大token预算
            include_v1_sections: 是否同时包含v1基础信息
            
        Returns:
            格式化的Prompt文本
        """
        sections_data = self._extract_deep_sections(deep_state)
        
        sorted_sections = sorted(
            sections_data.items(),
            key=lambda x: self.DEEP_SECTION_WEIGHTS.get(x[0], 0.05),
            reverse=True,
        )
        
        rendered_parts: List[str] = []
        current_tokens = 0
        
        for section_name, section_text in sorted_sections:
            if not section_text or not section_text.strip():
                continue
            
            section_tokens = self.estimate_tokens(section_text)
            
            if current_tokens + section_tokens > max_tokens:
                remaining = max_tokens - current_tokens
                if remaining > self._MIN_SECTION_TOKENS:
                    truncated = self._truncate_to_tokens(section_text, remaining)
                    rendered_parts.append(truncated)
                break
            
            rendered_parts.append(section_text)
            current_tokens += section_tokens
        
        result = "\n".join(rendered_parts) if rendered_parts else ""
        
        if deep_state.response_style_hint:
            style_hint = f"[回复风格] {deep_state.response_style_hint}"
            hint_tokens = self.estimate_tokens(style_hint)
            total_with_hint = current_tokens + hint_tokens
            if total_with_hint <= max_tokens or not result:
                result = result + ("\n" if result else "") + style_hint
        
        return result
    
    def render_with_token_budget(
        self,
        deep_state: Any,
        budget_profile: TokenBudgetProfile,
    ) -> str:
        """
        使用自定义Token预算配置渲染
        
        Args:
            deep_state: DeepCharacterState对象
            budget_profile: Token预算配置
            
        Returns:
            格式化的Prompt文本
        """
        return self.render_deep_state(
            deep_state=deep_state,
            max_tokens=budget_profile.total_budget,
        )
    
    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        估算文本的token数量
        
        中文字符约1.5字符/token, 英文约4字符/token
        
        Args:
            text: 待估算文本
            
        Returns:
            估算的token数
        """
        if not text:
            return 0
        chinese_count = sum(1 for c in text if "\u4e00" <= c <= "\u9fff" or "\u3000" <= c <= "\u303f")
        other_count = len(text) - chinese_count
        return int(chinese_count / 1.5 + other_count / 4) + 1
    
    def _extract_deep_sections(self, deep_state: Any) -> Dict[str, str]:
        """从DeepCharacterState中提取各section文本"""
        sections: Dict[str, str] = {}
        
        personality_parts: List[str] = []
        if getattr(deep_state, 'dominant_archetype', None):
            archetype_map = {
                "INNOCENT": "天真者", "SAGE": "智者", "EXPLORER": "探索者",
                "RULER": "统治者", "CREATOR": "创造者", "CAREGIVER": "照顾者",
                "MAGICIAN": "魔术师", "HERO": "英雄", "OUTLAW": "反叛者",
                "LOVER": "恋人", "JESTER": "小丑", "EVERYMAN": "普通人",
            }
            arch_cn = archetype_map.get(deep_state.dominant_archetype, deep_state.dominant_archetype)
            personality_parts.append(f"原型:{arch_cn}")
        
        shadow_state = getattr(deep_state, 'shadow_state', None)
        if shadow_state and shadow_state.name != "DORMANT":
            shadow_cn = {
                "RUMBLING": "潜伏躁动", "ACTIVE": "活跃", "OVERRUN": "失控"
            }.get(shadow_state.name, shadow_state.name)
            active_aspects = getattr(deep_state, 'active_shadow_aspects', None) or []
            aspects_str = ",".join(active_aspects[:3]) if active_aspects else ""
            personality_parts.append(f"阴影:{shadow_cn}({aspects_str})" if aspects_str else f"阴影:{shadow_cn}")
        
        persona_active = getattr(deep_state, 'persona_active', False)
        if persona_active:
            persona_desc = getattr(deep_state, 'persona_description', '') or ""
            personality_parts.append(f"面具:{persona_desc}")
        
        if personality_parts:
            sections["personality_core"] = "[深层人格] " + " | ".join(personality_parts)
        
        tension_level = getattr(deep_state, 'tension_level', None)
        anxiety = getattr(deep_state, 'existential_anxiety', 0.0)
        authenticity = getattr(deep_state, 'authenticity_score', 0.5)
        
        if tension_level and tension_level.name != "CALM" or anxiety > 0.3 or authenticity < 0.6:
            tension_cn = {"TENSE": "紧绷", "CRISIS": "危机", "DISSOCIATED": "解离"}.get(
                tension_level.name if tension_level else "", "平静"
            )
            exist_parts = [f"张力:{tension_cn}", f"本真:{int(authenticity * 100)}%"]
            if anxiety > 0.3:
                exist_parts.append(f"焦虑:{int(anxiety * 100)}%")
            
            dissonance = getattr(deep_state, 'cognitive_dissonance', 0.0)
            if dissonance > 0.3:
                exist_parts.append(f"失调:{int(dissonance * 100)}%")
            
            sections["existential_state"] = "[存在状态] " + " | ".join(exist_parts)
        
        core_narrative = getattr(deep_state, 'core_narrative', "")
        narrative_phase = getattr(deep_state, 'narrative_phase', None)
        narrative_tension = getattr(deep_state, 'narrative_tension', 0.0)
        
        if core_narrative or (narrative_phase and narrative_tension > 0.3):
            phase_cn = {
                "CALL": "启程召唤", "INITIATION": "试炼入门",
                "ORDEAL": "严峻考验", "TRANSFORMATION": "蜕变转化", "RETURN": "回归升华"
            }.get(narrative_phase.name if narrative_phase else "", "未知")
            nar_parts = [f"阶段:{phase_cn}"]
            if core_narrative:
                nar_parts.append(core_narrative[:60])
            if narrative_tension > 0.5:
                nar_parts.append(f"张力:{int(narrative_tension * 100)}%")
            sections["narrative_identity"] = "[叙事弧] " + " | ".join(nar_parts)
        
        dominant_need = getattr(deep_state, 'dominant_need', "")
        need_satisfaction = getattr(deep_state, 'need_satisfaction_map', {}) or {}
        urgency = getattr(deep_state, 'urgency_level', 1.0)
        conflict = getattr(deep_state, 'current_conflict', None)
        
        if dominant_need:
            need_cn = {
                "PHYSIOLOGICAL": "生理", "SAFETY": "安全", "BELONGING": "归属",
                "ESTEEM": "尊重", "COGNITIVE": "认知", "AESTHETIC": "审美",
                "SELF_ACTUALIZATION": "自我实现", "TRANSCENDENCE": "超越"
            }
            sat_val = need_satisfaction.get(dominant_need, 0.5)
            mot_parts = [
                f"{need_cn.get(dominant_need, dominant_need)}({int(sat_val * 100)}%)",
                f"紧急:{urgency:.1f}",
            ]
            if conflict:
                mot_parts.append(f"冲突:{conflict}")
            sections["motivation"] = "[主导需求] " + " | ".join(mot_parts)
        
        relevant_memories = getattr(deep_state, 'relevant_memories', []) or []
        if relevant_memories:
            mem_texts: List[str] = []
            for m in relevant_memories[:4]:
                content = m.get("content", "") if isinstance(m, dict) else str(m)
                emotion = m.get("emotion", "") if isinstance(m, dict) else ""
                if content:
                    entry = content[:50]
                    if emotion:
                        entry = f"{entry}({emotion})"
                    mem_texts.append(entry)
            if mem_texts:
                sections["memory"] = "[核心记忆] " + "; ".join(mem_texts)
        
        rel_summary = getattr(deep_state, 'relationship_summary', "")
        trust = getattr(deep_state, 'trust_level_current', 0.5)
        social_role = getattr(deep_state, 'social_role', "")
        
        if rel_summary or social_role:
            soc_parts: List[str] = []
            if rel_summary:
                soc_parts.append(rel_summary[:60])
            soc_parts.append(f"信任:{int(trust * 100)}%")
            if social_role:
                soc_parts.append(f"角色:{social_role}")
            sections["social"] = "[社交关系] " + " | ".join(soc_parts)
        
        scene_ctx = getattr(deep_state, 'scene_context', "")
        if scene_ctx:
            sections["scene_instruction"] = f"[场景] {scene_ctx[:100]}"
        
        # === Phase 4: 博弈论状态渲染 ===
        
        primary_beliefs = getattr(deep_state, 'primary_target_beliefs', None)
        if primary_beliefs:
            belief_parts: List[str] = []
            for tid, coop_est in list(primary_beliefs.items())[:3]:
                label = tid[-8:] if len(tid) > 8 else tid
                belief_parts.append(f"{label}:{coop_est:.2f}")
            if belief_parts:
                sections["belief_state"] = f"[目标信念] {'; '.join(belief_parts)}"
        
        active_threats = getattr(deep_state, 'active_threats', None)
        threat_readiness = getattr(deep_state, 'threat_response_readiness', 0.5)
        if active_threats or threat_readiness < 0.4:
            threat_parts: List[str] = [f"准备度:{int(threat_readiness * 100)}%"]
            if active_threats:
                for t in active_threats[:2]:
                    target_label = t.get("target", "?")[-6:]
                    threat_parts.append(f"@{target_label}")
            sections["threat_assessment"] = f"[威胁评估] {', '.join(threat_parts)}"
        
        current_strategy = getattr(deep_state, 'current_strategy', None)
        alignment = getattr(deep_state, 'belief_action_alignment', 0.5)
        if current_strategy:
            dominant_action = current_strategy.get("dominant_action", "OBSERVE")
            action_cn = {
                "COOPERATE": "合作", "DEFECT": "背叛", "OBSERVE": "观察",
                "WITHDRAW": "撤退", "PUNISH": "惩罚", "NEGOTIATE": "谈判",
            }.get(dominant_action, dominant_action)
            
            entropy_val = current_strategy.get("entropy", 1.0)
            temp_val = current_strategy.get("temperature", 1.0)
            
            strat_parts = [
                f"策略:{action_cn}",
                f"熵:{entropy_val:.2f}",
                f"τ:{temp_val:.1f}",
                f"一致:{int(alignment * 100)}%",
            ]
            sections["strategy_hint"] = f"[博弈策略] {' | '.join(strat_parts)}"
        
        return sections
    
    @staticmethod
    def _truncate_to_tokens(text: str, target_tokens: int) -> str:
        """将文本截断到目标token数"""
        if not text:
            return text
        
        est_chars_per_token = 2.0
        target_chars = int(target_tokens * est_chars_per_token)
        
        if len(text) <= target_chars:
            return text
        
        return text[:target_chars - len(_TRUNCATION_SUFFIX_V2)] + _TRUNCATION_SUFFIX_V2
