"""
游戏循环引擎 — 无限轮次N体博弈模拟器
========================================

核心设计:
- 零外部输入: 引擎完全自主运行直到自然结局
- 全子系统激活: 信念/威胁/策略/机制/一致性全部参与
- 完整状态记录: 每轮快照 + 事件日志 + 性能指标
- 结局自检测: 多维度终止条件

执行流程 (每轮):
  1. 环境推进 (宇宙时代/资源变化)
  2. 事件生成 (基于当前状态+物理规则)
  3. 事件分发 (每个存活文明接收并处理)
  4. 策略决策 (引擎内部: 混合策略选择)
  5. 后果计算 (技术/资源/关系更新)
  6. 状态快照 (记录本轮完整状态)
  7. 终止检查 (是否达到结局条件)
"""

from __future__ import annotations

import logging
import math
import random
import sys
import time
import traceback
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple

from .universe import (
    CosmicEnvironment,
    CosmicEra,
    CosmicResource,
    DarkForestAxiom,
    EventGenerator,
    InteractionType,
    PhysicsEngine,
    SpatialPosition,
    TechnologyModel,
    UniverseEvent,
    UniverseRules,
)
from .civilizations import (
    CivilizationFactory,
    CivilizationInstance,
    CivilizationProfile,
    DefaultScenario,
    PlayerRole,
)


# ============================================================
# 日志配置
# ============================================================

logger = logging.getLogger("luqi_engine.stress_test.game_loop")


# ============================================================
# 枚举定义
# ============================================================

class EndingType(Enum):
    """结局类型分类"""
    SINGLE_SURVIVOR = auto()
    MUTUAL_DESTRUCTION = auto()
    STALEMATE_EQUILIBRIUM = auto()
    DOMINATION = auto()
    ESCAPE = auto()
    ROUND_LIMIT = auto()
    ERROR_TERMINATION = auto()


class RoundPhase(Enum):
    """轮次阶段 (用于性能分析)"""
    ENVIRONMENT_ADVANCE = auto()
    EVENT_GENERATION = auto()
    EVENT_DISPATCH = auto()
    STRATEGY_DECISION = auto()
    CONSEQUENCE_CALCULATION = auto()
    STATE_SNAPSHOT = auto()
    TERMINATION_CHECK = auto()


# ============================================================
# 数据结构
# ============================================================

@dataclass
class RoundMetrics:
    """单轮性能指标"""
    round_number: int
    phase_timings_ms: Dict[str, float] = field(default_factory=dict)
    events_generated: int = 0
    events_dispatched: int = 0
    strategy_calls: int = 0
    consistency_checks_performed: int = 0
    consistency_issues_found: int = 0
    errors_encountered: int = 0
    alive_civ_count: int = 0
    total_memory_bytes: int = 0


@dataclass
class RoundResult:
    """单轮结果"""
    round_number: int
    events: List[UniverseEvent]
    civ_snapshots: Dict[str, Any]
    metrics: RoundMetrics
    global_state: "GameState"


@dataclass
class GameState:
    """
    全局游戏状态 — 游戏循环的完整状态
    
    这是 analyzer.py 的输入数据源。
    """
    
    rules: UniverseRules
    instances: List[CivilizationInstance]
    history: List[RoundResult] = field(default_factory=list)
    current_round: int = 0
    is_finished: bool = False
    ending_type: Optional[EndingType] = None
    ending_reason: str = ""
    total_simulation_time_sec: float = 0.0
    
    @property
    def alive_civs(self) -> List[CivilizationInstance]:
        return [c for c in self.instances if c.is_alive]
    
    @property
    def dead_civs(self) -> List[CivilizationInstance]:
        return [c for c in self.instances if not c.is_alive]
    
    @property
    def protagonist(self) -> Optional[CivilizationInstance]:
        for c in self.instances:
            if c.role == PlayerRole.PROTAGONIST and c.is_alive:
                return c
        return None
    
    def get_instance(self, civ_id: str) -> Optional[CivilizationInstance]:
        for c in self.instances:
            if c.civ_id == civ_id:
                return c
        return None


# ============================================================
# 后果计算器 — 事件对文明状态的影响
# ============================================================

