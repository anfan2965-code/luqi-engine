"""自动模式测试"""

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from luqi_engine.scheduler.auto_mode import AutoModeExecutor, TickResult
from luqi_engine.core.types import (
    AtmosphereOutput,
    AutoModeConfig,
    CanonicalIR,
    CriticVerdict,
    EmotionDelta,
    LLMResponse,
    SDKType,
)
from luqi_engine.character.goap import GOAPPlanner, GOAPAction, GOAPWorldState


def _make_mock_bridge() -> MagicMock:
    bridge = MagicMock()
    bridge.get_sdk_type.return_value = SDKType.OPENAI
    return bridge


def _make_mock_dialogue_agent(ir: CanonicalIR = None) -> MagicMock:
    agent = MagicMock()
    default = ir or CanonicalIR(intent="respond", confidence=0.9)
    agent.run = AsyncMock(return_value=default)
    return agent


def _make_mock_critic_agent(verdict: CriticVerdict = None) -> MagicMock:
    agent = MagicMock()
    default = verdict or CriticVerdict(verdict="accept", overall_confidence=0.9)
    agent.run = AsyncMock(return_value=default)
    return agent


def _make_mock_atmosphere_agent(output: AtmosphereOutput = None) -> MagicMock:
    agent = MagicMock()
    default = output or AtmosphereOutput()
    agent.run = AsyncMock(return_value=default)
    return agent


def _run_tick(executor, dialogue_agent, critic_agent, atmosphere_agent, context, bridge, **kwargs):
    return asyncio.run(
        executor.execute_tick(
            dialogue_agent, critic_agent, atmosphere_agent, context, bridge, **kwargs,
        )
    )


class TestAutoModeExecutorInit:
    def test_default_config(self):
        executor = AutoModeExecutor()
        assert executor.get_tick_count() == 0
        assert executor.is_paused() is False

    def test_custom_config(self):
        config = AutoModeConfig(max_auto_ticks=5, npc_autonomy_level=0.8)
        executor = AutoModeExecutor(config=config)
        assert executor.get_tick_count() == 0


class TestAutoModeExecutorExecuteTick:
    def test_basic_tick_increments_count(self):
        executor = AutoModeExecutor()
        result = _run_tick(
            executor,
            _make_mock_dialogue_agent(),
            _make_mock_critic_agent(),
            _make_mock_atmosphere_agent(),
            {}, _make_mock_bridge(),
        )
        assert executor.get_tick_count() == 1
        assert result.tick_number == 1

    def test_tick_returns_dialogue_ir(self):
        ir = CanonicalIR(intent="greet", confidence=0.95, tone="warm")
        executor = AutoModeExecutor()
        result = _run_tick(
            executor,
            _make_mock_dialogue_agent(ir),
            _make_mock_critic_agent(),
            _make_mock_atmosphere_agent(),
            {}, _make_mock_bridge(),
        )
        assert result.dialogue_ir is ir

    def test_tick_returns_critic_verdict(self):
        verdict = CriticVerdict(verdict="accept", overall_confidence=0.9)
        executor = AutoModeExecutor()
        result = _run_tick(
            executor,
            _make_mock_dialogue_agent(),
            _make_mock_critic_agent(verdict),
            _make_mock_atmosphere_agent(),
            {}, _make_mock_bridge(),
        )
        assert result.critic_verdict is verdict

    def test_tick_returns_atmosphere_output(self):
        output = AtmosphereOutput(mode="light")
        executor = AutoModeExecutor()
        result = _run_tick(
            executor,
            _make_mock_dialogue_agent(),
            _make_mock_critic_agent(),
            _make_mock_atmosphere_agent(output),
            {}, _make_mock_bridge(),
        )
        assert result.atmosphere_output is output

    def test_rejected_by_critic_skips_atmosphere(self):
        ir = CanonicalIR(intent="attack", confidence=0.8)
        verdict = CriticVerdict(verdict="reject", overall_confidence=0.3)
        executor = AutoModeExecutor()
        result = _run_tick(
            executor,
            _make_mock_dialogue_agent(ir),
            _make_mock_critic_agent(verdict),
            _make_mock_atmosphere_agent(),
            {}, _make_mock_bridge(),
        )
        assert result.critic_verdict.verdict == "reject"
        assert result.atmosphere_output is None

    def test_dialogue_failure_returns_partial_result(self):
        executor = AutoModeExecutor()
        dialogue_agent = MagicMock()
        dialogue_agent.run = AsyncMock(side_effect=RuntimeError("LLM不可用"))
        result = _run_tick(
            executor,
            dialogue_agent,
            _make_mock_critic_agent(),
            _make_mock_atmosphere_agent(),
            {}, _make_mock_bridge(),
        )
        assert result.dialogue_ir is None
        assert result.critic_verdict is None
        assert executor.get_tick_count() == 1


