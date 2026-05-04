"""
引擎状态快照系统 - ISnapshotable协议 + EngineSnapshot管理器
提供引擎全量状态保存/恢复能力，支持原子写入和版本兼容性检查
"""

from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict


class SnapshotError(Exception):
    """快照操作相关异常"""

    pass


class ISnapshotable(ABC):
    """
    可快照子系统协议
    所有需要参与引擎状态持久化的子系统必须实现此接口
    """

    @abstractmethod
    def save_snapshot(self) -> Dict[str, Any]:
        """
        返回子系统完整状态的字典，必须可JSON序列化

        Returns:
            Dict[str, Any]: 子系统状态数据
        """

    @abstractmethod
    def load_snapshot(self, data: Dict[str, Any]) -> None:
        """
        从字典恢复子系统完整状态

        Args:
            data: 之前通过save_snapshot()保存的状态字典
        """


class EngineSnapshot:
    """
    引擎快照管理器
    负责收集所有ISnapshotable子系统的状态并序列化为JSON文件
    支持原子写入（先写临时文件再rename）和版本校验
    """

    SNAPSHOT_VERSION = "1.0"
    _SUBSYSTEM_KEYS = [
        "worldview",
        "narrative",
        "scene",
        "interaction",
        "character_manager",
    ]

    @staticmethod
    def save(engine: Any, path: str) -> str:
        """
        将引擎全量状态保存为JSON文件

        流程：
        1. 收集所有 ISnapshotable 子系统的 save_snapshot() 结果
        2. 包装为 {"version", "timestamp", "subsystems": {...}}
        3. 原子写入到 path（先写临时文件再rename）
        4. 返回实际保存路径

        Args:
            engine: 引擎实例，需包含 worldview/narrative/scene/interaction/character_manager 属性
            path: 目标文件路径

        Returns:
            str: 实际保存的文件路径

        Raises:
            SnapshotError: 保存过程中发生错误
        """
        subsystems: Dict[str, Any] = {}
        for key in EngineSnapshot._SUBSYSTEM_KEYS:
            subsystem = getattr(engine, key, None)
            if subsystem is None:
                continue
            if not isinstance(subsystem, ISnapshotable):
                raise SnapshotError(
                    f"子系统 '{key}' 未实现 ISnapshotable 接口"
                )
            try:
                subsystems[key] = subsystem.save_snapshot()
            except Exception as exc:
                raise SnapshotError(f"保存子系统 '{key}' 状态失败: {exc}") from exc

        snapshot_data: Dict[str, Any] = {
            "version": EngineSnapshot.SNAPSHOT_VERSION,
            "timestamp": time.time(),
            "subsystems": subsystems,
        }

        target_path = Path(path)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = target_path.with_suffix(target_path.suffix + ".tmp")

        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(snapshot_data, f, ensure_ascii=False, indent=2)
            os.replace(str(tmp_path), str(target_path))
        except (OSError, IOError) as exc:
            if tmp_path.exists():
                tmp_path.unlink()
            raise SnapshotError(f"写入快照文件失败: {exc}") from exc

        return str(target_path)

    @staticmethod
    def load(path: str) -> Dict[str, Any]:
        """
        从JSON文件加载快照数据

        返回可用于 engine.load_snapshot() 的字典。
        包含版本校验和基本完整性检查。

        Args:
            path: 快照文件路径

        Returns:
            Dict[str, Any]: 包含 version/timestamp/subsystems 的快照字典

        Raises:
            SnapshotError: 文件不存在、格式错误或版本不兼容
        """
        file_path = Path(path)
        if not file_path.exists():
            raise SnapshotError(f"快照文件不存在: {path}")

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            raise SnapshotError(f"读取快照文件失败: {exc}") from exc

        if not isinstance(data, dict):
            raise SnapshotError("快照文件根节点必须是字典")

        version = data.get("version")
        if version is None:
            raise SnapshotError("快照缺少 version 字段")

        major_version = str(version).split(".")[0]
        current_major = EngineSnapshot.SNAPSHOT_VERSION.split(".")[0]
        if major_version != current_major:
            raise SnapshotError(
                f"快照版本不兼容: 文件版本={version}, "
                f"当前支持版本={EngineSnapshot.SNAPSHOT_VERSION}"
            )

        subsystems = data.get("subsystems")
        if subsystems is None:
            raise SnapshotError("快照缺少 subsystems 字段")
        if not isinstance(subsystems, dict):
            raise SnapshotError("subsystems 必须是字典类型")

        return data
