"""
Lorenz混沌与情感波动 - 基于Lorenz吸引子的混沌动力学
使用四阶Runge-Kutta方法求解，归一化输出到[0,1]区间
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import ClassVar, List, Tuple

from luqi_engine.core.rng import PCGRandom

_LORENZ_SIGMA: float = 10.0
_LORENZ_RHO: float = 28.0
_LORENZ_BETA: float = 8.0 / 3.0
_LORENZ_DEFAULT_DT: float = 0.01
_LORENZ_DEFAULT_X: float = 0.1
_LORENZ_DEFAULT_Y: float = 0.0
_LORENZ_DEFAULT_Z: float = 0.0

_NORMALIZE_RANGE_X: Tuple[float, float] = (-20.0, 20.0)
_NORMALIZE_RANGE_Y: Tuple[float, float] = (-30.0, 30.0)
_NORMALIZE_RANGE_Z: Tuple[float, float] = (0.0, 50.0)
_NORMALIZE_CLAMP_MIN: float = 0.0
_NORMALIZE_CLAMP_MAX: float = 1.0

_EMOTIONAL_FLUCTUATION_DEFAULT_COUPLING: float = 0.1
_EMOTIONAL_FLUCTUATION_DEFAULT_DECAY: float = 0.95
_EMOTIONAL_FLUCTUATION_DEFAULT_INTENSITY: float = 0.5
_EMOTIONAL_RANGE_MIN: float = -1.0
_EMOTIONAL_RANGE_MAX: float = 1.0
_PERTURB_DEFAULT_MAGNITUDE: float = 0.001
_RK4_HALF: float = 0.5
_RK4_SIXTH: float = 1.0 / 6.0
_RK4_COEFFICIENTS: Tuple[float, float, float, float] = (_RK4_HALF, _RK4_HALF, 1.0, 0.0)


def _lorenz_derivatives(
    state: Tuple[float, float, float],
    sigma: float,
    rho: float,
    beta: float,
) -> Tuple[float, float, float]:
    x, y, z = state
    dx = sigma * (y - x)
    dy = x * (rho - z) - y
    dz = x * y - beta * z
    return (dx, dy, dz)


def _rk4_step(
    state: Tuple[float, float, float],
    dt: float,
    sigma: float,
    rho: float,
    beta: float,
) -> Tuple[float, float, float]:
    k1 = _lorenz_derivatives(state, sigma, rho, beta)
    s2 = (
        state[0] + _RK4_COEFFICIENTS[0] * dt * k1[0],
        state[1] + _RK4_COEFFICIENTS[0] * dt * k1[1],
        state[2] + _RK4_COEFFICIENTS[0] * dt * k1[2],
    )
    k2 = _lorenz_derivatives(s2, sigma, rho, beta)
    s3 = (
        state[0] + _RK4_COEFFICIENTS[1] * dt * k2[0],
        state[1] + _RK4_COEFFICIENTS[1] * dt * k2[1],
        state[2] + _RK4_COEFFICIENTS[1] * dt * k2[2],
    )
    k3 = _lorenz_derivatives(s3, sigma, rho, beta)
    s4 = (
        state[0] + _RK4_COEFFICIENTS[2] * dt * k3[0],
        state[1] + _RK4_COEFFICIENTS[2] * dt * k3[1],
        state[2] + _RK4_COEFFICIENTS[2] * dt * k3[2],
    )
    k4 = _lorenz_derivatives(s4, sigma, rho, beta)
    new_x = state[0] + _RK4_SIXTH * dt * (k1[0] + 2.0 * k2[0] + 2.0 * k3[0] + k4[0])
    new_y = state[1] + _RK4_SIXTH * dt * (k1[1] + 2.0 * k2[1] + 2.0 * k3[1] + k4[1])
    new_z = state[2] + _RK4_SIXTH * dt * (k1[2] + 2.0 * k2[2] + 2.0 * k3[2] + k4[2])
    return (new_x, new_y, new_z)


def _normalize_component(value: float, low: float, high: float) -> float:
    span = high - low
    if span <= 0.0:
        return _NORMALIZE_CLAMP_MIN
    normalized = (value - low) / span
    return max(_NORMALIZE_CLAMP_MIN, min(_NORMALIZE_CLAMP_MAX, normalized))


class LorenzAttractor:
    SIGMA: ClassVar[float] = _LORENZ_SIGMA
    RHO: ClassVar[float] = _LORENZ_RHO
    BETA: ClassVar[float] = _LORENZ_BETA
    DEFAULT_DT: ClassVar[float] = _LORENZ_DEFAULT_DT

    def __init__(
        self,
        sigma: float = _LORENZ_SIGMA,
        rho: float = _LORENZ_RHO,
        beta: float = _LORENZ_BETA,
        dt: float = _LORENZ_DEFAULT_DT,
        initial_state: Optional[Tuple[float, float, float]] = None,
    ) -> None:
        self._sigma = sigma
        self._rho = rho
        self._beta = beta
        self._dt = dt
        if initial_state is not None:
            self._state = initial_state
        else:
            self._state = (_LORENZ_DEFAULT_X, _LORENZ_DEFAULT_Y, _LORENZ_DEFAULT_Z)
        self._step_count: int = 0

    def step(self) -> Tuple[float, float, float]:
        self._state = _rk4_step(self._state, self._dt, self._sigma, self._rho, self._beta)
        self._step_count += 1
        return self._state

    def step_normalized(self) -> Tuple[float, float, float]:
        raw = self.step()
        return (
            _normalize_component(raw[0], *_NORMALIZE_RANGE_X),
            _normalize_component(raw[1], *_NORMALIZE_RANGE_Y),
            _normalize_component(raw[2], *_NORMALIZE_RANGE_Z),
        )

    def advance(self, steps: int) -> List[Tuple[float, float, float]]:
        results: List[Tuple[float, float, float]] = []
        for _ in range(steps):
            results.append(self.step())
        return results

    def advance_normalized(self, steps: int) -> List[Tuple[float, float, float]]:
        results: List[Tuple[float, float, float]] = []
        for _ in range(steps):
            results.append(self.step_normalized())
        return results

    def perturb(self, rng: PCGRandom, magnitude: float = _PERTURB_DEFAULT_MAGNITUDE) -> None:
        x, y, z = self._state
        x += rng.gaussian(0.0, magnitude)
        y += rng.gaussian(0.0, magnitude)
        z += rng.gaussian(0.0, magnitude)
        self._state = (x, y, z)

    @property
    def state(self) -> Tuple[float, float, float]:
        return self._state

    @state.setter
    def state(self, value: Tuple[float, float, float]) -> None:
        self._state = value

    @property
    def step_count(self) -> int:
        return self._step_count

    def reset(self, initial_state: Optional[Tuple[float, float, float]] = None) -> None:
        if initial_state is not None:
            self._state = initial_state
        else:
            self._state = (_LORENZ_DEFAULT_X, _LORENZ_DEFAULT_Y, _LORENZ_DEFAULT_Z)
        self._step_count = 0


class EmotionalFluctuation:
    DEFAULT_COUPLING: ClassVar[float] = _EMOTIONAL_FLUCTUATION_DEFAULT_COUPLING
    DEFAULT_DECAY: ClassVar[float] = _EMOTIONAL_FLUCTUATION_DEFAULT_DECAY
    DEFAULT_INTENSITY: ClassVar[float] = _EMOTIONAL_FLUCTUATION_DEFAULT_INTENSITY

    def __init__(
        self,
        attractor: Optional[LorenzAttractor] = None,
        coupling: float = _EMOTIONAL_FLUCTUATION_DEFAULT_COUPLING,
        decay: float = _EMOTIONAL_FLUCTUATION_DEFAULT_DECAY,
    ) -> None:
        self._attractor = attractor if attractor is not None else LorenzAttractor()
        self._coupling = coupling
        self._decay = decay
        self._accumulated: Tuple[float, float, float] = (0.0, 0.0, 0.0)

    def update(self, current_emotion: Tuple[float, float, float]) -> Tuple[float, float, float]:
        chaotic = self._attractor.step_normalized()
        acc = self._accumulated
        new_acc = (
            acc[0] * self._decay + chaotic[0] * self._coupling,
            acc[1] * self._decay + chaotic[1] * self._coupling,
            acc[2] * self._decay + chaotic[2] * self._coupling,
        )
        self._accumulated = new_acc
        result = (
            max(_EMOTIONAL_RANGE_MIN, min(_EMOTIONAL_RANGE_MAX, current_emotion[0] + new_acc[0])),
            max(_EMOTIONAL_RANGE_MIN, min(_EMOTIONAL_RANGE_MAX, current_emotion[1] + new_acc[1])),
            max(_EMOTIONAL_RANGE_MIN, min(_EMOTIONAL_RANGE_MAX, current_emotion[2] + new_acc[2])),
        )
        return result

    def reset(self) -> None:
        self._accumulated = (0.0, 0.0, 0.0)
        self._attractor.reset()

    @property
    def attractor(self) -> LorenzAttractor:
        return self._attractor

    @property
    def accumulated(self) -> Tuple[float, float, float]:
        return self._accumulated
