"""轮次调度器 - 管理多角色对话的轮次分配"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from luqi_engine.core.rng import PCGRandom


_DEFAULT_TURN_WEIGHTS: Dict[str, float] = {
    "main_char": 0.35,
    "secondary_char": 0.15,
    "user": 0.15,
    "atmosphere": 0.05,
    "silence": 0.10,
    "reaction": 0.20,
}

_DEFAULT_DIVERSITY_WINDOW: int = 10
_DEFAULT_STAGNATION_THRESHOLD: int = 5
_STAGNATION_BOOST_MAIN: float = 0.15
_STAGNATION_REDUCE_SILENCE: float = 0.15
_SCENE_SWITCH_MAX_ROUNDS: int = 30
_SCENE_SWITCH_MIN_DIVERSITY: float = 0.4
_PERIODIC_SCENE_SWITCH_INTERVAL: int = 40
_DIVERSITY_STAGNATION_THRESHOLD: float = 0.5
_CONSECUTIVE_DIALOGUE_LIMIT: int = 5
_USER_ABSENCE_BOOST: float = 0.10
_USER_ABSENCE_THRESHOLD: int = 10


class TurnScheduler:

    def __init__(
        self,
        config: Optional[Dict[str, float]] = None,
        rng: Optional[PCGRandom] = None,
    ) -> None:
        self._weights: Dict[str, float] = dict(config) if config is not None else dict(_DEFAULT_TURN_WEIGHTS)
        self._rng: PCGRandom = rng if rng is not None else PCGRandom()
        self._round_history: List[str] = []
        self._diversity_window: int = _DEFAULT_DIVERSITY_WINDOW
        self._stagnation_threshold: int = _DEFAULT_STAGNATION_THRESHOLD
        self._stagnation_counter: int = 0
        self._pending_user_response: bool = False
        self._consecutive_dialogue_count: int = 0
        self._last_user_round: int = -100

    def mark_user_addressed(self) -> None:
        self._pending_user_response = True

    def clear_user_addressed(self) -> None:
        self._pending_user_response = False

    def schedule_turn(self, round_num: int, user_present: bool = True) -> str:
        if self._pending_user_response and user_present:
            self._pending_user_response = False
            self._round_history.append("user")
            self._last_user_round = round_num
            self._consecutive_dialogue_count += 1
            return "user"

        if self._consecutive_dialogue_count >= _CONSECUTIVE_DIALOGUE_LIMIT:
            self._consecutive_dialogue_count = 0
            self._round_history.append("reaction")
            return "reaction"

        weights = dict(self._weights)
        if not user_present:
            user_weight = weights.pop("user", 0.0)
            weights["main_char"] = weights.get("main_char", 0.0) + user_weight

        if user_present and (round_num - self._last_user_round) > _USER_ABSENCE_THRESHOLD:
            weights["user"] = weights.get("user", 0.0) + _USER_ABSENCE_BOOST

        if self._stagnation_counter >= self._stagnation_threshold:
            weights["main_char"] = weights.get("main_char", 0.0) + _STAGNATION_BOOST_MAIN
            weights["silence"] = max(0.0, weights.get("silence", 0.0) - _STAGNATION_REDUCE_SILENCE)

        turn_types = list(weights.keys())
        weight_values = list(weights.values())
        idx = self._rng.weighted_choice(weight_values)
        selected = turn_types[idx]
        self._round_history.append(selected)

        if selected in ("main_char", "secondary_char", "user"):
            self._consecutive_dialogue_count += 1
        else:
            self._consecutive_dialogue_count = 0

        if selected == "user":
            self._last_user_round = round_num

        return selected

    def diversity_score(self) -> float:
        window = self._round_history[-self._diversity_window:]
        if not window:
            return 0.0
        unique_count = len(set(window))
        return unique_count / len(window)

    def auto_intervene(self) -> Optional[Dict[str, Any]]:
        if self.diversity_score() < _DIVERSITY_STAGNATION_THRESHOLD:
            self._stagnation_counter += 1
        else:
            self._stagnation_counter = 0
        if self._stagnation_counter >= self._stagnation_threshold:
            return {
                "action": "scene_switch",
                "boost_main": True,
                "reason": "diversity_stagnation",
            }
        return None

    def should_switch_scene(self, round_num: int, current_scene_rounds: int) -> bool:
        if current_scene_rounds > _SCENE_SWITCH_MAX_ROUNDS and self.diversity_score() < _SCENE_SWITCH_MIN_DIVERSITY:
            return True
        if self._stagnation_counter >= self._stagnation_threshold:
            return True
        if round_num % _PERIODIC_SCENE_SWITCH_INTERVAL == 0 and round_num > 0:
            return True
        return False

    def reset_stagnation(self) -> None:
        self._stagnation_counter = 0