class TestAutoModeExecutorBranchPoint:
    def test_branch_point_detected(self):
        ir = CanonicalIR(intent="choose", confidence=0.9, narrative_signal="branch_point")
        executor = AutoModeExecutor()
        assert executor.is_branch_point(ir) is True

    def test_non_branch_point(self):
        ir = CanonicalIR(intent="respond", confidence=0.9, narrative_signal=None)
        executor = AutoModeExecutor()
        assert executor.is_branch_point(ir) is False

    def test_branch_point_with_pause_enabled(self):
        ir = CanonicalIR(intent="choose", confidence=0.9, narrative_signal="branch_point")
        config = AutoModeConfig(pause_on_branch_point=True)
        executor = AutoModeExecutor(config=config)
        result = _run_tick(
            executor,
            _make_mock_dialogue_agent(ir),
            _make_mock_critic_agent(),
            _make_mock_atmosphere_agent(),
            {}, _make_mock_bridge(),
        )
        assert result.is_branch_point is True
        assert result.paused_at_branch is True
        assert executor.is_paused() is True

    def test_branch_point_without_pause(self):
        ir = CanonicalIR(intent="choose", confidence=0.9, narrative_signal="branch_point")
        config = AutoModeConfig(pause_on_branch_point=False)
        executor = AutoModeExecutor(config=config)
        result = _run_tick(
            executor,
            _make_mock_dialogue_agent(ir),
            _make_mock_critic_agent(),
            _make_mock_atmosphere_agent(),
            {}, _make_mock_bridge(),
        )
        assert result.is_branch_point is True
        assert result.paused_at_branch is False
        assert executor.is_paused() is False


class TestAutoModeExecutorPauseControl:
    def test_set_pause_at_branch(self):
        executor = AutoModeExecutor()
        assert executor.is_paused() is False

        executor.set_pause_at_branch(True)
        assert executor.is_paused() is True

        executor.set_pause_at_branch(False)
        assert executor.is_paused() is False


class TestAutoModeExecutorTickCount:
    def test_multiple_ticks(self):
        executor = AutoModeExecutor()
        dialogue_agent = _make_mock_dialogue_agent()
        critic_agent = _make_mock_critic_agent()
        atmosphere_agent = _make_mock_atmosphere_agent()
        bridge = _make_mock_bridge()

        for _ in range(5):
            _run_tick(executor, dialogue_agent, critic_agent, atmosphere_agent, {}, bridge)
        assert executor.get_tick_count() == 5

    def test_reset_ticks(self):
        executor = AutoModeExecutor()
        _run_tick(
            executor,
            _make_mock_dialogue_agent(),
            _make_mock_critic_agent(),
            _make_mock_atmosphere_agent(),
            {}, _make_mock_bridge(),
        )
        assert executor.get_tick_count() == 1

        executor.reset_ticks()
        assert executor.get_tick_count() == 0
        assert executor.is_paused() is False


class TestAutoModeExecutorWithGOAP:
    def test_goap_plan_injected_into_context(self):
        planner = GOAPPlanner()
        planner.add_action(GOAPAction(
            name="approach_character",
            preconditions={"distance": "far"},
            effects={"distance": "close"},
            cost=1.0,
        ))
        start = GOAPWorldState({"distance": "far"})
        goal = GOAPWorldState({"distance": "close"})

        executor = AutoModeExecutor()
        context = {}
        result = _run_tick(
            executor,
            _make_mock_dialogue_agent(),
            _make_mock_critic_agent(),
            _make_mock_atmosphere_agent(),
            context, _make_mock_bridge(),
            goap_planner=planner,
            goap_start_state=start,
            goap_goal_state=goal,
        )
        assert result.tick_number == 1
        assert "goap_next_action" in context
        assert context["goap_next_action"] == "approach_character"
