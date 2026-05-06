import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from luqi_engine.scheduler.gap_precomputer import GapPrecomputer, GapTaskResult
from luqi_engine.core.types import (
    AtmosphereOutput,
    CanonicalIR,
    CriticVerdict,
    EmotionDelta,
    LLMResponse,
    NarrativeDelta,
    SDKType,
)


def _make_mock_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.get_sdk_type.return_value = SDKType.OPENAI
    return bridge


def _make_mock_novel_agent(delta: NarrativeDelta = None) -> MagicMock:
    agent = MagicMock()
    default = delta or NarrativeDelta(narrative_note="test_novel")
    agent.run = AsyncMock(return_value=default)
    return agent


def _make_mock_critic_agent(verdict: CriticVerdict = None) -> MagicMock:
    agent = MagicMock()
    default = verdict or CriticVerdict(verdict="accept")
    agent.run = AsyncMock(return_value=default)
    return agent


def _make_mock_dialogue_agent(ir: CanonicalIR = None) -> MagicMock:
    agent = MagicMock()
    default = ir or CanonicalIR(intent="test", confidence=0.9)
    agent.run = AsyncMock(return_value=default)
    return agent


def _make_mock_atmosphere_agent(output: AtmosphereOutput = None) -> MagicMock:
    agent = MagicMock()
    default = output or AtmosphereOutput()
    agent.run = AsyncMock(return_value=default)
    return agent


class TestGapPrecomputerInit:
    def test_initial_cache_is_empty(self):
        precomputer = GapPrecomputer()
        assert precomputer.get_cached_results() == {}

    def test_clear_cache_on_empty(self):
        precomputer = GapPrecomputer()
        precomputer.clear_cache()
        assert precomputer.get_cached_results() == {}


class TestGapPrecomputerTaskA:
    def test_novel_update_success(self):
        precomputer = GapPrecomputer()
        delta = NarrativeDelta(narrative_note="incremental_update")
        novel_agent = _make_mock_novel_agent(delta)
        bridge = _make_mock_bridge()

        result = asyncio.run(
            precomputer.task_a_novel_update(novel_agent, {"narrative_context": "test"}, bridge)
        )
        assert result.success is True
        assert result.task_name == "novel_update"
        assert result.result is delta

    def test_novel_update_cached(self):
        precomputer = GapPrecomputer()
        delta = NarrativeDelta(narrative_note="cached_delta")
        novel_agent = _make_mock_novel_agent(delta)
        bridge = _make_mock_bridge()

        asyncio.run(
            precomputer.task_a_novel_update(novel_agent, {}, bridge)
        )
        cached = precomputer.get_cached_results()
        assert "novel" in cached
        assert cached["novel"] is delta

    def test_novel_update_failure(self):
        precomputer = GapPrecomputer()
        novel_agent = MagicMock()
        novel_agent.run = AsyncMock(side_effect=RuntimeError("LLM不可用"))
        bridge = _make_mock_bridge()

        result = asyncio.run(
            precomputer.task_a_novel_update(novel_agent, {}, bridge)
        )
        assert result.success is False
        assert "LLM不可用" in result.error_message


class TestGapPrecomputerTaskB:
    def test_critic_precheck_success(self):
        precomputer = GapPrecomputer()
        verdict = CriticVerdict(verdict="accept", overall_confidence=0.9)
        critic_agent = _make_mock_critic_agent(verdict)
        bridge = _make_mock_bridge()

        result = asyncio.run(
            precomputer.task_b_critic_precheck(critic_agent, {"canonical_ir": {}}, bridge)
        )
        assert result.success is True
        assert result.result is verdict

    def test_critic_precheck_failure(self):
        precomputer = GapPrecomputer()
        critic_agent = MagicMock()
        critic_agent.run = AsyncMock(side_effect=RuntimeError("超时"))
        bridge = _make_mock_bridge()

        result = asyncio.run(
            precomputer.task_b_critic_precheck(critic_agent, {}, bridge)
        )
        assert result.success is False


