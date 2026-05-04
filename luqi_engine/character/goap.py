"""
GOAP规划器 - 基于目标导向行动规划的A*搜索
实现世界状态表示、行动定义和启发式路径规划
"""

from __future__ import annotations

import heapq
import math
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, FrozenSet, List, Optional, Set, Tuple

from luqi_engine.core.rng import PCGRandom

_GOAP_DEFAULT_COST: float = 1.0
_GOAP_MAX_SEARCH_NODES: int = 1000
_GOAP_HEURISTIC_WEIGHT: float = 1.0
_GOAP_STATE_MATCH_TOLERANCE: float = 1e-6

_GOAP_PLEASURE_THREAT_THRESHOLD: float = -0.3
_GOAP_AROUSAL_SOCIAL_HIGH_THRESHOLD: float = 0.5
_GOAP_PLEASURE_SOCIAL_POSITIVE_THRESHOLD: float = 0.2
_GOAP_AROUSAL_SOCIAL_NEGATIVE_THRESHOLD: float = 0.4
_GOAP_PLEASURE_NEGATIVE_NEUTRAL: float = 0.0
_GOAP_PLEASURE_GROWTH_THRESHOLD: float = 0.3
_GOAP_OCEAN_OPENNESS_REFLECTIVE_THRESHOLD: float = 65.0
_GOAP_OCEAN_EXTRAVERSION_SOCIAL_THRESHOLD: float = 60.0
_GOAP_OCEAN_SCORE_DEFAULT: float = 50.0

_ASTAR_COUNTER_INIT: int = 0


class GOAPWorldState:
    _TOLERANCE: ClassVar[float] = _GOAP_STATE_MATCH_TOLERANCE

    def __init__(self, data: Optional[Dict[str, Any]] = None) -> None:
        self._data: Dict[str, Any] = dict(data) if data is not None else {}

    def get(self, key: str, default: Any = None) -> Any:
        return self._data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value

    def satisfies(self, goal: GOAPWorldState) -> bool:
        for key, goal_value in goal._data.items():
            current = self._data.get(key)
            if current is None:
                return False
            if isinstance(goal_value, (int, float)) and isinstance(current, (int, float)):
                if abs(current - goal_value) > self._TOLERANCE:
                    return False
            elif current != goal_value:
                return False
        return True

    def apply(self, effects: Dict[str, Any]) -> GOAPWorldState:
        new_data = dict(self._data)
        for key, value in effects.items():
            if isinstance(value, dict) and key in new_data and isinstance(new_data[key], dict):
                merged = dict(new_data[key])
                merged.update(value)
                new_data[key] = merged
            else:
                new_data[key] = value
        return GOAPWorldState(new_data)

    def unsatisfied_count(self, goal: GOAPWorldState) -> int:
        count = 0
        for key, goal_value in goal._data.items():
            current = self._data.get(key)
            if current is None:
                count += 1
            elif isinstance(goal_value, (int, float)) and isinstance(current, (int, float)):
                if abs(current - goal_value) > self._TOLERANCE:
                    count += 1
            elif current != goal_value:
                count += 1
        return count

    def fingerprint(self) -> str:
        return str(sorted(self._data.items()))

    @property
    def data(self) -> Dict[str, Any]:
        return dict(self._data)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GOAPWorldState):
            return NotImplemented
        return self._data == other._data

    def __hash__(self) -> int:
        return hash(tuple(sorted(self._data.items())))


@dataclass
class GOAPAction:
    DEFAULT_COST: ClassVar[float] = _GOAP_DEFAULT_COST

    name: str
    preconditions: Dict[str, Any] = field(default_factory=dict)
    effects: Dict[str, Any] = field(default_factory=dict)
    cost: float = _GOAP_DEFAULT_COST

    def is_valid(self, state: GOAPWorldState) -> bool:
        check = GOAPWorldState(self.preconditions)
        return state.satisfies(check)

    def execute(self, state: GOAPWorldState) -> GOAPWorldState:
        return state.apply(self.effects)


_GOAP_DEFAULT_GOALS: Dict[str, GOAPWorldState] = {
    "safety": GOAPWorldState(data={"threat_avoided": True, "situation_assessed": True}),
    "social": GOAPWorldState(data={"conversation_started": True, "is_alone": False}),
    "expression": GOAPWorldState(data={"conversation_started": True, "is_alone": False}),
    "growth": GOAPWorldState(data={"situation_assessed": True, "memory_reflected": True}),
    "reflection": GOAPWorldState(data={"memory_reflected": True, "has_memory": True}),
    "comfort": GOAPWorldState(data={"situation_assessed": True, "is_alone": False}),
}


class _SearchNode:
    __slots__ = ("state", "g_cost", "h_cost", "f_cost", "action", "parent", "counter")

    def __init__(
        self,
        state: GOAPWorldState,
        g_cost: float,
        h_cost: float,
        action: Optional[GOAPAction],
        parent: Optional[_SearchNode],
        counter: int,
    ) -> None:
        self.state = state
        self.g_cost = g_cost
        self.h_cost = h_cost
        self.f_cost = g_cost + h_cost
        self.action = action
        self.parent = parent
        self.counter = counter

    def __lt__(self, other: _SearchNode) -> bool:
        if self.f_cost != other.f_cost:
            return self.f_cost < other.f_cost
        return self.counter < other.counter


