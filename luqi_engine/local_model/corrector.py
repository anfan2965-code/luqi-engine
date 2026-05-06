from __future__ import annotations

import copy
import time
from typing import Any, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.config import LocalModelConfig
from luqi_engine.core.logging_config import get_logger

_logger = get_logger(__name__)


class ContentCorrector:
    _SEVERITY_LOW: ClassVar[float] = 0.3
    _SEVERITY_MEDIUM: ClassVar[float] = 0.6
    _SEVERITY_HIGH: ClassVar[float] = 0.9
    _NORMALIZED_RANGE_MIN: ClassVar[float] = 0.0
    _NORMALIZED_RANGE_MAX: ClassVar[float] = 1.0
    _CONFLICT_TYPE_CONTRADICTION: ClassVar[str] = "contradiction"
    _CONFLICT_TYPE_MISSING_REF: ClassVar[str] = "missing_reference"
    _CONFLICT_TYPE_TYPE_MISMATCH: ClassVar[str] = "type_mismatch"
    _CONFLICT_TYPE_RANGE_VIOLATION: ClassVar[str] = "range_violation"
    _CONFLICT_TYPE_CIRCULAR_REF: ClassVar[str] = "circular_reference"
    _CONFLICT_TYPE_SEMANTIC_DRIFT: ClassVar[str] = "semantic_drift"
    _CONFLICT_TYPE_OOC: ClassVar[str] = "out_of_character"
    _CONFLICT_TYPE_REPETITION: ClassVar[str] = "repetition"
    _REPAIR_KEY_CORRECTIONS: ClassVar[str] = "_corrections"
    _REPAIR_KEY_TIMESTAMP: ClassVar[str] = "_correction_timestamp"
    _DATA_KEY_TYPE: ClassVar[str] = "type"
    _DATA_KEY_DATA: ClassVar[str] = "data"
    _DATA_KEY_RELATIONS: ClassVar[str] = "relations"
    _DATA_KEY_CONSTRAINTS: ClassVar[str] = "constraints"
    _DATA_KEY_REFERENCES: ClassVar[str] = "references"
    _DATA_KEY_TEXT: ClassVar[str] = "text"
    _DATA_KEY_REFERENCE_TEXT: ClassVar[str] = "reference_text"
    _DATA_KEY_EXISTING_TEXTS: ClassVar[str] = "existing_texts"
    _SEMANTIC_REPORT_KEY: ClassVar[str] = "_semantic_report"
    _NUMERIC_RANGE_FIELDS: ClassVar[Tuple[str, ...]] = (
        "severity", "probability", "weight", "confidence", "score", "ratio",
    )
    _MAX_CIRCULAR_DEPTH: ClassVar[int] = 50
    _PREVIOUS_TEXTS_MAX_SIZE: ClassVar[int] = 100
    _PREVIOUS_TEXTS_KEEP_SIZE: ClassVar[int] = 50
    _CONTRADICTION_LOW: ClassVar[float] = 0.01
    _CONTRADICTION_HIGH: ClassVar[float] = 0.3
    _IRRELEVANT_THRESHOLD: ClassVar[float] = 0.45
    _CONSISTENCY_WEAK_THRESHOLD: ClassVar[float] = 0.65
    _TEXT_PREVIEW_LENGTH: ClassVar[int] = 30
    _RECENT_TEXTS_DISPLAY_LIMIT: ClassVar[int] = 20

    _ANTONYM_PAIRS: ClassVar[List[Tuple[Tuple[str, ...], Tuple[str, ...]]]] = [
        (("温柔", "善良", "仁慈", "慈悲", "和善"), ("残暴", "暴虐", "残忍", "冷酷", "狠毒")),
        (("勇敢", "坚毅", "果断", "刚强", "无畏"), ("懦弱", "胆怯", "退缩", "畏缩", "发抖", "颤抖")),
        (("诚实", "正直", "坦率", "真诚"), ("虚伪", "欺诈", "狡诈", "阴险")),
        (("慷慨", "大方", "无私"), ("吝啬", "自私", "贪婪")),
        (("谦逊", "低调", "内敛"), ("傲慢", "狂妄", "自大")),
        (("忠诚", "忠心", "忠义"), ("背叛", "叛逆", "出卖")),
        (("冷静", "理智", "沉稳"), ("暴躁", "冲动", "鲁莽")),
        (("活泼", "开朗", "乐观"), ("沉闷", "悲观", "抑郁")),
    ]

    _OOC_SEMANTIC_THRESHOLD: ClassVar[float] = 0.35

    _TYPE_SCHEMAS: ClassVar[Dict[str, Dict[str, type]]] = {
        "worldview_setting": {"name": str, "rules": list},
        "plot_logic": {"events": list, "causality": dict},
        "character_consistency": {"name": str, "personality": dict},
        "spatial_relation": {"locations": list},
        "temporal_logic": {"timeline": list},
    }

    def __init__(
        self,
        config: LocalModelConfig | None = None,
        semantic_engine: Optional[Any] = None,
    ) -> None:
        self._config = config or LocalModelConfig()
        self._semantic_engine = semantic_engine
        self._correction_log: List[Dict[str, Any]] = []
        self._previous_texts: List[Tuple[str, str]] = []

    async def correct(self, content: Dict[str, Any]) -> Dict[str, Any]:
        if not content:
            return content

        result = copy.deepcopy(content)

        conflicts = self._detect_conflicts(result)
        consistency_issues = self._check_consistency(result)
        all_issues = conflicts + consistency_issues

        if all_issues:
            result = self._repair_logic(result, all_issues)

        semantic_report = await self._run_semantic_correction(content)
        if semantic_report and (semantic_report.get("issues") or semantic_report.get("warnings")):
            result[self._SEMANTIC_REPORT_KEY] = semantic_report
            if self._config.enable_debug_output:
                issues_count = len(semantic_report.get("issues", []))
                warnings_count = len(semantic_report.get("warnings", []))
                _logger.info(
                    "Semantic check: issues=%d, warnings=%d",
                    issues_count, warnings_count,
                )

        result[self._REPAIR_KEY_TIMESTAMP] = time.time()

        text_content = content.get(self._DATA_KEY_TEXT, "")
        text_label = content.get(self._DATA_KEY_TYPE, "unknown")
        if text_content:
            self._previous_texts.append((text_label, text_content))
            if len(self._previous_texts) > self._PREVIOUS_TEXTS_MAX_SIZE:
                self._previous_texts = self._previous_texts[-self._PREVIOUS_TEXTS_KEEP_SIZE:]

        return result

    def check_character_behavior(
        self,
        character_profile: str,
        behavior_text: str,
    ) -> Optional[Dict[str, Any]]:
        if not self._semantic_engine or not hasattr(self._semantic_engine, "is_initialized"):
            return None
        if not self._semantic_engine.is_initialized:
            return None

        try:
            report = self._semantic_engine.check_consistency(
                character_profile, behavior_text, context_label="角色行为一致性"
            )

            antonym_conflicts = self._detect_antonym_conflict(character_profile, behavior_text)

            is_ooc = (
                (not report.is_consistent and report.consistency_score < self._OOC_SEMANTIC_THRESHOLD)
                or len(antonym_conflicts) > 0
            )

            all_contradictions = list(report.contradictions)
            for conflict in antonym_conflicts:
                all_contradictions.append(conflict)

            return {
                "is_ooc": is_ooc,
                "consistency_score": report.consistency_score,
                "drift_magnitude": report.drift_magnitude,
                "contradictions": all_contradictions,
                "antonym_conflicts": antonym_conflicts,
                "suggestion": report.suggestion if is_ooc else "",
            }
        except Exception as exc:
            _logger.warning("check_character_behavior异常: %s", exc)
            return None

    def _detect_antonym_conflict(
        self,
        profile_text: str,
        behavior_text: str,
    ) -> List[str]:
        conflicts: List[str] = []
        for positive_group, negative_group in self._ANTONYM_PAIRS:
            profile_has_positive = any(p in profile_text for p in positive_group)
            behavior_has_negative = any(n in behavior_text for n in negative_group)
            if profile_has_positive and behavior_has_negative:
                matched_pos = [p for p in positive_group if p in profile_text]
                matched_neg = [n for n in negative_group if n in behavior_text]
                conflicts.append(
                    f"角色设定含'{','.join(matched_pos)}'但行为含'{','.join(matched_neg)}'，疑似OOC"
                )
                break

            profile_has_negative = any(n in profile_text for n in negative_group)
            behavior_has_positive = any(p in behavior_text for p in positive_group)
            if profile_has_negative and behavior_has_positive:
                matched_neg = [n for n in negative_group if n in profile_text]
                matched_pos = [p for p in positive_group if p in behavior_text]
                conflicts.append(
                    f"角色设定含'{','.join(matched_neg)}'但行为含'{','.join(matched_pos)}'，疑似OOC"
                )
                break

        return conflicts

    def check_worldview_contradiction(
        self,
        established_setting: str,
        new_content: str,
    ) -> Optional[Dict[str, Any]]:
        if not self._semantic_engine or not self._semantic_engine.is_initialized:
            return None

        try:
            sim = self._semantic_engine.similarity(
                self._semantic_engine.encode(established_setting),
                self._semantic_engine.encode(new_content),
            )

            has_contradiction = sim < self._CONTRADICTION_HIGH and sim > self._CONTRADICTION_LOW

            return {
                "has_potential_contradiction": has_contradiction,
                "similarity": sim,
                "relation": (
                    "矛盾" if sim < self._CONTRADICTION_HIGH else
                    ("无关" if sim < self._IRRELEVANT_THRESHOLD else
                     ("相关" if sim < self._CONSISTENCY_WEAK_THRESHOLD else "一致"))
                ),
            }
        except Exception as exc:
            _logger.warning("check_worldview_contradiction异常: %s", exc)
            return None

    async def _run_semantic_correction(self, content: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self._semantic_engine or not hasattr(self._semantic_engine, "is_initialized"):
            return None
        if not self._semantic_engine.is_initialized:
            return None

        try:
            issues: List[Dict[str, Any]] = []
            warnings: List[Dict[str, Any]] = []

            ref_text = content.get(self._DATA_KEY_REFERENCE_TEXT, "")
            new_text = content.get(self._DATA_KEY_TEXT, "")

            if ref_text and new_text:
                report = self._semantic_engine.check_consistency(
                    ref_text, new_text, context_label=content.get(self._DATA_KEY_TYPE, "")
                )
                for contradiction in report.contradictions:
                    issues.append({
                        "type": self._CONFLICT_TYPE_SEMANTIC_DRIFT,
                        "message": contradiction,
                        "severity": self._SEVERITY_HIGH,
                        "consistency_score": report.consistency_score,
                    })
                for warning in report.warnings:
                    warnings.append({
                        "type": "semantic_warning",
                        "message": warning,
                        "severity": self._SEVERITY_LOW,
                    })
                if report.suggestion:
                    warnings.append({
                        "type": "suggestion",
                        "message": report.suggestion,
                        "severity": self._SEVERITY_LOW,
                    })

            existing_texts_raw = content.get(self._DATA_KEY_EXISTING_TEXTS, [])
            if new_text and existing_texts_raw:
                entries = [(t[:self._TEXT_PREVIEW_LENGTH], t) for t in existing_texts_raw[:self._RECENT_TEXTS_DISPLAY_LIMIT]]
                dup_matches = self._semantic_engine.detect_repetition(new_text, entries)
                for match in dup_matches:
                    if match.is_duplicate:
                        issues.append({
                            "type": self._CONFLICT_TYPE_REPETITION,
                            "message": (
                                f"检测到重复内容(相似度={match.similarity:.3f}), "
                                f"类型={match.overlap_type}"
                            ),
                            "severity": self._SEVERITY_MEDIUM,
                            "similarity": match.similarity,
                        })
                    elif match.overlap_type == "near_duplicate":
                        warnings.append({
                            "type": "near_repetition",
                            "message": (
                                f"疑似近似内容(相似度={match.similarity:.3f})"
                            ),
                            "severity": self._SEVERITY_LOW,
                        })

            if issues or warnings:
                return {
                    "issues": issues,
                    "warnings": warnings,
                    "checked_at": time.time(),
                }
            return None
        except Exception as e:
            _logger.error("Semantic check exception: %s", e)
            return None

    def get_recent_texts(self, limit: int = 20) -> List[Tuple[str, str]]:
        return list(self._previous_texts[-limit:])

    def clear_history(self) -> None:
        self._previous_texts.clear()

    def _detect_conflicts(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        conflicts: List[Dict[str, Any]] = []
        conflicts.extend(self._detect_contradictions(content))
        conflicts.extend(self._detect_missing_references(content))
        conflicts.extend(self._detect_circular_references(content))
        return conflicts

    def _detect_contradictions(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        contradictions: List[Dict[str, Any]] = []
        data_section = content.get(self._DATA_KEY_DATA, {})
        if not isinstance(data_section, dict):
            return contradictions
        constraints = content.get(self._DATA_KEY_CONSTRAINTS, [])
        if not isinstance(constraints, list):
            return contradictions
        for constraint in constraints:
            if not isinstance(constraint, dict):
                continue
            field_name = constraint.get("field", "")
            if not field_name or field_name not in data_section:
                continue
            actual_value = data_section[field_name]
            constraint_type = constraint.get("type", "")
            if constraint_type == "enum":
                allowed = constraint.get("values", [])
                if actual_value not in allowed:
                    contradictions.append({
                        "type": self._CONFLICT_TYPE_CONTRADICTION,
                        "field": field_name,
                        "actual": actual_value,
                        "expected_one_of": allowed,
                        "severity": self._SEVERITY_HIGH,
                    })
            elif constraint_type == "range":
                min_val = constraint.get("min")
                max_val = constraint.get("max")
                if isinstance(actual_value, (int, float)):
                    if min_val is not None and actual_value < min_val:
                        contradictions.append({
                            "type": self._CONFLICT_TYPE_RANGE_VIOLATION,
                            "field": field_name,
                            "actual": actual_value,
                            "min": min_val,
                            "severity": self._SEVERITY_MEDIUM,
                        })
                    if max_val is not None and actual_value > max_val:
                        contradictions.append({
                            "type": self._CONFLICT_TYPE_RANGE_VIOLATION,
                            "field": field_name,
                            "actual": actual_value,
                            "max": max_val,
                            "severity": self._SEVERITY_MEDIUM,
                        })
        return contradictions

    def _detect_missing_references(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        references = content.get(self._DATA_KEY_REFERENCES, [])
        if not isinstance(references, list):
            return issues
        data_section = content.get(self._DATA_KEY_DATA, {})
        if not isinstance(data_section, dict):
            return issues
        known_keys = set(data_section.keys())
        for ref in references:
            if isinstance(ref, str) and ref not in known_keys:
                issues.append({
                    "type": self._CONFLICT_TYPE_MISSING_REF,
                    "reference": ref,
                    "severity": self._SEVERITY_MEDIUM,
                })
            elif isinstance(ref, dict):
                ref_key = ref.get("key", "")
                if ref_key and ref_key not in known_keys:
                    issues.append({
                        "type": self._CONFLICT_TYPE_MISSING_REF,
                        "reference": ref_key,
                        "severity": self._SEVERITY_MEDIUM,
                    })
        return issues

    def _detect_circular_references(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        relations = content.get(self._DATA_KEY_RELATIONS, [])
        if not isinstance(relations, list):
            return issues
        graph: Dict[str, List[str]] = {}
        for rel in relations:
            if not isinstance(rel, dict):
                continue
            source = rel.get("source", "")
            target = rel.get("target", "")
            if source and target:
                graph.setdefault(source, []).append(target)
        visited_global: set = set()
        for node in graph:
            if node in visited_global:
                continue
            path: List[str] = []
            if self._has_cycle(graph, node, path, set(), visited_global):
                issues.append({
                    "type": self._CONFLICT_TYPE_CIRCULAR_REF,
                    "path": path,
                    "severity": self._SEVERITY_HIGH,
                })
        return issues

    def _has_cycle(
        self,
        graph: Dict[str, List[str]],
        node: str,
        path: List[str],
        visiting: set,
        visited_global: set,
    ) -> bool:
        if len(path) > self._MAX_CIRCULAR_DEPTH:
            return False
        if node in visiting:
            cycle_start = path.index(node) if node in path else 0
            path[:] = path[cycle_start:] + [node]
            return True
        visiting.add(node)
        path.append(node)
        for neighbor in graph.get(node, []):
            if self._has_cycle(graph, neighbor, path, visiting, visited_global):
                return True
        visiting.discard(node)
        visited_global.add(node)
        path.pop()
        return False

    def _check_consistency(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        data_section = content.get(self._DATA_KEY_DATA, {})
        if not isinstance(data_section, dict):
            return issues
        for field_name in self._NUMERIC_RANGE_FIELDS:
            if field_name in data_section:
                value = data_section[field_name]
                if isinstance(value, (int, float)):
                    if not (self._NORMALIZED_RANGE_MIN <= value <= self._NORMALIZED_RANGE_MAX):
                        issues.append({
                            "type": self._CONFLICT_TYPE_RANGE_VIOLATION,
                            "field": field_name,
                            "actual": value,
                            "expected_range": [self._NORMALIZED_RANGE_MIN, self._NORMALIZED_RANGE_MAX],
                            "severity": self._SEVERITY_LOW,
                        })
        issues.extend(self._check_type_consistency(content))
        return issues

    def _check_type_consistency(self, content: Dict[str, Any]) -> List[Dict[str, Any]]:
        issues: List[Dict[str, Any]] = []
        data_section = content.get(self._DATA_KEY_DATA, {})
        if not isinstance(data_section, dict):
            return issues
        content_type = content.get(self._DATA_KEY_TYPE, "")
        if not content_type:
            return issues
        schema = self._TYPE_SCHEMAS.get(content_type)
        if not schema:
            return issues
        for field, expected_type in schema.items():
            if field in data_section and not isinstance(data_section[field], expected_type):
                issues.append({
                    "type": self._CONFLICT_TYPE_TYPE_MISMATCH,
                    "field": field,
                    "actual_type": type(data_section[field]).__name__,
                    "expected_type": expected_type.__name__,
                    "severity": self._SEVERITY_MEDIUM,
                })
        return issues

    def _repair_logic(self, content: Dict[str, Any], issues: List[Dict[str, Any]]) -> Dict[str, Any]:
        corrections: List[Dict[str, Any]] = []
        for issue in issues:
            repair = self._apply_repair(content, issue)
            if repair:
                corrections.append(repair)
        if corrections:
            content[self._REPAIR_KEY_CORRECTIONS] = corrections
        return content

    def _apply_repair(self, content: Dict[str, Any], issue: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        issue_type = issue.get("type", "")
        data_section = content.get(self._DATA_KEY_DATA, {})
        if not isinstance(data_section, dict):
            return None
        if issue_type == self._CONFLICT_TYPE_RANGE_VIOLATION:
            field = issue.get("field", "")
            if field in data_section and isinstance(data_section[field], (int, float)):
                original = data_section[field]
                clamped = max(self._NORMALIZED_RANGE_MIN, min(self._NORMALIZED_RANGE_MAX, original))
                data_section[field] = clamped
                return {
                    "field": field,
                    "original": original,
                    "repaired": clamped,
                    "issue_type": issue_type,
                }
        elif issue_type == self._CONFLICT_TYPE_TYPE_MISMATCH:
            field = issue.get("field", "")
            expected_type_name = issue.get("expected", "")
            if field in data_section:
                original = data_section[field]
                repaired = self._coerce_type(original, expected_type_name)
                if repaired is not None:
                    data_section[field] = repaired
                    return {
                        "field": field,
                        "original": original,
                        "repaired": repaired,
                        "issue_type": issue_type,
                    }
        elif issue_type == self._CONFLICT_TYPE_MISSING_REF:
            ref = issue.get("reference", "")
            if ref:
                data_section[ref] = None
                return {
                    "field": ref,
                    "action": "added_null_placeholder",
                    "issue_type": issue_type,
                }
        elif issue_type == self._CONFLICT_TYPE_CIRCULAR_REF:
            path = issue.get("path", [])
            if len(path) >= 2:
                relations = content.get(self._DATA_KEY_RELATIONS, [])
                if isinstance(relations, list):
                    source = path[-2] if len(path) >= 2 else ""
                    target = path[-1]
                    relations = [
                        r for r in relations
                        if not (
                            isinstance(r, dict)
                            and r.get("source") == source
                            and r.get("target") == target
                        )
                    ]
                    content[self._DATA_KEY_RELATIONS] = relations
                    return {
                        "action": "removed_circular_edge",
                        "source": source,
                        "target": target,
                        "issue_type": issue_type,
                    }
        return None

    @staticmethod
    def _coerce_type(value: Any, target_type_name: str) -> Any:
        type_map: Dict[str, type] = {
            "str": str,
            "int": int,
            "float": float,
            "list": list,
            "dict": dict,
            "bool": bool,
        }
        target_type = type_map.get(target_type_name)
        if target_type is None:
            return None
        if isinstance(value, target_type):
            return value
        try:
            if target_type is str:
                return str(value)
            elif target_type is int:
                return int(float(value))
            elif target_type is float:
                return float(value)
            elif target_type is list:
                return [value]
            elif target_type is dict:
                return {"value": value}
            elif target_type is bool:
                return bool(value)
        except (ValueError, TypeError):
            return None
        return None

    def get_correction_log(self) -> List[Dict[str, Any]]:
        return list(self._correction_log)

    def clear_correction_log(self) -> None:
        self._correction_log.clear()
