"""
宇宙规则模块 — 定义N体博弈的物理/社会法则
============================================

核心设计: 将"三体问题"抽象为通用的N体博弈框架
- 不包含任何原著具体内容
- 仅定义结构性规则和参数空间
- 引擎通过这些规则自主演化出结局

学术映射:
  三体运动混沌 → 信念系统非线性耦合
  黑暗森林公理 → 机制设计中的激励不相容
  猜疑链 → 递归信念嵌套(二阶信念)
  技术爆炸 → 阶跃式能力增长函数
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional, Tuple


# ============================================================
# 常量 — 宇宙物理参数 (非魔法数字, 基于比例关系)
# ============================================================

_SPEED_OF_LIGHT: float = 1.0
_COSMIC_SCALE_FACTOR: float = 1000.0

_DETECTION_BASE_PROB: float = 0.001
_DETECTION_DISTANCE_EXPONENT: float = 2.0
_TECH_GROWTH_BASE: float = 1.02
_TECH_GROWTH_ACCELERATION_THRESHOLD: float = 100.0
_RESOURCE_SCARCITY_BASE: float = 0.3
_CONFLICT_ESCALATION_PROB: float = 0.15
_COOPERATION_DECAY_RATE: float = 0.005
_TRUST_BUILDING_SLOWNESS: float = 0.1


# ============================================================
# 枚举定义
# ============================================================

class CosmicEra(Enum):
    """宇宙时代 — 文明发展阶段的通用分类"""
    PRIMORDIAL = auto()
    EXPANDING = auto()
    CONTACT = auto()
    CRISIS = auto()
    EQUILIBRIUM = auto()
    COLLAPSE = auto()


class InteractionType(Enum):
    """文明间交互类型"""
    SILENCE = auto()
    SIGNAL = auto()
    CONTACT = auto()
    CONFLICT = auto()
    ALLIANCE = auto()
    DOMINATION = auto()
    EXTINCTION = auto()


class ResourceScarcityLevel(Enum):
    """资源稀缺等级"""
    ABUNDANT = auto()
    SUFFICIENT = auto()
    SCARCE = auto()
    CRITICAL = auto()
    EXHAUSTED = auto()


class TechnologyTier(Enum):
    """技术层级 (对数刻度)"""
    TIER_0_PLANETARY = 0
    TIER_1_STELLAR = 1
    TIER_2_GALACTIC = 2
    TIER_3_INTERGALACTIC = 3
    TIER_4_DIMENSIONAL = 4
    TIER_5_COSMIC = 5


# ============================================================
# 数据结构
# ============================================================

@dataclass
class SpatialPosition:
    """三维空间位置"""
    x: float
    y: float
    z: float
    
    def distance_to(self, other: "SpatialPosition") -> float:
        dx = self.x - other.x
        dy = self.y - other.y
        dz = self.z - other.z
        return math.sqrt(dx * dx + dy * dy + dz * dz)


@dataclass
class CosmicResource:
    """资源状态"""
    energy_available: float
    matter_density: float
    information_access: float
    habitable_zone_quality: float
    
    @property
    def scarcity_level(self) -> ResourceScarcityLevel:
        total = (
            self.energy_available +
            self.matter_density +
            self.information_access +
            self.habitable_zone_quality
        ) / 4.0
        
        if total >= 0.8:
            return ResourceScarcityLevel.ABUNDANT
        elif total >= 0.6:
            return ResourceScarcityLevel.SUFFICIENT
        elif total >= 0.4:
            return ResourceScarcityLevel.SCARCE
        elif total >= 0.2:
            return ResourceScarcityLevel.CRITICAL
        else:
            return ResourceScarcityLevel.EXHAUSTED


@dataclass
class CivilizationStateSnapshot:
    """文明状态快照 (每轮记录用)"""
    round_number: int
    civ_id: str
    technology_level: float
    resource_state: CosmicResource
    active_threats_count: int
    primary_target_id: Optional[str]
    belief_entropy: float
    strategy_entropy: float
    credibility_scores: Dict[str, float]
    is_alive: bool
    dominance_position: float
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class UniverseEvent:
    """宇宙事件 — 每轮由引擎生成"""
    round_number: int
    source_civ_id: str
    target_civ_id: Optional[str]
    event_type: InteractionType
    intensity: float
    description: str
    engine_metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_engine_event(self) -> Dict[str, Any]:
        """转换为 DeepCharacter.on_event() 的输入格式"""
        return {
            "event_type": self.event_type.name.lower(),
            "intensity": self.intensity,
            "metadata": {
                "source_id": self.source_civ_id,
                "target_id": self.target_civ_id,
                "description": self.description,
                **self.engine_metadata,
            },
        }


# ============================================================
# 黑暗森林公理体系 (纯结构性描述, 无具体情节)
# ============================================================

@dataclass
class DarkForestAxiom:
    """
    黑暗森林公理 — N体博弈的基础假设集
    
    公理是纯逻辑陈述, 不包含任何叙事内容。
    引擎通过这些公理自行推导出行为模式。
    
    公理体系设计原则:
    - 每条公理可独立开启/关闭 (用于对照实验)
    - 公理强度可调节 (0.0 ~ 1.0)
    - 公理间存在相互作用矩阵
    """
    
    axiom_id: str
    name: str
    formal_statement: str
    strength: float = 1.0
    enabled: bool = True
    
    def effective_strength(self) -> float:
        if not self.enabled:
            return 0.0
        return max(0.0, min(1.0, self.strength))


class DefaultAxioms:
    """默认公理集合 — 可被覆盖以创建不同宇宙"""
    
    @staticmethod
    def survival_first() -> DarkForestAxiom:
        return DarkForestAxiom(
            axiom_id="AXIOM_001",
            name="生存第一",
            formal_statement=(
                "文明的生存是第一优先级; "
                "当生存受到威胁时, 其他价值降级为约束条件"
            ),
            strength=0.95,
        )
    
    @staticmethod
    def resource_competition() -> DarkForestAxiom:
        return DarkForestAxiom(
            axiom_id="AXIOM_002",
            name="资源竞争",
            formal_statement=(
                "宇宙总资源有限且分布不均; "
                "文明扩张必然导致资源竞争"
            ),
            strength=0.85,
        )
    
    @staticmethod
    def information_asymmetry() -> DarkForestAxiom:
        return DarkForestAxiom(
            axiom_id="AXIOM_003",
            name="信息不对称",
            formal_statement=(
                "任意两个文明间的信息永远不完全对称; "
                "无法完全验证对方的真实意图"
            ),
            strength=0.90,
        )
    
    @staticmethod
    def chain_of_suspicion() -> DarkForestAxiom:
        return DarkForestAxiom(
            axiom_id="AXIOM_004",
            name="猜疑链",
            formal_statement=(
                "由于信息不对称, A无法确定B是否善意, "
                "B也无法确定A是否认为B善意, "
                "此递归无终止条件"
            ),
            strength=0.88,
        )
    
    @staticmethod
    def tech_explosion() -> DarkForestAxiom:
        return DarkForestAxiom(
            axiom_id="AXIOM_005",
            name="技术爆炸",
            formal_statement=(
                "技术进步是非线性的; "
                "弱小文明可能在短时间内超越强大文明"
            ),
            strength=0.80,
        )
    
    @staticmethod
    def detection_risk() -> DarkForestAxiom:
        return DarkForestAxiom(
            axiom_id="AXIOM_006",
            name="暴露风险",
            formal_statement=(
                "暴露自身位置带来被探测的风险; "
                "探测概率随距离衰减但永不归零"
            ),
            strength=0.92,
        )
    
    @staticmethod
    def all_default() -> List[DarkForestAxiom]:
        return [
            DefaultAxioms.survival_first(),
            DefaultAxioms.resource_competition(),
            DefaultAxioms.information_asymmetry(),
            DefaultAxioms.chain_of_suspicion(),
            DefaultAxioms.tech_explosion(),
            DefaultAxioms.detection_risk(),
        ]


# ============================================================
# 物理引擎 — 距离/探测/移动
# ============================================================

@dataclass
class PhysicsEngine:
    """
    物理引擎 — 处理空间距离、探测概率、信号传播
    
    所有计算基于相对单位, 不依赖绝对尺度
    """
    
    light_speed: float = _SPEED_OF_LIGHT
    detection_base_prob: float = _DETECTION_BASE_PROB
    detection_distance_exponent: float = _DETECTION_DISTANCE_EXPONENT
    
    def detection_probability(
        self,
        emitter_pos: SpatialPosition,
        observer_pos: SpatialPosition,
        emitter_tech_level: float,
        observer_tech_level: float,
        signal_strength: float = 1.0,
    ) -> float:
        """
        计算观测者探测到发射者的概率
        
        模型: P(detect) = base_prob × (tech_ratio)^0.5 / distance^exp × signal
        """
        distance = emitter_pos.distance_to(observer_pos)
        if distance < 0.01:
            distance = 0.01
        
        tech_ratio = (observer_tech_level + 0.1) / (emitter_tech_level + 0.1)
        tech_factor = math.sqrt(max(0.01, min(10.0, tech_ratio)))
        
        distance_factor = 1.0 / (distance ** self.detection_distance_exponent)
        
        raw_prob = (
            self.detection_base_prob *
            tech_factor *
            distance_factor *
            signal_strength
        )
        return max(0.0, min(1.0, raw_prob))
    
    def signal_travel_time(
        self,
        source: SpatialPosition,
        target: SpatialPosition,
    ) -> float:
        """信号传播延迟 (光速限制)"""
        return source.distance_to(target) / max(0.01, self.light_speed)
    
    def movement_cost(
        self,
        from_pos: SpatialPosition,
        to_pos: SpatialPosition,
        tech_level: float,
    ) -> float:
        """移动的资源成本"""
        distance = from_pos.distance_to(to_pos)
        base_cost = distance / (tech_level + 1.0)
        return base_cost


# ============================================================
# 技术增长模型
# ============================================================

@dataclass
class TechnologyModel:
    """
    技术增长模型 — 阶跃式 + 指数式混合
    
    特性:
    - 平稳期: 缓慢指数增长 (base_rate)
    - 加速期: 达到阈值后进入快速增长
    - 阶跃期: 小概率发生技术阶跃 (tier transition)
    """
    
    base_growth_rate: float = _TECH_GROWTH_BASE
    acceleration_threshold: float = _TECH_GROWTH_ACCELERATION_THRESHOLD
    jump_probability: float = 0.002
    jump_magnitude_range: Tuple[float, float] = (1.5, 5.0)
    decay_under_crisis: float = 0.98
    
    def evolve(
        self,
        current_level: float,
        investment_ratio: float,
        is_in_crisis: bool,
        has_contact: bool,
        rng: random.Random,
    ) -> float:
        """
        计算下一轮的技术水平
        
        Args:
            current_level: 当前技术水平
            investment_ratio: 资源投入比例 [0, 1]
            is_in_crisis: 是否处于危机状态
            has_contact: 是否已与其他文明接触
            rng: 随机数生成器
            
        Returns:
            新的技术水平
        """
        growth = self.base_growth_rate
        
        contact_bonus = 1.0
        if has_contact and current_level > 10.0:
            contact_bonus += 0.01 * math.log10(current_level)
        
        crisis_penalty = 1.0
        if is_in_crisis:
            crisis_penalty = self.decay_under_crisis
        
        acceleration = 1.0
        if current_level > self.acceleration_threshold:
            excess = current_level - self.acceleration_threshold
            acceleration = 1.0 + 0.01 * math.sqrt(excess)
        
        normal_growth = current_level * growth * investment_ratio * contact_bonus * crisis_penalty * acceleration
        
        jump = 0.0
        if rng.random() < self.jump_probability:
            low, high = self.jump_magnitude_range
            jump = rng.uniform(low, high) * current_level * 0.1
        
        new_level = current_level + normal_growth + jump
        return max(0.1, new_level)


# ============================================================
# 宇宙环境 — 整合所有规则
# ============================================================

@dataclass
class CosmicEnvironment:
    """
    宇宙环境 — 整合物理/技术/资源规则的统一接口
    
    这是游戏循环与引擎之间的中间层:
    GameLoop → CosmicEnvironment → Engine API calls
    """
    
    physics: PhysicsEngine = field(default_factory=PhysicsEngine)
    technology: TechnologyModel = field(default_factory=TechnologyModel)
    axioms: List[DarkForestAxiom] = field(
        default_factory=lambda: DefaultAxioms.all_default()
    )
    era: CosmicEra = CosmicEra.PRIMORDIAL
    current_round: int = 0
    total_civilizations_alive: int = 0
    history: List[UniverseEvent] = field(default_factory=list)
    state_history: List[CivilizationStateSnapshot] = field(
        default_factory=list
    )
    
    _rng: random.Random = field(default_factory=lambda: random.Random(42), repr=False)
    _max_rounds_soft_limit: int = 100000
    _max_rounds_hard_limit: int = 500000
    
    @property
    def active_axiom_strength(self) -> Dict[str, float]:
        return {a.axiom_id: a.effective_strength() for a in self.axioms}
    
    @property
    def is_dark_forest_active(self) -> bool:
        dark_forest_required = {"AXIOM_001", "AXIOM_003", "AXIOM_004", "AXIOM_006"}
        strengths = self.active_axiom_strength
        return all(
            strengths.get(aid, 0.0) > 0.5 for aid in dark_forest_required
        )
    
    def advance_round(self) -> None:
        self.current_round += 1
        if self.current_round % 100 == 0:
            self._update_era()
    
    def _update_era(self) -> None:
        alive = self.total_civilizations_alive
        if alive <= 1:
            self.era = CosmicEra.COLLAPSE
        elif alive <= 2:
            self.era = CosmicEra.EQUILIBRIUM
        elif self.current_round > 10000:
            self.era = CosmicEra.CRISIS
        elif self.current_round > 1000:
            self.era = CosmicEra.CONTACT
        elif self.current_round > 100:
            self.era = CosmicEra.EXPANDING
        else:
            self.era = CosmicEra.PRIMORDIAL
    
    def record_event(self, event: UniverseEvent) -> None:
        self.history.append(event)
    
    def record_snapshot(self, snapshot: CivilizationStateSnapshot) -> None:
        self.state_history.append(snapshot)
    
    def should_terminate(self) -> Tuple[bool, Optional[str]]:
        """
        终止条件检测
        
        Returns:
            (should_stop, reason)
        """
        if self.current_round >= self._max_rounds_hard_limit:
            return True, f"达到硬上限 {self._max_rounds_hard_limit} 轮"
        
        if self.total_civilizations_alive <= 0:
            return True, "全文明灭绝"
        
        if self.total_civilizations_alive == 1:
            return True, "单一文明胜出"
        
        recent_events = [
            e for e in self.history[-200:]
            if e.round_number >= self.current_round - 200
        ]
        
        if len(recent_events) > 50:
            conflict_events = sum(
                1 for e in recent_events
                if e.event_type == InteractionType.CONFLICT
            )
            if conflict_events == 0 and self.current_round > 1000:
                stable_rounds = 0
                for e in reversed(recent_events):
                    if e.event_type != InteractionType.CONFLICT:
                        stable_rounds += 1
                    else:
                        break
                if stable_rounds >= 150:
                    return True, f"长期稳态 ({stable_rounds}轮无冲突)"
        
        return False, None
    
    def get_summary_stats(self) -> Dict[str, Any]:
        events_by_type: Dict[str, int] = {}
        for event in self.history:
            key = event.event_type.name
            events_by_type[key] = events_by_type.get(key, 0) + 1
        
        return {
            "total_rounds": self.current_round,
            "total_events": len(self.history),
            "total_snapshots": len(self.state_history),
            "final_era": self.era.name,
            "dark_forest_active": self.is_dark_forest_active,
            "events_by_type": events_by_type,
            "axiom_strengths": self.active_axiom_strength,
        }


# ============================================================
# 事件生成器 — 宇宙事件的程序化生成
# ============================================================

@dataclass
class EventGenerator:
    """
    事件生成器 — 基于当前宇宙状态生成事件
    
    关键约束:
    - 不注入任何外部内容
    - 纯粹基于当前状态+随机扰动
    - 事件类型和强度由物理/社会规则决定
    """
    
    environment: CosmicEnvironment
    _rng: random.Random = field(
        default_factory=lambda: random.Random(42), repr=False
    )
    
    def generate_round_events(
        self,
        civ_states: List[CivilizationStateSnapshot],
    ) -> List[UniverseEvent]:
        """
        为当前轮次生成所有事件
        
        生成策略:
        1. 每个存活文明有概率主动行动
        2. 成对文明间有概率被动交互
        3. 全局环境事件 (资源变化等)
        """
        events: List[UniverseEvent] = []
        round_num = self.environment.current_round
        
        alive_civs = [s for s in civ_states if s.is_alive]
        
        for civ in alive_civs:
            action_event = self._generate_individual_action(civ, alive_civs)
            if action_event:
                events.append(action_event)
        
        for i, civ_a in enumerate(alive_civs):
            for civ_b in alive_civs[i + 1 :]:
                pair_event = self._generate_pairwise_interaction(
                    civ_a, civ_b
                )
                if pair_event:
                    events.append(pair_event)
        
        global_event = self._generate_global_event(round_num, alive_civs)
        if global_event:
            events.append(global_event)
        
        return events
    
    def _generate_individual_action(
        self,
        civ: CivilizationStateSnapshot,
        all_alive: List[CivilizationStateSnapshot],
    ) -> Optional[UniverseEvent]:
        action_prob = 0.3 + 0.1 * math.tanh((civ.technology_level - 50.0) / 20.0)
        if self._rng.random() > action_prob:
            return None
        
        actions = self._select_action_type(civ)
        action_type, intensity, description = actions
        
        target = None
        if action_type in (InteractionType.SIGNAL, InteractionType.CONFLICT, InteractionType.CONTACT):
            candidates = [c for c in all_alive if c.civ_id != civ.civ_id]
            if candidates:
                target = self._rng.choice(candidates).civ_id
        
        return UniverseEvent(
            round_number=civ.round_number,
            source_civ_id=civ.civ_id,
            target_civ_id=target,
            event_type=action_type,
            intensity=intensity,
            description=description,
            engine_metadata={
                "tech_level": civ.technology_level,
                "strategy_entropy": civ.strategy_entropy,
            },
        )
    
    def _select_action_type(
        self, civ: CivilizationStateSnapshot
    ) -> Tuple[InteractionType, float, str]:
        weights: Dict[InteractionType, float] = {
            InteractionType.SILENCE: 0.25,
            InteractionType.SIGNAL: 0.20,
            InteractionType.CONFLICT: 0.15,
            InteractionType.CONTACT: 0.10,
            InteractionType.ALLIANCE: 0.05,
            InteractionType.DOMINATION: 0.05,
        }
        
        if civ.resource_state.scarcity_level in (
            ResourceScarcityLevel.CRITICAL,
            ResourceScarcityLevel.EXHAUSTED,
        ):
            weights[InteractionType.CONFLICT] += 0.15
            weights[InteractionType.SIGNAL] -= 0.10
        
        if civ.strategy_entropy > 1.5:
            weights[InteractionType.SILENCE] += 0.15
            weights[InteractionType.SIGNAL] -= 0.08
        
        if civ.belief_entropy > 1.3:
            weights[InteractionType.CONFLICT] += 0.10
            weights[InteractionType.ALLIANCE] -= 0.08
        
        total_weight = sum(weights.values())
        r = self._rng.random() * total_weight
        cumulative = 0.0
        selected = InteractionType.SILENCE
        
        for atype, w in weights.items():
            cumulative += w
            if r <= cumulative:
                selected = atype
                break
        
        intensity = 0.3 + self._rng.random() * 0.6
        
        descriptions = {
            InteractionType.SILENCE: "保持静默, 收集信息",
            InteractionType.SIGNAL: "发送定向信号",
            InteractionType.CONFLICT: "发起对抗行为",
            InteractionType.CONTACT: "尝试建立联系",
            InteractionType.ALLIANCE: "提议合作安排",
            InteractionType.DOMINATION: "展示力量优势",
        }
        
        return selected, intensity, descriptions.get(selected, "未知行动")
    
    def _generate_pairwise_interaction(
        self,
        civ_a: CivilizationStateSnapshot,
        civ_b: CivilizationStateSnapshot,
    ) -> Optional[UniverseEvent]:
        prob = 0.08
        dist_proxy = abs(civ_a.technology_level - civ_b.technology_level)
        if dist_proxy < 10.0:
            prob += 0.05
        
        if self._rng.random() > prob:
            return None
        
        is_hostile = (
            civ_a.technology_level > civ_b.technology_level * 2.0 or
            civ_a.resource_state.scarcity_level.value >=
            ResourceScarcityLevel.CRITICAL.value
        )
        
        if is_hostile:
            event_type = InteractionType.CONFLICT
            intensity = 0.5 + self._rng.random() * 0.4
            desc = f"对{civ_b.civ_id}施加压力"
        else:
            event_type = self._rng.choice([
                InteractionType.SIGNAL,
                InteractionType.CONTACT,
            ])
            intensity = 0.2 + self._rng.random() * 0.4
            desc = f"与{civ_b.civ_id}交互"
        
        source = self._rng.choice([civ_a, civ_b])
        target = civ_b if source == civ_a else civ_a
        
        return UniverseEvent(
            round_number=self.environment.current_round,
            source_civ_id=source.civ_id,
            target_civ_id=target.civ_id,
            event_type=event_type,
            intensity=intensity,
            description=desc,
        )
    
    def _generate_global_event(
        self,
        round_num: int,
        alive_civs: List[CivilizationStateSnapshot],
    ) -> Optional[UniverseEvent]:
        if self._rng.random() > 0.05:
            return None
        
        if not alive_civs:
            return None
        
        victim = self._rng.choice(alive_civs)
        intensity = 0.3 + self._rng.random() * 0.5
        
        return UniverseEvent(
            round_number=round_num,
            source_civ_id="COSMIC_ENVIRONMENT",
            target_civ_id=victim.civ_id,
            event_type=InteractionType.SILENCE,
            intensity=intensity,
            description="宇宙环境变化影响资源可用性",
            engine_metadata={"global_event": True},
        )


# ============================================================
# 宇宙规则整合器 — 对外统一接口
# ============================================================

@dataclass
class UniverseRules:
    """
    宇宙规则 — 压力测试的完整规则集合
    
    使用方式:
        rules = UniverseRules.create_default()
        env = rules.environment
        generator = rules.event_generator
        
        # 每轮调用:
        events = generator.generate_round_events(civ_snapshots)
        for event in events:
            engine_input = event.to_engine_event()
            character.on_event(**engine_input)
    """
    
    environment: CosmicEnvironment
    physics: PhysicsEngine
    technology: TechnologyModel
    event_generator: EventGenerator
    axioms: List[DarkForestAxiom]
    
    @classmethod
    def create_default(
        cls,
        seed: int = 42,
        custom_axioms: Optional[List[DarkForestAxiom]] = None,
    ) -> "UniverseRules":
        """创建默认规则集"""
        rng = random.Random(seed)
        
        env = CosmicEnvironment(_rng=rng)
        physics = PhysicsEngine()
        tech = TechnologyModel()
        axioms = custom_axioms or DefaultAxioms.all_default()
        generator = EventGenerator(environment=env, _rng=rng)
        
        env.axioms = axioms
        
        return cls(
            environment=env,
            physics=physics,
            technology=tech,
            event_generator=generator,
            axioms=axioms,
        )
    
    @classmethod
    def create_high_chaos(cls, seed: int = 42) -> "UniverseRules":
        """高混沌配置 — 更强的猜疑链和更快的冲突升级"""
        rules = cls.create_default(seed=seed)
        
        for axiom in rules.axioms:
            if axiom.axiom_id in ("AXIOM_004", "AXIOM_006"):
                axiom.strength = min(1.0, axiom.strength + 0.1)
        
        rules.physics.detection_base_prob *= 2.0
        rules.technology.jump_probability *= 3.0
        
        return rules
    
    @classmethod
    def create_cooperative(cls, seed: int = 42) -> "UniverseRules":
        """低混沌配置 — 弱化黑暗森林效应"""
        rules = cls.create_default(seed=seed)
        
        for axiom in rules.axioms:
            if axiom.axiom_id in ("AXIOM_004", "AXIOM_006"):
                axiom.strength = max(0.0, axiom.strength - 0.3)
        
        rules.physics.detection_base_prob *= 0.5
        rules.technology.jump_probability *= 0.5
        
        return rules
