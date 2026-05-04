"""
概率分布工具包 - 提供正态/指数/帕累托/Beta/三角形分布采样
所有采样基于PCGRandom，不依赖numpy
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Dict, List, Optional, Tuple

from luqi_engine.core.rng import PCGRandom

_DISTRIBUTION_NORMAL_DEFAULT_MEAN: float = 0.0
_DISTRIBUTION_NORMAL_DEFAULT_STDDEV: float = 1.0
_DISTRIBUTION_EXPONENTIAL_DEFAULT_LAMBDA: float = 1.0
_DISTRIBUTION_PARETO_DEFAULT_ALPHA: float = 1.0
_DISTRIBUTION_PARETO_DEFAULT_XM: float = 1.0
_DISTRIBUTION_BETA_DEFAULT_ALPHA: float = 1.0
_DISTRIBUTION_BETA_DEFAULT_BETA: float = 1.0
_DISTRIBUTION_TRIANGULAR_DEFAULT_LOW: float = 0.0
_DISTRIBUTION_TRIANGULAR_DEFAULT_HIGH: float = 1.0
_DISTRIBUTION_TRIANGULAR_DEFAULT_MODE_RATIO: float = 0.5

_BETA_ITERATION_LIMIT: int = 1000
_GAMMA_EULER_MASCHERONI: float = 0.5772156649015329
_LOG_2: float = math.log(2.0)
_SQRT_2_PI: float = math.sqrt(2.0 * math.pi)
_MARSAGLIA_TSANG_QUICK_ACCEPT: float = 0.0331


def _gamma_func(x: float) -> float:
    if x <= 0.0:
        return 0.0
    if x < 0.5:
        return math.pi / (math.sin(math.pi * x) * _gamma_func(1.0 - x))
    x -= 1.0
    a = 0.99999999999980993
    coefficients = (
        676.5203681218851,
        -1259.1392167224028,
        771.32342877765313,
        -176.61502916214059,
        12.507343278686905,
        -0.13857109526572012,
        9.9843695780195716e-6,
        1.5056327351493116e-7,
    )
    for i, c in enumerate(coefficients):
        a += c / (x + i + 1.0)
    t = x + len(coefficients) - 0.5
    return math.sqrt(2.0 * math.pi) * t ** (x + 0.5) * math.exp(-t) * a


def _sample_gamma(rng: PCGRandom, shape: float, scale: float = 1.0) -> float:
    if shape < 1.0:
        return _sample_gamma(rng, shape + 1.0, scale) * (rng.uniform(0.0, 1.0) ** (1.0 / shape))
    d = shape - 1.0 / 3.0
    c = 1.0 / math.sqrt(9.0 * d)
    for _ in range(_BETA_ITERATION_LIMIT):
        while True:
            x = rng.gaussian(0.0, 1.0)
            v = 1.0 + c * x
            if v > 0.0:
                break
        v = v * v * v
        u = rng.uniform(0.0, 1.0)
        if u < 1.0 - _MARSAGLIA_TSANG_QUICK_ACCEPT * (x * x) * (x * x):
            return d * v * scale
        if math.log(u) < 0.5 * x * x + d * (1.0 - v + math.log(v)):
            return d * v * scale
    return shape * scale


class DistributionToolkit:
    NORMAL_DEFAULT_MEAN: ClassVar[float] = _DISTRIBUTION_NORMAL_DEFAULT_MEAN
    NORMAL_DEFAULT_STDDEV: ClassVar[float] = _DISTRIBUTION_NORMAL_DEFAULT_STDDEV
    EXPONENTIAL_DEFAULT_LAMBDA: ClassVar[float] = _DISTRIBUTION_EXPONENTIAL_DEFAULT_LAMBDA
    PARETO_DEFAULT_ALPHA: ClassVar[float] = _DISTRIBUTION_PARETO_DEFAULT_ALPHA
    PARETO_DEFAULT_XM: ClassVar[float] = _DISTRIBUTION_PARETO_DEFAULT_XM
    BETA_DEFAULT_ALPHA: ClassVar[float] = _DISTRIBUTION_BETA_DEFAULT_ALPHA
    BETA_DEFAULT_BETA: ClassVar[float] = _DISTRIBUTION_BETA_DEFAULT_BETA
    TRIANGULAR_DEFAULT_LOW: ClassVar[float] = _DISTRIBUTION_TRIANGULAR_DEFAULT_LOW
    TRIANGULAR_DEFAULT_HIGH: ClassVar[float] = _DISTRIBUTION_TRIANGULAR_DEFAULT_HIGH
    TRIANGULAR_DEFAULT_MODE_RATIO: ClassVar[float] = _DISTRIBUTION_TRIANGULAR_DEFAULT_MODE_RATIO

    def __init__(self, rng: Optional[PCGRandom] = None) -> None:
        self._rng = rng if rng is not None else PCGRandom()

    def normal(self, mean: float = _DISTRIBUTION_NORMAL_DEFAULT_MEAN, stddev: float = _DISTRIBUTION_NORMAL_DEFAULT_STDDEV) -> float:
        return self._rng.gaussian(mean, stddev)

    def exponential(self, lam: float = _DISTRIBUTION_EXPONENTIAL_DEFAULT_LAMBDA) -> float:
        if lam <= 0.0:
            raise ValueError("lambda must be positive")
        u = self._rng.uniform(0.0, 1.0)
        return -math.log(1.0 - u) / lam

    def pareto(self, alpha: float = _DISTRIBUTION_PARETO_DEFAULT_ALPHA, xm: float = _DISTRIBUTION_PARETO_DEFAULT_XM) -> float:
        if alpha <= 0.0:
            raise ValueError("alpha must be positive")
        if xm <= 0.0:
            raise ValueError("xm must be positive")
        u = self._rng.uniform(0.0, 1.0)
        return xm / (1.0 - u) ** (1.0 / alpha)

    def beta(self, a: float = _DISTRIBUTION_BETA_DEFAULT_ALPHA, b: float = _DISTRIBUTION_BETA_DEFAULT_BETA) -> float:
        if a <= 0.0:
            raise ValueError("alpha must be positive")
        if b <= 0.0:
            raise ValueError("beta must be positive")
        x = _sample_gamma(self._rng, a)
        y = _sample_gamma(self._rng, b)
        total = x + y
        if total == 0.0:
            return a / (a + b)
        return x / total

    def triangular(
        self,
        low: float = _DISTRIBUTION_TRIANGULAR_DEFAULT_LOW,
        high: float = _DISTRIBUTION_TRIANGULAR_DEFAULT_HIGH,
        mode_ratio: float = _DISTRIBUTION_TRIANGULAR_DEFAULT_MODE_RATIO,
    ) -> float:
        if low >= high:
            raise ValueError("low must be less than high")
        mode_ratio = max(0.0, min(1.0, mode_ratio))
        u = self._rng.uniform(0.0, 1.0)
        span = high - low
        if u < mode_ratio:
            return low + span * math.sqrt(u * mode_ratio)
        else:
            return high - span * math.sqrt((1.0 - u) * (1.0 - mode_ratio))

    def sample(self, distribution: str, **params: Any) -> float:
        dispatch: Dict[str, Callable[..., float]] = {
            "normal": self.normal,
            "exponential": self.exponential,
            "pareto": self.pareto,
            "beta": self.beta,
            "triangular": self.triangular,
        }
        if distribution not in dispatch:
            raise ValueError(f"unknown distribution: {distribution}")
        return dispatch[distribution](**params)

    @property
    def rng(self) -> PCGRandom:
        return self._rng