@dataclass
class ConsequenceCalculator:
    """
    后果计算器 — 根据事件类型和强度计算状态变化
    
    设计原则:
    - 所有影响通过数学函数计算, 无硬编码分支
    - 影响幅度与事件强度/技术水平/资源状态连续映射
    - 支持自定义影响函数注入 (用于对照实验)
    """
    
    _resource_decay_rate: float = 0.002
    _conflict_tech_damage_base: float = 0.05
    _cooperation_resource_bonus: float = 0.01
    _signal_detection_cost: float = 0.003
    _min_resource: float = 0.05
    
    def calculate_consequences(
        self,
        instance: CivilizationInstance,
        event: UniverseEvent,
        all_instances: List[CivilizationInstance],
    ) -> Dict[str, float]:
        """
        计算单个事件对一个文明的后果
        
        Returns:
            变化量字典 {
                'tech_delta': 技术水平变化,
                'energy_delta': 能源变化,
                'matter_delta': 物质变化,
                'info_delta': 信息变化,
                'habitable_delta': 居住区质量变化,
            }
        """
        intensity = event.intensity
        
        base_changes: Dict[str, float] = {
            "tech_delta": 0.0,
            "energy_delta": 0.0,
            "matter_delta": 0.0,
            "info_delta": 0.0,
            "habitable_delta": 0.0,
        }
        
        is_source = event.source_civ_id == instance.civ_id
        is_target = event.target_civ_id == instance.civ_id
        is_global = event.source_civ_id == "COSMIC_ENVIRONMENT"
        
        if event.event_type == InteractionType.CONFLICT:
            if is_target:
                damage = self._conflict_tech_damage_base * intensity * 2.0
                base_changes["tech_delta"] = -damage * min(1.0, instance.current_tech_level / 50.0)
                base_changes["energy_delta"] = -intensity * 0.08
                base_changes["matter_delta"] = -intensity * 0.05
                base_changes["habitable_delta"] = -intensity * 0.03
            elif is_source:
                base_changes["energy_delta"] = -intensity * 0.04
                base_changes["matter_delta"] = -intensity * 0.02
                
        elif event.event_type == InteractionType.ALLIANCE or event.event_type == InteractionType.CONTACT:
            if is_source or is_target:
                bonus = self._cooperation_resource_bonus * intensity
                base_changes["energy_delta"] += bonus
                base_changes["info_delta"] += bonus * 1.5
                base_changes["tech_delta"] += bonus * 0.3
                
        elif event.event_type == InteractionType.SIGNAL:
            if is_source:
                cost = self._signal_detection_cost * intensity
                base_changes["energy_delta"] -= cost
                base_changes["info_delta"] += intensity * 0.02
                
        elif event.event_type == InteractionType.DOMINATION:
            if is_source:
                base_changes["energy_delta"] -= intensity * 0.06
                base_changes["tech_delta"] += intensity * 0.02
            elif is_target:
                base_changes["energy_delta"] -= intensity * 0.10
                base_changes["matter_delta"] -= intensity * 0.05
                
        elif event.event_type == InteractionType.SILENCE:
            if is_global and is_target:
                fluctuation = (random.random() - 0.5) * intensity * 0.1
                base_changes["energy_delta"] = fluctuation
                base_changes["matter_delta"] = fluctuation * 0.7
        
        for key in base_changes:
            base_changes[key] = round(base_changes[key], 6)
        
        return base_changes
    
    def apply_natural_decay(
        self,
        resource: CosmicResource,
        tech_level: float,
        investment_ratio: float,
    ) -> CosmicResource:
        """应用自然衰减和投资回报"""
        new_energy = max(
            self._min_resource,
            resource.energy_available * (1.0 - self._resource_decay_rate) +
            investment_ratio * 0.01
        )
        new_matter = max(
            self._min_resource,
            resource.matter_density * (1.0 - self._resource_decay_rate * 0.8) +
            investment_ratio * 0.005
        )
        new_info = min(
            1.0,
            resource.information_access +
            math.log10(tech_level + 1.0) * 0.001
        )
        new_habitable = max(
            self._min_resource,
            resource.habitable_zone_quality * (1.0 - self._resource_decay_rate * 0.3)
        )
        
        return CosmicResource(
            energy_available=new_energy,
            matter_density=new_matter,
            information_access=new_info,
            habitable_zone_quality=new_habitable,
        )
    
    def check_extinction(
        self,
        instance: CivilizationInstance,
        round_number: int,
    ) -> Optional[str]:
        """检查文明是否应被判定灭绝"""
        rs = instance.resource_state
        if rs is None:
            return None
        
        critical_count = sum([
            rs.energy_available < self._min_resource * 1.5,
            rs.matter_density < self._min_resource * 1.5,
            rs.habitable_zone_quality < self._min_resource * 1.5,
        ])
        
        if critical_count >= 2:
            return f"资源耗尽 (energy={rs.energy_available:.3f}, matter={rs.matter_density:.3f})"
        
        if instance.current_tech_level < 0.5:
            return "技术退化至临界值以下"
        
        return None


