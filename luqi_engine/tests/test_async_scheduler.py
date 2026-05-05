"""异步调度器测试"""

import pytest

from luqi_engine.scheduler.async_scheduler import AsyncTaskScheduler, EngineState, _TransitionError


class TestEngineStateEnum:
    def test_all_states_exist(self):
        assert EngineState.IDLE is not None
        assert EngineState.SYNC is not None
        assert EngineState.RESPONDING is not None
        assert EngineState.ASYNC_PREP is not None
        assert EngineState.READY is not None
        assert EngineState.AUTO is not None

    def test_state_values_are_unique(self):
        values = [s.value for s in EngineState]
        assert len(values) == len(set(values))


class TestAsyncTaskSchedulerInit:
    def test_initial_state_is_idle(self):
        scheduler = AsyncTaskScheduler()
        assert scheduler.get_state() == EngineState.IDLE

    def test_can_accept_input_initially(self):
        scheduler = AsyncTaskScheduler()
        assert scheduler.can_accept_input() is True

    def test_is_auto_mode_initially_false(self):
        scheduler = AsyncTaskScheduler()
        assert scheduler.is_auto_mode() is False


class TestAsyncTaskSchedulerHappyPath:
    def test_full_lifecycle_idle_to_auto(self):
        scheduler = AsyncTaskScheduler()
        assert scheduler.get_state() == EngineState.IDLE

        scheduler.start_sync()
        assert scheduler.get_state() == EngineState.SYNC

        scheduler.start_responding()
        assert scheduler.get_state() == EngineState.RESPONDING

        scheduler.start_async_prep()
        assert scheduler.get_state() == EngineState.ASYNC_PREP

        scheduler.mark_ready()
        assert scheduler.get_state() == EngineState.READY
        assert scheduler.can_accept_input() is True

        scheduler.enter_auto()
        assert scheduler.get_state() == EngineState.AUTO
        assert scheduler.is_auto_mode() is True

    def test_auto_to_sync_on_user_input(self):
        scheduler = AsyncTaskScheduler()
        scheduler.start_sync()
        scheduler.start_responding()
        scheduler.start_async_prep()
        scheduler.mark_ready()
        scheduler.enter_auto()

        scheduler.start_sync()
        assert scheduler.get_state() == EngineState.SYNC
        assert scheduler.is_auto_mode() is False

    def test_ready_to_sync_directly(self):
        scheduler = AsyncTaskScheduler()
        scheduler.start_sync()
        scheduler.start_responding()
        scheduler.start_async_prep()
        scheduler.mark_ready()

        scheduler.start_sync()
        assert scheduler.get_state() == EngineState.SYNC


class TestAsyncTaskSchedulerReset:
    def test_reset_from_any_state(self):
        scheduler = AsyncTaskScheduler()
        scheduler.start_sync()
        assert scheduler.get_state() == EngineState.SYNC

        scheduler.reset()
        assert scheduler.get_state() == EngineState.IDLE
        assert scheduler.can_accept_input() is True

    def test_reset_from_auto(self):
        scheduler = AsyncTaskScheduler()
        scheduler.start_sync()
        scheduler.start_responding()
        scheduler.start_async_prep()
        scheduler.mark_ready()
        scheduler.enter_auto()

        scheduler.reset()
        assert scheduler.get_state() == EngineState.IDLE
        assert scheduler.is_auto_mode() is False


class TestAsyncTaskSchedulerInvalidTransitions:
    def test_idle_cannot_enter_auto(self):
        scheduler = AsyncTaskScheduler()
        with pytest.raises(_TransitionError):
            scheduler.enter_auto()

    def test_idle_cannot_responding(self):
        scheduler = AsyncTaskScheduler()
        with pytest.raises(_TransitionError):
            scheduler.start_responding()

    def test_idle_cannot_async_prep(self):
        scheduler = AsyncTaskScheduler()
        with pytest.raises(_TransitionError):
            scheduler.start_async_prep()

    def test_idle_cannot_mark_ready(self):
        scheduler = AsyncTaskScheduler()
        with pytest.raises(_TransitionError):
            scheduler.mark_ready()

    def test_sync_cannot_enter_auto(self):
        scheduler = AsyncTaskScheduler()
        scheduler.start_sync()
        with pytest.raises(_TransitionError):
            scheduler.enter_auto()

    def test_auto_cannot_mark_ready(self):
        scheduler = AsyncTaskScheduler()
        scheduler.start_sync()
        scheduler.start_responding()
        scheduler.start_async_prep()
        scheduler.mark_ready()
        scheduler.enter_auto()
        with pytest.raises(_TransitionError):
            scheduler.mark_ready()

    def test_responding_cannot_enter_auto(self):
        scheduler = AsyncTaskScheduler()
        scheduler.start_sync()
        scheduler.start_responding()
        with pytest.raises(_TransitionError):
            scheduler.enter_auto()


class TestAsyncTaskSchedulerCanAcceptInput:
    def test_idle_accepts_input(self):
        scheduler = AsyncTaskScheduler()
        assert scheduler.can_accept_input() is True

    def test_sync_rejects_input(self):
        scheduler = AsyncTaskScheduler()
        scheduler.start_sync()
        assert scheduler.can_accept_input() is False

    def test_responding_rejects_input(self):
        scheduler = AsyncTaskScheduler()
        scheduler.start_sync()
        scheduler.start_responding()
        assert scheduler.can_accept_input() is False

    def test_async_prep_rejects_input(self):
        scheduler = AsyncTaskScheduler()
        scheduler.start_sync()
        scheduler.start_responding()
        scheduler.start_async_prep()
        assert scheduler.can_accept_input() is False

    def test_ready_accepts_input(self):
        scheduler = AsyncTaskScheduler()
        scheduler.start_sync()
        scheduler.start_responding()
        scheduler.start_async_prep()
        scheduler.mark_ready()
        assert scheduler.can_accept_input() is True

    def test_auto_accepts_input(self):
        scheduler = AsyncTaskScheduler()
        scheduler.start_sync()
        scheduler.start_responding()
        scheduler.start_async_prep()
        scheduler.mark_ready()
        scheduler.enter_auto()
        assert scheduler.can_accept_input() is True
