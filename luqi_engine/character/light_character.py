from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Set, Tuple

from luqi_engine.core.types import EntityId, generate_entity_id
from luqi_engine.core.rng import PCGRandom
from luqi_engine.character.emotion import ocean_to_pad_baseline

_OCEAN_SCORE_MIN: float = 0.0
_OCEAN_SCORE_MAX: float = 100.0
_OCEAN_SCORE_MIDPOINT: float = 50.0
_OCEAN_DIMENSION_NAMES: Tuple[str, ...] = (
    "openness",
    "conscientiousness",
    "extraversion",
    "agreeableness",
    "neuroticism",
)
_PAD_DIMENSION_NAMES: Tuple[str, ...] = ("pleasure", "arousal", "dominance")
_PAD_DIMENSION_MIN: float = -1.0
_PAD_DIMENSION_MAX: float = 1.0

_DEFAULT_SPOKEN_ROUND: int = -1
_DEFAULT_COOLDOWN_ROUNDS: int = 3
_RECENT_ACTIONS_MAX_CAPACITY: int = 5
_ENTITY_ID_PREFIX: str = "lc"

_EXTRAVERSION_WEIGHT_BASE: float = 1.0
_EXTRAVERSION_WEIGHT_SCALE: float = 0.02
_RECENT_ACTION_PENALTY: float = 0.5
_WEIGHT_MIN: float = 0.01

_RNG_DEFAULT_SEED: int = 0

_DEDUP_KEY_DELIMITER: str = "::"


def _clamp_ocean(value: float) -> float:
    return max(_OCEAN_SCORE_MIN, min(_OCEAN_SCORE_MAX, value))


def _clamp_pad(value: float) -> float:
    return max(_PAD_DIMENSION_MIN, min(_PAD_DIMENSION_MAX, value))


def _make_dedup_key(name: str, scene: str) -> str:
    return f"{name}{_DEDUP_KEY_DELIMITER}{scene}"


@dataclass
class LightCharacter:
    entity_id: str
    name: str
    archetype: str
    ocean: Dict[str, float]
    pad: Dict[str, float]
    scene: str
    speech_style: str
    last_spoken_round: int = _DEFAULT_SPOKEN_ROUND
    recent_actions: List[str] = field(default_factory=list)
    cooldown: int = _DEFAULT_COOLDOWN_ROUNDS

    MAX_RECENT_ACTIONS: ClassVar[int] = _RECENT_ACTIONS_MAX_CAPACITY

    def add_recent_action(self, action: str) -> None:
        self.recent_actions.append(action)
        if len(self.recent_actions) > self.MAX_RECENT_ACTIONS:
            self.recent_actions = self.recent_actions[-self.MAX_RECENT_ACTIONS:]


class LightCharacterSubsystem:
    _ENTITY_PREFIX: ClassVar[str] = _ENTITY_ID_PREFIX

    def __init__(self, seed: int = _RNG_DEFAULT_SEED) -> None:
        self._characters: Dict[EntityId, LightCharacter] = {}
        self._scene_index: Dict[str, List[EntityId]] = {}
        self._dedup_keys: Set[str] = set()
        self._rng: PCGRandom = PCGRandom(seed=seed)

    def create_batch(self, archetypes_config: List[Dict[str, Any]]) -> List[LightCharacter]:
        created: List[LightCharacter] = []
        for config in archetypes_config:
            name = config.get("name", "")
            scene = config.get("scene", "")
            dedup_key = _make_dedup_key(name, scene)
            if dedup_key in self._dedup_keys:
                continue

            ocean_raw = config.get("ocean", {})
            ocean: Dict[str, float] = {}
            for dim in _OCEAN_DIMENSION_NAMES:
                ocean[dim] = _clamp_ocean(float(ocean_raw.get(dim, _OCEAN_SCORE_MIDPOINT)))

            pad_raw = config.get("pad")
            if pad_raw is not None:
                pad: Dict[str, float] = {}
                for dim in _PAD_DIMENSION_NAMES:
                    pad[dim] = _clamp_pad(float(pad_raw.get(dim, 0.0)))
            else:
                pad_state = ocean_to_pad_baseline(ocean)
                pad = {
                    "pleasure": pad_state.pleasure,
                    "arousal": pad_state.arousal,
                    "dominance": pad_state.dominance,
                }

            entity_id = generate_entity_id(self._ENTITY_PREFIX)
            character = LightCharacter(
                entity_id=entity_id,
                name=name,
                archetype=config.get("archetype", ""),
                ocean=ocean,
                pad=pad,
                scene=scene,
                speech_style=config.get("speech_style", ""),
                last_spoken_round=_DEFAULT_SPOKEN_ROUND,
                recent_actions=[],
                cooldown=config.get("cooldown", _DEFAULT_COOLDOWN_ROUNDS),
            )
            self._characters[entity_id] = character
            self._dedup_keys.add(dedup_key)
            if scene not in self._scene_index:
                self._scene_index[scene] = []
            self._scene_index[scene].append(entity_id)
            created.append(character)
        return created

    def get_characters_in_scene(self, scene_name: str) -> List[LightCharacter]:
        entity_ids = self._scene_index.get(scene_name, [])
        return [self._characters[eid] for eid in entity_ids if eid in self._characters]

    def select_speaker(
        self,
        round_num: int,
        scene_name: str,
        exclude_ids: Optional[Set[str]] = None,
    ) -> Optional[LightCharacter]:
        candidates = self.get_characters_in_scene(scene_name)
        if not candidates:
            return None

        exclude = exclude_ids or set()

        eligible: List[LightCharacter] = []
        for c in candidates:
            if c.entity_id in exclude:
                continue
            if c.last_spoken_round != _DEFAULT_SPOKEN_ROUND:
                if round_num - c.last_spoken_round < c.cooldown:
                    continue
            eligible.append(c)

        if not eligible:
            return None

        weights: List[float] = []
        for c in eligible:
            extraversion = c.ocean.get("extraversion", _OCEAN_SCORE_MIDPOINT)
            weight = _EXTRAVERSION_WEIGHT_BASE + extraversion * _EXTRAVERSION_WEIGHT_SCALE

            if self._is_in_others_recent_actions(c, candidates):
                weight *= _RECENT_ACTION_PENALTY

            weights.append(max(weight, _WEIGHT_MIN))

        chosen_idx = self._rng.weighted_choice(weights)
        return eligible[chosen_idx]

    def mark_spoken(self, entity_id: str, round_num: int, action: str = "") -> None:
        character = self._characters.get(entity_id)
        if character is None:
            return
        character.last_spoken_round = round_num
        if action:
            character.add_recent_action(action)

    def get_character(self, entity_id: str) -> Optional[LightCharacter]:
        return self._characters.get(entity_id)

    def _is_in_others_recent_actions(
        self, character: LightCharacter, scene_characters: List[LightCharacter]
    ) -> bool:
        for other in scene_characters:
            if other.entity_id == character.entity_id:
                continue
            for action in other.recent_actions:
                if character.entity_id in action or character.name in action:
                    return True
        return False
