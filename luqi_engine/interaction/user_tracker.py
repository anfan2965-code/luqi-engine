"""用户追踪器 - 追踪用户交互状态"""

from __future__ import annotations

from typing import Any, Dict, Set


_STATUS_NOT_ARRIVED = "not_arrived"
_STATUS_PRESENT = "present"
_STATUS_DEPARTED = "departed"

_TOPIC_BONUS_UNRESPONDED = 0.3
_TOPIC_BONUS_RESPONDED = 0.0
_TOPIC_COOLDOWN_DEFAULT = 3

_CONSTRAINT_DEPARTED = "旅人已离开，不可对旅人说话，可用过去时提及或转向在场者"
_CONSTRAINT_NOT_ARRIVED = "旅人尚未到达，不可对旅人说话"
_CONSTRAINT_NONE = ""


class UserPresenceTracker:
    """
    用户在场追踪器
    追踪用户到达/离开/说话状态，管理话题影响冷却，确保角色不会对空气说话
    """

    def __init__(self) -> None:
        self._status: str = _STATUS_NOT_ARRIVED
        self._topic_active: bool = False
        self._topic_content: str = ""
        self._topic_round: int = -1
        self._topic_cooldown: int = _TOPIC_COOLDOWN_DEFAULT
        self._user_response_given: bool = False
        self._departure_round: int = -1
        self._arrival_round: int = -1
        self._responded_characters: Set[str] = set()

    def arrive(self, round_num: int) -> None:
        self._status = _STATUS_PRESENT
        self._arrival_round = round_num

    def depart(self, round_num: int) -> None:
        self._status = _STATUS_DEPARTED
        self._departure_round = round_num
        self._topic_active = False

    def speak(self, content: str, round_num: int) -> None:
        if self._status == _STATUS_PRESENT:
            self._topic_active = True
            self._topic_content = content
            self._topic_round = round_num
            self._user_response_given = False
            self._responded_characters.clear()

    def is_present(self) -> bool:
        return self._status == _STATUS_PRESENT

    def is_departed(self) -> bool:
        return self._status == _STATUS_DEPARTED

    def get_departure_constraint(self) -> str:
        if self._status == _STATUS_DEPARTED:
            return _CONSTRAINT_DEPARTED
        if self._status == _STATUS_NOT_ARRIVED:
            return _CONSTRAINT_NOT_ARRIVED
        return _CONSTRAINT_NONE

    def get_topic_bonus(self, character_id: str, round_num: int) -> float:
        if self._topic_active and (round_num - self._topic_round) <= self._topic_cooldown:
            if character_id not in self._responded_characters:
                return _TOPIC_BONUS_UNRESPONDED
            return _TOPIC_BONUS_RESPONDED
        self._topic_active = False
        return _TOPIC_BONUS_RESPONDED

    def mark_response(self, character_id: str) -> None:
        self._responded_characters.add(character_id)
        self._user_response_given = True

    def get_status_info(self) -> Dict[str, Any]:
        return {
            "status": self._status,
            "topic_active": self._topic_active,
            "topic_content": self._topic_content,
            "topic_round": self._topic_round,
            "user_response_given": self._user_response_given,
            "departure_round": self._departure_round,
        }
