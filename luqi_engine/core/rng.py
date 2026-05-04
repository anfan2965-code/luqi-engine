"""
PCG随机数与种子管理 - 基于PCG-XSH-RR变体的确定性随机数生成
提供多独立流管理和叙事种子层级派生
"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from typing import Any, ClassVar, Dict, List, Optional, Sequence, Tuple

_PCG_MULTIPLIER: int = 6364136223846793005
_PCG_DEFAULT_INCREMENT: int = 1442695040888963407
_PCG_XORSHIFT_SHIFT: int = 18
_PCG_OUTPUT_SHIFT: int = 27
_PCG_ROTATION_SHIFT: int = 59
_PCG_STATE_MASK: int = (1 << 64) - 1
_PCG_OUTPUT_MASK: int = (1 << 32) - 1
_PCG_ROTATION_MASK: int = 31

_UINT32_MAX: int = 0xFFFFFFFF
_UINT32_MAX_PLUS_ONE: float = float(_UINT32_MAX) + 1.0
_UNIFORM_UPPER_SHIFT: int = 11
_UNIFORM_LOWER_SHIFT: int = 21
_UNIFORM_COMBINED_SHIFT: int = 32
_UNIFORM_DENOMINATOR: float = float(1 << 53)
_UNIFORM_NUMERATOR_SCALE: float = float(1 << 53)
_GAUSSIAN_DEFAULT_MEAN: float = 0.0
_GAUSSIAN_DEFAULT_STDDEV: float = 1.0

_SEED_HIERARCHY_DELIMITER: str = ":"
_SHA256_HEX_LENGTH: int = 16
_SHA256_DIGEST_BYTES: int = 32


def _rotr32(value: int, rot: int) -> int:
    rotated = (value >> rot) | (value << ((_PCG_ROTATION_MASK - rot + 1) & _PCG_ROTATION_MASK))
    return rotated & _PCG_OUTPUT_MASK


class PCGRandom:
    _MULTIPLIER: ClassVar[int] = _PCG_MULTIPLIER
    _DEFAULT_INCREMENT: ClassVar[int] = _PCG_DEFAULT_INCREMENT
    _XORSHIFT_SHIFT: ClassVar[int] = _PCG_XORSHIFT_SHIFT
    _OUTPUT_SHIFT: ClassVar[int] = _PCG_OUTPUT_SHIFT
    _ROTATION_SHIFT: ClassVar[int] = _PCG_ROTATION_SHIFT
    _STATE_MASK: ClassVar[int] = _PCG_STATE_MASK
    _OUTPUT_MASK: ClassVar[int] = _PCG_OUTPUT_MASK

    def __init__(self, seed: int = 0, stream: int = 0) -> None:
        self._state: int = 0
        increment = (stream << 1) | 1
        self._increment: int = increment & _PCG_STATE_MASK
        self._state = (seed + self._increment) & _PCG_STATE_MASK
        self._state = (self._state * self._MULTIPLIER + self._increment) & _PCG_STATE_MASK
        self._has_gaussian: bool = False
        self._gaussian_spare: float = 0.0

    def next_uint32(self) -> int:
        old_state = self._state
        self._state = (old_state * self._MULTIPLIER + self._increment) & self._STATE_MASK
        xorshifted = ((old_state >> self._XORSHIFT_SHIFT) ^ old_state) >> self._OUTPUT_SHIFT
        xorshifted &= self._OUTPUT_MASK
        rot = old_state >> self._ROTATION_SHIFT
        return _rotr32(xorshifted, rot & _PCG_ROTATION_MASK)

    def uniform(self, low: float = 0.0, high: float = 1.0) -> float:
        upper = self.next_uint32() >> _UNIFORM_UPPER_SHIFT
        lower = self.next_uint32() >> _UNIFORM_LOWER_SHIFT
        combined = (upper << _UNIFORM_COMBINED_SHIFT) | lower
        result = combined / _UNIFORM_DENOMINATOR
        return low + result * (high - low)

    def gaussian(self, mean: float = _GAUSSIAN_DEFAULT_MEAN, stddev: float = _GAUSSIAN_DEFAULT_STDDEV) -> float:
        if self._has_gaussian:
            self._has_gaussian = False
            return mean + stddev * self._gaussian_spare
        x1: float = 0.0
        x2: float = 0.0
        w: float = 0.0
        while True:
            x1 = self.uniform(-1.0, 1.0)
            x2 = self.uniform(-1.0, 1.0)
            w = x1 * x1 + x2 * x2
            if w > 0.0 and w < 1.0:
                break
        w = (-2.0 * math.log(w)) / w
        sqrt_w = w ** 0.5
        self._gaussian_spare = x2 * sqrt_w
        self._has_gaussian = True
        return mean + stddev * x1 * sqrt_w

    def weighted_choice(self, weights: Sequence[float]) -> int:
        if not weights:
            raise ValueError("weights sequence must not be empty")
        total = sum(weights)
        if total <= 0.0:
            raise ValueError("sum of weights must be positive")
        threshold = self.uniform(0.0, total)
        cumulative = 0.0
        for idx, w in enumerate(weights):
            cumulative += w
            if cumulative >= threshold:
                return idx
        return len(weights) - 1

    @property
    def state(self) -> Tuple[int, int]:
        return (self._state, self._increment)

    @state.setter
    def state(self, value: Tuple[int, int]) -> None:
        self._state = value[0] & _PCG_STATE_MASK
        self._increment = value[1] & _PCG_STATE_MASK


_STREAM_ID_DEFAULT_OFFSET: int = 1


class SeededRNGManager:
    _DEFAULT_OFFSET: ClassVar[int] = _STREAM_ID_DEFAULT_OFFSET

    def __init__(self, master_seed: int) -> None:
        self._master_seed: int = master_seed
        self._streams: Dict[str, PCGRandom] = {}

    def get_stream(self, stream_id: str) -> PCGRandom:
        if stream_id not in self._streams:
            stream_index = len(self._streams) + self._DEFAULT_OFFSET
            self._streams[stream_id] = PCGRandom(seed=self._master_seed, stream=stream_index)
        return self._streams[stream_id]

    def create_stream(self, stream_id: str, seed_override: Optional[int] = None) -> PCGRandom:
        if seed_override is not None:
            self._streams[stream_id] = PCGRandom(seed=seed_override)
        else:
            stream_index = len(self._streams) + self._DEFAULT_OFFSET
            self._streams[stream_id] = PCGRandom(seed=self._master_seed, stream=stream_index)
        return self._streams[stream_id]

    def remove_stream(self, stream_id: str) -> None:
        self._streams.pop(stream_id, None)

    @property
    def active_streams(self) -> List[str]:
        return list(self._streams.keys())

    @property
    def master_seed(self) -> int:
        return self._master_seed


_SEED_HIERARCHY_LEVELS: Tuple[str, ...] = (
    "world",
    "faction",
    "character",
    "scene",
    "event",
)


class NarrativeSeedHierarchy:
    _LEVELS: ClassVar[Tuple[str, ...]] = _SEED_HIERARCHY_LEVELS
    _DELIMITER: ClassVar[str] = _SEED_HIERARCHY_DELIMITER
    _HEX_LENGTH: ClassVar[int] = _SHA256_HEX_LENGTH

    def __init__(self, root_seed: int) -> None:
        self._root_seed: int = root_seed
        self._cache: Dict[str, int] = {}

    def derive_seed(self, *path_components: str) -> int:
        path = self._DELIMITER.join(path_components)
        if path in self._cache:
            return self._cache[path]
        seed_str = str(self._root_seed) + self._DELIMITER + path
        digest = hashlib.sha256(seed_str.encode("utf-8")).hexdigest()
        derived = int(digest[: self._HEX_LENGTH], 16)
        self._cache[path] = derived
        return derived

    def create_rng(self, *path_components: str, stream: int = 0) -> PCGRandom:
        seed = self.derive_seed(*path_components)
        return PCGRandom(seed=seed, stream=stream)

    def derive_world_seed(self, world_name: str) -> int:
        return self.derive_seed(self._LEVELS[0], world_name)

    def derive_faction_seed(self, world_name: str, faction_name: str) -> int:
        return self.derive_seed(self._LEVELS[0], world_name, self._LEVELS[1], faction_name)

    def derive_character_seed(self, world_name: str, character_name: str) -> int:
        return self.derive_seed(self._LEVELS[0], world_name, self._LEVELS[2], character_name)

    def derive_scene_seed(self, world_name: str, scene_name: str) -> int:
        return self.derive_seed(self._LEVELS[0], world_name, self._LEVELS[3], scene_name)

    def derive_event_seed(self, world_name: str, event_name: str) -> int:
        return self.derive_seed(self._LEVELS[0], world_name, self._LEVELS[4], event_name)

    @property
    def root_seed(self) -> int:
        return self._root_seed

    def clear_cache(self) -> None:
        self._cache.clear()
