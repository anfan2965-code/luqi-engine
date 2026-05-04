"""
提示词构建器 - 将OCEAN/PAD/记忆/世界观/叙事规则注入系统提示词
根据SDK格式适配system/user/assistant消息结构
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from luqi_engine.core.types import SDKType
from luqi_engine.core.constants import (
    LLMMessageRole,
    NovelMode,
    MemoryType,
    AtmosphereMode,
    OCEAN_HIGH_THRESHOLD,
    OCEAN_LOW_THRESHOLD,
    PAD_POSITIVE_THRESHOLD,
    PAD_NEGATIVE_THRESHOLD,
    _MAX_RECENT_EXCHANGES,
    _DEFAULT_ROLE_LABEL,
    _MAX_PROMPT_RECENT_FACTS,
    _MAX_MEMORY_ITEMS_PER_TYPE,
)


_OCEAN_LABEL_MAP: Dict[str, str] = {
    "openness": "开放性",
    "conscientiousness": "尽责性",
    "extraversion": "外向性",
    "agreeableness": "宜人性",
    "neuroticism": "神经质",
}
_PAD_LABEL_MAP: Dict[str, str] = {
    "pleasure": "愉悦度",
    "arousal": "唤醒度",
    "dominance": "支配度",
}

_MEMORY_TYPE_LABEL_MAP: Dict[str, str] = {
    "sensory": "感觉记忆",
    "working": "工作记忆",
    "short_term": "近期记忆",
    "long_term": "长期记忆",
    "emotional": "情感记忆",
    "procedural": "程序记忆",
    "shared": "共享记忆",
}

_ROLE_SYSTEM: str = LLMMessageRole.SYSTEM
_ROLE_USER: str = LLMMessageRole.USER
_ROLE_ASSISTANT: str = LLMMessageRole.ASSISTANT

_PREFIX_FORCE_TEXT: str = "（微微点头）"

_FEW_SHOT_EXAMPLES: List[Dict[str, str]] = [
    {
        "role": _ROLE_USER,
        "content": "你是谁？",
    },
    {
        "role": _ROLE_ASSISTANT,
        "content": "（微微皱眉）我？一个四处漂泊的旅人罢了。你问这个做什么？",
    },
    {
        "role": _ROLE_USER,
        "content": "这里看起来很危险。",
    },
    {
        "role": _ROLE_ASSISTANT,
        "content": "（轻笑一声，手按剑柄）危险？呵，我这一生何时不曾与危险为伴。多谢提醒，我会小心的。",
    },
]


@dataclass
class PromptContext:
    character_name: str = ""
    personality: Optional[Dict[str, float]] = None
    emotion_pad: Optional[Dict[str, float]] = None
    dominant_emotion: str = ""
    memories: Optional[List[Dict[str, Any]]] = None
    worldview_summary: str = ""
    narrative_rules: Optional[List[str]] = None
    dialogue_mode_instruction: str = ""
    format_constraint: str = ""
    custom_sections: Optional[Dict[str, str]] = None


class PromptBuilder:
    """
    提示词构建器
    将角色性格、情感、记忆、世界观、叙事规则等注入系统提示词
    根据SDK格式适配消息结构
    """

    def build_system_prompt(self, context: PromptContext) -> str:
        sections: List[str] = []

        sections.append(
            "语言与角色规则：\n"
            "1. 对话内容必须使用中文\n"
            "2. 你是角色本人，用「我」自称，称呼对方为「你」\n"
            "3. 动作描写使用中文，格式：（动作描写）\n"
            "4. 专有名词（人名、地名、特殊术语）可保留原文语言\n"
            "5. 禁止整句或大段使用英文回复\n"
            "6. 必须直接回应用户的问题或话语"
        )

        if context.character_name:
            sections.append(
                f"你正在扮演角色「{context.character_name}」。"
                "请始终保持角色设定，不要跳出角色。"
            )

        if context.personality:
            sections.append(self._build_personality_section(context.personality))

        if context.emotion_pad:
            sections.append(self._build_emotion_section(context.emotion_pad))

        if context.memories:
            sections.append(self._build_memory_section(context.memories))

        if context.worldview_summary:
            sections.append(
                f"【世界观背景】\n{context.worldview_summary}"
            )

        if context.narrative_rules:
            rules_text = "\n".join(
                f"- {rule}" for rule in context.narrative_rules
            )
            sections.append(f"【叙事规则】\n{rules_text}")

        if context.dialogue_mode_instruction:
            sections.append(f"【对话模式】{context.dialogue_mode_instruction}")

        sections.append(self._build_format_section(context.format_constraint))

        if context.custom_sections:
            for title, content in context.custom_sections.items():
                sections.append(f"【{title}】\n{content}")

        return "\n\n".join(sections)

    @staticmethod
    def _build_format_section(format_constraint: str = "") -> str:
        constraint_lines = []
        if format_constraint:
            constraint_lines.append(format_constraint)
        constraint_lines.extend([
            "回复要求：",
            "- 用「我」自称，称呼对方为「你」，始终以角色第一人称回复",
            "- 必须直接回应用户的问题或话语，不能回避或答非所问",
            "- 以对话为主，动作描写和内心独白为辅",
            "- 动作描写用（动作）标注，内心独白用（内心：内容）标注",
            "- 每条回复最多一处内心独白，放在对话之后",
            "- 回复简洁自然，一到三句话即可，禁止重复相同词语",
            "示例：（轻轻叹气）唉，这条路我走了太久了。你问这些，是想知道什么？",
        ])
        return f"【输出规范】\n" + "\n".join(constraint_lines)

    def build_messages(
        self,
        context: PromptContext,
        sdk_type: SDKType,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        """
        构建完整的消息列表
        根据SDK格式适配消息结构
        """
        system_prompt = self.build_system_prompt(context)

        if sdk_type == SDKType.ANTHROPIC:
            return self._build_anthropic_messages(
                system_prompt, user_message, history
            )
        return self._build_openai_messages(
            system_prompt, user_message, history
        )

    @staticmethod
    def extract_system_prompt_from_messages(
        messages: List[Dict[str, str]],
    ) -> tuple:
        """
        从消息列表中提取system消息（用于Anthropic格式转换）
        返回: (system_text, non_system_messages)
        """
        system_parts: List[str] = []
        other: List[Dict[str, str]] = []
        for msg in messages:
            if msg.get("role") == _ROLE_SYSTEM:
                system_parts.append(msg.get("content", ""))
            else:
                other.append(msg)
        return "\n\n".join(system_parts), other

    @staticmethod
    def _build_openai_messages(
        system_prompt: str,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = [
            {"role": _ROLE_SYSTEM, "content": system_prompt}
        ]
        if not history:
            messages.extend(_FEW_SHOT_EXAMPLES)
        else:
            messages.extend(history)
        messages.append({"role": _ROLE_USER, "content": user_message})
        messages.append({
            "role": _ROLE_ASSISTANT,
            "content": _PREFIX_FORCE_TEXT,
        })
        return messages

    @staticmethod
    def _build_anthropic_messages(
        system_prompt: str,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> List[Dict[str, str]]:
        """
        Anthropic格式：system作为顶级参数，消息只含user/assistant
        此处返回的消息不含system，system由adapter单独处理
        """
        messages: List[Dict[str, str]] = []
        if history:
            for msg in history:
                role = msg.get("role", "")
                if role in (_ROLE_USER, _ROLE_ASSISTANT):
                    messages.append(msg)
        messages.append({"role": _ROLE_USER, "content": user_message})
        return messages

    @staticmethod
    def _build_personality_section(personality: Dict[str, float]) -> str:
        lines = ["【角色性格】"]
        for dim, score in personality.items():
            label = _OCEAN_LABEL_MAP.get(dim, dim)
            desc = _personality_score_description(score, label)
            lines.append(f"- {label}({dim}): {score:.0f}/100 — {desc}")
        return "\n".join(lines)

    @staticmethod
    def _build_emotion_section(emotion_pad: Dict[str, float]) -> str:
        lines = ["【当前情感状态】"]
        for dim, value in emotion_pad.items():
            label = _PAD_LABEL_MAP.get(dim, dim)
            desc = _pad_value_description(value)
            lines.append(f"- {label}: {value:+.2f} ({desc})")
        return "\n".join(lines)

    @staticmethod
    def _build_memory_section(memories: List[Dict[str, Any]]) -> str:
        lines = ["【相关记忆】"]
        by_type: Dict[str, List[Dict[str, Any]]] = {}
        for mem in memories:
            mtype = mem.get("memory_type", MemoryType.SHORT_TERM)
            by_type.setdefault(mtype, []).append(mem)

        type_order = [MemoryType.WORKING, MemoryType.SHORT_TERM, MemoryType.LONG_TERM, MemoryType.EMOTIONAL, MemoryType.PROCEDURAL, MemoryType.SHARED]
        for mtype in type_order:
            mems = by_type.get(mtype)
            if not mems:
                continue
            label = _MEMORY_TYPE_LABEL_MAP.get(mtype, mtype)
            lines.append(f"\n{label}:")
            max_items = len(mems) if mtype == MemoryType.WORKING else _MAX_MEMORY_ITEMS_PER_TYPE
            for mem in mems[:max_items]:
                who = mem.get("who", "未知")
                what = mem.get("what", "未知事件")
                when = mem.get("when", "未知时间")
                where = mem.get("where", "未知地点")
                lines.append(f"  - [{when}@{where}] {who}: {what}")
        return "\n".join(lines)

    def build_dialogue_prompt(self, context: Dict[str, Any]) -> str:
        """
        构建对话智能体提示词
        引导 LLM 将用户输入解析为 CanonicalIR JSON
        """
        sections: List[str] = []

        character_name = context.get("character_name", "")
        if character_name:
            sections.append(
                f"你正在扮演角色「{character_name}」。"
                "请始终保持角色设定，不要跳出角色。"
            )

        personality = context.get("personality")
        if personality:
            sections.append(self._build_personality_section(personality))

        emotion_pad = context.get("emotion_pad")
        if emotion_pad:
            sections.append(self._build_emotion_section(emotion_pad))

        memories = context.get("memories")
        if memories:
            sections.append(self._build_memory_section(memories))

        worldview = context.get("worldview_summary", "")
        if worldview:
            sections.append(f"【世界观背景】\n{worldview}")

        narrative_rules = context.get("narrative_rules")
        if narrative_rules:
            rules_text = "\n".join(f"- {rule}" for rule in narrative_rules)
            sections.append(f"【叙事规则】\n{rules_text}")

        recent = context.get("recent_exchanges", [])
        if recent:
            exchange_lines: List[str] = []
            for ex in recent[-_MAX_RECENT_EXCHANGES:]:
                role = ex.get("role", _DEFAULT_ROLE_LABEL)
                content = ex.get("content", "")
                exchange_lines.append(f"[{role}] {content}")
            sections.append("【近期对话】\n" + "\n".join(exchange_lines))

        sections.append(
            "【任务】\n"
            "分析用户输入，输出紧凑JSON，仅含3个字段：\n"
            "- intent: 意图(如greeting/question/statement/request/emotion)\n"
            "- emotion: {p:浮点数, a:浮点数, d:浮点数} 情感变化(p=愉悦度,a=激活度,d=控制感,范围-1到1)\n"
            "- key_points: 关键要点字符串列表\n"
            "示例: {\"intent\":\"greeting\",\"emotion\":{\"p\":0.3,\"a\":0.1,\"d\":0},\"key_points\":[\"问候\"]}"
        )

        return "\n\n".join(sections)

    def build_novel_prompt(self, context: Dict[str, Any]) -> str:
        """
        构建叙事智能体提示词
        引导 LLM 生成 NarrativeDelta JSON
        """
        sections: List[str] = []

        mode = context.get("novel_mode", NovelMode.INCREMENTAL)
        mode_instruction_map: Dict[str, str] = {
            NovelMode.FULL_UPDATE: "请进行完整的叙事状态更新，包括事实、章节进度、场景预测和开放问题。",
            NovelMode.INCREMENTAL: "请进行增量叙事更新，仅更新变化的事实和章节进度。",
            NovelMode.PREDICTION_ONLY: "请仅预测下一场景走向，不需要更新事实或章节。",
        }
        sections.append(
            f"【叙事更新模式】{mode_instruction_map.get(mode, mode_instruction_map[NovelMode.INCREMENTAL])}"
        )

        chapter = context.get("chapter_outline")
        if chapter:
            sections.append(f"【章节大纲】\n{chapter}")

        character_arcs = context.get("character_arcs")
        if character_arcs:
            sections.append(f"【角色弧线】\n{character_arcs}")

        open_questions = context.get("open_questions", [])
        if open_questions:
            q_lines = [f"- {q}" for q in open_questions]
            sections.append("【开放问题】\n" + "\n".join(q_lines))

        recent_facts = context.get("recent_facts", [])
        if recent_facts:
            fact_lines = [f"- {f}" for f in recent_facts[-_MAX_PROMPT_RECENT_FACTS:]]
            sections.append("【近期事实】\n" + "\n".join(fact_lines))

        canonical_ir = context.get("canonical_ir")
        if canonical_ir:
            sections.append(f"【对话智能体输出】\n{canonical_ir}")

        sections.append(
            "【任务】\n"
            "请根据上下文生成JSON格式的NarrativeDelta，包含以下字段：\n"
            "- version: 版本号\n"
            "- new_facts: 新增事实列表 [{id, timestamp, source, content, participants, emotional_valence, tags}]\n"
            "- chapter_update: {current_beat_progress, new_beat_suggested, character_arcs_update}(可选)\n"
            "- next_prediction: {likely_next_scenes, narrative_tension, suggested_pace}(可选)\n"
            "- open_questions_added: 新增开放问题\n"
            "- open_questions_resolved: 已解决开放问题\n"
            "- narrative_note: 叙事备注"
        )

        return "\n\n".join(sections)

    def build_critic_prompt(self, context: Dict[str, Any]) -> str:
        """
        构建评论智能体提示词
        引导 LLM 对 CanonicalIR 进行质量审查
        """
        sections: List[str] = []

        mode = context.get("critic_mode", AtmosphereMode.LIGHT)
        mode_instruction_map: Dict[str, str] = {
            "full": "请进行全面审查，覆盖一致性、情感合理性、叙事对齐、角色忠实度、动作合理性、语气适当性。",
            AtmosphereMode.LIGHT: "请进行轻量审查，仅检查一致性和情感合理性。",
        }
        sections.append(
            f"【审查模式】{mode_instruction_map.get(mode, mode_instruction_map[AtmosphereMode.LIGHT])}"
        )

        character_state = context.get("character_state")
        if character_state:
            sections.append(f"【角色当前状态】\n{character_state}")

        narrative_context = context.get("narrative_context", "")
        if narrative_context:
            sections.append(f"【叙事上下文】\n{narrative_context}")

        sections.append(
            "【任务】\n"
            "请审查提供的CanonicalIR，输出JSON格式的CriticVerdict：\n"
            "- verdict: 审查结论(accept/reject/revise)\n"
            "- checks: 检查项列表 [{dimension, severity(pass/warning/critical), score(0-1), detail}]\n"
            "- overall_confidence: 总体置信度(0-1)\n"
            "- corrections: {suggested_emotion_delta, suggested_action, suggested_key_point_addition, narrative_risk_flag}(可选)\n"
            "- override_recommendation: 覆盖建议(可选)"
        )

        return "\n\n".join(sections)

    def build_atmosphere_prompt(self, context: Dict[str, Any]) -> str:
        """
        构建氛围智能体提示词
        引导 LLM 生成 AtmosphereOutput JSON
        """
        sections: List[str] = []

        mode = context.get("atmosphere_mode", AtmosphereMode.LIGHT)
        mode_instruction_map: Dict[str, str] = {
            AtmosphereMode.LIGHT: "请生成轻量氛围描述，仅包含环境感官和情绪声明。",
            AtmosphereMode.FULL: "请生成完整氛围描述，包含环境、旁白、舞台指示和情绪声明。",
        }
        sections.append(
            f"【氛围生成模式】{mode_instruction_map.get(mode, mode_instruction_map[AtmosphereMode.LIGHT])}"
        )

        scene_name = context.get("scene_name", "")
        if scene_name:
            sections.append(f"【当前场景】{scene_name}")

        dominant_emotion = context.get("dominant_emotion", "")
        if dominant_emotion:
            sections.append(f"【主导情感】{dominant_emotion}")

        emotion_intensity = context.get("emotion_intensity")
        if emotion_intensity is not None:
            sections.append(f"【情感强度】{emotion_intensity}")

        characters = context.get("characters_present", [])
        if characters:
            sections.append("【在场角色】\n" + "\n".join(f"- {c}" for c in characters))

        time_of_day = context.get("time_of_day", "")
        if time_of_day:
            sections.append(f"【时间段】{time_of_day}")

        narrative_context = context.get("narrative_context", "")
        if narrative_context:
            sections.append(f"【叙事上下文】\n{narrative_context}")

        sections.append(
            "【任务】\n"
            "请生成JSON格式的AtmosphereOutput：\n"
            "- mode: 生成模式(light/full)\n"
            "- environment: {visual, auditory, olfactory, thermal, spatial}\n"
            "- narration: {transition, inner_voice, omniscient_note}(可选字段可为null)\n"
            "- stage_directions: [{character, action, detail}]\n"
            "- mood_declaration: {dominant_emotion, intensity(0-1), color_palette, pacing_hint}\n"
            "- suggested_position: prefix/suffix/inline\n"
            "- length_budget: short/medium/long\n"
            "- priority: 优先级(0-1)"
        )

        return "\n\n".join(sections)


def _personality_score_description(score: float, label: str) -> str:
    if score >= OCEAN_HIGH_THRESHOLD:
        return f"高{label}，倾向明显"
    if score <= OCEAN_LOW_THRESHOLD:
        return f"低{label}，倾向不明显"
    return f"中等{label}"


def _pad_value_description(value: float) -> str:
    if value >= PAD_POSITIVE_THRESHOLD:
        return "偏高"
    if value <= PAD_NEGATIVE_THRESHOLD:
        return "偏低"
    return "中性"
