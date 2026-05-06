"""
叙事引擎 — 五层架构实现

锚定论文机制:
- Layer5 叙事弧控制器: Storyform(UNM论文) + Dramatis悬念模型
- Layer4 主线/支线管理器: Hybrid Orchestrator + Storylet触发器
- Layer3 场景驻留引擎: Mise-en-Scene对齐 + Beat序列编排
- Layer2 角色分层: 动态分层 + 分组轮换 + 叙事记忆
- Layer1 涌现检测: MACIE论文 SI/CS/II指标体系

用户决策:
1. 涌现检测: 三种预选方案(保守/均衡/激进) + 自定义接口
2. Beat粒度: 由主线/支线当前张力强度算法动态控制
3. Storyform核心不平等: 通用引擎均衡算法 + 自定义支持
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Set, Tuple


# ============================================================
# Layer1: 涌现检测引擎 (MACIE论文 SI/CS/II指标体系)
# ============================================================

class EmergencePreset(Enum):
    CONSERVATIVE = "保守型"
    BALANCED = "均衡型"
    AGGRESSIVE = "激进型"
    CUSTOM = "自定义"


@dataclass
class EmergenceThresholds:
    si_threshold: float = 0.6
    cs_threshold: float = 0.5
    ii_threshold: float = 0.4
    min_interaction_count: int = 5
    cooldown_rounds: int = 20
    promotion_score: float = 0.7
    demotion_score: float = 0.3

    @classmethod
    def from_preset(cls, preset: EmergencePreset) -> "EmergenceThresholds":
        presets = {
            EmergencePreset.CONSERVATIVE: cls(
                si_threshold=0.75,
                cs_threshold=0.65,
                ii_threshold=0.55,
                min_interaction_count=8,
                cooldown_rounds=30,
                promotion_score=0.8,
                demotion_score=0.25,
            ),
            EmergencePreset.BALANCED: cls(
                si_threshold=0.6,
                cs_threshold=0.5,
                ii_threshold=0.4,
                min_interaction_count=5,
                cooldown_rounds=20,
                promotion_score=0.7,
                demotion_score=0.3,
            ),
            EmergencePreset.AGGRESSIVE: cls(
                si_threshold=0.4,
                cs_threshold=0.35,
                ii_threshold=0.25,
                min_interaction_count=3,
                cooldown_rounds=10,
                promotion_score=0.55,
                demotion_score=0.4,
            ),
        }
        return presets.get(preset, presets[EmergencePreset.BALANCED])


@dataclass
class EmergenceSignal:
    source_chars: List[str]
    synergy_index: float
    coordination_score: float
    information_integration: float
    overall_score: float
    detected_at_round: int
    narrative_potential: str
    suggested_thread_type: str


class EmergenceDetector:
    def __init__(
        self,
        preset: EmergencePreset = EmergencePreset.BALANCED,
        custom_thresholds: Optional[EmergenceThresholds] = None,
    ):
        if preset == EmergencePreset.CUSTOM and custom_thresholds:
            self.thresholds = custom_thresholds
        else:
            self.thresholds = EmergenceThresholds.from_preset(preset)
        self.preset = preset
        self._interaction_buffer: List[Dict[str, Any]] = []
        self._last_detection_round: int = 0
        self._detection_history: List[EmergenceSignal] = []

    def record_interaction(
        self,
        char_ids: List[str],
        action_type: str,
        round_num: int,
        relationship_deltas: Optional[Dict[str, float]] = None,
    ):
        self._interaction_buffer.append({
            "char_ids": char_ids,
            "action_type": action_type,
            "round": round_num,
            "rel_deltas": relationship_deltas or {},
        })
        if len(self._interaction_buffer) > 500:
            self._interaction_buffer = self._interaction_buffer[-300:]

    def detect(self, round_num: int, pool: Any) -> Optional[EmergenceSignal]:
        if round_num - self._last_detection_round < self.thresholds.cooldown_rounds:
            return None
        recent = [
            i for i in self._interaction_buffer
            if round_num - i["round"] <= self.thresholds.cooldown_rounds * 2
        ]
        if len(recent) < self.thresholds.min_interaction_count:
            return None
        char_interaction_count: Dict[str, int] = {}
        char_pair_count: Dict[str, int] = {}
        for interaction in recent:
            for cid in interaction["char_ids"]:
                char_interaction_count[cid] = char_interaction_count.get(cid, 0) + 1
            if len(interaction["char_ids"]) >= 2:
                pair_key = "~".join(sorted(interaction["char_ids"][:2]))
                char_pair_count[pair_key] = char_pair_count.get(pair_key, 0) + 1
        total_interactions = len(recent)
        unique_chars = len(char_interaction_count)
        if unique_chars < 2:
            return None
        si = self._calc_synergy_index(char_pair_count, total_interactions)
        cs = self._calc_coordination_score(recent, char_interaction_count)
        ii = self._calc_information_integration(recent, unique_chars)
        overall = si * 0.4 + cs * 0.35 + ii * 0.25
        if (si >= self.thresholds.si_threshold and
            cs >= self.thresholds.cs_threshold and
            ii >= self.thresholds.ii_threshold):
            top_chars = sorted(
                char_interaction_count.items(),
                key=lambda x: x[1], reverse=True,
            )[:5]
            top_char_ids = [c[0] for c in top_chars]
            thread_type = self._classify_emergence(si, cs, ii)
            potential = self._assess_potential(overall, thread_type)
            signal = EmergenceSignal(
                source_chars=top_char_ids,
                synergy_index=si,
                coordination_score=cs,
                information_integration=ii,
                overall_score=overall,
                detected_at_round=round_num,
                narrative_potential=potential,
                suggested_thread_type=thread_type,
            )
            self._last_detection_round = round_num
            self._detection_history.append(signal)
            return signal
        return None

    @staticmethod
    def _calc_synergy_index(
        pair_count: Dict[str, int],
        total: int,
    ) -> float:
        if not pair_count or total == 0:
            return 0.0
        top_pair_count = sum(sorted(pair_count.values(), reverse=True)[:3])
        concentration = top_pair_count / max(total, 1)
        num_pairs = len(pair_count)
        diversity = min(num_pairs / 10.0, 1.0)
        return concentration * 0.6 + diversity * 0.4

    @staticmethod
    def _calc_coordination_score(
        interactions: List[Dict],
        char_counts: Dict[str, int],
    ) -> float:
        if not interactions or not char_counts:
            return 0.0
        type_sequence = [i["action_type"] for i in interactions]
        if len(type_sequence) < 3:
            return 0.0
        pattern_count = 0
        window = min(5, len(type_sequence))
        for i in range(len(type_sequence) - window + 1):
            segment = type_sequence[i:i + window]
            unique = len(set(segment))
            if unique <= 2 and len(segment) >= 4:
                pattern_count += 1
        max_patterns = max(len(type_sequence) - window + 1, 1)
        pattern_score = min(pattern_count / max_patterns, 1.0)
        count_vals = list(char_counts.values())
        if not count_vals:
            return pattern_score * 0.5
        avg_count = sum(count_vals) / len(count_vals)
        variance = sum((c - avg_count) ** 2 for c in count_vals) / len(count_vals)
        balance = 1.0 / (1.0 + math.sqrt(variance))
        return pattern_score * 0.6 + balance * 0.4

    @staticmethod
    def _calc_information_integration(
        interactions: List[Dict],
        unique_chars: int,
    ) -> float:
        if not interactions or unique_chars < 2:
            return 0.0
        char_info: Dict[str, Set[str]] = {}
        for interaction in interactions:
            for cid in interaction["char_ids"]:
                char_info.setdefault(cid, set())
                for other_cid in interaction["char_ids"]:
                    if other_cid != cid:
                        char_info[cid].add(other_cid)
        if not char_info:
            return 0.0
        avg_connections = sum(len(v) for v in char_info.values()) / len(char_info)
        max_possible = unique_chars - 1
        connectivity = avg_connections / max(max_possible, 1)
        cross_type: Set[str] = set()
        for interaction in interactions:
            cross_type.add(interaction["action_type"])
        type_diversity = min(len(cross_type) / 4.0, 1.0)
        return connectivity * 0.6 + type_diversity * 0.4

    @staticmethod
    def _classify_emergence(si: float, cs: float, ii: float) -> str:
        if cs > 0.7 and si > 0.6:
            return "conspiracy"
        if si > 0.7 and ii > 0.5:
            return "alliance"
        if ii > 0.6:
            return "information_network"
        if cs > 0.5:
            return "conflict_escalation"
        return "ambient"

    @staticmethod
    def _assess_potential(overall: float, thread_type: str) -> str:
        high_types = {"conspiracy", "conflict_escalation"}
        if overall > 0.8 and thread_type in high_types:
            return "critical"
        if overall > 0.6:
            return "high"
        if overall > 0.4:
            return "medium"
        return "low"

    @property
    def detection_count(self) -> int:
        return len(self._detection_history)

    @property
    def last_signal(self) -> Optional[EmergenceSignal]:
        return self._detection_history[-1] if self._detection_history else None


# ============================================================
# Layer2: 角色分层 + 分组轮换 + 叙事记忆
# ============================================================

class CharacterLayer(Enum):
    CORE = "核心层"
    ACTIVE = "活跃层"
    BACKGROUND = "背景层"


@dataclass
class NarrativeMemory:
    char_id: str
    key_events: List[str] = field(default_factory=list)
    relationship_changes: Dict[str, float] = field(default_factory=dict)
    arc_participation: List[str] = field(default_factory=list)
    last_active_round: int = 0
    prominence_score: float = 0.5

    def record_event(self, event: str, round_num: int):
        self.key_events.append(f"[R{round_num}]{event}")
        if len(self.key_events) > 50:
            self.key_events = self.key_events[-30:]
        self.last_active_round = round_num

    def update_prominence(self, delta: float):
        self.prominence_score = max(0.0, min(1.0, self.prominence_score + delta))


class CharacterStratifier:
    CORE_MAX = 8
    ACTIVE_MAX = 40
    PROMINENCE_CORE_THRESHOLD = 0.75
    PROMINENCE_ACTIVE_THRESHOLD = 0.45
    PROMINENCE_DECAY_PER_ROUND = 0.002
    PROMINENCE_BOOST_PROTAGONIST = 0.3
    PROMINENCE_BOOST_EVENT = 0.1
    PROMINENCE_BOOST_DEATH = 0.2

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self._layers: Dict[str, CharacterLayer] = {}
        self._memories: Dict[str, NarrativeMemory] = {}
        self._faction_rotation_index: int = 0
        self._rotation_counter: int = 0
        self._rotation_interval: int = 15

    def initialize(self, pool: Any):
        for c in pool.get_alive():
            self._memories[c.char_id] = NarrativeMemory(char_id=c.char_id)
            if c.char_id in pool.protagonist_ids:
                self._layers[c.char_id] = CharacterLayer.CORE
                self._memories[c.char_id].prominence_score = 0.9
                self._memories[c.char_id].update_prominence(
                    self.PROMINENCE_BOOST_PROTAGONIST
                )
            elif c.char_id == pool.user_id:
                self._layers[c.char_id] = CharacterLayer.CORE
                self._memories[c.char_id].prominence_score = 0.85
            else:
                self._layers[c.char_id] = CharacterLayer.BACKGROUND
                self._memories[c.char_id].prominence_score = 0.3 + self.rng.random() * 0.2

    def get_layer(self, char_id: str) -> CharacterLayer:
        return self._layers.get(char_id, CharacterLayer.BACKGROUND)

    def get_memory(self, char_id: str) -> NarrativeMemory:
        if char_id not in self._memories:
            self._memories[char_id] = NarrativeMemory(char_id=char_id)
        return self._memories[char_id]

    def record_event(
        self,
        char_id: str,
        event: str,
        round_num: int,
        is_significant: bool = False,
    ):
        mem = self.get_memory(char_id)
        mem.record_event(event, round_num)
        boost = (
            self.PROMINENCE_BOOST_EVENT if not is_significant
            else self.PROMINENCE_BOOST_DEATH
        )
        mem.update_prominence(boost)

    def update_relationship_change(
        self,
        char_id: str,
        target_id: str,
        delta: float,
    ):
        mem = self.get_memory(char_id)
        mem.relationship_changes[target_id] = (
            mem.relationship_changes.get(target_id, 0.0) + delta
        )

    def decay_prominence(self):
        for mem in self._memories.values():
            mem.update_prominence(-self.PROMINENCE_DECAY_PER_ROUND)

    def reclassify(self, pool: Any):
        core_count = sum(
            1 for l in self._layers.values() if l == CharacterLayer.CORE
        )
        active_count = sum(
            1 for l in self._layers.values() if l == CharacterLayer.ACTIVE
        )
        for char_id, mem in self._memories.items():
            char = pool.get(char_id)
            if not char or not char.is_alive:
                continue
            current = self._layers.get(char_id, CharacterLayer.BACKGROUND)
            if current == CharacterLayer.CORE:
                if mem.prominence_score < self.PROMINENCE_ACTIVE_THRESHOLD:
                    self._layers[char_id] = CharacterLayer.ACTIVE
                    core_count -= 1
                    active_count += 1
            elif current == CharacterLayer.ACTIVE:
                if mem.prominence_score >= self.PROMINENCE_CORE_THRESHOLD:
                    if core_count < self.CORE_MAX:
                        self._layers[char_id] = CharacterLayer.CORE
                        core_count += 1
                        active_count -= 1
                elif mem.prominence_score < self.PROMINENCE_ACTIVE_THRESHOLD:
                    self._layers[char_id] = CharacterLayer.BACKGROUND
                    active_count -= 1
            else:
                if mem.prominence_score >= self.PROMINENCE_CORE_THRESHOLD:
                    if core_count < self.CORE_MAX:
                        self._layers[char_id] = CharacterLayer.CORE
                        core_count += 1
                elif mem.prominence_score >= self.PROMINENCE_ACTIVE_THRESHOLD:
                    if active_count < self.ACTIVE_MAX:
                        self._layers[char_id] = CharacterLayer.ACTIVE
                        active_count += 1

    def get_active_cast(
        self,
        pool: Any,
        arc_phase: str,
        max_size: int = 12,
    ) -> List[str]:
        phase_core_weight = {"起": 0.6, "承": 0.4, "转": 0.5, "合": 0.7}
        phase_active_weight = {"起": 0.3, "承": 0.4, "转": 0.3, "合": 0.2}
        core_w = phase_core_weight.get(arc_phase, 0.5)
        active_w = phase_active_weight.get(arc_phase, 0.35)
        bg_w = 1.0 - core_w - active_w
        core_ids = [
            cid for cid, layer in self._layers.items()
            if layer == CharacterLayer.CORE
            and (c := pool.get(cid)) and c.is_alive
        ]
        active_ids = [
            cid for cid, layer in self._layers.items()
            if layer == CharacterLayer.ACTIVE
            and (c := pool.get(cid)) and c.is_alive
        ]
        bg_ids = [
            cid for cid, layer in self._layers.items()
            if layer == CharacterLayer.BACKGROUND
            and (c := pool.get(cid)) and c.is_alive
        ]
        core_n = max(1, int(max_size * core_w))
        active_n = max(1, int(max_size * active_w))
        bg_n = max(0, max_size - core_n - active_n)
        selected = list(core_ids[:core_n])
        remaining_active = [c for c in active_ids if c not in selected]
        self.rng.shuffle(remaining_active)
        selected.extend(remaining_active[:active_n])
        remaining_bg = [c for c in bg_ids if c not in selected]
        self.rng.shuffle(remaining_bg)
        selected.extend(remaining_bg[:bg_n])
        return selected

    def rotate_faction_focus(self, pool: Any) -> Optional[Any]:
        from .world import Faction
        all_factions = list(Faction)
        if not all_factions:
            return None
        self._rotation_counter += 1
        if self._rotation_counter % self._rotation_interval != 0:
            return None
        self._faction_rotation_index = (
            self._faction_rotation_index + 1
        ) % len(all_factions)
        return all_factions[self._faction_rotation_index]

    def get_layer_summary(self) -> Dict[str, int]:
        counts = {"核心层": 0, "活跃层": 0, "背景层": 0}
        for layer in self._layers.values():
            counts[layer.value] = counts.get(layer.value, 0) + 1
        return counts


# ============================================================
# Layer3: 场景驻留引擎 + Beat序列编排
# ============================================================

class BeatType(Enum):
    DIALOGUE = auto()
    ACTION = auto()
    REACTION = auto()
    REVELATION = auto()
    TRANSITION = auto()


@dataclass
class Beat:
    beat_type: BeatType
    round_number: int
    char_ids: List[str]
    content_summary: str = ""
    tension_level: float = 0.5
    plot_relevance: float = 0.0


@dataclass
class BeatSequence:
    beats: List[Beat] = field(default_factory=list)
    scene_id: str = ""
    started_at_round: int = 0
    target_length: int = 5

    @property
    def current_tension(self) -> float:
        if not self.beats:
            return 0.3
        recent = self.beats[-3:]
        return sum(b.tension_level for b in recent) / len(recent)

    @property
    def is_complete(self) -> bool:
        return len(self.beats) >= self.target_length

    @property
    def plot_progress(self) -> float:
        if not self.beats:
            return 0.0
        return sum(b.plot_relevance for b in self.beats) / len(self.beats)


class SceneResidencyEngine:
    BASE_RESIDENCY = {"起": 3, "承": 5, "转": 7, "合": 5}

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self._current_sequence: Optional[BeatSequence] = None
        self._completed_sequences: List[BeatSequence] = []

    def start_scene(self, scene_id: str, round_num: int, arc_phase: str):
        target = self.BASE_RESIDENCY.get(arc_phase, 5)
        self._current_sequence = BeatSequence(
            scene_id=scene_id,
            started_at_round=round_num,
            target_length=target,
        )

    def should_continue_scene(
        self,
        scene_id: str,
        arc_phase: str,
        has_unresolved_conflict: bool,
        protagonist_present: bool,
        advances_main_plot: bool,
        turns_in_scene: int,
        beat_sequence: Optional[BeatSequence] = None,
    ) -> bool:
        if has_unresolved_conflict:
            return True
        if protagonist_present and advances_main_plot:
            return True
        seq = beat_sequence or self._current_sequence
        if seq and not seq.is_complete:
            return True
        base = self.BASE_RESIDENCY.get(arc_phase, 5)
        if turns_in_scene < base:
            return True
        return False

    def calc_beat_granularity(
        self,
        main_plot_tension: float,
        side_plot_tension: float,
        arc_phase: str,
        current_tension: float,
    ) -> int:
        combined = main_plot_tension * 0.6 + side_plot_tension * 0.4
        phase_multiplier = {"起": 0.8, "承": 1.0, "转": 1.4, "合": 1.1}
        multiplier = phase_multiplier.get(arc_phase, 1.0)
        effective_tension = combined * multiplier + current_tension * 0.3
        effective_tension = max(0.0, min(1.0, effective_tension))
        if effective_tension > 0.75:
            return 1
        if effective_tension > 0.5:
            return 2
        if effective_tension > 0.3:
            return 3
        return 4

    def record_beat(
        self,
        beat_type: BeatType,
        round_num: int,
        char_ids: List[str],
        tension_level: float,
        plot_relevance: float,
        content_summary: str = "",
    ):
        if self._current_sequence is None:
            self._current_sequence = BeatSequence(
                started_at_round=round_num,
            )
        beat = Beat(
            beat_type=beat_type,
            round_number=round_num,
            char_ids=char_ids,
            content_summary=content_summary,
            tension_level=tension_level,
            plot_relevance=plot_relevance,
        )
        self._current_sequence.beats.append(beat)

    def end_scene(self) -> Optional[BeatSequence]:
        if self._current_sequence:
            self._completed_sequences.append(self._current_sequence)
            seq = self._current_sequence
            self._current_sequence = None
            return seq
        return None

    @property
    def current_sequence(self) -> Optional[BeatSequence]:
        return self._current_sequence

    @property
    def turns_in_current_scene(self) -> int:
        if self._current_sequence:
            return len(self._current_sequence.beats)
        return 0


# ============================================================
# Layer4: 主线/支线管理器 (Hybrid Orchestrator + Storylet触发器)
# ============================================================

class PlotThreadType(Enum):
    MAIN = "主线"
    SIDE = "支线"
    EMERGENT = "涌现"


class PlotThreadStatus(Enum):
    DORMANT = "休眠"
    ACTIVE = "激活"
    CLIMAX = "高潮"
    RESOLVED = "已解决"
    ABANDONED = "已放弃"


@dataclass
class PlotPoint:
    point_id: str
    description: str
    required_conditions: Dict[str, Any] = field(default_factory=dict)
    trigger_round_range: Tuple[int, int] = (0, 99999)
    tension_impact: float = 0.0
    plot_relevance: float = 1.0
    is_mandatory: bool = False
    resolved: bool = False


@dataclass
class PlotThread:
    thread_id: str
    thread_type: PlotThreadType
    title: str
    description: str
    status: PlotThreadStatus = PlotThreadStatus.DORMANT
    plot_points: List[PlotPoint] = field(default_factory=list)
    current_point_index: int = 0
    involved_chars: List[str] = field(default_factory=list)
    tension_level: float = 0.3
    priority: float = 0.5
    activated_at_round: int = 0
    resolved_at_round: int = 0
    source_signal: Optional[EmergenceSignal] = None

    @property
    def current_point(self) -> Optional[PlotPoint]:
        if 0 <= self.current_point_index < len(self.plot_points):
            return self.plot_points[self.current_point_index]
        return None

    @property
    def progress(self) -> float:
        if not self.plot_points:
            return 0.0
        resolved = sum(1 for p in self.plot_points if p.resolved)
        return resolved / len(self.plot_points)

    @property
    def is_complete(self) -> bool:
        return all(p.resolved for p in self.plot_points)


@dataclass
class StoryletCondition:
    field_path: str
    operator: str
    value: Any

    def evaluate(self, context: Dict[str, Any]) -> bool:
        parts = self.field_path.split(".")
        current = context
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                current = getattr(current, part, None)
            if current is None:
                return False
        ops = {
            "==": lambda a, b: a == b,
            "!=": lambda a, b: a != b,
            ">": lambda a, b: a > b,
            "<": lambda a, b: a < b,
            ">=": lambda a, b: a >= b,
            "<=": lambda a, b: a <= b,
            "in": lambda a, b: a in b,
            "contains": lambda a, b: b in a if a else False,
        }
        op_fn = ops.get(self.operator)
        if op_fn is None:
            return False
        try:
            return op_fn(current, self.value)
        except (TypeError, ValueError):
            return False


@dataclass
class Storylet:
    storylet_id: str
    title: str
    description: str
    conditions: List[StoryletCondition]
    thread_type: PlotThreadType
    tension_impact: float = 0.0
    priority_boost: float = 0.0
    required_chars: List[str] = field(default_factory=list)

    def can_trigger(self, context: Dict[str, Any]) -> bool:
        return all(c.evaluate(context) for c in self.conditions)


class PlotThreadManager:
    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self._threads: Dict[str, PlotThread] = {}
        self._storylets: List[Storylet] = []
        self._main_thread_id: Optional[str] = None
        self._next_thread_counter: int = 0

    def register_main_thread(self, thread: PlotThread):
        self._threads[thread.thread_id] = thread
        self._main_thread_id = thread.thread_id
        thread.status = PlotThreadStatus.ACTIVE

    def register_side_thread(self, thread: PlotThread):
        self._threads[thread.thread_id] = thread

    def register_emergent_thread(
        self,
        signal: EmergenceSignal,
        title: str,
        description: str,
    ) -> PlotThread:
        self._next_thread_counter += 1
        thread_id = f"EMERGENT_{self._next_thread_counter:04d}"
        thread = PlotThread(
            thread_id=thread_id,
            thread_type=PlotThreadType.EMERGENT,
            title=title,
            description=description,
            status=PlotThreadStatus.ACTIVE,
            involved_chars=signal.source_chars[:5],
            tension_level=signal.overall_score,
            priority=0.4 + signal.overall_score * 0.3,
            activated_at_round=signal.detected_at_round,
            source_signal=signal,
        )
        self._threads[thread_id] = thread
        return thread

    def register_storylet(self, storylet: Storylet):
        self._storylets.append(storylet)

    def get_main_thread(self) -> Optional[PlotThread]:
        if self._main_thread_id:
            return self._threads.get(self._main_thread_id)
        return None

    def get_active_threads(self) -> List[PlotThread]:
        return [
            t for t in self._threads.values()
            if t.status in (PlotThreadStatus.ACTIVE, PlotThreadStatus.CLIMAX)
        ]

    def get_thread(self, thread_id: str) -> Optional[PlotThread]:
        return self._threads.get(thread_id)

    def advance_thread(self, thread_id: str, round_num: int) -> Optional[PlotPoint]:
        thread = self._threads.get(thread_id)
        if not thread or thread.status == PlotThreadStatus.RESOLVED:
            return None
        current = thread.current_point
        if current and not current.resolved:
            current.resolved = True
        thread.current_point_index += 1
        next_point = thread.current_point
        if thread.is_complete:
            thread.status = PlotThreadStatus.RESOLVED
            thread.resolved_at_round = round_num
        elif next_point and next_point.is_mandatory:
            thread.status = PlotThreadStatus.CLIMAX
        return next_point

    def check_storylets(self, context: Dict[str, Any]) -> List[Storylet]:
        triggered = []
        for storylet in self._storylets:
            if storylet.can_trigger(context):
                triggered.append(storylet)
        return triggered

    def calculate_main_plot_tension(self, round_num: int) -> float:
        main = self.get_main_thread()
        if not main:
            return 0.3
        progress = main.progress
        if progress < 0.2:
            return 0.2 + progress * 0.5
        if progress < 0.5:
            return 0.3 + progress * 0.7
        if progress < 0.8:
            return 0.5 + progress * 0.5
        return 0.8 + progress * 0.2

    def calculate_side_plot_tension(self) -> float:
        active = self.get_active_threads()
        side_threads = [
            t for t in active
            if t.thread_type in (PlotThreadType.SIDE, PlotThreadType.EMERGENT)
        ]
        if not side_threads:
            return 0.2
        avg_tension = sum(t.tension_level for t in side_threads) / len(side_threads)
        count_factor = min(len(side_threads) / 5.0, 1.0)
        return avg_tension * 0.7 + count_factor * 0.3

    def get_dominant_thread(self) -> Optional[PlotThread]:
        active = self.get_active_threads()
        if not active:
            return self.get_main_thread()
        main = self.get_main_thread()
        if main and main.status == PlotThreadStatus.CLIMAX:
            return main
        return max(active, key=lambda t: t.priority)

    def update_priorities(self, round_num: int):
        for thread in self._threads.values():
            if thread.status == PlotThreadStatus.RESOLVED:
                continue
            if thread.thread_type == PlotThreadType.MAIN:
                thread.priority = 0.8 + thread.progress * 0.2
            elif thread.thread_type == PlotThreadType.EMERGENT:
                age = round_num - thread.activated_at_round
                decay = max(0.0, 1.0 - age * 0.005)
                thread.priority = (0.4 + thread.tension_level * 0.3) * decay
            else:
                thread.priority = 0.3 + thread.tension_level * 0.3
            if thread.status == PlotThreadStatus.CLIMAX:
                thread.priority = min(1.0, thread.priority + 0.2)

    def get_thread_summary(self) -> Dict[str, Any]:
        main = self.get_main_thread()
        active = self.get_active_threads()
        return {
            "main_progress": main.progress if main else 0.0,
            "main_status": main.status.value if main else "无",
            "active_count": len(active),
            "total_threads": len(self._threads),
            "resolved_count": sum(
                1 for t in self._threads.values()
                if t.status == PlotThreadStatus.RESOLVED
            ),
        }


# ============================================================
# Layer5: 叙事弧控制器 (Storyform + Dramatis悬念模型)
# ============================================================

class ArcPhase(Enum):
    INTRODUCTION = "起"
    DEVELOPMENT = "承"
    CLIMAX = "转"
    RESOLUTION = "合"


@dataclass
class StoryformInequality:
    name: str
    description: str
    weight: float = 1.0
    current_value: float = 0.5
    target_direction: str = "increase"

    def update(self, delta: float):
        self.current_value = max(0.0, min(1.0, self.current_value + delta))

    @property
    def tension_contribution(self) -> float:
        if self.target_direction == "increase":
            return self.current_value * self.weight
        return (1.0 - self.current_value) * self.weight


class StoryformEngine:
    def __init__(
        self,
        custom_inequalities: Optional[List[StoryformInequality]] = None,
    ):
        if custom_inequalities:
            self._inequalities = {
                ineq.name: ineq for ineq in custom_inequalities
            }
        else:
            self._inequalities = self._create_default_inequalities()
        self._inequality_history: List[Dict[str, float]] = []

    @staticmethod
    def _create_default_inequalities() -> Dict[str, StoryformInequality]:
        return {
            "power_gap": StoryformInequality(
                name="power_gap",
                description="强弱势力差距",
                weight=1.0,
                current_value=0.5,
                target_direction="increase",
            ),
            "truth_concealment": StoryformInequality(
                name="truth_concealment",
                description="真相隐藏程度",
                weight=0.8,
                current_value=0.7,
                target_direction="decrease",
            ),
            "loyalty_conflict": StoryformInequality(
                name="loyalty_conflict",
                description="忠诚与背叛的张力",
                weight=0.9,
                current_value=0.4,
                target_direction="increase",
            ),
            "resource_scarcity": StoryformInequality(
                name="resource_scarcity",
                description="资源稀缺程度",
                weight=0.6,
                current_value=0.5,
                target_direction="increase",
            ),
            "moral_ambiguity": StoryformInequality(
                name="moral_ambiguity",
                description="正邪界限模糊度",
                weight=0.7,
                current_value=0.3,
                target_direction="increase",
            ),
        }

    def update_from_world(self, pool: Any, world_state: Any):
        alive = pool.get_alive()
        total = len(pool.all_characters)
        if total > 0:
            faction_counts: Dict[str, int] = {}
            for c in alive:
                fname = c.faction.value if c.faction else "散人"
                faction_counts[fname] = faction_counts.get(fname, 0) + 1
            if faction_counts:
                max_count = max(faction_counts.values())
                min_count = min(faction_counts.values())
                gap = (max_count - min_count) / max(max_count, 1)
                self._inequalities["power_gap"].update(
                    gap * 0.1 - self._inequalities["power_gap"].current_value * 0.02
                )
        death_ratio = pool.dead_count / max(total, 1)
        self._inequalities["resource_scarcity"].update(
            death_ratio * 0.05 - 0.01
        )
        if world_state:
            betrayal_ratio = world_state.betrayals / max(world_state.alliances_formed, 1)
            self._inequalities["loyalty_conflict"].update(
                betrayal_ratio * 0.08 - 0.01
            )
            secret_ratio = world_state.secrets_revealed / max(8, 1)
            self._inequalities["truth_concealment"].update(
                -secret_ratio * 0.1
            )
        snapshot = {
            name: ineq.current_value
            for name, ineq in self._inequalities.items()
        }
        self._inequality_history.append(snapshot)
        if len(self._inequality_history) > 200:
            self._inequality_history = self._inequality_history[-100:]

    @property
    def overall_tension(self) -> float:
        if not self._inequalities:
            return 0.3
        total_weight = sum(i.weight for i in self._inequalities.values())
        if total_weight == 0:
            return 0.3
        weighted_sum = sum(
            i.tension_contribution for i in self._inequalities.values()
        )
        return min(1.0, weighted_sum / total_weight)

    @property
    def inequalities(self) -> Dict[str, StoryformInequality]:
        return dict(self._inequalities)

    def get_tension_report(self) -> str:
        lines = ["Storyform张力报告:"]
        for name, ineq in self._inequalities.items():
            bar_len = int(ineq.current_value * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)
            lines.append(
                f"  {ineq.description}: [{bar}] {ineq.current_value:.2f}"
            )
        lines.append(f"  综合张力: {self.overall_tension:.2f}")
        return "\n".join(lines)


class DramatisSuspenseModel:
    def __init__(self):
        self._protagonist_plans: Dict[str, List[str]] = {}
        self._threat_level: Dict[str, float] = {}
        self._time_pressure: Dict[str, float] = {}

    def update_protagonist_state(
        self,
        char_id: str,
        available_plans: List[str],
        threat_level: float,
        time_pressure: float,
    ):
        self._protagonist_plans[char_id] = available_plans
        self._threat_level[char_id] = max(0.0, min(1.0, threat_level))
        self._time_pressure[char_id] = max(0.0, min(1.0, time_pressure))

    def calculate_suspense(self, char_id: str) -> float:
        plans = self._protagonist_plans.get(char_id, [])
        threat = self._threat_level.get(char_id, 0.3)
        time_p = self._time_pressure.get(char_id, 0.3)
        plan_count = len(plans)
        if plan_count == 0:
            escape_difficulty = 1.0
        elif plan_count == 1:
            escape_difficulty = 0.8
        elif plan_count <= 3:
            escape_difficulty = 0.5
        else:
            escape_difficulty = 0.2
        suspense = (
            threat * 0.4 +
            time_p * 0.3 +
            escape_difficulty * 0.3
        )
        return max(0.0, min(1.0, suspense))

    def get_suspense_report(self, char_ids: List[str]) -> str:
        lines = ["Dramatis悬念报告:"]
        for cid in char_ids:
            suspense = self.calculate_suspense(cid)
            plans = self._protagonist_plans.get(cid, [])
            threat = self._threat_level.get(cid, 0.0)
            lines.append(
                f"  {cid}: 悬念={suspense:.2f} "
                f"威胁={threat:.2f} 可用计划={len(plans)}"
            )
        return "\n".join(lines)


class StoryArcController:
    PHASE_RANGES = {
        ArcPhase.INTRODUCTION: (0.0, 0.15),
        ArcPhase.DEVELOPMENT: (0.15, 0.5),
        ArcPhase.CLIMAX: (0.5, 0.8),
        ArcPhase.RESOLUTION: (0.8, 1.0),
    }

    def __init__(
        self,
        max_rounds: int = 5000,
        custom_inequalities: Optional[List[StoryformInequality]] = None,
        seed: int = 42,
    ):
        self.max_rounds = max_rounds
        self.storyform = StoryformEngine(custom_inequalities=custom_inequalities)
        self.suspense_model = DramatisSuspenseModel()
        self.rng = random.Random(seed)
        self._current_phase: ArcPhase = ArcPhase.INTRODUCTION
        self._phase_transitions: List[Dict[str, Any]] = []

    def get_current_phase(self, current_round: int) -> ArcPhase:
        progress = current_round / max(self.max_rounds, 1)
        for phase, (start, end) in self.PHASE_RANGES.items():
            if start <= progress < end:
                self._current_phase = phase
                return phase
        self._current_phase = ArcPhase.RESOLUTION
        return ArcPhase.RESOLUTION

    @property
    def current_phase(self) -> ArcPhase:
        return self._current_phase

    def get_phase_directives(self, phase: ArcPhase) -> Dict[str, Any]:
        directives = {
            ArcPhase.INTRODUCTION: {
                "scene_pace": "slow",
                "main_plot_weight": 0.7,
                "side_plot_weight": 0.3,
                "character_introduction_rate": 0.8,
                "conflict_intensity": 0.3,
                "beat_granularity_bias": 0.3,
                "narrative_focus": "world_building",
            },
            ArcPhase.DEVELOPMENT: {
                "scene_pace": "moderate",
                "main_plot_weight": 0.6,
                "side_plot_weight": 0.4,
                "character_introduction_rate": 0.4,
                "conflict_intensity": 0.5,
                "beat_granularity_bias": 0.5,
                "narrative_focus": "escalation",
            },
            ArcPhase.CLIMAX: {
                "scene_pace": "fast",
                "main_plot_weight": 0.8,
                "side_plot_weight": 0.2,
                "character_introduction_rate": 0.1,
                "conflict_intensity": 0.9,
                "beat_granularity_bias": 0.8,
                "narrative_focus": "confrontation",
            },
            ArcPhase.RESOLUTION: {
                "scene_pace": "decelerating",
                "main_plot_weight": 0.75,
                "side_plot_weight": 0.25,
                "character_introduction_rate": 0.1,
                "conflict_intensity": 0.4,
                "beat_granularity_bias": 0.4,
                "narrative_focus": "closure",
            },
        }
        return directives.get(phase, directives[ArcPhase.DEVELOPMENT])

    def record_phase_transition(
        self,
        from_phase: ArcPhase,
        to_phase: ArcPhase,
        round_num: int,
    ):
        self._phase_transitions.append({
            "from": from_phase.value,
            "to": to_phase.value,
            "round": round_num,
        })

    def get_suspense_adjusted_tension(
        self,
        base_tension: float,
        protagonist_ids: List[str],
    ) -> float:
        max_suspense = 0.0
        for pid in protagonist_ids:
            suspense = self.suspense_model.calculate_suspense(pid)
            max_suspense = max(max_suspense, suspense)
        adjusted = base_tension * 0.6 + max_suspense * 0.4
        return max(0.0, min(1.0, adjusted))

    def get_arc_summary(self) -> Dict[str, Any]:
        return {
            "current_phase": self._current_phase.value,
            "overall_tension": self.storyform.overall_tension,
            "phase_transitions": len(self._phase_transitions),
            "inequalities": {
                name: ineq.current_value
                for name, ineq in self.storyform.inequalities.items()
            },
        }


# ============================================================
# 叙事引擎总控 (五层整合)
# ============================================================

class NarrativeEngine:
    def __init__(
        self,
        max_rounds: int = 5000,
        emergence_preset: EmergencePreset = EmergencePreset.BALANCED,
        custom_emergence_thresholds: Optional[EmergenceThresholds] = None,
        custom_inequalities: Optional[List[StoryformInequality]] = None,
        seed: int = 42,
    ):
        self.arc_controller = StoryArcController(
            max_rounds=max_rounds,
            custom_inequalities=custom_inequalities,
            seed=seed,
        )
        self.plot_manager = PlotThreadManager(seed=seed)
        self.residency_engine = SceneResidencyEngine(seed=seed)
        self.stratifier = CharacterStratifier(seed=seed)
        self.emergence_detector = EmergenceDetector(
            preset=emergence_preset,
            custom_thresholds=custom_emergence_thresholds,
        )
        self._initialized = False

    def initialize(self, pool: Any):
        self.stratifier.initialize(pool)
        self._setup_default_main_thread()
        self._setup_default_storylets()
        self._initialized = True

    def _setup_default_main_thread(self):
        main_points = [
            PlotPoint(
                point_id="MP001",
                description="杀父之仇线索发现",
                trigger_round_range=(50, 200),
                tension_impact=0.2,
                plot_relevance=1.0,
                is_mandatory=True,
            ),
            PlotPoint(
                point_id="MP002",
                description="朝廷阴谋初露端倪",
                trigger_round_range=(200, 600),
                tension_impact=0.3,
                plot_relevance=1.0,
                is_mandatory=True,
            ),
            PlotPoint(
                point_id="MP003",
                description="门派背叛事件爆发",
                trigger_round_range=(600, 1500),
                tension_impact=0.4,
                plot_relevance=1.0,
                is_mandatory=True,
            ),
            PlotPoint(
                point_id="MP004",
                description="终极真相大白",
                trigger_round_range=(1500, 3500),
                tension_impact=0.5,
                plot_relevance=1.0,
                is_mandatory=True,
            ),
            PlotPoint(
                point_id="MP005",
                description="最终决战",
                trigger_round_range=(3500, 5000),
                tension_impact=0.8,
                plot_relevance=1.0,
                is_mandatory=True,
            ),
        ]
        main_thread = PlotThread(
            thread_id="MAIN_001",
            thread_type=PlotThreadType.MAIN,
            title="江湖真相",
            description="追寻灭门真相，揭露朝廷阴谋，面对门派背叛，最终决战",
            status=PlotThreadStatus.ACTIVE,
            plot_points=main_points,
            involved_chars=[],
            tension_level=0.3,
            priority=0.9,
        )
        self.plot_manager.register_main_thread(main_thread)

    def _setup_default_storylets(self):
        storylets = [
            Storylet(
                storylet_id="SL001",
                title="阵营冲突升级",
                description="两大阵营关系恶化到临界点",
                conditions=[
                    StoryletCondition(
                        field_path="world_state.combat_events",
                        operator=">",
                        value=30,
                    ),
                ],
                thread_type=PlotThreadType.SIDE,
                tension_impact=0.3,
                priority_boost=0.2,
            ),
            Storylet(
                storylet_id="SL002",
                title="秘密揭露契机",
                description="发现隐藏的线索指向更大阴谋",
                conditions=[
                    StoryletCondition(
                        field_path="world_state.secrets_revealed",
                        operator=">=",
                        value=3,
                    ),
                ],
                thread_type=PlotThreadType.SIDE,
                tension_impact=0.2,
                priority_boost=0.15,
            ),
            Storylet(
                storylet_id="SL003",
                title="英雄陨落",
                description="一位重要角色面临生死危机",
                conditions=[
                    StoryletCondition(
                        field_path="world_state.death_toll",
                        operator=">",
                        value=10,
                    ),
                ],
                thread_type=PlotThreadType.SIDE,
                tension_impact=0.4,
                priority_boost=0.25,
            ),
        ]
        for sl in storylets:
            self.plot_manager.register_storylet(sl)

    def process_round(
        self,
        round_num: int,
        pool: Any,
        world_state: Any,
        speaker_id: str,
        action_type: str,
        event_outcome: Any = None,
    ) -> Dict[str, Any]:
        if not self._initialized:
            return {}
        prev_phase = self.arc_controller.current_phase
        current_phase = self.arc_controller.get_current_phase(round_num)
        if prev_phase != current_phase:
            self.arc_controller.record_phase_transition(
                prev_phase, current_phase, round_num,
            )
        self.arc_controller.storyform.update_from_world(pool, world_state)
        self.stratifier.decay_prominence()
        if round_num % 25 == 0:
            self.stratifier.reclassify(pool)
        rotated_faction = self.stratifier.rotate_faction_focus(pool)
        if event_outcome and hasattr(event_outcome, "description"):
            is_significant = (
                hasattr(event_outcome, "target_dead") and event_outcome.target_dead
            ) or (
                hasattr(event_outcome, "event_type") and
                event_outcome.event_type in ("COMBAT", "ALLIANCE")
            )
            self.stratifier.record_event(
                speaker_id, event_outcome.description, round_num, is_significant,
            )
        if action_type in ("AGGRESSIVE", "FRIENDLY"):
            self.emergence_detector.record_interaction(
                char_ids=[speaker_id],
                action_type=action_type,
                round_num=round_num,
            )
        emergence_signal = self.emergence_detector.detect(round_num, pool)
        new_thread = None
        if emergence_signal:
            new_thread = self._handle_emergence(emergence_signal, round_num)
        main_tension = self.plot_manager.calculate_main_plot_tension(round_num)
        side_tension = self.plot_manager.calculate_side_plot_tension()
        beat_granularity = self.residency_engine.calc_beat_granularity(
            main_plot_tension=main_tension,
            side_plot_tension=side_tension,
            arc_phase=current_phase.value,
            current_tension=self.residency_engine.current_sequence.current_tension
            if self.residency_engine.current_sequence else 0.3,
        )
        beat_type = self._classify_beat_type(action_type, event_outcome)
        self.residency_engine.record_beat(
            beat_type=beat_type,
            round_num=round_num,
            char_ids=[speaker_id],
            tension_level=main_tension * 0.6 + side_tension * 0.4,
            plot_relevance=1.0 if action_type == "AGGRESSIVE" else 0.3,
        )
        self.plot_manager.update_priorities(round_num)
        dominant_thread = self.plot_manager.get_dominant_thread()
        directives = self.arc_controller.get_phase_directives(current_phase)
        active_cast = self.stratifier.get_active_cast(
            pool, current_phase.value, max_size=12,
        )
        context = {
            "world_state": world_state,
            "pool": pool,
        }
        triggered_storylets = self.plot_manager.check_storylets(context)
        for sl in triggered_storylets:
            self._activate_storylet(sl, round_num)
        result = {
            "phase": current_phase.value,
            "phase_directives": directives,
            "main_plot_tension": main_tension,
            "side_plot_tension": side_tension,
            "beat_granularity": beat_granularity,
            "dominant_thread": (
                dominant_thread.title if dominant_thread else "无"
            ),
            "active_cast": active_cast,
            "storyform_tension": self.arc_controller.storyform.overall_tension,
            "layer_summary": self.stratifier.get_layer_summary(),
            "thread_summary": self.plot_manager.get_thread_summary(),
            "emergence_signal": (
                {
                    "score": emergence_signal.overall_score,
                    "type": emergence_signal.suggested_thread_type,
                    "potential": emergence_signal.narrative_potential,
                } if emergence_signal else None
            ),
            "new_thread": (
                new_thread.title if new_thread else None
            ),
            "triggered_storylets": [
                {"id": sl.storylet_id, "title": sl.title}
                for sl in triggered_storylets
            ],
            "rotated_faction": (
                rotated_faction.value if rotated_faction else None
            ),
        }
        return result

    def _handle_emergence(
        self,
        signal: EmergenceSignal,
        round_num: int,
    ) -> PlotThread:
        type_titles = {
            "conspiracy": "暗中阴谋",
            "alliance": "意外结盟",
            "information_network": "情报网络",
            "conflict_escalation": "冲突升级",
            "ambient": "暗流涌动",
        }
        title = type_titles.get(signal.suggested_thread_type, "未知事件")
        desc = (
            f"检测到{signal.narrative_potential}级涌现信号: "
            f"SI={signal.synergy_index:.2f} "
            f"CS={signal.coordination_score:.2f} "
            f"II={signal.information_integration:.2f}"
        )
        return self.plot_manager.register_emergent_thread(signal, title, desc)

    def _activate_storylet(self, storylet: Storylet, round_num: int):
        self._setup_default_storylets_counter = getattr(
            self, "_setup_default_storylets_counter", 0
        ) + 1
        thread_id = f"STORYLET_{storylet.storylet_id}_{self._setup_default_storylets_counter}"
        thread = PlotThread(
            thread_id=thread_id,
            thread_type=storylet.thread_type,
            title=storylet.title,
            description=storylet.description,
            status=PlotThreadStatus.ACTIVE,
            involved_chars=storylet.required_chars,
            tension_level=0.3 + storylet.tension_impact,
            priority=0.3 + storylet.priority_boost,
            activated_at_round=round_num,
        )
        self.plot_manager.register_side_thread(thread)

    @staticmethod
    def _classify_beat_type(
        action_type: str,
        event_outcome: Any,
    ) -> BeatType:
        if action_type == "AGGRESSIVE":
            return BeatType.ACTION
        if action_type == "FRIENDLY":
            return BeatType.DIALOGUE
        if action_type == "EVASIVE":
            return BeatType.TRANSITION
        if event_outcome and hasattr(event_outcome, "event_type"):
            if event_outcome.event_type == "INFORMATION_GATHERING":
                return BeatType.REVELATION
            if event_outcome.event_type == "OBSERVATION":
                return BeatType.REACTION
        return BeatType.DIALOGUE

    def should_continue_scene(
        self,
        scene_id: str,
        has_unresolved_conflict: bool,
        protagonist_present: bool,
        advances_main_plot: bool,
    ) -> bool:
        return self.residency_engine.should_continue_scene(
            scene_id=scene_id,
            arc_phase=self.arc_controller.current_phase.value,
            has_unresolved_conflict=has_unresolved_conflict,
            protagonist_present=protagonist_present,
            advances_main_plot=advances_main_plot,
            turns_in_scene=self.residency_engine.turns_in_current_scene,
            beat_sequence=self.residency_engine.current_sequence,
        )

    def start_scene(self, scene_id: str, round_num: int):
        self.residency_engine.start_scene(
            scene_id, round_num, self.arc_controller.current_phase.value,
        )

    def end_scene(self) -> Optional[BeatSequence]:
        return self.residency_engine.end_scene()

    def get_narrative_context_for_prompt(
        self,
        round_num: int,
        speaker_id: str,
    ) -> str:
        phase = self.arc_controller.current_phase
        directives = self.arc_controller.get_phase_directives(phase)
        main_tension = self.plot_manager.calculate_main_plot_tension(round_num)
        side_tension = self.plot_manager.calculate_side_plot_tension()
        dominant = self.plot_manager.get_dominant_thread()
        layer = self.stratifier.get_layer(speaker_id)
        mem = self.stratifier.get_memory(speaker_id)
        lines = [
            f"【叙事引擎状态】",
            f"叙事弧阶段: {phase.value}",
            f"叙事焦点: {directives['narrative_focus']}",
            f"主线张力: {main_tension:.2f} | 支线张力: {side_tension:.2f}",
            f"Storyform综合张力: {self.arc_controller.storyform.overall_tension:.2f}",
            f"当前主导剧情: {dominant.title if dominant else '无'}",
            f"你的角色层级: {layer.value} | 突出度: {mem.prominence_score:.2f}",
        ]
        if mem.key_events:
            recent_events = mem.key_events[-3:]
            lines.append(f"你的近期叙事事件: {'; '.join(recent_events)}")
        thread_summary = self.plot_manager.get_thread_summary()
        lines.append(
            f"剧情进度: 主线{thread_summary['main_progress']:.0%} | "
            f"活跃线程{thread_summary['active_count']} | "
            f"已解决{thread_summary['resolved_count']}"
        )
        return "\n".join(lines)

    def get_full_report(self) -> Dict[str, Any]:
        return {
            "arc": self.arc_controller.get_arc_summary(),
            "threads": self.plot_manager.get_thread_summary(),
            "layers": self.stratifier.get_layer_summary(),
            "emergence_detections": self.emergence_detector.detection_count,
            "residency_turns": self.residency_engine.turns_in_current_scene,
            "storyform_tension": self.arc_controller.storyform.overall_tension,
        }
