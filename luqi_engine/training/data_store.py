"""
训练数据存储 — 按 character_id 分桶隔离存储
防止风格污染：每个角色的训练数据完全隔离
存储路径: training_data/{char_id}/layer{N}/*.json
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from typing import Any, Dict, List, Optional, Tuple, Union, get_args, get_origin, get_type_hints

from luqi_engine.core.types import TrainingSample, SampleQuality, AgentOutputs, AlgorithmCorrections
from luqi_engine.core.config import TrainingConfig
from luqi_engine.core.constants import (
    QualityGrade,
    _DEFAULT_DIALOGUE_SOURCE,
    _LAYER_DIR_PREFIX,
    _SAMPLE_FILE_EXTENSION,
)

_LAYER_MAP = {
    "layer1_narrative": 1,
    "layer2_decision": 2,
    "layer3_voice": 3,
    "layer4_critic": 4,
    "layer5_atmosphere": 5,
}

_DEFAULT_LAYER = 1
_JSON_INDENT = 2
_JSON_ENSURE_ASCII = False


def _construct_nested(cls, data):
    if data is None or not isinstance(data, dict):
        return data
    if not is_dataclass(cls):
        return data
    try:
        hints = get_type_hints(cls)
    except Exception:
        hints = {}
    kwargs = {}
    for f in fields(cls):
        if f.name not in data:
            continue
        value = data[f.name]
        ft = hints.get(f.name, f.type)
        kwargs[f.name] = _resolve_typed_value(ft, value)
    return cls(**kwargs)


def _resolve_typed_value(ft, value):
    if value is None:
        return None
    origin = get_origin(ft)
    args = get_args(ft)
    if origin is Union:
        dataclass_args = [a for a in args if a is not type(None) and is_dataclass(a)]
        if dataclass_args and isinstance(value, dict):
            return _construct_nested(dataclass_args[0], value)
        return value
    if origin is list:
        if args and is_dataclass(args[0]) and isinstance(value, list):
            return [_construct_nested(args[0], item) for item in value]
        return value
    if origin is dict:
        return value
    if is_dataclass(ft) and isinstance(value, dict):
        return _construct_nested(ft, value)
    return value


@dataclass
class StoreStats:
    total_samples: int = 0
    samples_by_character: Dict[str, int] = field(default_factory=dict)
    samples_by_layer: Dict[int, int] = field(default_factory=dict)
    samples_by_grade: Dict[str, int] = field(default_factory=dict)
    storage_bytes: int = 0


class TrainingDataStore:
    """
    训练数据存储
    按 character_id 分桶存储，每个角色的数据完全隔离
    """

    def __init__(self, config: Optional[TrainingConfig] = None) -> None:
        self._config = config or TrainingConfig()
        self._base_path = self._resolve_base_path()
        self._ensure_base_path()

    def store(self, sample: TrainingSample) -> str:
        if not sample.character_id:
            raise ValueError("character_id is required for storing training sample")
        if not sample.sample_id:
            raise ValueError("sample_id is required for storing training sample")

        self._enforce_max_samples(sample.character_id)

        layers = self._resolve_layers(sample.usage_tags)
        stored_paths: List[str] = []
        for layer_num in layers:
            path = self._build_sample_path(sample.character_id, layer_num, sample.sample_id)
            self._write_sample(path, sample)
            stored_paths.append(path)

        return stored_paths[0] if stored_paths else ""

    def list_samples(
        self,
        character_id: str,
        layer: Optional[int] = None,
    ) -> List[str]:
        if layer is not None:
            return self._list_layer_samples(character_id, layer)

        seen: set = set()
        all_ids: List[str] = []
        for layer_num in sorted(_LAYER_MAP.values()):
            for sid in self._list_layer_samples(character_id, layer_num):
                if sid not in seen:
                    seen.add(sid)
                    all_ids.append(sid)
        return all_ids

    def get_sample(
        self,
        character_id: str,
        sample_id: str,
        layer: Optional[int] = None,
    ) -> Optional[TrainingSample]:
        if layer is not None:
            path = self._build_sample_path(character_id, layer, sample_id)
            return self._read_sample(path)

        for layer_num in sorted(_LAYER_MAP.values()):
            path = self._build_sample_path(character_id, layer_num, sample_id)
            sample = self._read_sample(path)
            if sample is not None:
                return sample
        return None

    def get_stats(self, character_id: Optional[str] = None) -> StoreStats:
        stats = StoreStats()
        target_chars = [character_id] if character_id else self._list_character_dirs()

        for char_id in target_chars:
            seen_ids: set = set()
            char_count = 0
            for layer_num in sorted(_LAYER_MAP.values()):
                layer_ids = self._list_layer_samples(char_id, layer_num)
                count = len(layer_ids)
                stats.samples_by_layer[layer_num] = (
                    stats.samples_by_layer.get(layer_num, 0) + count
                )
                for sid in layer_ids:
                    if sid in seen_ids:
                        continue
                    seen_ids.add(sid)
                    char_count += 1
                    sample = self._read_sample(
                        self._build_sample_path(char_id, layer_num, sid)
                    )
                    if sample and sample.quality:
                        grade = sample.quality.grade
                        stats.samples_by_grade[grade] = (
                            stats.samples_by_grade.get(grade, 0) + 1
                        )
            stats.samples_by_character[char_id] = char_count
            stats.total_samples += char_count

        stats.storage_bytes = self._calculate_storage_bytes(target_chars)
        return stats

    def _resolve_base_path(self) -> str:
        path = self._config.storage_path
        if not os.path.isabs(path):
            path = os.path.join(os.getcwd(), path)
        return path

    def _ensure_base_path(self) -> None:
        os.makedirs(self._base_path, exist_ok=True)

    def _enforce_max_samples(self, character_id: str) -> None:
        max_samples = self._config.max_samples_per_character
        current_ids = self.list_samples(character_id)
        if len(current_ids) < max_samples:
            return

        overflow = len(current_ids) - max_samples + 1
        for sid in current_ids[:overflow]:
            self._delete_sample_files(character_id, sid)

    def _resolve_layers(self, usage_tags: List[str]) -> List[int]:
        if not usage_tags:
            return [_DEFAULT_LAYER]
        layers: List[int] = []
        for tag in usage_tags:
            layer_num = _LAYER_MAP.get(tag)
            if layer_num is not None and layer_num not in layers:
                layers.append(layer_num)
        if not layers:
            return [_DEFAULT_LAYER]
        return sorted(layers)

    def _build_sample_path(self, character_id: str, layer: int, sample_id: str) -> str:
        dir_path = os.path.join(
            self._base_path, character_id, f"{_LAYER_DIR_PREFIX}{layer}"
        )
        os.makedirs(dir_path, exist_ok=True)
        filename = f"{sample_id}{_SAMPLE_FILE_EXTENSION}"
        return os.path.join(dir_path, filename)

    def _write_sample(self, path: str, sample: TrainingSample) -> None:
        data = self._sample_to_dict(sample)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=_JSON_INDENT, ensure_ascii=_JSON_ENSURE_ASCII)

    def _read_sample(self, path: str) -> Optional[TrainingSample]:
        if not os.path.isfile(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return self._dict_to_sample(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    def _list_character_dirs(self) -> List[str]:
        if not os.path.isdir(self._base_path):
            return []
        entries = os.listdir(self._base_path)
        return [
            e for e in entries
            if os.path.isdir(os.path.join(self._base_path, e))
        ]

    def _list_layer_samples(self, character_id: str, layer: int) -> List[str]:
        layer_dir = os.path.join(
            self._base_path, character_id, f"{_LAYER_DIR_PREFIX}{layer}"
        )
        if not os.path.isdir(layer_dir):
            return []
        return sorted(
            os.path.splitext(f)[0]
            for f in os.listdir(layer_dir)
            if f.endswith(_SAMPLE_FILE_EXTENSION)
        )

    def _delete_sample_files(self, character_id: str, sample_id: str) -> None:
        for layer_num in _LAYER_MAP.values():
            path = self._build_sample_path(character_id, layer_num, sample_id)
            if os.path.isfile(path):
                os.remove(path)

    def _calculate_storage_bytes(self, character_ids: List[str]) -> int:
        total = 0
        for char_id in character_ids:
            for layer_num in _LAYER_MAP.values():
                layer_dir = os.path.join(
                    self._base_path, char_id, f"{_LAYER_DIR_PREFIX}{layer_num}"
                )
                if not os.path.isdir(layer_dir):
                    continue
                for fname in os.listdir(layer_dir):
                    fpath = os.path.join(layer_dir, fname)
                    if os.path.isfile(fpath):
                        total += os.path.getsize(fpath)
        return total

    @staticmethod
    def _sample_to_dict(sample: TrainingSample) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "sample_id": sample.sample_id,
            "character_id": sample.character_id,
            "timestamp": sample.timestamp,
            "narrative_version": sample.narrative_version,
            "usage_tags": sample.usage_tags,
        }
        if sample.input is not None:
            result["input"] = {
                "narrative_summary": sample.input.narrative_summary,
                "narrative_facts_recent": sample.input.narrative_facts_recent,
                "chapter_context": sample.input.chapter_context,
                "user_message": sample.input.user_message,
                "scene_context": sample.input.scene_context,
                "pace_context": sample.input.pace_context,
            }
        if sample.quality is not None:
            result["quality"] = {
                "overall_score": sample.quality.overall_score,
                "coherence_score": sample.quality.coherence_score,
                "character_faithfulness": sample.quality.character_faithfulness,
                "narrative_alignment": sample.quality.narrative_alignment,
                "grade": sample.quality.grade,
                "contamination_flags": sample.quality.contamination_flags,
            }
        if sample.final_output is not None:
            result["final_output"] = {
                "reply_text": sample.final_output.reply_text,
                "executed_action": sample.final_output.executed_action,
                "dialogue_source": sample.final_output.dialogue_source,
                "voice_renderer_used": sample.final_output.voice_renderer_used,
                "narrative_version_after": sample.final_output.narrative_version_after,
            }
        if sample.agent_outputs is not None:
            result["agent_outputs"] = asdict(sample.agent_outputs)
        if sample.algorithm_corrections is not None:
            result["algorithm_corrections"] = asdict(sample.algorithm_corrections)
        return result

    @staticmethod
    def _dict_to_sample(data: Dict[str, Any]) -> TrainingSample:
        from luqi_engine.core.types import TrainingInput, FinalOutput

        quality = None
        if "quality" in data:
            qd = data["quality"]
            quality = SampleQuality(
                overall_score=qd.get("overall_score", 0.0),
                coherence_score=qd.get("coherence_score", 0.0),
                character_faithfulness=qd.get("character_faithfulness", 0.0),
                narrative_alignment=qd.get("narrative_alignment", 0.0),
                grade=qd.get("grade", QualityGrade.BRONZE),
                contamination_flags=qd.get("contamination_flags", []),
            )

        training_input = None
        if "input" in data:
            id_ = data["input"]
            training_input = TrainingInput(
                narrative_summary=id_.get("narrative_summary", ""),
                narrative_facts_recent=id_.get("narrative_facts_recent", []),
                chapter_context=id_.get("chapter_context", ""),
                user_message=id_.get("user_message", ""),
                scene_context=id_.get("scene_context", ""),
                pace_context=id_.get("pace_context", ""),
            )

        final_output = None
        if "final_output" in data:
            fd = data["final_output"]
            final_output = FinalOutput(
                reply_text=fd.get("reply_text", ""),
                executed_action=fd.get("executed_action", ""),
                dialogue_source=fd.get("dialogue_source", _DEFAULT_DIALOGUE_SOURCE),
                voice_renderer_used=fd.get("voice_renderer_used", False),
                narrative_version_after=fd.get("narrative_version_after", 0),
            )

        agent_outputs = None
        if "agent_outputs" in data:
            agent_outputs = _construct_nested(AgentOutputs, data["agent_outputs"])

        algorithm_corrections = None
        if "algorithm_corrections" in data:
            algorithm_corrections = _construct_nested(
                AlgorithmCorrections, data["algorithm_corrections"]
            )

        return TrainingSample(
            sample_id=data.get("sample_id", ""),
            character_id=data.get("character_id", ""),
            timestamp=data.get("timestamp", 0.0),
            narrative_version=data.get("narrative_version", 0),
            input=training_input,
            agent_outputs=agent_outputs,
            algorithm_corrections=algorithm_corrections,
            quality=quality,
            final_output=final_output,
            usage_tags=data.get("usage_tags", []),
        )