class GOAPPlanner:
    MAX_SEARCH_NODES: ClassVar[int] = _GOAP_MAX_SEARCH_NODES
    HEURISTIC_WEIGHT: ClassVar[float] = _GOAP_HEURISTIC_WEIGHT

    def __init__(self, actions: Optional[List[GOAPAction]] = None) -> None:
        self._actions: List[GOAPAction] = list(actions) if actions is not None else []
        self._counter: int = _ASTAR_COUNTER_INIT

    def add_action(self, action: GOAPAction) -> None:
        self._actions.append(action)

    def remove_action(self, name: str) -> None:
        self._actions = [a for a in self._actions if a.name != name]

    def plan(
        self,
        start: GOAPWorldState,
        goal: GOAPWorldState,
    ) -> Optional[List[GOAPAction]]:
        if start.satisfies(goal):
            return []
        self._counter = _ASTAR_COUNTER_INIT
        h = self._heuristic(start, goal)
        start_node = _SearchNode(
            state=start,
            g_cost=0.0,
            h_cost=h,
            action=None,
            parent=None,
            counter=self._next_counter(),
        )
        open_set: List[_SearchNode] = []
        heapq.heappush(open_set, start_node)
        closed_set: Set[str] = set()
        nodes_explored = 0
        while open_set and nodes_explored < self.MAX_SEARCH_NODES:
            current = heapq.heappop(open_set)
            state_key = current.state.fingerprint()
            if state_key in closed_set:
                continue
            closed_set.add(state_key)
            nodes_explored += 1
            if current.state.satisfies(goal):
                return self._reconstruct_path(current)
            for action in self._actions:
                if not action.is_valid(current.state):
                    continue
                new_state = action.execute(current.state)
                new_key = new_state.fingerprint()
                if new_key in closed_set:
                    continue
                new_g = current.g_cost + action.cost
                new_h = self._heuristic(new_state, goal)
                neighbor = _SearchNode(
                    state=new_state,
                    g_cost=new_g,
                    h_cost=new_h,
                    action=action,
                    parent=current,
                    counter=self._next_counter(),
                )
                heapq.heappush(open_set, neighbor)
        return None

    def _heuristic(self, state: GOAPWorldState, goal: GOAPWorldState) -> float:
        return state.unsatisfied_count(goal) * self.HEURISTIC_WEIGHT

    def _next_counter(self) -> int:
        self._counter += 1
        return self._counter

    def _reconstruct_path(self, node: _SearchNode) -> List[GOAPAction]:
        path: List[GOAPAction] = []
        current = node
        while current.parent is not None:
            if current.action is not None:
                path.append(current.action)
            current = current.parent
        path.reverse()
        return path

    @property
    def available_actions(self) -> List[str]:
        return [a.name for a in self._actions]


class GOAPGoalSelector:
    DEFAULT_GOALS: ClassVar[Dict[str, GOAPWorldState]] = _GOAP_DEFAULT_GOALS

    def __init__(self, rng: Optional[PCGRandom] = None) -> None:
        self._rng = rng if rng is not None else PCGRandom()

    def select_goal(self, pad_state: Dict[str, float], ocean_state: Optional[Dict[str, float]] = None) -> GOAPWorldState:
        """根据PAD/OCEAN状态选择GOAP目标世界状态"""
        p = pad_state.get("pleasure", 0.0)
        a = pad_state.get("arousal", 0.0)
        d = pad_state.get("dominance", 0.0)

        if p < _GOAP_PLEASURE_THREAT_THRESHOLD:
            return GOAPWorldState(data={"threat_avoided": True, "situation_assessed": True})
        if a > _GOAP_AROUSAL_SOCIAL_HIGH_THRESHOLD and p > _GOAP_PLEASURE_SOCIAL_POSITIVE_THRESHOLD:
            return GOAPWorldState(data={"conversation_started": True, "is_alone": False})
        if a > _GOAP_AROUSAL_SOCIAL_NEGATIVE_THRESHOLD and p < _GOAP_PLEASURE_NEGATIVE_NEUTRAL:
            return GOAPWorldState(data={"conversation_started": True, "is_alone": False})
        if p > _GOAP_PLEASURE_GROWTH_THRESHOLD:
            return GOAPWorldState(data={"situation_assessed": True, "memory_reflected": True})
        if ocean_state is not None and ocean_state.get("openness", _GOAP_OCEAN_SCORE_DEFAULT) > _GOAP_OCEAN_OPENNESS_REFLECTIVE_THRESHOLD:
            return GOAPWorldState(data={"memory_reflected": True, "has_memory": True})
        if ocean_state is not None and ocean_state.get("extraversion", _GOAP_OCEAN_SCORE_DEFAULT) > _GOAP_OCEAN_EXTRAVERSION_SOCIAL_THRESHOLD:
            return GOAPWorldState(data={"conversation_started": True, "is_alone": False})
        return GOAPWorldState(data={"situation_assessed": True, "is_alone": False})
