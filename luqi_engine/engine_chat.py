"""
EngineChat - 对话模块
负责对话功能、流式对话、意图分类
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, AsyncIterator, Dict, List, Optional

from luqi_engine.core.types import (
    EntityId, LLMRequest, LLMStreamChunk,
)
from luqi_engine.core.constants import (
    _MAX_INPUT_LENGTH,
    _REPETITION_MIN_TEXT_LENGTH,
    _REPETITION_SHORT_PATTERN_MIN,
    _REPETITION_SHORT_PATTERN_MAX,
    _REPETITION_MEDIUM_PATTERN_MIN,
    _REPETITION_MEDIUM_PATTERN_MAX,
    _REPETITION_LONG_PATTERN_MIN,
    _REPETITION_LONG_PATTERN_MAX,
    _REPETITION_CUTOFF_MIN,
    _REPETITION_NGRAM_SIZES,
    _REPETITION_NGRAM_GAP_MULTIPLIER,
    _REPETITION_NGRAM_POSITION_MULTIPLIER,
    _LOCAL_LLM_OUTPUT_REQUIREMENTS,
)
from luqi_engine.llm.dialogue_modes import DialogueMode
from luqi_engine.llm.intent_classifier import IntentLevel
from luqi_engine.orchestration.character_extractor import CharacterExtractor

_logger = logging.getLogger(__name__)


class EngineChat:
    """
    对话模块
    负责对话功能、流式对话、意图分类
    """

    def _validate_chat_input(self, user_input: str) -> Optional[Dict[str, str]]:
        """
        验证chat方法的输入参数
        
        Args:
            user_input: 用户输入字符串
            
        Returns:
            None if validation passes, error dict if validation fails
        """
        if not isinstance(user_input, str):
            return {"error": "invalid_input_type", "reply": "输入必须是字符串"}
        
        if len(user_input) > _MAX_INPUT_LENGTH:
            return {"error": "input_too_long", "reply": f"输入内容过长（最大{_MAX_INPUT_LENGTH}字符），请缩短。"}
        
        if not user_input.strip():
            return {"error": "empty_input", "reply": "请输入内容。"}
        
        return None

    def _prepare_chat_context(self, character_id: Optional[str]) -> Optional[Dict[str, str]]:
        """
        准备chat方法的上下文（初始化检查、节奏感知更新）
        
        Args:
            character_id: 角色ID
            
        Returns:
            None if preparation succeeds, error dict if preparation fails
        """
        try:
            self._ensure_initialized()
        except RuntimeError:
            return {"error": "engine_not_initialized", "reply": "引擎未初始化"}

        if self._scheduler is not None:
            try:
                self._scheduler.start_sync()
            except Exception as exc:
                _logger.warning("AsyncTaskScheduler start_sync 失败: %s", exc)

        now = time.time()
        if self._last_user_message_time > 0 and self._pace_sensor is not None:
            interval = now - self._last_user_message_time
            self._pace_sensor.update_pace(interval)
        self._last_user_message_time = now
        
        return None

    def _is_local_llm_fast_path(self) -> bool:
        """
        检查是否使用本地LLM快速路径
        
        Returns:
            True if using local LLM fast path, False otherwise
        """
        return (
            getattr(self._config.llm, 'sdk_type', '') == 'local_llm'
            and self._local_llm_adapter is not None
        )

    async def chat(
        self,
        user_input: str,
        character_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        四智能体协作数据流 — Phase 0→6
        Dialogue → SupremeCourt → Critic → Novelist → Atmosphere → Voice → Assemble
        
        委托给ChatOrchestrator.orchestrate()执行完整流水线
        
        Args:
            user_input: 用户输入
            character_id: 角色ID
            
        Returns:
            包含reply/character_id/narrative_version等字段的Dict
        """
        validation_error = self._validate_chat_input(user_input)
        if validation_error is not None:
            return validation_error
        
        context_error = self._prepare_chat_context(character_id)
        if context_error is not None:
            return context_error

        if self._orchestrator is None or self._character_extractor is None:
            return {"error": "orchestrator_not_initialized", "reply": "编排器未初始化"}
        
        target_char = self._resolve_character(character_id)
        if target_char is None:
            return {"error": "Character not found", "reply": "角色未找到"}
        
        is_local_llm_fast = self._is_local_llm_fast_path()
        result = await self._orchestrator.orchestrate(
            user_input, target_char, is_local_llm_fast, self._character_extractor,
        )
        result["character_id"] = character_id or ""
        return result

    async def chat_stream(
        self,
        character_id: EntityId,
        user_message: str,
        mode: DialogueMode = DialogueMode.MULTI_CHARACTER,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """
        流式对话 - 三级路由架构
        
        Args:
            character_id: 角色ID
            user_message: 用户消息
            mode: 对话模式
            history: 历史消息
            
        Raises:
            ValueError: 输入验证失败
            RuntimeError: LLM桥接器未初始化
        """
        if not isinstance(user_message, str):
            raise ValueError("user_message must be a string")
        
        if len(user_message) > _MAX_INPUT_LENGTH:
            raise ValueError(f"user_message too long (max {_MAX_INPUT_LENGTH} characters)")
        
        if not user_message.strip():
            raise ValueError("user_message cannot be empty")
        
        self._ensure_initialized()
        character = self._character_manager.get_character(character_id) if self._character_manager else None
        if character is None:
            raise ValueError("角色不存在: {}".format(character_id))

        intent_level = self._classify_intent(user_message)

        if intent_level == IntentLevel.MODERATE and self._local_llm_adapter is not None:
            async for chunk in self._chat_stream_via_local_llm(character, user_message, history):
                yield chunk
            return

        if intent_level == IntentLevel.COMPLEX:
            offline = self._intent_classifier.is_offline if self._intent_classifier else False
            if offline and self._local_llm_adapter is not None:
                async for chunk in self._chat_stream_via_local_llm(character, user_message, history):
                    yield chunk
                return

        if self._llm_bridge is None:
            raise RuntimeError("LLM桥接器未初始化")

        from luqi_engine.llm.prompt_builder import PromptContext
        context = self._build_prompt_context(character, mode)
        request = self._llm_bridge.build_request(context, user_message, history)
        from luqi_engine.llm.openai_adapter import _CHINESE_ONLY_GRAMMAR
        request.grammar = _CHINESE_ONLY_GRAMMAR

        from luqi_engine.llm.prompt_builder import _PREFIX_FORCE_TEXT
        prefix_len = len(_PREFIX_FORCE_TEXT)
        raw_text = ""
        prefix_stripped = False
        async for chunk in self._llm_bridge.chat_stream(request):
            if chunk and hasattr(chunk, 'delta') and chunk.delta:
                if not prefix_stripped and chunk.delta.startswith(_PREFIX_FORCE_TEXT):
                    chunk_delta = chunk.delta[prefix_len:]
                    if chunk_delta:
                        raw_text += chunk_delta
                        yield LLMStreamChunk(delta=chunk_delta, finish_reason=chunk.finish_reason if hasattr(chunk, 'finish_reason') else None)
                    prefix_stripped = True
                else:
                    raw_text += chunk.delta
                    yield chunk

        if raw_text:
            truncated = self._truncate_repetition_loop(raw_text)
            if truncated is not None and len(truncated) < len(raw_text):
                _logger.debug("检测到重复循环，截断 %d→%d 字符", len(raw_text), len(truncated))
                raw_text = truncated
            if self._output_corrector is not None:
                cleaned = self._output_corrector.parse_and_clean(raw_text)
                if cleaned != raw_text:
                    _logger.debug("后处理清理: %d→%d 字符", len(raw_text), len(cleaned))
                    raw_text = cleaned
                await self._output_corrector.correct(raw_text)

    def _resolve_character(self, character_id: Optional[str]) -> Any:
        """
        解析角色
        
        Args:
            character_id: 角色ID
            
        Returns:
            角色对象，未找到返回None
        """
        if character_id and self._character_manager is not None:
            char = self._character_manager.get_character(character_id)
            if char is not None:
                return char
        if self._character_manager is not None:
            all_chars = self._character_manager.list_characters() if hasattr(self._character_manager, 'list_characters') else []
            if all_chars:
                return self._character_manager.get_character(all_chars[0])
        return None

    @staticmethod
    def _truncate_repetition_loop(text: str) -> Optional[str]:
        """
        截断文本中的重复循环
        
        Args:
            text: 输入文本
            
        Returns:
            截断后的文本，无重复返回None
        """
        if not text or len(text) < _REPETITION_MIN_TEXT_LENGTH:
            return None
        
        # 模式1: 短模式重复检测
        for pattern, min_repeat in [
            (rf'(.{{{_REPETITION_SHORT_PATTERN_MIN},{_REPETITION_SHORT_PATTERN_MAX}}})[：:]\s*\1[：:]\s*\1', _REPETITION_SHORT_PATTERN_MIN),
            (rf'(.{{{_REPETITION_MEDIUM_PATTERN_MIN},{_REPETITION_MEDIUM_PATTERN_MAX}}})[，,]\s*\1([，,]\s*\1){{1,}}', _REPETITION_MEDIUM_PATTERN_MIN),
            (r'(（内心[：:].*?）)\s*\1', _REPETITION_SHORT_PATTERN_MIN),
            (rf'(.{{{_REPETITION_LONG_PATTERN_MIN},{_REPETITION_LONG_PATTERN_MAX}}})\s+\1\s+\1', _REPETITION_LONG_PATTERN_MIN),
        ]:
            match = re.search(pattern, text)
            if match:
                cutoff = match.start()
                if cutoff > _REPETITION_CUTOFF_MIN:
                    return text[:cutoff]
        
        # 模式2: n-gram重复检测
        for ngram_size in _REPETITION_NGRAM_SIZES:
            seen: Dict[str, int] = {}
            for i in range(len(text) - ngram_size + 1):
                ngram = text[i:i + ngram_size]
                if ngram in seen:
                    gap = i - seen[ngram]
                    if gap <= ngram_size * _REPETITION_NGRAM_GAP_MULTIPLIER and i > ngram_size * _REPETITION_NGRAM_POSITION_MULTIPLIER:
                        return text[:seen[ngram]]
                else:
                    seen[ngram] = i
        
        return None

    def _extract_personality(self, character: Any) -> Dict[str, float]:
        """
        提取OCEAN性格分数
        
        Args:
            character: 角色对象
            
        Returns:
            OCEAN性格分数Dict
        """
        if self._character_extractor is not None:
            return self._character_extractor.extract_personality(character)
        if not hasattr(character, 'personality'):
            return {}
        return {
            "openness": character.personality.get_score("openness"),
            "conscientiousness": character.personality.get_score("conscientiousness"),
            "extraversion": character.personality.get_score("extraversion"),
            "agreeableness": character.personality.get_score("agreeableness"),
            "neuroticism": character.personality.get_score("neuroticism"),
        }

    def _extract_emotion_pad(self, character: Any) -> Dict[str, float]:
        """
        提取PAD情感状态
        
        Args:
            character: 角色对象
            
        Returns:
            PAD情感状态Dict
        """
        if self._character_extractor is not None:
            return self._character_extractor.extract_emotion_pad(character)
        if not hasattr(character, 'emotion'):
            return {}
        return {
            "pleasure": character.emotion.pleasure,
            "arousal": character.emotion.arousal,
            "dominance": character.emotion.dominance,
        }

    def _extract_character_state(self, character: Any) -> Dict[str, Any]:
        """
        提取完整角色状态
        
        Args:
            character: 角色对象
            
        Returns:
            包含可用字段的Dict
        """
        if self._character_extractor is not None:
            return self._character_extractor.extract_character_state(character)
        state: Dict[str, Any] = {}
        if hasattr(character, 'name'):
            state["name"] = character.name
        if hasattr(character, 'personality'):
            state["personality"] = self._extract_personality(character)
        if hasattr(character, 'emotion'):
            state["emotion_pad"] = self._extract_emotion_pad(character)
        return state

    def _classify_intent(self, user_message: str) -> IntentLevel:
        """
        分类用户意图
        
        Args:
            user_message: 用户消息
            
        Returns:
            意图级别
        """
        if self._intent_classifier is None:
            return IntentLevel.COMPLEX
        return self._intent_classifier.classify(user_message)

    async def _chat_stream_via_local_llm(
        self,
        character: Any,
        user_message: str,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncIterator[LLMStreamChunk]:
        """
        通过本地LLM流式对话
        
        Args:
            character: 角色对象
            user_message: 用户消息
            history: 历史消息
            
        Yields:
            LLMStreamChunk
        """
        system_prompt = self._render_system_prompt(character)
        messages = [{"role": "system", "content": system_prompt}]
        if history:
            for msg in history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                })
        messages.append({"role": "user", "content": user_message})

        request = LLMRequest(
            sdk_type=self._local_llm_adapter.get_sdk_type() if self._local_llm_adapter else None,
            messages=messages,
            temperature=self._config.local_llm.local_llm_temperature,
            max_tokens=self._config.local_llm.local_llm_max_tokens,
        )
        if self._fallback is not None:
            async for chunk in self._fallback.get_local_llm_stream(request):
                yield chunk
            return
        if self._local_llm_adapter is not None:
            async for chunk in self._local_llm_adapter.chat_stream(request):
                yield chunk

    def _render_system_prompt(self, character: Any) -> str:
        """
        渲染本地LLM系统提示词
        
        Args:
            character: 角色对象
            
        Returns:
            系统提示词字符串
        """
        if self._character_extractor is not None:
            return self._character_extractor.render_system_prompt(character)
        if self._state_renderer is None:
            return ""
        personality = {
            "openness": character.personality.get_score("openness"),
            "conscientiousness": character.personality.get_score("conscientiousness"),
            "extraversion": character.personality.get_score("extraversion"),
            "agreeableness": character.personality.get_score("agreeableness"),
            "neuroticism": character.personality.get_score("neuroticism"),
        }
        pad_emotion = {
            "pleasure": character.emotion.pleasure,
            "arousal": character.emotion.arousal,
            "dominance": character.emotion.dominance,
        }
        return self._state_renderer.render_system_prompt(
            character_name=character.name,
            personality=personality,
            pad_emotion=pad_emotion,
            seven_emotions=getattr(character, "seven_emotions", None),
            scene="",
            behavior_instruction="",
            memories=[],
            background=getattr(character, "background", ""),
            output_requirements=_LOCAL_LLM_OUTPUT_REQUIREMENTS,
        )

    def _build_prompt_context(self, character: Any, mode: DialogueMode) -> Any:
        """
        构建LLM PromptContext
        
        Args:
            character: 角色对象
            mode: 对话模式
            
        Returns:
            PromptContext对象
        """
        if self._character_extractor is not None:
            return self._character_extractor.build_prompt_context(
                character, mode, self._world_guidance,
            )
        from luqi_engine.llm.prompt_builder import PromptContext
        return PromptContext(
            character_name=character.name,
            personality={
                "openness": character.personality.get_score("openness"),
                "conscientiousness": character.personality.get_score("conscientiousness"),
                "extraversion": character.personality.get_score("extraversion"),
                "agreeableness": character.personality.get_score("agreeableness"),
                "neuroticism": character.personality.get_score("neuroticism"),
            },
            emotion_pad={
                "pleasure": character.emotion.pleasure,
                "arousal": character.emotion.arousal,
                "dominance": character.emotion.dominance,
            },
            dominant_emotion=character.emotion.dominant_emotion if hasattr(character.emotion, 'dominant_emotion') else "neutral",
            memories=[],
            worldview_summary=self._world_guidance,
            narrative_rules=None,
            dialogue_mode_instruction=mode.value if hasattr(mode, 'value') else str(mode),
        )
