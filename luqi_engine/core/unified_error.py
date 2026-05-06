"""
统一异常体系 — Phase 4 生产就绪组件

定义鹿栖引擎所有模块的异常层次结构, 确保错误信息一致性和可追溯性。

设计原则:
- 层次化: 基类→模块级→具体异常, 支持精确捕获
- 信息丰富: 每个异常携带上下文, 便于调试和日志
- 可序列化: 所有异常支持 str() 输出人类可读消息
- 零吞没: 异常必须被显式处理或向上传播

异常分类树:
LuqiEngineError (基类)
├── ConfigurationError          — 配置/参数错误
│   └── ParameterOutOfBounds    — 参数超出合法范围
├── SubsystemInitializationError — 子系统初始化失败
├── BeliefError                 — 信念系统相关
│   ├── InvalidObservationError  — 无效观测数据
│   └── BeliefTargetLimitExceeded — 超过最大跟踪目标数
├── GameTheoryError             — 博弈论模块通用
│   ├── NoEquilibriumFound      — 无法找到纳什均衡
│   ├── InvalidPayoffMatrix     — 无效收益矩阵
│   └── TemperatureOutOfRange   — 温度参数越界
└── MechanismDesignError        — 机制设计层
    ├── IncompatibilityDetected — 激励不相容检测到
    └── ParameterOutOfBounds    — 机制参数越界
└── PerformanceBudgetExceeded   — 性能预算超限
"""

from __future__ import annotations

from typing import Any, Optional


class LuqiEngineError(Exception):
    """
    鹿栖引擎基础异常
    
    所有引擎内部异常的根类。捕获此异常可以处理任何引擎级别的错误。
    
    Attributes:
        message: 人类可读的错误描述
        details: 额外的结构化错误详情 (可选)
    """
    
    def __init__(self, message: str = "", details: Optional[dict] = None) -> None:
        self.message = message or "An unknown error occurred in Luqi Engine"
        self.details = details or {}
        super().__init__(self.message)
    
    def __str__(self) -> str:
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"[{self.__class__.__name__}] {self.message} ({detail_str})"
        return f"[{self.__class__.__name__}] {self.message}"
    
    def to_dict(self) -> dict:
        """序列化为字典 (用于日志/API响应)"""
        return {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "details": self.details,
        }


# ============================================================
# 配置与初始化异常
# ============================================================

class ConfigurationError(LuqiEngineError):
    """
    配置错误 — 无效的配置值或缺失必要配置项
    """
    
    def __init__(
        self,
        param_name: str,
        value: Any,
        reason: str = "",
        **kwargs,
    ) -> None:
        super().__init__(
            message=f"Configuration error for '{param_name}': got {value!r}. {reason}",
            details={"parameter": param_name, "value": str(value), "reason": reason},
            **kwargs,
        )


class SubsystemInitializationError(LuqiEngineError):
    """
    子系统初始化失败 — 依赖未满足或资源不可用
    """
    
    def __init__(
        self,
        subsystem: str,
        reason: str = "",
        cause: Optional[Exception] = None,
        **kwargs,
    ) -> None:
        details: dict = {"subsystem": subsystem, "reason": reason}
        if cause is not None:
            details["cause"] = str(cause)
        super().__init__(
            message=f"Failed to initialize subsystem '{subsystem}': {reason}",
            details=details,
            **kwargs,
        )


# ============================================================
# 信念系统异常
# ============================================================

class BeliefError(LuqiEngineError):
    """信念系统相关异常基类"""
    
    def __init__(self, target_id: str = "", dimension: str = "", **kwargs) -> None:
        extra_details: dict = {}
        if target_id:
            extra_details["target_id"] = target_id
        if dimension:
            extra_details["dimension"] = dimension
        super().__init__(**kwargs, details={**extra_details, **(kwargs.get("details") or {})})


class InvalidObservationError(BeliefError):
    """
    无效观测数据 — evidence_value 或 source_reliability 超出 [0,1] 或为 NaN/Inf
    """
    
    def __init__(
        self,
        field_name: str,
        actual_value: Any,
        valid_range: tuple = (0.0, 1.0),
        **kwargs,
    ) -> None:
        super().__init__(
            message=(
                f"Invalid observation: '{field_name}'={actual_value!r}, "
                f"expected range {valid_range}"
            ),
            details={
                "field": field_name,
                "actual_value": str(actual_value),
                "valid_range": str(valid_range),
            },
            **kwargs,
        )


class BeliefTargetLimitExceeded(BeliefError):
    """
    超过最大跟踪目标数 — 无法再添加新的信念目标
    """
    
    def __init__(
        self,
        current_count: int,
        max_allowed: int,
        rejected_target: str = "",
        **kwargs,
    ) -> None:
        super().__init__(
            target_id=rejected_target,
            message=(
                f"Belief target limit exceeded: {current_count}/{max_allowed}. "
                f"Cannot track additional target '{rejected_target}'."
            ),
            details={
                "current_count": current_count,
                "max_allowed": max_allowed,
                "rejected_target": rejected_target,
            },
            **kwargs,
        )