class TestGapPrecomputerTaskC:
    def test_dialogue_preanalyze_success(self):
        precomputer = GapPrecomputer()
        ir = CanonicalIR(intent="greet", confidence=0.85)
        dialogue_agent = _make_mock_dialogue_agent(ir)
        bridge = _make_mock_bridge()

        result = asyncio.run(
            precomputer.task_c_dialogue_preanalyze(dialogue_agent, {"user_message": "你好"}, bridge)
        )
        assert result.success is True
        assert result.result is ir

    def test_dialogue_preanalyze_failure(self):
        precomputer = GapPrecomputer()
        dialogue_agent = MagicMock()
        dialogue_agent.run = AsyncMock(side_effect=RuntimeError("连接失败"))
        bridge = _make_mock_bridge()

        result = asyncio.run(
            precomputer.task_c_dialogue_preanalyze(dialogue_agent, {}, bridge)
        )
        assert result.success is False


class TestGapPrecomputerTaskD:
    def test_atmosphere_prerender_success(self):
        precomputer = GapPrecomputer()
        output = AtmosphereOutput(mode="light")
        atmosphere_agent = _make_mock_atmosphere_agent(output)
        bridge = _make_mock_bridge()

        result = asyncio.run(
            precomputer.task_d_atmosphere_prerender(atmosphere_agent, {"scene_name": "森林"}, bridge)
        )
        assert result.success is True
        assert result.result is output

    def test_atmosphere_prerender_failure(self):
        precomputer = GapPrecomputer()
        atmosphere_agent = MagicMock()
        atmosphere_agent.run = AsyncMock(side_effect=RuntimeError("渲染失败"))
        bridge = _make_mock_bridge()

        result = asyncio.run(
            precomputer.task_d_atmosphere_prerender(atmosphere_agent, {}, bridge)
        )
        assert result.success is False


class TestGapPrecomputerRunAllTasks:
    def test_run_all_tasks_parallel(self):
        precomputer = GapPrecomputer()
        novel_agent = _make_mock_novel_agent()
        critic_agent = _make_mock_critic_agent()
        dialogue_agent = _make_mock_dialogue_agent()
        atmosphere_agent = _make_mock_atmosphere_agent()
        bridge = _make_mock_bridge()

        results = asyncio.run(
            precomputer.run_all_tasks(
                novel_agent, critic_agent, dialogue_agent, atmosphere_agent,
                {"narrative_context": "test"}, bridge,
            )
        )
        assert len(results) == 4
        assert all(r.success for r in results)

    def test_run_all_tasks_caches_all(self):
        precomputer = GapPrecomputer()
        novel_agent = _make_mock_novel_agent()
        critic_agent = _make_mock_critic_agent()
        dialogue_agent = _make_mock_dialogue_agent()
        atmosphere_agent = _make_mock_atmosphere_agent()
        bridge = _make_mock_bridge()

        asyncio.run(
            precomputer.run_all_tasks(
                novel_agent, critic_agent, dialogue_agent, atmosphere_agent,
                {}, bridge,
            )
        )
        cached = precomputer.get_cached_results()
        assert "novel" in cached
        assert "critic" in cached
        assert "dialogue" in cached
        assert "atmosphere" in cached

    def test_run_all_tasks_partial_failure(self):
        precomputer = GapPrecomputer()
        novel_agent = _make_mock_novel_agent()
        critic_agent = MagicMock()
        critic_agent.run = AsyncMock(side_effect=RuntimeError("critic失败"))
        dialogue_agent = _make_mock_dialogue_agent()
        atmosphere_agent = _make_mock_atmosphere_agent()
        bridge = _make_mock_bridge()

        results = asyncio.run(
            precomputer.run_all_tasks(
                novel_agent, critic_agent, dialogue_agent, atmosphere_agent,
                {}, bridge,
            )
        )
        success_count = sum(1 for r in results if r.success)
        failure_count = sum(1 for r in results if not r.success)
        assert success_count == 3
        assert failure_count == 1


class TestGapPrecomputerClearCache:
    def test_clear_cache_after_run(self):
        precomputer = GapPrecomputer()
        novel_agent = _make_mock_novel_agent()
        critic_agent = _make_mock_critic_agent()
        dialogue_agent = _make_mock_dialogue_agent()
        atmosphere_agent = _make_mock_atmosphere_agent()
        bridge = _make_mock_bridge()

        asyncio.run(
            precomputer.run_all_tasks(
                novel_agent, critic_agent, dialogue_agent, atmosphere_agent,
                {}, bridge,
            )
        )
        assert len(precomputer.get_cached_results()) == 4

        precomputer.clear_cache()
        assert precomputer.get_cached_results() == {}