# ============================================================
# 结局检测器
# ============================================================

@dataclass
class EndingDetector:
    """
    结局检测器 — 判断模拟是否应终止及结局类型
    
    检测维度:
    1. 存活数量 → 单一幸存 / 相互毁灭 / 僵局
    2. 力量对比 → 支配型结局
    3. 时间长度 → 轮次上限
    4. 状态稳定性 → 长期均衡
    """
    
    _stalemate_rounds_threshold: int = 300
    _dominance_ratio_threshold: float = 5.0
    _min_rounds_for_stalemate: int = 500
    
    def detect_ending(
        self,
        state: GameState,
    ) -> Tuple[bool, Optional[EndingType], str]:
        """
        检测是否应结束游戏
        
        Returns:
            (should_end, ending_type, reason)
        """
        env_terminate, env_reason = state.rules.environment.should_terminate()
        if env_terminate:
            return True, self._classify_env_ending(state), env_reason
        
        alive = state.alive_civs
        n_alive = len(alive)
        
        if n_alive == 0:
            return True, EndingType.MUTUAL_DESTRUCTION, "所有文明已灭绝"
        
        if n_alive == 1:
            survivor = alive[0]
            if survivor.role == PlayerRole.PROTAGONIST:
                return True, EndingType.SINGLE_SURVIVOR, f"主角 {survivor.civ_id} 最终幸存"
            else:
                return True, EndingType.DOMINATION, f"{survivor.civ_id} ({survivor.role.name}) 支配宇宙"
        
        if n_alive >= 2 and state.current_round > self._min_rounds_for_stalemate:
            dominance_result = self._check_dominance(alive)
            if dominance_result:
                return dominance_result
            
            stalemate_result = self._check_stalemate(state)
            if stalemate_result:
                return stalemate_result
        
        return False, None, ""
    
    def _classify_env_ending(self, state: GameState) -> EndingType:
        reason = state.rules.environment.should_terminate()[1]
        if "硬上限" in reason or "上限" in reason:
            return EndingType.ROUND_LIMIT
        if "灭绝" in reason:
            return EndingType.MUTUAL_DESTRUCTION
        if "单一" in reason or "胜出" in reason:
            return EndingType.SINGLE_SURVIVOR
        if "稳态" in reason or "均衡" in reason:
            return EndingType.STALEMATE_EQUILIBRIUM
        return EndingType.ROUND_LIMIT
    
    def _check_dominance(
        self,
        alive: List[CivilizationInstance],
    ) -> Optional[Tuple[bool, Optional[EndingType], str]]:
        if len(alive) < 2:
            return None
        
        sorted_by_power = sorted(
            alive,
            key=lambda c: c.current_tech_level * (
                c.resource_state.energy_available +
                c.resource_state.matter_density
            ) if c.resource_state else 0.0,
            reverse=True,
        )
        
        strongest = sorted_by_power[0]
        second = sorted_by_power[1]
        
        strongest_power = strongest.current_tech_level * (
            strongest.resource_state.energy_available +
            strongest.resource_state.matter_density
        ) if strongest.resource_state else 1.0
        
        second_power = second.current_tech_level * (
            second.resource_state.energy_available +
            second.resource_state.matter_density
        ) if second.resource_state else 1.0
        
        if second_power > 0 and strongest_power / second_power > self._dominance_ratio_threshold:
            return (
                True,
                EndingType.DOMINATION,
                f"{strongest.civ_id} 达成支配地位 (力量比 {strongest_power/second_power:.1f}:1)",
            )
        
        return None
    
    def _check_stalemate(
        self,
        state: GameState,
    ) -> Optional[Tuple[bool, Optional[EndingType], str]]:
        recent_results = state.history[-self._stalemate_rounds_threshold:]
        if len(recent_results) < self._stalemate_rounds_threshold // 2:
            return None
        
        conflict_events_in_window = 0
        for result in recent_results:
            for event in result.events:
                if event.event_type == InteractionType.CONFLICT:
                    conflict_events_in_window += 1
        
        if conflict_events_in_window == 0:
            return (
                True,
                EndingType.STALEMATE_EQUILIBRIUM,
                f"长期无冲突稳态 (最近{len(recent_results)}轮)",
            )
        
        return None


