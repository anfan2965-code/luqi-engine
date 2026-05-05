"""
LLM响应解析器 - 解析LLM输出为结构化数据
兼容OpenAI和Anthropic两种SDK的响应格式差异
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_logger = logging.getLogger(__name__)

_FALLBACK_RESPONSE_TRUNCATION: int = 200
_FALLBACK_CONFIDENCE_DEFAULT: float = 0.5


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if isinstance(value, (int, float)):
            return float(value)
        s = str(value).strip().rstrip('%')
        return float(s) if s else default
    except (ValueError, TypeError):
        return default

from luqi_engine.core.types import (
    AtmosphereEnvironment,
    AtmosphereNarration,
    AtmosphereOutput,
    CanonicalIR,
    ChapterUpdate,
    CriticCheck,
    CriticCorrections,
    CriticVerdict,
    EmotionDelta,
    LLMResponse,
    MoodDeclaration,
    NarrativeDelta,
    NextPrediction,
    NewFact,
    SDKType,
    StageDirection,
)
from luqi_engine.core.constants import (
    ToneType,
    LengthHint,
    PaceLevel,
    CriticSeverity,
    CriticVerdictType,
    AtmosphereMode,
    _DEFAULT_MOOD_INTENSITY,
    _DEFAULT_ATMOSPHERE_PRIORITY,
    _DEFAULT_SUGGESTED_POSITION,
    _DEFAULT_LENGTH_BUDGET,
    _DEFAULT_ACTION_TYPE,
)

_TAG_ACTION_OPEN: str = "<action>"
_TAG_ACTION_CLOSE: str = "</action>"
_TAG_DIALOGUE_OPEN: str = "<dialogue>"
_TAG_DIALOGUE_CLOSE: str = "</dialogue>"
_TAG_EMOTION_OPEN: str = "<emotion>"
_TAG_EMOTION_CLOSE: str = "</emotion>"
_TAG_THINK_OPEN: str = "<think>"
_TAG_THINK_CLOSE: str = "</think>"
_TAG_RESPONSE_OPEN: str = "<response>"
_TAG_RESPONSE_CLOSE: str = "</response>"

_PATTERN_ACTION_TARGET: re.Pattern = re.compile(
    r"(.+?)(?:→|->|对|向)(.+?)(?:说|喊|低语|怒吼|询问)?[:：]?\s*(.*)",
    re.DOTALL,
)
_PATTERN_DIALOGUE_SPEAKER: re.Pattern = re.compile(
    r"(.+?)[\(（](.+?)[\)）]\s*[:：]?\s*(.*)",
    re.DOTALL,
)
_PATTERN_EMOTION_PAD: re.Pattern = re.compile(
    r"(?:pleasure|愉悦度?)\s*[:：]\s*([-\d.]+)\s*[,\s]*"
    r"(?:arousal|唤醒度?)\s*[:：]\s*([-\d.]+)\s*[,\s]*"
    r"(?:dominance|支配度?)\s*[:：]\s*([-\d.]+)",
    re.IGNORECASE,
)


@dataclass
class ParsedAction:
    action_type: str = ""
    description: str = ""
    target: str = ""
    raw_text: str = ""


@dataclass
class ParsedDialogue:
    speaker: str = ""
    tone: str = ""
    content: str = ""
    raw_text: str = ""


@dataclass
class ParsedEmotionDelta:
    pleasure_delta: float = 0.0
    arousal_delta: float = 0.0
    dominance_delta: float = 0.0
    raw_text: str = ""


@dataclass
class ParsedResponse:
    thinking: str = ""
    response_text: str = ""
    actions: List[ParsedAction] = field(default_factory=list)
    dialogues: List[ParsedDialogue] = field(default_factory=list)
    emotion_deltas: List[ParsedEmotionDelta] = field(default_factory=list)
    raw_content: str = ""
    sdk_type: SDKType = SDKType.OPENAI


class ResponseParser:
    """
    LLM响应解析器
    从LLM输出中提取动作、对话、情感变化
    支持结构化标签和自由文本两种格式
    """

    def parse(self, response: LLMResponse, sdk_type: SDKType) -> ParsedResponse:
        """
        解析LLM响应
        """
        content = response.content
        thinking, main_text = self._extract_thinking(content)

        actions = self._extract_tagged(main_text, _TAG_ACTION_OPEN, _TAG_ACTION_CLOSE)
        dialogues = self._extract_tagged(main_text, _TAG_DIALOGUE_OPEN, _TAG_DIALOGUE_CLOSE)
        emotions = self._extract_tagged(main_text, _TAG_EMOTION_OPEN, _TAG_EMOTION_CLOSE)

        parsed_actions = [self._parse_action(a) for a in actions]
        parsed_dialogues = [self._parse_dialogue(d) for d in dialogues]
        parsed_emotions = [self._parse_emotion(e) for e in emotions]

        if not parsed_actions and not parsed_dialogues and not parsed_emotions:
            fallback = self._fallback_parse(main_text)
            parsed_actions = fallback.actions or parsed_actions
            parsed_dialogues = fallback.dialogues or parsed_dialogues

        return ParsedResponse(
            thinking=thinking,
            response_text=main_text,
            actions=parsed_actions,
            dialogues=parsed_dialogues,
            emotion_deltas=parsed_emotions,
            raw_content=content,
            sdk_type=sdk_type,
        )

    def parse_stream_accumulated(
        self, accumulated_text: str, sdk_type: SDKType
    ) -> ParsedResponse:
        """
        解析流式累积的文本
        """
        fake_response = LLMResponse(
            content=accumulated_text,
            role="assistant",
            finish_reason="stop",
            usage={},
            tokens=0,
        )
        return self.parse(fake_response, sdk_type)

    @staticmethod
    def _extract_thinking(text: str) -> tuple:
        start = text.find(_TAG_THINK_OPEN)
        end = text.find(_TAG_THINK_CLOSE)
        if start >= 0 and end > start:
            thinking = text[start + len(_TAG_THINK_OPEN) : end].strip()
            rest = text[:start] + text[end + len(_TAG_THINK_CLOSE) :]
            return thinking, rest.strip()

        resp_start = text.find(_TAG_RESPONSE_OPEN)
        resp_end = text.find(_TAG_RESPONSE_CLOSE)
        if resp_start >= 0 and resp_end > resp_start:
            response_text = text[
                resp_start + len(_TAG_RESPONSE_OPEN) : resp_end
            ].strip()
            before = text[:resp_start].strip()
            return before, response_text

        return "", text

    @staticmethod
    def _extract_tagged(text: str, open_tag: str, close_tag: str) -> List[str]:
        results: List[str] = []
        pos = 0
        while True:
            start = text.find(open_tag, pos)
            if start < 0:
                break
            end = text.find(close_tag, start + len(open_tag))
            if end < 0:
                break
            results.append(text[start + len(open_tag) : end].strip())
            pos = end + len(close_tag)
        return results

    @staticmethod
    def _parse_action(raw: str) -> ParsedAction:
        match = _PATTERN_ACTION_TARGET.search(raw)
        if match:
            return ParsedAction(
                action_type=match.group(1).strip(),
                target=match.group(2).strip(),
                description=match.group(3).strip() if match.group(3) else raw,
                raw_text=raw,
            )
        return ParsedAction(
            action_type=_DEFAULT_ACTION_TYPE,
            description=raw,
            target="",
            raw_text=raw,
        )

    @staticmethod
    def _parse_dialogue(raw: str) -> ParsedDialogue:
        match = _PATTERN_DIALOGUE_SPEAKER.search(raw)
        if match:
            return ParsedDialogue(
                speaker=match.group(1).strip(),
                tone=match.group(2).strip(),
                content=match.group(3).strip() if match.group(3) else raw,
                raw_text=raw,
            )
        return ParsedDialogue(
            speaker="",
            tone="",
            content=raw,
            raw_text=raw,
        )

    @staticmethod
    def _parse_emotion(raw: str) -> ParsedEmotionDelta:
        match = _PATTERN_EMOTION_PAD.search(raw)
        if match:
            try:
                return ParsedEmotionDelta(
                    pleasure_delta=_safe_float(match.group(1)),
                    arousal_delta=_safe_float(match.group(2)),
                    dominance_delta=_safe_float(match.group(3)),
                    raw_text=raw,
                )
            except (ValueError, IndexError) as exc:
                _logger.debug("PAD向量解析失败: %s", exc)
        return ParsedEmotionDelta(raw_text=raw)

    @staticmethod
    def _fallback_parse(text: str) -> ParsedResponse:
        """
        自由文本回退解析
        尝试从非结构化文本中提取信息
        """
        dialogues: List[ParsedDialogue] = []
        actions: List[ParsedAction] = []

        quote_pattern = re.compile(r"[「""](.+?)[」""]")
        for match in quote_pattern.finditer(text):
            dialogues.append(
                ParsedDialogue(
                    speaker="",
                    tone="",
                    content=match.group(1),
                    raw_text=match.group(0),
                )
            )

        return ParsedResponse(
            thinking="",
            response_text=text,
            actions=actions,
            dialogues=dialogues,
            emotion_deltas=[],
            raw_content=text,
            sdk_type=SDKType.OPENAI,
        )

    def parse_canonical_ir(self, response: str) -> CanonicalIR:
        """
        解析 LLM 响应为 CanonicalIR
        支持纯 JSON、```json ... ``` 包裹、简化字段名(p/a/d)和正则兜底
        """
        data = self._extract_json(response)
        if data is None:
            data = self._regex_extract_ir(response)
        if data is None:
            return CanonicalIR(key_points=[response[:_FALLBACK_RESPONSE_TRUNCATION]] if response.strip() else [])

        emotion_raw = data.get("emotion_delta") or data.get("emotion") or {}
        emotion_delta = EmotionDelta(
            pleasure=_safe_float(emotion_raw.get("pleasure") or emotion_raw.get("p"), 0.0),
            arousal=_safe_float(emotion_raw.get("arousal") or emotion_raw.get("a"), 0.0),
            dominance=_safe_float(emotion_raw.get("dominance") or emotion_raw.get("d"), 0.0),
        )

        return CanonicalIR(
            intent=str(data.get("intent", "")),
            confidence=_safe_float(data.get("confidence", _FALLBACK_CONFIDENCE_DEFAULT), _FALLBACK_CONFIDENCE_DEFAULT),
            emotion_delta=emotion_delta,
            seven_trigger=str(data.get("seven_trigger", "")),
            action=str(data.get("action", "")),
            action_params=dict(data.get("action_params", {})),
            key_points=list(data.get("key_points", [])),
            tone=str(data.get("tone", ToneType.NEUTRAL)),
            length_hint=str(data.get("length_hint", LengthHint.MEDIUM)),
            narrative_signal=data.get("narrative_signal"),
            memory_to_add=data.get("memory_to_add"),
        )

    def parse_narrative_delta(self, response: str) -> NarrativeDelta:
        """
        解析 LLM 响应为 NarrativeDelta
        """
        data = self._extract_json(response)
        if data is None:
            return NarrativeDelta()

        new_facts = [
            NewFact(
                id=str(f.get("id", "")),
                timestamp=str(f.get("timestamp", "")),
                source=str(f.get("source", "")),
                content=str(f.get("content", "")),
                participants=list(f.get("participants", [])),
                emotional_valence=_safe_float(f.get("emotional_valence", 0.0)),
                tags=list(f.get("tags", [])),
            )
            for f in data.get("new_facts", [])
        ]

        chapter_data = data.get("chapter_update")
        chapter_update = None
        if chapter_data is not None:
            chapter_update = ChapterUpdate(
                current_beat_progress=_safe_float(
                    chapter_data.get("current_beat_progress", 0.0)
                ),
                new_beat_suggested=chapter_data.get("new_beat_suggested"),
                character_arcs_update=dict(
                    chapter_data.get("character_arcs_update", {})
                ),
                constraints_added=list(chapter_data.get("constraints_added", [])),
                constraints_removed=list(
                    chapter_data.get("constraints_removed", [])
                ),
            )

        prediction_data = data.get("next_prediction")
        next_prediction = None
        if prediction_data is not None:
            next_prediction = NextPrediction(
                likely_next_scenes=list(
                    prediction_data.get("likely_next_scenes", [])
                ),
                narrative_tension=_safe_float(
                    prediction_data.get("narrative_tension", 0.0)
                ),
                suggested_pace=str(prediction_data.get("suggested_pace", PaceLevel.NORMAL)),
            )

        return NarrativeDelta(
            version=int(data.get("version", 0)),
            new_facts=new_facts,
            chapter_update=chapter_update,
            next_prediction=next_prediction,
            open_questions_added=list(data.get("open_questions_added", [])),
            open_questions_resolved=list(data.get("open_questions_resolved", [])),
            narrative_note=str(data.get("narrative_note", "")),
        )

    def parse_critic_verdict(self, response: str) -> CriticVerdict:
        """
        解析 LLM 响应为 CriticVerdict
        """
        data = self._extract_json(response)
        if data is None:
            return CriticVerdict()

        checks = [
            CriticCheck(
                dimension=str(c.get("dimension", "")),
                severity=str(c.get("severity", CriticSeverity.PASS)),
                score=_safe_float(c.get("score", 1.0)),
                detail=str(c.get("detail", "")),
            )
            for c in data.get("checks", [])
        ]

        corrections_data = data.get("corrections")
        corrections = None
        if corrections_data is not None:
            sed = corrections_data.get("suggested_emotion_delta")
            suggested_emotion = None
            if sed is not None:
                suggested_emotion = EmotionDelta(
                    pleasure=_safe_float(sed.get("pleasure", 0.0)),
                    arousal=_safe_float(sed.get("arousal", 0.0)),
                    dominance=_safe_float(sed.get("dominance", 0.0)),
                )
            corrections = CriticCorrections(
                suggested_emotion_delta=suggested_emotion,
                suggested_action=corrections_data.get("suggested_action"),
                suggested_key_point_addition=corrections_data.get(
                    "suggested_key_point_addition"
                ),
                narrative_risk_flag=bool(
                    corrections_data.get("narrative_risk_flag", False)
                ),
            )

        return CriticVerdict(
            verdict=str(data.get("verdict", CriticVerdictType.ACCEPT)),
            checks=checks,
            overall_confidence=_safe_float(data.get("overall_confidence", 1.0)),
            corrections=corrections,
            override_recommendation=data.get("override_recommendation"),
        )

    def parse_atmosphere_output(self, response: str) -> AtmosphereOutput:
        """
        解析 LLM 响应为 AtmosphereOutput
        """
        data = self._extract_json(response)
        if data is None:
            return AtmosphereOutput()

        env_data = data.get("environment", {})
        environment = AtmosphereEnvironment(
            visual=str(env_data.get("visual", "")),
            auditory=str(env_data.get("auditory", "")),
            olfactory=str(env_data.get("olfactory", "")),
            thermal=str(env_data.get("thermal", "")),
            spatial=str(env_data.get("spatial", "")),
        )

        narr_data = data.get("narration", {})
        narration = AtmosphereNarration(
            transition=narr_data.get("transition"),
            inner_voice=narr_data.get("inner_voice"),
            omniscient_note=narr_data.get("omniscient_note"),
        )

        stage_directions = [
            StageDirection(
                character=str(s.get("character", "")),
                action=str(s.get("action", "")),
                detail=str(s.get("detail", "")),
            )
            for s in data.get("stage_directions", [])
        ]

        mood_data = data.get("mood_declaration", {})
        mood = MoodDeclaration(
            dominant_emotion=str(mood_data.get("dominant_emotion", ToneType.NEUTRAL)),
            intensity=_safe_float(mood_data.get("intensity", _DEFAULT_MOOD_INTENSITY)),
            color_palette=list(mood_data.get("color_palette", [])),
            pacing_hint=str(mood_data.get("pacing_hint", PaceLevel.NORMAL)),
        )

        return AtmosphereOutput(
            mode=str(data.get("mode", AtmosphereMode.LIGHT)),
            environment=environment,
            narration=narration,
            stage_directions=stage_directions,
            mood_declaration=mood,
            suggested_position=str(data.get("suggested_position", _DEFAULT_SUGGESTED_POSITION)),
            length_budget=str(data.get("length_budget", _DEFAULT_LENGTH_BUDGET)),
            priority=_safe_float(data.get("priority", _DEFAULT_ATMOSPHERE_PRIORITY)),
        )

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict[str, Any]]:
        """
        从 LLM 响应中提取 JSON 对象
        支持 ```json ... ``` 包裹和纯 JSON 两种格式
        """
        import json

        fenced = re.search(r"```(?:json)?\s*\n?(.*?)```", text, re.DOTALL)
        candidate = fenced.group(1).strip() if fenced else text.strip()

        try:
            result = json.loads(candidate)
            if isinstance(result, dict):
                return result
        except (json.JSONDecodeError, ValueError):
            pass

        brace_start = candidate.find("{")
        brace_end = candidate.rfind("}")
        if brace_start >= 0 and brace_end > brace_start:
            try:
                result = json.loads(candidate[brace_start : brace_end + 1])
                if isinstance(result, dict):
                    return result
            except (json.JSONDecodeError, ValueError):
                pass

        return None

    @staticmethod
    def _regex_extract_ir(text: str) -> Optional[Dict[str, Any]]:
        """
        正则兜底：当JSON解析完全失败时，从自然语言中提取关键字段
        """
        result: Dict[str, Any] = {}

        intent_patterns = [
            r'"intent"\s*:\s*"([^"]+)"',
            r'意图[：:]\s*(\w+)',
            r'intent\s*[：:=]\s*(\w+)',
        ]
        for pat in intent_patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                result["intent"] = m.group(1)
                break

        p_val = a_val = d_val = None
        for label, store in [("p", "p"), ("pleasure", "pleasure"),
                             ("a", "a"), ("arousal", "arousal"),
                             ("d", "d"), ("dominance", "dominance")]:
            m = re.search(rf'"{store}"\s*:\s*(-?[\d.]+)', text)
            if m:
                if store in ("p", "pleasure"):
                    p_val = _safe_float(m.group(1))
                elif store in ("a", "arousal"):
                    a_val = _safe_float(m.group(1))
                elif store in ("d", "dominance"):
                    d_val = _safe_float(m.group(1))

        if any(v is not None for v in (p_val, a_val, d_val)):
            result["emotion"] = {
                "p": p_val or 0.0,
                "a": a_val or 0.0,
                "d": d_val or 0.0,
            }

        kp_match = re.search(r'"key_points"\s*:\s*\[(.*?)\]', text, re.DOTALL)
        if kp_match:
            items = re.findall(r'"([^"]+)"', kp_match.group(1))
            if items:
                result["key_points"] = items

        return result if result else None
