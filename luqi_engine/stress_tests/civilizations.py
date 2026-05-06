"""
文明工厂模块 — 角色定义与初始化
================================

设计原则:
- 纯结构性角色定义 (无叙事内容)
- 每个文明由参数向量唯一确定
- 初始信念状态反映文明"性格"
- 主角(用户)是引擎模拟的AI角色, 非外部控制

角色体系:
  PROTAGONIST  → 引擎模拟的用户视角文明
  ANTAGONIST   → 主要对立文明
  OBSERVER     → 第三方观察/干预者文明
  WILDCARD     → 不可预测的混沌变量
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple

from luqi_engine.character.deep_character import DeepCharacter
from luqi_engine.game_theory.types import (
    BeliefDimension,
    BeliefState,
    Observation,
    ObservationType,
)
from luqi_engine.game_theory.belief_system import BeliefSystem
from luqi_engine.game_theory.threat_credibility import (
    ThreatCredibilityEngine,
    ThreatRecord,
    ThreatType,
    CommitmentLevel,
)

from .universe import (
    CosmicResource,
    ResourceScarcityLevel,
    TechnologyTier,
    SpatialPosition,
)


# ============================================================
# 枚举定义
# ============================================================

class PlayerRole(Enum):
    """角色定位"""
    PROTAGONIST = auto()
    ANTAGONIST = auto()
    OBSERVER = auto()
    WILDCARD = auto()


class CivilizationArchetype(Enum):
    """
    文明原型 — 决定初始行为倾向
    
    原型通过信念系统的初始参数体现,
    而非硬编码行为规则。
    """
    EXPANSIONIST = auto()
    ISOLATIONIST = auto()
    DIPLOMAT = auto()
    SURVIVALIST = auto()
    AGGRESSOR = auto()
    MYSTERY = auto()


class SurvivalStrategy(Enum):
    """生存策略倾向"""
    HIDE = auto()
    FLEE = auto()
    FIGHT = auto()
    ALLY = auto()
    SUBMIT = auto()
    DECEIVE = auto()


# ============================================================
# 文明配置文件 — 完全参数化
# ============================================================

@dataclass
class CivilizationProfile:
    """
    文明配置文件 — 定义一个文明的全部初始属性
    
    所有属性都是数值化的, 无任何叙事描述。
    引擎根据这些数值自行演化出行为模式。
    """
    
    civ_id: str
    display_name: str
    role: PlayerRole
    archetype: CivilizationArchetype
    
    initial_technology_level: float = 10.0
    initial_resource_state: CosmicResource = field(
        default_factory=lambda: CosmicResource(
            energy_available=0.7,
            matter_density=0.6,
            information_access=0.5,
            habitable_zone_quality=0.8,
        )
    )
    initial_position: SpatialPosition = field(
        default_factory=lambda: SpatialPosition(0.0, 0.0, 0.0)
    )
    
    survival_strategy: SurvivalStrategy = SurvivalStrategy.HIDE
    
    belief_initial_alpha: Dict[BeliefDimension, float] = field(
        default_factory=dict
    )
    belief_initial_beta: Dict[BeliefDimension, float] = field(
        default_factory=dict
    )
    
    threat_default_cost: float = 0.5
    threat_default_commitment: CommitmentLevel = CommitmentLevel.VERBAL
    
    strategy_temperature_base: float = 1.0
    cooperation_tendency: float = 0.5
    paranoia_level: float = 0.3
    
    def __post_init__(self) -> None:
        if not self.belief_initial_alpha:
            self.belief_initial_alpha = self._default_alpha_for_archetype()
        if not self.belief_initial_beta:
            self.belief_initial_beta = self._default_beta_for_archetype()
    
    def _default_alpha_for_archetype(self) -> Dict[BeliefDimension, float]:
        base: Dict[BeliefDimension, float] = {
            BeliefDimension.COOPERATIVITY: 1.0,
            BeliefDimension.THREAT_LEVEL: 1.0,
            BeliefDimension.COMPETENCE: 1.0,
            BeliefDimension.ALIGNMENT: 1.0,
            BeliefDimension.HONESTY: 1.0,
            BeliefDimension.STABILITY: 1.0,
        }
        
        modifiers: Dict[CivilizationArchetype, Dict[BeliefDimension, float]] = {
            CivilizationArchetype.EXPANSIONIST: {
                BeliefDimension.COMPETENCE: 3.0,
                BeliefDimension.COOPERATIVITY: 1.8,
            },
            CivilizationArchetype.ISOLATIONIST: {
                BeliefDimension.THREAT_LEVEL: 3.0,
                BeliefDimension.STABILITY: 2.5,
                BeliefDimension.COOPERATIVITY: 0.6,
            },
            CivilizationArchetype.DIPLOMAT: {
                BeliefDimension.HONESTY: 3.0,
                BeliefDimension.COOPERATIVITY: 2.5,
                BeliefDimension.ALIGNMENT: 2.0,
            },
            CivilizationArchetype.SURVIVALIST: {
                BeliefDimension.THREAT_LEVEL: 4.0,
                BeliefDimension.STABILITY: 3.0,
            },
            CivilizationArchetype.AGGRESSOR: {
                BeliefDimension.COMPETENCE: 4.0,
                BeliefDimension.THREAT_LEVEL: 0.5,
                BeliefDimension.COOPERATIVITY: 0.4,
            },
            CivilizationArchetype.MYSTERY: {
                BeliefDimension.HONESTY: 0.5,
                BeliefDimension.STABILITY: 0.7,
            },
        }
        
        arch_mods = modifiers.get(self.archetype, {})
        for dim, mod in arch_mods.items():
            base[dim] = mod
        
        return base
    
    def _default_beta_for_archetype(self) -> Dict[BeliefDimension, float]:
        alpha_map = self._default_alpha_for_archetype()
        return {dim: max(0.1, 2.0 - val * 0.5) for dim, val in alpha_map.items()}


# ============================================================
# 默认场景配置
# ============================================================

class DefaultScenario:
    """默认三体式N体博弈场景"""
    
    N_CIVILIZATIONS: int = 3
    
    @staticmethod
    def protagonist() -> CivilizationProfile:
        return CivilizationProfile(
            civ_id="CIV_ALPHA",
            display_name="阿尔法文明",
            role=PlayerRole.PROTAGONIST,
            archetype=CivilizationArchetype.DIPLOMAT,
            initial_technology_level=15.0,
            initial_position=SpatialPosition(100.0, 50.0, 20.0),
            survival_strategy=SurvivalStrategy.ALLY,
            paranoia_level=0.25,
            cooperation_tendency=0.65,
            threat_default_commitment=CommitmentLevel.MATERIAL,
            initial_resource_state=CosmicResource(
                energy_available=0.65,
                matter_density=0.55,
                information_access=0.40,
                habitable_zone_quality=0.85,
            ),
        )
    
    @staticmethod
    def antagonist() -> CivilizationProfile:
        return CivilizationProfile(
            civ_id="CIV_BETA",
            display_name="贝塔文明",
            role=PlayerRole.ANTAGONIST,
            archetype=CivilizationArchetype.EXPANSIONIST,
            initial_technology_level=80.0,
            initial_position=SpatialPosition(400.0, 200.0, 80.0),
            survival_strategy=SurvivalStrategy.FIGHT,
            paranoia_level=0.45,
            cooperation_tendency=0.30,
            threat_default_commitment=CommitmentLevel.IRREVERSIBLE,
            initial_resource_state=CosmicResource(
                energy_available=0.35,
                matter_density=0.30,
                information_access=0.70,
                habitable_zone_quality=0.20,
            ),
        )
    
    @staticmethod
    def observer() -> CivilizationProfile:
        return CivilizationProfile(
            civ_id="CIV_GAMMA",
            display_name="伽马文明",
            role=PlayerRole.OBSERVER,
            archetype=CivilizationArchetype.MYSTERY,
            initial_technology_level=200.0,
            initial_position=SpatialPosition(900.0, 450.0, 180.0),
            survival_strategy=SurvivalStrategy.DECEIVE,
            paranoia_level=0.70,
            cooperation_tendency=0.15,
            threat_default_commitment=CommitmentLevel.NONE,
            initial_resource_state=CosmicResource(
                energy_available=0.90,
                matter_density=0.85,
                information_access=0.95,
                habitable_zone_quality=0.60,
            ),
        )
    
    @classmethod
    def all_profiles(cls) -> List[CivilizationProfile]:
        return [cls.protagonist(), cls.antagonist(), cls.observer()]
    
    @classmethod
    def extended_scenario(cls) -> List[CivilizationProfile]:
        """扩展场景: 4个文明 (含WILDCARD)"""
        base = cls.all_profiles()
        wildcard = CivilizationProfile(
            civ_id="CIV_DELTA",
            display_name="德尔塔文明",
            role=PlayerRole.WILDCARD,
            archetype=CivilizationArchetype.SURVIVALIST,
            initial_technology_level=35.0,
            initial_position=SpatialPosition(600.0, 300.0, 120.0),
            survival_strategy=SurvivalStrategy.FLEE,
            paranoia_level=0.60,
            cooperation_tendency=0.20,
            initial_resource_state=CosmicResource(
                energy_available=0.45,
                matter_density=0.40,
                information_access=0.30,
                habitable_zone_quality=0.70,
            ),
        )
        base.append(wildcard)
        return base


# ============================================================
# 文明实例化器 — 将Profile转换为运行时DeepCharacter
# ============================================================

@dataclass
class CivilizationInstance:
    """
    文明运行时实例 — 包装DeepCharacter + 元数据
    
    这是游戏循环操作的基本单元。
    """
    
    profile: CivilizationProfile
    character: DeepCharacter
    is_alive: bool = True
    current_tech_level: float = 0.0
    resource_state: Optional[CosmicResource] = None
    position: Optional[SpatialPosition] = None
    round_created: int = 0
    round_destroyed: Optional[int] = None
    total_events_received: int = 0
    actions_taken: List[str] = field(default_factory=list)
    
    def __post_init__(self) -> None:
        if self.current_tech_level <= 0:
            self.current_tech_level = self.profile.initial_technology_level
        if self.resource_state is None:
            self.resource_state = self.profile.initial_resource_state
        if self.position is None:
            self.position = self.profile.initial_position
    
    @property
    def civ_id(self) -> str:
        return self.profile.civ_id
    
    @property
    def role(self) -> PlayerRole:
        return self.profile.role
    
    def receive_event(self, event_type: str, intensity: float, metadata: Dict[str, Any]) -> List[str]:
        """转发事件到底层DeepCharacter"""
        self.total_events_received += 1
        try:
            affected = self.character.on_event(
                event_type=event_type,
                intensity=intensity,
                metadata=metadata,
            )
            return affected
        except Exception:
            return []
    
    def kill(self, round_num: int, reason: str = "") -> None:
        self.is_alive = False
        self.round_destroyed = round_num
        self.actions_taken.append(f"[R{round_num}] DESTROYED: {reason}")
    
    def get_belief_about(self, target_civ_id: str) -> Dict[str, float]:
        """获取对目标文明的各维度信念值"""
        result: Dict[str, float] = {}
        try:
            bs = self.character.belief_system
            for dim in BeliefDimension:
                state = bs.get_belief(target_civ_id, dim)
                result[dim.name] = state.expected_value
        except (KeyError, AttributeError):
            for dim in BeliefDimension:
                result[dim.name] = 0.5
        return result
    
    def get_threat_credibility(self, target_civ_id: str) -> Optional[float]:
        """获取对目标威胁的可信度评分"""
        try:
            score = self.character.threat_engine.get_credibility(target_civ_id)
            return score.overall_score
        except (KeyError, AttributeError):
            return None
    
    def to_snapshot(self, round_number: int) -> "CivilizationStateSnapshot":
        from .universe import CivilizationStateSnapshot
        
        cred_scores: Dict[str, float] = {}
        try:
            all_scores = self.character.threat_engine.get_all_scores()
            cred_scores = {k: v.overall_score for k, v in all_scores.items()}
        except (AttributeError, TypeError):
            pass

        primary_target = None
        try:
            bs_targets = self.character.belief_system.get_all_targets()
            if bs_targets:
                primary_target = bs_targets[0]
        except (AttributeError, TypeError):
            pass

        belief_entropy = 0.0
        strategy_entropy = 0.0
        try:
            snapshot = self.character.get_state_snapshot(
                force_refresh=True,
                target_entity_id=primary_target,
            )
            beliefs = getattr(snapshot, 'primary_target_beliefs', {})
            if beliefs:
                import statistics
                vals = list(beliefs.values())
                if len(vals) > 1:
                    belief_entropy = statistics.stdev(vals)
                if not primary_target and vals:
                    primary_target = list(beliefs.keys())[0]

            strategy_data = getattr(snapshot, 'current_strategy', None)
            if isinstance(strategy_data, dict):
                entropy_val = strategy_data.get('entropy')
                if entropy_val is not None and isinstance(entropy_val, (int, float)):
                    strategy_entropy = float(entropy_val)
                else:
                    coop_prob = strategy_data.get('cooperate_probability')
                    if coop_prob is not None:
                        import math
                        p = max(0.01, min(0.99, coop_prob))
                        strategy_entropy = -(p * math.log(p) + (1 - p) * math.log(1 - p))
        except (AttributeError, TypeError):
            pass
        
        return CivilizationStateSnapshot(
            round_number=round_number,
            civ_id=self.civ_id,
            technology_level=self.current_tech_level,
            resource_state=self.resource_state or CosmicResource(0.5, 0.5, 0.5, 0.5),
            active_threats_count=len(cred_scores),
            primary_target_id=primary_target,
            belief_entropy=belief_entropy,
            strategy_entropy=strategy_entropy,
            credibility_scores=cred_scores,
            is_alive=self.is_alive,
            dominance_position=self._compute_dominance(),
        )
    
    def _compute_dominance(self) -> float:
        try:
            tech_norm = min(1.0, self.current_tech_level / 200.0)
            resource_norm = (
                (
                    self.resource_state.energy_available +
                    self.resource_state.matter_density
                ) / 2.0
                if self.resource_state else 0.5
            )
            return tech_norm * 0.6 + resource_norm * 0.4
        except (AttributeError, TypeError):
            return 0.5


@dataclass
class CivilizationFactory:
    """
    文明工厂 — 从Profile创建完整的运行时实例
    
    工厂负责:
    1. 创建DeepCharacter实例
    2. 初始化信念系统 (预填充其他文明的信息)
    3. 初始化威胁可信度引擎
    4. 设置初始观测记录
    """
    
    @classmethod
    def create_all(
        cls,
        profiles: List[CivilizationProfile],
        seed: int = 42,
    ) -> List[CivilizationInstance]:
        """
        批量创建所有文明实例
        
        关键: 先创建所有实例, 再交叉初始化信念,
              确保每个文明都"知道"其他文明的存在(但不了解其意图)
        """
        instances: List[CivilizationInstance] = []
        
        for profile in profiles:
            instance = cls._create_single(profile, seed=seed)
            instances.append(instance)
        
        cls._cross_initialize_beliefs(instances)
        
        return instances
    
    @classmethod
    def _create_single(
        cls,
        profile: CivilizationProfile,
        seed: int = 42,
    ) -> CivilizationInstance:
        """创建单个文明实例"""
        char = DeepCharacter(character_id=profile.civ_id)
        
        _ = char.belief_system
        _ = char.threat_engine
        _ = char.strategy_engine
        
        instance = CivilizationInstance(
            profile=profile,
            character=char,
            current_tech_level=profile.initial_technology_level,
            resource_state=profile.initial_resource_state,
            position=profile.initial_position,
        )
        
        cls._apply_archetype_initial_observations(instance)
        
        return instance
    
    @classmethod
    def _cross_initialize_beliefs(
        cls,
        instances: List[CivilizationInstance],
    ) -> None:
        """
        交叉初始化信念 — 让每个文明对所有其他文明有基础认知
        
        原则: 
        - 初始信念为弱不确定 (接近0.5)
        - 技术差距影响COMPETENCE维度的初始偏移
        - 距离影响信息可靠性折扣
        """
        for instance in instances:
            for other in instances:
                if other.civ_id == instance.civ_id:
                    continue
                
                cls._initialize_belief_about(
                    observer=instance,
                    target_profile=other.profile,
                    distance=instance.position.distance_to(other.position),
                )
                
                cls._register_initial_threat_perception(
                    observer=instance,
                    target_civ_id=other.civ_id,
                    target_profile=other.profile,
                )
    
    @classmethod
    def _initialize_belief_about(
        cls,
        observer: CivilizationInstance,
        target_profile: CivilizationProfile,
        distance: float,
    ) -> None:
        """为observer初始化关于target的基础信念"""
        bs = observer.character.belief_system
        
        tech_ratio = (
            target_profile.initial_technology_level /
            (observer.current_tech_level + 0.1)
        )
        competence_bias = min(0.9, max(0.1, tech_ratio / (tech_ratio + 1)))
        
        distance_factor = max(0.3, 1.0 / (1.0 + distance / 500.0))
        
        arch = observer.profile.archetype
        
        dim_values: Dict[BeliefDimension, Tuple[float, float]] = {
            BeliefDimension.COOPERATIVITY: (
                observer.profile.belief_initial_alpha.get(BeliefDimension.COOPERATIVITY, 1.0),
                observer.profile.belief_initial_beta.get(BeliefDimension.COOPERATIVITY, 1.0),
            ),
            BeliefDimension.THREAT_LEVEL: (
                observer.profile.belief_initial_alpha.get(BeliefDimension.THREAT_LEVEL, 1.0),
                observer.profile.belief_initial_beta.get(BeliefDimension.THREAT_LEVEL, 1.0),
            ),
            BeliefDimension.COMPETENCE: (
                1.0 + competence_bias * 3.0,
                1.0 + (1.0 - competence_bias) * 3.0,
            ),
            BeliefDimension.ALIGNMENT: (
                observer.profile.belief_initial_alpha.get(BeliefDimension.ALIGNMENT, 1.0),
                observer.profile.belief_initial_beta.get(BeliefDimension.ALIGNMENT, 1.0),
            ),
            BeliefDimension.HONESTY: (
                observer.profile.belief_initial_alpha.get(BeliefDimension.HONESTY, 1.0),
                observer.profile.belief_initial_beta.get(BeliefDimension.HONESTY, 1.0),
            ),
            BeliefDimension.STABILITY: (
                observer.profile.belief_initial_alpha.get(BeliefDimension.STABILITY, 1.0),
                observer.profile.belief_initial_beta.get(BeliefDimension.STABILITY, 1.0),
            ),
        }
        
        obs_type = (
            ObservationType.CONTEXTUAL_CUE
            if distance > 200.0
            else ObservationType.REPORTED_INFO
        )
        reliability = distance_factor
        
        for dimension, (alpha_val, beta_val) in dim_values.items():
            obs = Observation(
                observation_type=obs_type,
                evidence_value=alpha_val / (alpha_val + beta_val),
                source_reliability=reliability,
                description=f"初始探测:{target_profile.display_name}",
            )
            try:
                bs.observe(
                    target_id=target_profile.civ_id,
                    dimension=dimension,
                    observation=obs,
                )
            except Exception:
                pass
    
    @classmethod
    def _register_initial_threat_perception(
        cls,
        observer: CivilizationInstance,
        target_civ_id: str,
        target_profile: CivilizationProfile,
    ) -> None:
        """注册初始威胁感知"""
        te = observer.character.threat_engine
        
        tech_gap = target_profile.initial_technology_level - observer.current_tech_level
        
        if tech_gap > 30.0:
            threat_content = f"检测到高技术等级实体 ({target_civ_id})"
            ttype = ThreatType.DETERRENCE
            cost = 0.7
        elif tech_gap < -30.0:
            threat_content = f"检测到低技术等级实体 ({target_civ_id})"
            ttype = ThreatType.BLUFF
            cost = 0.2
        else:
            threat_content = f"检测到同级别实体 ({target_civ_id})"
            ttype = ThreatType.SIGNALING
            cost = 0.4
        
        tr = ThreatRecord(
            content=threat_content,
            threat_type=ttype,
            commitment_level=target_profile.threat_default_commitment,
            estimated_cost=cost,
        )
        
        try:
            te.record_threat(tr)
        except Exception:
            pass
    
    @classmethod
    def _apply_archetype_initial_observations(
        cls,
        instance: CivilizationInstance,
    ) -> None:
        """应用原型特征作为自观测"""
        char = instance.character
        profile = instance.profile
        
        self_observation = Observation(
            observation_type=ObservationType.DIRECT_ACTION,
            evidence_value=profile.cooperation_tendency,
            source_reliability=1.0,
            description=f"自我评估: {profile.archetype.name}",
            context_tags=["self", "archetype", profile.archetype.name],
        )
        
        try:
            char.on_event(
                event_type="self_reflection",
                intensity=0.5,
                metadata={
                    "content": f"{profile.display_name} 自我身份确认",
                    "action_type": "INTERNAL",
                    "cooperation_tendency": profile.cooperation_tendency,
                    "paranoia_level": profile.paranoia_level,
                    "survival_strategy": profile.survival_strategy.name,
                },
            )
        except Exception:
            pass