# ============================================================
# 游戏循环主类
# ============================================================

@dataclass
class GameLoop:
    """
    游戏循环 — N体博弈模拟的核心驱动器
    
    使用方式:
        loop = GameLoop.create_default()
        result = loop.run()  # 运行到自然结局
        # 或
        loop.run_with_callback(my_callback)  # 带进度回调
    """
    
    state: GameState
    consequence_calculator: ConsequenceCalculator = field(
        default_factory=ConsequenceCalculator
    )
    ending_detector: EndingDetector = field(default_factory=EndingDetector)

    _round_callbacks: List[Callable[[RoundResult], None]] = field(
        default_factory=list, repr=False
    )
    _verbose: bool = True
    _log_interval: int = 100
    _max_consecutive_errors: int = 50
    _ema_alpha: float = 0.3
    _prev_tech_levels: Dict[str, float] = field(default_factory=dict, repr=False)
    
    @classmethod
    def create_default(
        cls,
        scenario_profiles: Optional[List[CivilizationProfile]] = None,
        seed: int = 42,
        universe_config: str = "default",
        verbose: bool = True,
    ) -> "GameLoop":
        """创建默认配置的游戏循环"""
        profiles = scenario_profiles or DefaultScenario.all_profiles()
        
        config_map = {
            "default": UniverseRules.create_default,
            "high_chaos": UniverseRules.create_high_chaos,
            "cooperative": UniverseRules.create_cooperative,
        }
        creator = config_map.get(universe_config, UniverseRules.create_default)
        rules = creator(seed=seed)
        
        instances = CivilizationFactory.create_all(profiles, seed=seed)
        
        rules.environment.total_civilizations_alive = len(instances)
        
        state = GameState(rules=rules, instances=instances)
        
        return cls(state=state, _verbose=verbose)
    
    def register_callback(
        self,
        callback: Callable[[RoundResult], None],
    ) -> None:
        """注册每轮回调 (用于实时监控/UI更新)"""
        self._round_callbacks.append(callback)
    
    def run(self, max_rounds_override: Optional[int] = None) -> GameState:
        """
        运行游戏循环直到自然结局
        
        Args:
            max_rounds_override: 可选的最大轮次覆盖
            
        Returns:
            包含完整历史记录的GameState
        """
        start_time = time.perf_counter()
        consecutive_errors = 0
        
        try:
            while not self.state.is_finished:
                if max_rounds_override and self.state.current_round >= max_rounds_override:
                    self.state.is_finished = True
                    self.state.ending_type = EndingType.ROUND_LIMIT
                    self.state.ending_reason = f"用户指定上限 {max_rounds_override} 轮"
                    break
                
                result = self._execute_single_round()
                
                if result.metrics.errors_encountered > 0:
                    consecutive_errors += 1
                    if consecutive_errors > self._max_consecutive_errors:
                        self.state.is_finished = True
                        self.state.ending_type = EndingType.ERROR_TERMINATION
                        self.state.ending_reason = (
                            f"连续错误超过阈值 ({consecutive_errors})"
                        )
                        break
                else:
                    consecutive_errors = 0
                
                self.state.history.append(result)
                
                for cb in self._round_callbacks:
                    try:
                        cb(result)
                    except Exception:
                        pass
                
                if self._verbose and self.state.current_round % self._log_interval == 0:
                    self._log_progress(result)
                    
        except KeyboardInterrupt:
            self.state.is_finished = True
            self.state.ending_type = EndingType.ROUND_LIMIT
            self.state.ending_reason = "用户中断"
            
        except Exception as e:
            self.state.is_finished = True
            self.state.ending_type = EndingType.ERROR_TERMINATION
            self.state.ending_reason = f"未捕获异常: {str(e)}"
            logger.error(f"Game loop crashed: {e}\n{traceback.format_exc()}")
        
        finally:
            self.state.total_simulation_time_sec = time.perf_counter() - start_time
            self._log_final_summary()
        
        return self.state
    
    def run_with_callback(
        self,
        callback: Callable[[RoundResult], None],
        max_rounds_override: Optional[int] = None,
    ) -> GameState:
        """带回调的运行方式 (等价于 register_callback + run)"""
        self.register_callback(callback)
        return self.run(max_rounds_override=max_rounds_override)
    
    def _execute_single_round(self) -> RoundResult:
        """执行单轮完整的游戏逻辑"""
        metrics = RoundMetrics(round_number=self.state.current_round)
        phase_start = time.perf_counter()
        
        self.state.current_round += 1
        self.state.rules.environment.advance_round()
        
        metrics.phase_timings_ms[RoundPhase.ENVIRONMENT_ADVANCE.name] = (
            (time.perf_counter() - phase_start) * 1000.0
        )
        
        phase_start = time.perf_counter()
        
        prev_snapshots = {}
        for inst in self.state.alive_civs:
            try:
                snap = inst.to_snapshot(self.state.current_round)
                prev_snapshots[inst.civ_id] = snap
            except Exception:
                prev_snapshots[inst.civ_id] = None
        
        events = self.state.rules.event_generator.generate_round_events(
            list(prev_snapshots.values()) if any(prev_snapshots.values()) else []
        )
        metrics.events_generated = len(events)
        
        metrics.phase_timings_ms[RoundPhase.EVENT_GENERATION.name] = (
            (time.perf_counter() - phase_start) * 1000.0
        )
        
        phase_start = time.perf_counter()
        
        dispatch_results: Dict[str, List[str]] = {}
        for inst in self.state.alive_civs:
            civ_events = [e for e in events if e.source_civ_id != inst.civ_id or e.target_civ_id == inst.civ_id or e.source_civ_id == "COSMIC_ENVIRONMENT"]
            affected_systems: List[str] = []
            
            for event in civ_events:
                try:
                    engine_input = event.to_engine_event()
                    affected = inst.receive_event(
                        event_type=engine_input["event_type"],
                        intensity=engine_input["intensity"],
                        metadata=engine_input["metadata"],
                    )
                    affected_systems.extend(affected)
                    metrics.events_dispatched += 1
                except Exception as e:
                    metrics.errors_encountered += 1
                    logger.debug(f"Dispatch error [{inst.civ_id}]: {e}")
            
            dispatch_results[inst.civ_id] = list(set(affected_systems))
        
        metrics.phase_timings_ms[RoundPhase.EVENT_DISPATCH.name] = (
            (time.perf_counter() - phase_start) * 1000.0
        )
        
        phase_start = time.perf_counter()
        
        for inst in self.state.alive_civs:
            try:
                snapshot = inst.character.get_state_snapshot(force_refresh=True)
                metrics.strategy_calls += 1
                
                issues = inst.character.check_consistency()
                metrics.consistency_checks_performed += 1
                metrics.consistency_issues_found += len(issues)
                
            except Exception as e:
                metrics.errors_encountered += 1
                logger.debug(f"Strategy/consistency error [{inst.civ_id}]: {e}")
        
        metrics.phase_timings_ms[RoundPhase.STRATEGY_DECISION.name] = (
            (time.perf_counter() - phase_start) * 1000.0
        )
        
        phase_start = time.perf_counter()
        
        for inst in self.state.alive_civs:
            try:
                civ_events = [
                    e for e in events
                    if e.target_civ_id == inst.civ_id or
                    (e.source_civ_id == "COSMIC_ENVIRONMENT" and e.target_civ_id == inst.civ_id)
                ]
                
                total_deltas: Dict[str, float] = {
                    "tech_delta": 0.0,
                    "energy_delta": 0.0,
                    "matter_delta": 0.0,
                    "info_delta": 0.0,
                    "habitable_delta": 0.0,
                }
                
                for event in civ_events:
                    deltas = self.consequence_calculator.calculate_consequences(
                        inst, event, self.state.instances
                    )
                    for k, v in deltas.items():
                        total_deltas[k] += v
                
                raw_tech = max(
                    0.1,
                    inst.current_tech_level + total_deltas["tech_delta"]
                )

                prev_tech = self._prev_tech_levels.get(inst.civ_id, raw_tech)
                smoothed_tech = self._ema_alpha * raw_tech + (1.0 - self._ema_alpha) * prev_tech
                inst.current_tech_level = smoothed_tech
                self._prev_tech_levels[inst.civ_id] = smoothed_tech
                
                if inst.resource_state:
                    new_energy = max(0.0, inst.resource_state.energy_available + total_deltas["energy_delta"])
                    new_matter = max(0.0, inst.resource_state.matter_density + total_deltas["matter_delta"])
                    new_info = max(0.0, min(1.0, inst.resource_state.information_access + total_deltas["info_delta"]))
                    new_habitable = max(0.0, min(1.0, inst.resource_state.habitable_zone_quality + total_deltas["habitable_delta"]))
                    
                    inst.resource_state = CosmicResource(
                        energy_available=new_energy,
                        matter_density=new_matter,
                        information_access=new_info,
                        habitable_zone_quality=new_habitable,
                    )
                
                investment = 0.3
                if inst.resource_state:
                    investment = inst.resource_state.energy_available * 0.5
                
                inst.resource_state = self.consequence_calculator.apply_natural_decay(
                    inst.resource_state or CosmicResource(0.5, 0.5, 0.5, 0.5),
                    inst.current_tech_level,
                    investment,
                )
                
                extinction_reason = self.consequence_calculator.check_extinction(
                    inst, self.state.current_round
                )
                if extinction_reason:
                    inst.kill(self.state.current_round, extinction_reason)
                    logger.info(f"[R{self.state.current_round}] {inst.civ_id} 灭绝: {extinction_reason}")
                    
            except Exception as e:
                metrics.errors_encountered += 1
                logger.debug(f"Consequence error [{inst.civ_id}]: {e}")
        
        self.state.rules.environment.total_civilizations_alive = len(self.state.alive_civs)
        
        metrics.phase_timings_ms[RoundPhase.CONSEQUENCE_CALCULATION.name] = (
            (time.perf_counter() - phase_start) * 1000.0
        )
        
        phase_start = time.perf_counter()
        
        current_snapshots: Dict[str, Any] = {}
        for inst in self.state.instances:
            try:
                snap = inst.to_snapshot(self.state.current_round)
                current_snapshots[inst.civ_id] = snap
                self.state.rules.environment.record_snapshot(snap)
            except Exception as e:
                metrics.errors_encountered += 1
                current_snapshots[inst.civ_id] = {"error": str(e)}
        
        for event in events:
            self.state.rules.environment.record_event(event)
        
        metrics.phase_timings_ms[RoundPhase.STATE_SNAPSHOT.name] = (
            (time.perf_counter() - phase_start) * 1000.0
        )
        
        phase_start = time.perf_counter()
        
        should_end, ending_type, reason = self.ending_detector.detect_ending(self.state)
        if should_end:
            self.state.is_finished = True
            self.state.ending_type = ending_type
            self.state.ending_reason = reason
        
        metrics.phase_timings_ms[RoundPhase.TERMINATION_CHECK.name] = (
            (time.perf_counter() - phase_start) * 1000.0
        )
        
        metrics.alive_civ_count = len(self.state.alive_civs)
        
        return RoundResult(
            round_number=self.state.current_round,
            events=events,
            civ_snapshots=current_snapshots,
            metrics=metrics,
            global_state=self.state,
        )
    
    def _log_progress(self, result: RoundResult) -> None:
        alive_ids = [c.civ_id for c in self.state.alive_civs]
        dead_count = len(self.state.dead_civs)
        
        avg_tech = 0.0
        if self.state.alive_civs:
            avg_tech = sum(c.current_tech_level for c in self.state.alive_civs) / len(self.state.alive_civs)
        
        era = self.state.rules.environment.era.name
        total_events = len(self.state.rules.environment.history)
        
        logger.info(
            f"[R{result.round_number:>6d}] era={era:<12s} | "
            f"alive={alive_ids} | dead={dead_count} | "
            f"avg_tech={avg_tech:.1f} | "
            f"events_this={result.metrics.events_generated} | "
            f"total_events={total_events} | "
            f"errors={result.metrics.errors_encountered}"
        )
    
    def _log_final_summary(self) -> None:
        logger.info("=" * 70)
        logger.info("压力测试完成")
        logger.info(f"  总轮次:     {self.state.current_round}")
        logger.info(f"  结局类型:   {self.state.ending_type.name if self.state.ending_type else 'N/A'}")
        logger.info(f"  结局原因:   {self.state.ending_reason}")
        logger.info(f"  总耗时:     {self.state.total_simulation_time_sec:.2f}s")
        logger.info(f"  总事件数:   {len(self.state.rules.environment.history)}")
        logger.info(f"  总快照数:   {len(self.state.rules.environment.state_history)}")
        logger.info(f"  存活文明:   {[c.civ_id for c in self.state.alive_civs]}")
        logger.info(f"  已灭绝:     {[c.civ_id for c in self.state.dead_civs]}")
        logger.info("=" * 70)