# ============================================================
# 博弈论模块通用异常
# ============================================================

class GameTheoryError(LuqiEngineError):
    """博弈论模块通用异常基类"""
    pass


class NoEquilibriumFound(GameTheoryError):
    """
    无法找到纳什均衡 — 给定收益矩阵无纯策略或混合策略均衡
    
    可能原因:
    - 收益矩阵维度不匹配
    - 收益值导致数值不稳定
    - 博弈不存在有限均衡
    """
    
    def __init__(
        self,
        matrix_size: tuple = (),
        reason: str = "",
        **kwargs,
    ) -> None:
        size_str = f"{matrix_size[0]}x{matrix_size[1]}" if len(matrix_size) == 2 else "unknown"
        super().__init__(
            message=f"No Nash equilibrium found for payoff matrix ({size_str}): {reason}",
            details={"matrix_size": size_str, "reason": reason},
            **kwargs,
        )


class InvalidPayoffMatrix(GameTheoryError):
    """
    无效收益矩阵 — 维度不一致、包含非法值或格式不正确
    """
    
    def __init__(
        self,
        reason: str = "",
        expected_shape: Optional[tuple] = None,
        actual_shape: Optional[tuple] = None,
        **kwargs,
    ) -> None:
        msg = f"Invalid payoff matrix: {reason}"
        if expected_shape and actual_shape:
            msg += f" (expected {expected_shape}, got {actual_shape})"
        super().__init__(
            message=msg,
            details={
                "reason": reason,
                "expected_shape": str(expected_shape),
                "actual_shape": str(actual_shape),
            },
            **kwargs,
        )


class TemperatureOutOfRange(GameTheoryError):
    """
    温度参数越界 — τ 不在有效范围内 [min_temp, max_temp]
    """
    
    def __init__(
        self,
        temperature: float,
        valid_range: tuple,
        **kwargs,
    ) -> None:
        super().__init__(
            message=(
                f"Temperature {temperature:.4f} out of valid range "
                f"[{valid_range[0]:.4f}, {valid_range[1]:.4f}]"
            ),
            details={
                "temperature": temperature,
                "min_valid": valid_range[0],
                "max_valid": valid_range[1],
            },
            **kwargs,
        )


# ============================================================
# 机制设计层异常
# ============================================================

class MechanismDesignError(LuqiEngineError):
    """机制设计层异常基类"""
    pass


class IncompatibilityDetected(MechanismDesignError):
    """
    激励不相容检测到 — 目标行为不是参与者的最优选择
    """
    
    def __init__(
        self,
        target_behavior: str,
        deviation_payoff: float,
        target_payoff: float,
        **kwargs,
    ) -> None:
        super().__init__(
            message=(
                f"Incentive incompatibility detected: '{target_behavior}' yields "
                f"{target_payoff:.3f}, but deviation yields {deviation_payoff:.3f}"
            ),
            details={
                "target_behavior": target_behavior,
                "deviation_payoff": deviation_payoff,
                "target_payoff": target_payoff,
                "gap": round(deviation_payoff - target_payoff, 4),
            },
            **kwargs,
        )


class ParameterOutOfBounds(MechanismDesignError):
    """
    机制参数越界 — 设置的值超出了该参数的允许范围
    """
    
    def __init__(
        self,
        parameter: str,
        value: float,
        allowed_range: tuple,
        **kwargs,
    ) -> None:
        super().__init__(
            message=(
                f"Mechanism parameter '{parameter}' value {value:.4f} "
                f"out of bounds [{allowed_range[0]:.4f}, {allowed_range[1]:.4f}]"
            ),
            details={
                "parameter": parameter,
                "value": value,
                "min_allowed": allowed_range[0],
                "max_allowed": allowed_range[1],
            },
            **kwargs,
        )


# ============================================================
# 性能异常
# ============================================================

class PerformanceBudgetExceeded(LuqiEngineError):
    """
    性能预算超限 — 操作耗时超过预定义阈值
    
    用于生产环境监控和告警。
    """
    
    def __init__(
        self,
        operation: str,
        budget_ms: float,
        actual_ms: float,
        **kwargs,
    ) -> None:
        super().__init__(
            message=(
                f"Performance budget exceeded: '{operation}' took "
                f"{actual_ms:.2f}ms (budget: {budget_ms:.2f}ms), "
                f"overrun by {(actual_ms - budget_ms):.2f}ms"
            ),
            details={
                "operation": operation,
                "budget_ms": budget_ms,
                "actual_ms": actual_ms,
                "overrun_ms": round(actual_ms - budget_ms, 3),
            },
            **kwargs,
        )
