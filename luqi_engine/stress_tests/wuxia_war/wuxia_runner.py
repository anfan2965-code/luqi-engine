"""
武侠战争全链路无限循环引擎 v2

架构:
1. WuxiaEngineAdapter — 80维武侠状态 ↔ 引擎博弈论类型映射 + 行为翻译
2. EventEngine — 事件判定引擎(战斗/结盟/背叛/暗杀/死亡)
3. WuxiaInfiniteLoop — 无限轮次对话驱动器
4. EndingDetector — 结局检测(自然结局/手动终止)

数据流:
对话 → 分类动作 → 事件判定 → 后果(受伤/死亡/结盟/背叛) → 
世界更新 → 80维回写 → 下一轮 → 循环直到结局

v2修复清单(对照RETRO-202605):
- [P0] 新增EventEngine: 激活mark_dead/health_status/mental_state
- [P0] 修复faction_power_balance覆盖Bug: 改为全量重算
- [P0] 动态对话历史窗口: 按场景角色数+轮次计算
- [P1] 场景约束激活: required_tiers过滤/faction_bias/possible_actions注入
- [P1] 主角叙事线注入: motivation/fatal_flaw/special_ability
- [P1] 80维→行为翻译层: 浮点数翻译为行为指引文本
- [P2] 关系系统激活: 初始化/交互更新/影响发言选择
- [P2] Prompt重构: 行为级指令+出戏检测+思考链分离
- [P2] AGGRESSIVE语义修正+检查点清理
"""

from __future__ import annotations

import json
import logging
import math
import os
import random
import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple

from .world import (
    Character80DimState,
    CombatStyle,
    Faction,
    FactionAlignment,
    GeographyPoint,
    GeographySystem,
    MartialDomain,
    PersonalityTrait,
    ProtagonistProfile,
    ResourceType,
    SceneCategory,
    SocialDimension,
    WuxiaBeliefDimension,
    WuxiaWorld,
)
from .character_pool import (
    CharacterPool,
    CharacterTier,
    RoleType,
    SceneRegistry,
    SceneTemplate,
    WuxiaCharacter,
    create_wuxia_world,
)
from .narrative_engine import (
    ArcPhase,
    BeatType,
    CharacterLayer,
    CharacterStratifier,
    DramatisSuspenseModel,
    EmergenceDetector,
    EmergencePreset,
    EmergenceSignal,
    EmergenceThresholds,
    NarrativeEngine,
    PlotThreadManager,
    PlotThreadStatus,
    PlotThreadType,
    SceneResidencyEngine,
    StoryArcController,
    StoryformEngine,
    StoryformInequality,
)

logger = logging.getLogger(__name__)


# ============================================================
# 武侠→引擎 映射层
# ============================================================

@dataclass
class EngineMappedState:
    char_id: str
    tech_level: float = 30.0
    energy: float = 50.0
    cooperation_tendency: float = 0.5
    paranoia_level: float = 0.5
    dominant_strategy: str = "DEFECT"
    strategy_entropy: float = 1.0
    threat_credibility: float = 0.5
    belief_cooperativity: float = 0.5
    belief_threat: float = 0.5
    belief_competence: float = 0.5
    belief_alignment: float = 0.5
    belief_honesty: float = 0.5
    belief_stability: float = 0.5


class WuxiaEngineAdapter:
    STRATEGY_MAP = {
        CombatStyle.OFFENSIVE: "ATTACK",
        CombatStyle.DEFENSIVE: "DEFEND",
        CombatStyle.SPEED_FOCUS: "EVADE",
        CombatStyle.POWER_FOCUS: "ATTACK",
        CombatStyle.TECHNIQUE_FOCUS: "COOPERATE",
        CombatStyle.INTERNAL_FOCUS: "DEFEND",
        CombatStyle.EXTERNAL_FOCUS: "ATTACK",
        CombatStyle.MELEE_PREFERENCE: "ATTACK",
        CombatStyle.RANGE_PREFERENCE: "DEFEND",
        CombatStyle.GROUP_COMBAT: "COOPERATE",
        CombatStyle.DUEL_PREFERENCE: "ATTACK",
        CombatStyle.ASSASSINATION: "ATTACK",
        CombatStyle.FRONTLINE: "ATTACK",
        CombatStyle.GUERRILLA: "EVADE",
        CombatStyle.WAR_OF_ATTRITION: "DEFEND",
        CombatStyle.QUICK_DECISION: "ATTACK",
    }

    @classmethod
    def map_to_engine(cls, wuxia_char: WuxiaCharacter) -> EngineMappedState:
        state = wuxia_char.state_80dim
        if not state:
            return EngineMappedState(char_id=wuxia_char.char_id)
        mapped = EngineMappedState(char_id=wuxia_char.char_id)
        martial_vals = list(state.martial_domains.values())
        if martial_vals:
            mapped.tech_level = (sum(martial_vals) / len(martial_vals)) * 100
        resource_vals = list(state.resource_levels.values())
        if resource_vals:
            mapped.energy = (sum(resource_vals) / len(resource_vals)) * 100
        kindness = state.personality_traits.get(PersonalityTrait.KINDNESS, 0.5)
        cruelty = state.personality_traits.get(PersonalityTrait.CRUELTY, 0.5)
        mapped.cooperation_tendency = max(0.0, min(1.0, kindness - cruelty + 0.5))
        suspicious = state.personality_traits.get(PersonalityTrait.SUSPICIOUSNESS, 0.5)
        naive = state.personality_traits.get(PersonalityTrait.NAIVETE, 0.5)
        mapped.paranoia_level = max(0.0, min(1.0, suspicious - naive + 0.5))
        combat_items = list(state.combat_styles.items())
        if combat_items:
            top_style = max(combat_items, key=lambda x: x[1])
            mapped.dominant_strategy = cls.STRATEGY_MAP.get(top_style[0], "DEFECT")
        belief_map = {
            WuxiaBeliefDimension.COOPERATIVITY: "belief_cooperativity",
            WuxiaBeliefDimension.THREAT_LEVEL: "belief_threat",
            WuxiaBeliefDimension.COMPETENCE: "belief_competence",
            WuxiaBeliefDimension.ALIGNMENT: "belief_alignment",
            WuxiaBeliefDimension.HONESTY: "belief_honesty",
            WuxiaBeliefDimension.STABILITY: "belief_stability",
        }
        for wuxia_bel, eng_key in belief_map.items():
            val = state.belief_dims.get(wuxia_bel, 0.5)
            setattr(mapped, eng_key, val)
        entropy_sum = sum(state.personality_traits.values())
        n_traits = len(state.personality_traits)
        if n_traits > 0:
            avg_trait = entropy_sum / n_traits
            variance = sum((v - avg_trait) ** 2 for v in state.personality_traits.values()) / n_traits
            mapped.strategy_entropy = min(2.0, variance * 4 + 0.3)
        threat_factors = [
            state.martial_domains.get(MartialDomain.LIGHTNESS_SKILL, 0),
            state.martial_domains.get(MartialDomain.HIDDEN_WEAPON, 0),
            state.martial_domains.get(MartialDomain.POISON_ART, 0),
            state.martial_domains.get(MartialDomain.DISGUISE, 0),
        ]
        mapped.threat_credibility = sum(threat_factors) / max(len(threat_factors), 1)
        return mapped

    @classmethod
    def update_from_dialogue(
        cls,
        wuxia_char: WuxiaCharacter,
        dialogue_action: str,
        target_id: Optional[str] = None,
        intensity: float = 0.3,
    ):
        state = wuxia_char.state_80dim
        if not state:
            return
        action_effects = {
            "AGGRESSIVE": {
                PersonalityTrait.ARROGANCE: intensity * 0.1,
                PersonalityTrait.BOLDNESS: intensity * 0.15,
                PersonalityTrait.CAUTIOUSNESS: -intensity * 0.1,
                PersonalityTrait.KINDNESS: -intensity * 0.05,
                CombatStyle.OFFENSIVE: intensity * 0.1,
                WuxiaBeliefDimension.THREAT_LEVEL: intensity * 0.08,
                SocialDimension.JIANGHU_CODE: -intensity * 0.03,
                ResourceType.SILVER: -intensity * 0.02,
                ResourceType.INTEL: intensity * 0.02,
            },
            "FRIENDLY": {
                PersonalityTrait.KINDNESS: intensity * 0.1,
                PersonalityTrait.AGREEABLENESS: intensity * 0.08,
                SocialDimension.JIANGHU_CODE: intensity * 0.05,
                SocialDimension.REPUTATION: intensity * 0.03,
                WuxiaBeliefDimension.COOPERATIVITY: intensity * 0.1,
                CombatStyle.GROUP_COMBAT: intensity * 0.05,
                ResourceType.CONNECTIONS: intensity * 0.04,
            },
            "NEUTRAL": {
                PersonalityTrait.CALMNESS: intensity * 0.05,
                PersonalityTrait.FLEXIBILITY: intensity * 0.05,
                WuxiaBeliefDimension.STABILITY: intensity * 0.03,
                ResourceType.INTEL: intensity * 0.02,
            },
            "EVASIVE": {
                PersonalityTrait.CAUTIOUSNESS: intensity * 0.1,
                CombatStyle.DEFENSIVE: intensity * 0.08,
                CombatStyle.GUERRILLA: intensity * 0.05,
                WuxiaBeliefDimension.THREAT_LEVEL: intensity * 0.05,
                SocialDimension.REPUTATION: -intensity * 0.02,
            },
        }
        effects = action_effects.get(dialogue_action, {})
        for key, delta in effects.items():
            if hasattr(state, 'martial_domains') and key in state.martial_domains:
                state.martial_domains[key] = max(0.0, min(1.0, state.martial_domains[key] + delta))
            elif hasattr(state, 'personality_traits') and key in state.personality_traits:
                state.personality_traits[key] = max(0.0, min(1.0, state.personality_traits[key] + delta))
            elif hasattr(state, 'combat_styles') and key in state.combat_styles:
                state.combat_styles[key] = max(0.0, min(1.0, state.combat_styles[key] + delta))
            elif hasattr(state, 'social_dims') and key in state.social_dims:
                state.social_dims[key] = max(0.0, min(1.0, state.social_dims[key] + delta))
            elif hasattr(state, 'belief_dims') and key in state.belief_dims:
                state.belief_dims[key] = max(0.0, min(1.0, state.belief_dims[key] + delta))
            elif hasattr(state, 'resource_levels') and key in state.resource_levels:
                state.resource_levels[key] = max(0.0, min(1.0, state.resource_levels[key] + delta))

    @classmethod
    def translate_to_behavior(cls, wuxia_char: WuxiaCharacter) -> List[str]:
        behaviors: List[str] = []
        state = wuxia_char.state_80dim
        if not state:
            return behaviors
        coop = state.belief_dims.get(WuxiaBeliefDimension.COOPERATIVITY, 0.5)
        if coop < 0.25:
            behaviors.append("你对他人极度不信任，倾向于独来独往，拒绝任何合作提议")
        elif coop < 0.4:
            behaviors.append("你很少信任他人，只在确有利益时才会有限度地合作")
        elif coop > 0.75:
            behaviors.append("你天性乐于与人合作，愿意信任他人并寻求共赢")
        elif coop > 0.6:
            behaviors.append("你倾向于与人合作，但会保持基本警惕")
        threat = state.belief_dims.get(WuxiaBeliefDimension.THREAT_LEVEL, 0.5)
        if threat > 0.75:
            behaviors.append("你感到强烈威胁，随时准备应对危险，精神高度紧张")
        elif threat > 0.6:
            behaviors.append("你察觉到周围存在潜在威胁，保持警惕")
        elif threat < 0.25:
            behaviors.append("你感到安全放松，对周围环境毫无戒心")
        kindness = state.personality_traits.get(PersonalityTrait.KINDNESS, 0.5)
        cruelty = state.personality_traits.get(PersonalityTrait.CRUELTY, 0.5)
        if kindness > 0.7:
            behaviors.append("你心怀慈悲，不愿见人受苦，会主动帮助弱者")
        elif cruelty > 0.7:
            behaviors.append("你心狠手辣，为达目的不择手段，视人命如草芥")
        elif kindness > 0.55:
            behaviors.append("你本性善良，但不会因此放弃原则")
        elif cruelty > 0.55:
            behaviors.append("你行事冷酷，但偶尔会流露出一丝人性")
        arrogance = state.personality_traits.get(PersonalityTrait.ARROGANCE, 0.5)
        if arrogance > 0.7:
            behaviors.append("你自视甚高，目中无人，不屑与庸者为伍")
        elif arrogance > 0.55:
            behaviors.append("你有些骄傲，但尚能克制")
        cautious = state.personality_traits.get(PersonalityTrait.CAUTIOUSNESS, 0.5)
        bold = state.personality_traits.get(PersonalityTrait.BOLDNESS, 0.5)
        if cautious > 0.7:
            behaviors.append("你行事极为谨慎，三思而后行，绝不冒进")
        elif bold > 0.7:
            behaviors.append("你胆大果决，敢冒奇险，绝不退缩")
        loyalty = state.personality_traits.get(PersonalityTrait.LOYALTY, 0.5)
        if loyalty > 0.7:
            behaviors.append("你忠义两全，绝不会背叛同门和盟友")
        elif loyalty < 0.3:
            behaviors.append("你见利忘义，随时可能背叛盟友")
        if state.health_status < 0.3:
            behaviors.append("你身受重伤，气息奄奄，随时可能倒下")
        elif state.health_status < 0.6:
            behaviors.append("你身上有伤，行动受限，需要休养")
        if state.mental_state < 0.3:
            behaviors.append("你精神崩溃，心神不宁，难以集中")
        elif state.mental_state < 0.6:
            behaviors.append("你心神不安，思绪混乱")
        top_combat = sorted(state.combat_styles.items(), key=lambda x: x[1], reverse=True)[:2]
        combat_desc = []
        for style, val in top_combat:
            if val > 0.6:
                combat_desc.append(f"擅长{style.value}")
        if combat_desc:
            behaviors.append("你的战斗风格: " + "、".join(combat_desc))
        return behaviors


# ============================================================
# 事件引擎 (v2新增 — 激活mark_dead/health_status/mental_state)
# ============================================================

@dataclass
class EventOutcome:
    event_type: str
    source_id: str
    target_id: Optional[str]
    description: str
    health_delta: float = 0.0
    mental_delta: float = 0.0
    target_dead: bool = False
    source_dead: bool = False
    relationship_delta: float = 0.0
    faction_power_delta: float = 0.0


class EventEngine:
    """
    事件判定引擎 — 将对话分类转化为世界事件
    
    核心逻辑:
    AGGRESSIVE + 高武力差 → 战斗判定 → 可能受伤/死亡
    FRIENDLY + 同阵营 → 结盟判定 → 关系提升
    AGGRESSIVE + 异阵营 + 高danger → 战争事件 → 大规模伤亡
    EVASIVE + 低health → 逃跑/隐匿 → 位置迁移
    """

    COMBAT_BASE_INJURY = 0.15
    COMBAT_MORTALITY_THRESHOLD = 0.85
    ALLIANCE_RELATIONSHIP_BOOST = 0.15
    BETRAYAL_RELATIONSHIP_DROP = -0.3
    MENTAL_STRESS_FROM_COMBAT = 0.05
    MENTAL_RECOVERY_PER_ROUND = 0.01

    @classmethod
    def process_action(
        cls,
        speaker: WuxiaCharacter,
        action_type: str,
        confidence: float,
        scene: SceneTemplate,
        pool: CharacterPool,
        rng: random.Random,
        geography: Optional[GeographySystem] = None,
    ) -> Optional[EventOutcome]:
        if not speaker.state_80dim or not speaker.is_alive:
            return None
        if action_type == "AGGRESSIVE":
            return cls._process_combat(speaker, confidence, scene, pool, rng, geography=geography)
        elif action_type == "FRIENDLY":
            return cls._process_alliance(speaker, confidence, scene, pool, rng, geography=geography)
        elif action_type == "EVASIVE":
            return cls._process_evasion(speaker, confidence, scene, rng, geography=geography)
        elif action_type == "NEUTRAL":
            return cls._process_neutral(speaker, confidence, scene, pool, rng, geography=geography)
        return None

    @classmethod
    def _process_combat(
        cls,
        speaker: WuxiaCharacter,
        confidence: float,
        scene: SceneTemplate,
        pool: CharacterPool,
        rng: random.Random,
        geography: Optional[GeographySystem] = None,
    ) -> EventOutcome:
        speaker_power = speaker.power_level
        speaker_health = speaker.state_80dim.health_status
        danger = scene.danger_level
        if geography and speaker.current_location:
            geo_danger = geography.get_danger_at(speaker.current_location)
            danger = max(danger, geo_danger)
        injury_scale = cls.COMBAT_BASE_INJURY * (0.5 + danger) * (0.5 + confidence)
        speaker_self_harm = injury_scale * 0.3 * rng.random()
        speaker.state_80dim.health_status = max(
            0.0, speaker_health - speaker_self_harm
        )
        speaker.state_80dim.mental_state = max(
            0.0, speaker.state_80dim.mental_state - cls.MENTAL_STRESS_FROM_COMBAT * rng.random()
        )
        speaker_dead = False
        if speaker.state_80dim.health_status <= 0.05:
            speaker_death_chance = cls.COMBAT_MORTALITY_THRESHOLD * 0.3 * danger
            if rng.random() < speaker_death_chance:
                speaker.state_80dim.health_status = 0.0
                speaker.state_80dim.alive = False
                pool.mark_dead(speaker.char_id)
                speaker_dead = True
        target = cls._find_combat_target(speaker, pool, rng)
        if target and target.state_80dim:
            target_power = target.power_level
            power_ratio = speaker_power / max(target_power, 1.0)
            target_injury = injury_scale * min(power_ratio, 3.0) * (0.5 + rng.random())
            target.state_80dim.health_status = max(
                0.0, target.state_80dim.health_status - target_injury
            )
            target.state_80dim.mental_state = max(
                0.0, target.state_80dim.mental_state - cls.MENTAL_STRESS_FROM_COMBAT * 1.5 * rng.random()
            )
            target_dead = False
            if target.state_80dim.health_status <= 0.05:
                death_chance = cls.COMBAT_MORTALITY_THRESHOLD * power_ratio * danger
                if rng.random() < death_chance:
                    target.state_80dim.health_status = 0.0
                    target.state_80dim.alive = False
                    pool.mark_dead(target.char_id)
                    target_dead = True
            speaker.relationships[target.char_id] = speaker.relationships.get(
                target.char_id, 0.0
            ) + cls.BETRAYAL_RELATIONSHIP_DROP
            target.relationships[speaker.char_id] = target.relationships.get(
                speaker.char_id, 0.0
            ) + cls.BETRAYAL_RELATIONSHIP_DROP
            desc_parts = [f"{speaker.display_name}对{target.display_name}发起攻击"]
            if target_dead:
                desc_parts.append(f"，{target.display_name}被击杀！")
            else:
                desc_parts.append(f"，{target.display_name}受伤(生命{target.state_80dim.health_status:.0%})")
            if speaker_dead:
                desc_parts.append(f" {speaker.display_name}亦受重创身亡！")
            desc = "".join(desc_parts)
            return EventOutcome(
                event_type="COMBAT",
                source_id=speaker.char_id,
                target_id=target.char_id,
                description=desc,
                health_delta=-target_injury,
                mental_delta=-cls.MENTAL_STRESS_FROM_COMBAT,
                target_dead=target_dead,
                source_dead=speaker_dead,
                relationship_delta=cls.BETRAYAL_RELATIONSHIP_DROP,
            )
        return EventOutcome(
            event_type="COMBAT_MISS",
            source_id=speaker.char_id,
            target_id=None,
            description=f"{speaker.display_name}发起攻击但未命中目标" + ("，自身伤重身亡！" if speaker_dead else ""),
            health_delta=-speaker_self_harm,
            source_dead=speaker_dead,
        )

    @classmethod
    def _process_alliance(
        cls,
        speaker: WuxiaCharacter,
        confidence: float,
        scene: SceneTemplate,
        pool: CharacterPool,
        rng: random.Random,
        geography: Optional[GeographySystem] = None,
    ) -> EventOutcome:
        target = cls._find_ally_target(speaker, pool, rng)
        if target:
            boost = cls.ALLIANCE_RELATIONSHIP_BOOST * confidence
            speaker.relationships[target.char_id] = min(
                1.0, speaker.relationships.get(target.char_id, 0.0) + boost
            )
            target.relationships[speaker.char_id] = min(
                1.0, target.relationships.get(speaker.char_id, 0.0) + boost * 0.8
            )
            if speaker.state_80dim:
                speaker.state_80dim.mental_state = min(
                    1.0, speaker.state_80dim.mental_state + 0.02
                )
                speaker.state_80dim.resource_levels[ResourceType.CONNECTIONS] = min(
                    1.0,
                    speaker.state_80dim.resource_levels.get(ResourceType.CONNECTIONS, 0.5) + 0.02,
                )
            desc = f"{speaker.display_name}与{target.display_name}增进关系"
            return EventOutcome(
                event_type="ALLIANCE",
                source_id=speaker.char_id,
                target_id=target.char_id,
                description=desc,
                relationship_delta=boost,
            )
        return EventOutcome(
            event_type="ALLIANCE_SOLO",
            source_id=speaker.char_id,
            target_id=None,
            description=f"{speaker.display_name}表达了合作意愿但无人响应",
        )

    @classmethod
    def _process_evasion(
        cls,
        speaker: WuxiaCharacter,
        confidence: float,
        scene: SceneTemplate,
        rng: random.Random,
        geography: Optional[GeographySystem] = None,
    ) -> EventOutcome:
        if speaker.state_80dim and speaker.state_80dim.health_status < 0.5:
            speaker.state_80dim.health_status = min(
                1.0, speaker.state_80dim.health_status + 0.03
            )
            speaker.state_80dim.mental_state = min(
                1.0, speaker.state_80dim.mental_state + 0.02
            )
        new_loc = None
        if geography:
            new_loc = geography.migrate_character(
                speaker, prefer_nearby=True, max_distance=20.0,
            )
        loc_desc = f"，转移至{new_loc}" if new_loc else ""
        desc = f"{speaker.display_name}选择回避，暂避锋芒{loc_desc}"
        return EventOutcome(
            event_type="EVASION",
            source_id=speaker.char_id,
            target_id=None,
            description=desc,
            health_delta=0.03,
            mental_delta=0.02,
        )

    @classmethod
    def _process_neutral(
        cls,
        speaker: WuxiaCharacter,
        confidence: float,
        scene: SceneTemplate,
        pool: CharacterPool,
        rng: random.Random,
        geography: Optional[GeographySystem] = None,
    ) -> EventOutcome:
        info_gain = confidence * 0.03
        if geography and speaker.current_location:
            loc = geography.get_location(speaker.current_location)
            if loc and loc.controlling_faction and loc.controlling_faction != speaker.faction:
                info_gain *= 1.5
        if speaker.state_80dim:
            speaker.state_80dim.resource_levels[ResourceType.INTEL] = min(
                1.0,
                speaker.state_80dim.resource_levels.get(ResourceType.INTEL, 0.5) + info_gain,
            )
            speaker.state_80dim.mental_state = min(
                1.0, speaker.state_80dim.mental_state + 0.01,
            )
        observers = [c for c in pool.get_alive()
                    if c.char_id != speaker.char_id and
                    c.current_location == speaker.current_location]
        if observers and rng.random() < confidence * 0.5:
            target = rng.choice(observers)
            speaker.relationships[target.char_id] = min(
                1.0, speaker.relationships.get(target.char_id, 0.0) + 0.01
            )
            desc = f"{speaker.display_name}观察了{target.display_name}的言行举止"
            return EventOutcome(
                event_type="OBSERVATION",
                source_id=speaker.char_id,
                target_id=target.char_id,
                description=desc,
                relationship_delta=0.01,
            )
        desc = f"{speaker.display_name}在{scene.name}静观其变，收集信息"
        return EventOutcome(
            event_type="INFORMATION_GATHERING",
            source_id=speaker.char_id,
            target_id=None,
            description=desc,
        )

    @classmethod
    def _find_combat_target(
        cls,
        speaker: WuxiaCharacter,
        pool: CharacterPool,
        rng: random.Random,
    ) -> Optional[WuxiaCharacter]:
        same_loc = pool.at_location(speaker.current_location) if speaker.current_location else []
        enemy_faction_chars = []
        if speaker.faction:
            for f in Faction:
                if f != speaker.faction:
                    enemy_faction_chars.extend(pool.by_faction(f))
        candidates = same_loc if len(same_loc) > 3 else pool.get_alive()
        candidates = [c for c in candidates if c.char_id != speaker.char_id and c.is_alive]
        if not candidates:
            return None
        weighted = []
        for c in candidates:
            w = 1.0
            if c in enemy_faction_chars:
                w *= 2.5
            rel = speaker.relationships.get(c.char_id, 0.0)
            if rel < -0.3:
                w *= 2.0
            elif rel > 0.3:
                w *= 0.3
            if c.power_level < speaker.power_level * 0.5:
                w *= 1.5
            weighted.append((c, w))
        total_w = sum(w for _, w in weighted)
        r = rng.random() * total_w
        cumul = 0.0
        for c, w in weighted:
            cumul += w
            if r <= cumul:
                return c
        return weighted[-1][0] if weighted else None

    @classmethod
    def _find_ally_target(
        cls,
        speaker: WuxiaCharacter,
        pool: CharacterPool,
        rng: random.Random,
    ) -> Optional[WuxiaCharacter]:
        same_loc = pool.at_location(speaker.current_location) if speaker.current_location else []
        same_faction = pool.by_faction(speaker.faction) if speaker.faction else []
        candidates = same_loc if len(same_loc) > 3 else pool.get_alive()
        candidates = [c for c in candidates if c.char_id != speaker.char_id and c.is_alive]
        if not candidates:
            return None
        weighted = []
        for c in candidates:
            w = 1.0
            if c in same_faction:
                w *= 3.0
            rel = speaker.relationships.get(c.char_id, 0.0)
            if rel > 0.1:
                w *= 2.0
            weighted.append((c, w))
        total_w = sum(w for _, w in weighted)
        r = rng.random() * total_w
        cumul = 0.0
        for c, w in weighted:
            cumul += w
            if r <= cumul:
                return c
        return weighted[-1][0] if weighted else None

    @classmethod
    def passive_recovery(cls, pool: CharacterPool, rng: random.Random):
        for c in pool.get_alive():
            if c.state_80dim:
                if c.state_80dim.health_status < 1.0 and c.state_80dim.health_status > 0.1:
                    c.state_80dim.health_status = min(
                        1.0, c.state_80dim.health_status + cls.MENTAL_RECOVERY_PER_ROUND * rng.random()
                    )
                if c.state_80dim.mental_state < 1.0:
                    c.state_80dim.mental_state = min(
                        1.0, c.state_80dim.mental_state + cls.MENTAL_RECOVERY_PER_ROUND
                    )


# ============================================================
# 对话动作分类器
# ============================================================

class DialogueActionClassifier:
    AGGRESSIVE_KEYWORDS = [
        "杀", "灭", "毁", "斩", "血", "死", "仇", "恨", "战", "攻",
        "狠", "毒", "刺", "暗杀", "灭口", "绝不", "誓不", "血债",
        "找死", "送死", "不知死活", "狂妄", "放肆", "胆敢",
        "受死", "拿命来", "不共戴天", "碎尸万段", "诛杀",
    ]
    FRIENDLY_KEYWORDS = [
        "请", "愿", "助", "帮", "共", "合", "友", "义", "信", "诚",
        "携手", "并肩", "结盟", "合作", "信任", "诚意", "以礼相待",
        "幸会", "久仰", "佩服", "敬佩", "感激", "多谢",
    ]
    EVASIVE_KEYWORDS = [
        "暂", "容", "再", "后", "缓", "退", "避", "走", "离",
        "三思", "从长计议", "来日方长", "不必急于", "容后再议",
        "告辞", "失陪", "改日", "稍后", "暂且",
    ]

    @classmethod
    def classify(cls, text: str) -> Tuple[str, float]:
        agg_score = sum(1 for kw in cls.AGGRESSIVE_KEYWORDS if kw in text)
        fri_score = sum(1 for kw in cls.FRIENDLY_KEYWORDS if kw in text)
        eva_score = sum(1 for kw in cls.EVASIVE_KEYWORDS if kw in text)
        scores = {
            "AGGRESSIVE": agg_score,
            "FRIENDLY": fri_score,
            "EVASIVE": eva_score,
            "NEUTRAL": 0.5,
        }
        best_type = max(scores, key=scores.get)
        best_score = scores[best_type]
        total = agg_score + fri_score + eva_score
        if total == 0:
            return "NEUTRAL", 0.3
        confidence = min(1.0, best_score / max(total, 1) * 1.5)
        return best_type, confidence


# ============================================================
# 出戏检测器 (v2新增)
# ============================================================

class OutOfCharacterDetector:
    BREAK_PATTERN = re.compile(
        r"(首先[，,]我是|身份是|核心性格|系统提示|作为AI|我是一个|我的设定|"
        r"根据指令|按照要求|我的角色设定|身份信息|角色背景如下)",
        re.IGNORECASE,
    )
    THINKING_PATTERN = re.compile(
        r"(让我思考|分析一下|从.*角度|综上所述|首先.*其次|第一步|"
        r"我认为应该|理性分析|逻辑上|推理过程)",
        re.IGNORECASE,
    )

    @classmethod
    def check(cls, text: str) -> Tuple[bool, str]:
        if cls.BREAK_PATTERN.search(text[:200]):
            return True, "BREAK_CHARACTER"
        if cls.THINKING_PATTERN.search(text[:300]):
            return True, "THINKING_LEAK"
        return False, ""


# ============================================================
# 场景管理器
# ============================================================

@dataclass
class WorldState:
    current_round: int = 0
    current_scene: Optional[SceneTemplate] = None
    current_location: str = ""
    active_characters: List[str] = field(default_factory=list)
    recent_events: List[str] = field(default_factory=list)
    faction_power_balance: Dict[str, float] = field(default_factory=dict)
    death_toll: int = 0
    alliances_formed: int = 0
    betrayals: int = 0
    secrets_revealed: int = 0
    combat_events: int = 0
    protagonist_speak_interval: int = 0

    def to_summary(self, max_events: int = 10) -> str:
        lines = [
            f"=== 第{self.current_round}轮世界状态 ===",
            f"当前场景: {self.current_scene.name if self.current_scene else '未知'}"
            f"[{self.current_scene.category.value if self.current_scene else '?'}]",
            f"当前位置: {self.current_location or '未知'}",
            f"活跃角色: {len(self.active_characters)}人",
            f"死亡人数: {self.death_toll}",
            f"战斗事件: {self.combat_events}",
            f"结盟次数: {self.alliances_formed}",
            f"背叛次数: {self.betrayals}",
        ]
        if self.recent_events:
            lines.append("近期事件:")
            for evt in self.recent_events[-max_events:]:
                lines.append(f"  - {evt}")
        return "\n".join(lines)


class SceneManager:
    def __init__(self, registry: SceneRegistry, seed: int = 42):
        self.registry = registry
        self.rng = random.Random(seed)
        self._scene_history: List[str] = []

    def select_next_scene(
        self,
        world_state: WorldState,
        pool: CharacterPool,
        preferred_category: Optional[SceneCategory] = None,
    ) -> SceneTemplate:
        all_scenes = self.registry.all_scenes()
        round_num = world_state.current_round
        total_chars = pool.alive_count
        danger_floor = min(0.2 + round_num * 0.002, 0.7)
        danger_ceil = min(danger_floor + 0.3, 1.0)
        candidates = self.registry.by_danger(danger_floor, danger_ceil)
        if preferred_category:
            cat_scenes = self.registry.by_category(preferred_category)
            if cat_scenes and self.rng.random() < 0.35:
                candidates = cat_scenes
        if not candidates:
            candidates = all_scenes
        recent_ids = set(self._scene_history[-20:])
        unique_candidates = [s for s in candidates if s.scene_id not in recent_ids]
        chosen_pool = unique_candidates if unique_candidates else candidates
        scene = self.rng.choice(chosen_pool)
        self._scene_history.append(scene.scene_id)
        return scene

    def filter_characters_for_scene(
        self,
        scene: SceneTemplate,
        pool: CharacterPool,
    ) -> List[WuxiaCharacter]:
        alive = pool.get_alive()
        filtered = []
        for c in alive:
            if scene.required_tiers and c.tier not in scene.required_tiers:
                tier_gap = abs(
                    list(CharacterTier).index(c.tier) -
                    min(list(CharacterTier).index(t) for t in scene.required_tiers)
                )
                if tier_gap > 2:
                    continue
            if scene.faction_bias and c.faction == scene.faction_bias:
                pass
            filtered.append(c)
        if not filtered:
            filtered = alive
        return filtered

    def get_scene_context(self, scene: SceneTemplate) -> str:
        parts = [
            f"【当前场景: {scene.name}】",
            f"类别: {scene.category.value}",
            f"危险等级: {int(scene.danger_level * 100)}%",
            f"环境氛围: {'、'.join(scene.atmosphere_keywords)}",
            f"场景描述: {scene.description}",
            f"在此场景中你可以: {' | '.join(scene.possible_actions)}",
        ]
        return "\n".join(parts)


# ============================================================
# 结局检测
# ============================================================

class EndingType(Enum):
    NATURAL_CONCLUSION = "自然结局"
    FACTION_DOMINANCE = "一统江湖"
    PROTAGONIST_DEATH = "主角陨落"
    TOTAL_WAR = "全面战争"
    PEACE_TREATY = "天下太平"
    MYSTERY_SOLVED = "真相大白"
    MANUAL_TERMINATE = "手动终止"


@dataclass
class EndingCondition:
    ending_type: EndingType
    reason: str
    round_number: int
    statistics: Dict[str, Any]


class EndingDetector:
    DOMINANCE_THRESHOLD = 0.7
    DEATH_RATIO_THRESHOLD = 0.3
    MAX_ROUNDS_HARD_LIMIT = 5000
    PEACE_ALLIANCE_MIN = 50
    PEACE_BETRAYAL_MAX_RATIO = 0.15
    MYSTERY_SECRETS_MIN = 8
    NATURAL_CONCLUSION_MIN_ROUNDS = 1500
    NATURAL_CONCLUSION_DEATH_RATIO_MAX = 0.10

    @classmethod
    def check(
        cls,
        pool: CharacterPool,
        world_state: WorldState,
        force_check: bool = False,
    ) -> Optional[EndingCondition]:
        alive = pool.alive_count
        total = len(pool.all_characters)
        current_round = world_state.current_round
        stats = {
            "alive": alive,
            "dead": pool.dead_count,
            "total": total,
            "death_ratio": pool.dead_count / max(total, 1),
            "factions_active": len(set(
                c.faction.value for c in pool.get_alive() if c.faction
            )),
            "rounds": current_round,
            "combat_events": world_state.combat_events,
            "alliances_formed": world_state.alliances_formed,
            "betrayals": world_state.betrayals,
            "secrets_revealed": world_state.secrets_revealed,
        }
        if current_round >= cls.MAX_ROUNDS_HARD_LIMIT:
            return EndingCondition(
                ending_type=EndingType.MANUAL_TERMINATE,
                reason=f"达到最大轮次上限({cls.MAX_ROUNDS_HARD_LIMIT}轮)",
                round_number=current_round,
                statistics=stats,
            )
        faction_counts: Dict[str, int] = {}
        for c in pool.get_alive():
            fname = c.faction.value if c.faction else "散人"
            faction_counts[fname] = faction_counts.get(fname, 0) + 1
        if faction_counts:
            top_faction = max(faction_counts, key=faction_counts.get)
            top_count = faction_counts[top_faction]
            dominance = top_count / max(alive, 1)
            if dominance >= cls.DOMINANCE_THRESHOLD and alive > 50:
                return EndingCondition(
                    ending_type=EndingType.FACTION_DOMINANCE,
                    reason=f"{top_faction}势力已控制江湖({dominance:.0%}存活角色属于该阵营)",
                    round_number=current_round,
                    statistics={**stats, "dominant_faction": top_faction},
                )
        death_ratio = pool.dead_count / max(total, 1)
        if death_ratio >= cls.DEATH_RATIO_THRESHOLD and pool.dead_count > 30:
            return EndingCondition(
                ending_type=EndingType.TOTAL_WAR,
                reason=f"死亡比例过高({death_ratio:.0%}), 累计{pool.dead_count}人死亡",
                round_number=current_round,
                statistics=stats,
            )
        legendary_alive = pool.by_tier(CharacterTier.LEGENDARY)
        elite_alive = pool.by_tier(CharacterTier.ELITE)
        if not legendary_alive and not elite_alive and current_round >= 200:
            return EndingCondition(
                ending_type=EndingType.TOTAL_WAR,
                reason=f"武林浩劫: 所有传奇与精英角色已全部陨落, 仅余{alive}名普通武者存活",
                round_number=current_round,
                statistics={**stats, "legendary_elite_extinct": True},
            )
        protag_alive = [pid for pid in pool.protagonist_ids
                       if (c := pool.get(pid)) and c.is_alive]
        protag_dead = [pid for pid in pool.protagonist_ids
                      if (c := pool.get(pid)) and not c.is_alive]
        user_alive = pool.user_id and (c := pool.get(pool.user_id)) and c.is_alive
        if protag_dead and len(protag_dead) == len(pool.protagonist_ids) and not user_alive:
            return EndingCondition(
                ending_type=EndingType.PROTAGONIST_DEATH,
                reason="所有主角均已阵亡",
                round_number=current_round,
                statistics=stats,
            )
        if protag_dead and len(protag_dead) < len(pool.protagonist_ids):
            dead_names = []
            for pid in protag_dead:
                pc = pool.get(pid)
                if pc:
                    dead_names.append(pc.display_name)
            return EndingCondition(
                ending_type=EndingType.PROTAGONIST_DEATH,
                reason=f"主角陨落: {', '.join(dead_names)}",
                round_number=current_round,
                statistics={**stats, "dead_protagonists": dead_names},
            )
        if (world_state.alliances_formed >= cls.PEACE_ALLIANCE_MIN and
            world_state.betrayals <= world_state.alliances_formed * cls.PEACE_BETRAYAL_MAX_RATIO and
            current_round >= 500):
            return EndingCondition(
                ending_type=EndingType.PEACE_TREATY,
                reason=f"天下太平: 结盟{world_state.alliances_formed}次, 背叛仅{world_state.betrayals}次, 江湖归于和平",
                round_number=current_round,
                statistics=stats,
            )
        if world_state.secrets_revealed >= cls.MYSTERY_SECRETS_MIN:
            return EndingCondition(
                ending_type=EndingType.MYSTERY_SOLVED,
                reason=f"真相大白: 已揭露{world_state.secrets_revealed}个秘密, 江湖隐秘尽被揭开",
                round_number=current_round,
                statistics=stats,
            )
        if (current_round >= cls.NATURAL_CONCLUSION_MIN_ROUNDS and
            death_ratio < cls.NATURAL_CONCLUSION_DEATH_RATIO_MAX and
            world_state.combat_events < current_round * 0.05):
            return EndingCondition(
                ending_type=EndingType.NATURAL_CONCLUSION,
                reason=f"自然结局: {current_round}轮后江湖趋于平静, 死亡率仅{death_ratio:.1%}",
                round_number=current_round,
                statistics=stats,
            )
        return None


# ============================================================
# 无限循环核心
# ============================================================

@dataclass
class TurnResult:
    turn_number: int
    speaker_id: str
    speaker_name: str
    response_text: str
    action_classified: str
    action_confidence: float
    scene: Optional[str]
    latency_ms: float
    tokens_used: int
    engine_state_snapshot: Dict[str, Any]
    event_outcome: Optional[EventOutcome] = None


@dataclass
class InfiniteLoopResult:
    session_id: str
    total_turns: int
    total_tokens: int
    total_latency_ms: float
    ending: Optional[EndingCondition]
    turns: List[TurnResult] = field(default_factory=list)
    final_world_state: Optional[Dict[str, Any]] = None
    error_log: List[str] = field(default_factory=list)


class WuxiaInfiniteLoop:
    PROTAGONIST_FORCE_INTERVAL = 8
    HISTORY_BASE_PER_CHAR = 2
    HISTORY_GROWTH_PER_HUNDRED_ROUNDS = 1
    HISTORY_MAX = 80

    def __init__(
        self,
        api_key: str,
        base_url: str,
        model: str = "mimo-v2.5",
        character_count: int = 620,
        seed: int = 42,
        temperature: float = 0.75,
        max_tokens: int = 800,
        max_rounds: int = 5000,
        save_interval: int = 25,
        output_dir: str = "G:/AAA研究/02 角色与世界的理解/wuxia_runs",
        emergence_preset: EmergencePreset = EmergencePreset.BALANCED,
        custom_emergence_thresholds: Optional[EmergenceThresholds] = None,
        custom_storyform_inequalities: Optional[List[StoryformInequality]] = None,
        narrative_arc_enabled: bool = True,
    ):
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.character_count = character_count
        self.seed = seed
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.max_rounds = max_rounds
        self.save_interval = save_interval
        self.output_dir = output_dir
        self.session_id = uuid.uuid4().hex[:12]
        self.rng = random.Random(seed)
        os.makedirs(output_dir, exist_ok=True)
        self.pool: Optional[CharacterPool] = None
        self.scene_registry: Optional[SceneRegistry] = None
        self.scene_manager: Optional[SceneManager] = None
        self.world_state: Optional[WorldState] = None
        self._turn_results: List[TurnResult] = []
        self._total_tokens = 0
        self._total_latency = 0.0
        self._conversation_history: List[Dict[str, str]] = []
        self._scene_history_summaries: List[str] = []
        self._is_running = False
        self._should_stop = False
        self._protagonist_profiles: Dict[str, ProtagonistProfile] = {}
        self.narrative_arc_enabled = narrative_arc_enabled
        self.emergence_preset = emergence_preset
        self.custom_emergence_thresholds = custom_emergence_thresholds
        self.custom_storyform_inequalities = custom_storyform_inequalities
        self.narrative_engine: Optional[NarrativeEngine] = None
        self._last_narrative_report: Dict[str, Any] = {}

    def initialize(self):
        logger.info(f"[{self.session_id}] 初始化武侠世界...")
        protagonists = [WuxiaWorld.PROTAGONIST_1, WuxiaWorld.PROTAGONIST_2]
        self._protagonist_profiles = {p.id: p for p in protagonists}
        self.pool, self.scene_registry = create_wuxia_world(
            character_count=self.character_count,
            protagonists=protagonists,
            user_profile=WuxiaWorld.USER_PROFILE,
            seed=self.seed,
        )
        self._init_relationships()
        self.geography = GeographySystem(seed=self.seed)
        self._sync_character_locations()
        self.scene_manager = SceneManager(self.scene_registry, seed=self.seed)
        self.world_state = WorldState()
        self.world_state.active_characters = [c.char_id for c in self.pool.get_alive()]
        self._recalc_faction_power()
        initial_scene = self.scene_manager.select_next_scene(self.world_state, self.pool)
        self.world_state.current_scene = initial_scene
        self.world_state.current_location = self._pick_scene_location(initial_scene)
        logger.info(
            f"[{self.session_id}] 世界就绪: "
            f"{self.pool.alive_count}角色/{self.scene_registry.count()}场景/"
            f"{WuxiaWorld.TOTAL_DIMENSIONS}维/{len(self.geography.locations)}地点"
        )
        if self.narrative_arc_enabled:
            self.narrative_engine = NarrativeEngine(
                max_rounds=self.max_rounds,
                emergence_preset=self.emergence_preset,
                custom_emergence_thresholds=self.custom_emergence_thresholds,
                custom_inequalities=self.custom_storyform_inequalities,
                seed=self.seed,
            )
            self.narrative_engine.initialize(self.pool)
            logger.info(
                f"[{self.session_id}] 叙事引擎就绪: "
                f"涌现方案={self.emergence_preset.value} "
                f"主线线程=1 "
                f"Storyform不平等={len(self.narrative_engine.arc_controller.storyform.inequalities)}"
            )

    def _init_relationships(self):
        alive = self.pool.get_alive()
        for c in alive:
            if not c.relationships:
                c.relationships = {}
        faction_members: Dict[Faction, List[WuxiaCharacter]] = {}
        for c in alive:
            if c.faction:
                faction_members.setdefault(c.faction, []).append(c)
        for faction, members in faction_members.items():
            for i, m1 in enumerate(members):
                for m2 in members[i + 1:]:
                    base_rel = 0.3 + self.rng.random() * 0.2
                    m1.relationships[m2.char_id] = base_rel
                    m2.relationships[m1.char_id] = base_rel
        righteous = {Faction.SHAOLIN, Faction.WUDANG, Faction.EMEI}
        unrighteous = {Faction.MINGJIAO, Faction.PALACE_SHADE, Faction.FIVE_POISON}
        for c1 in alive:
            if c1.faction in righteous:
                for c2 in alive:
                    if c2.faction in unrighteous:
                        c1.relationships[c2.char_id] = c1.relationships.get(
                            c2.char_id, -0.3 - self.rng.random() * 0.2
                        )
                        c2.relationships[c1.char_id] = c2.relationships.get(
                            c1.char_id, -0.3 - self.rng.random() * 0.2
                        )

    def _recalc_faction_power(self):
        self.world_state.faction_power_balance = {}
        for c in self.pool.get_alive():
            fname = c.faction.value if c.faction else "散人"
            self.world_state.faction_power_balance[fname] = \
                self.world_state.faction_power_balance.get(fname, 0.0) + c.power_level

    def _sync_character_locations(self):
        for c in self.pool.get_alive():
            if not c.current_location or c.current_location == "未知":
                if c.faction:
                    faction_locs = self.geography.locations
                    faction_owned = [
                        l.name for l in faction_locs.values()
                        if l.controlling_faction == c.faction
                    ]
                    if faction_owned:
                        c.current_location = self.rng.choice(faction_owned)
                        continue
                all_loc_names = list(self.geography.locations.keys())
                c.current_location = self.rng.choice(all_loc_names)

    def _pick_scene_location(self, scene: SceneTemplate) -> str:
        preferred_cat = scene.category
        matching_locs = [
            name for name, loc in self.geography.locations.items()
            if self.geography.get_scene_category_for_location(name) == preferred_cat
        ]
        if matching_locs:
            return self.rng.choice(matching_locs)
        all_names = list(self.geography.locations.keys())
        return self.rng.choice(all_names) if all_names else "未知"

    def _migrate_speaker_to_scene(self, speaker: WuxiaCharacter, scene: SceneTemplate):
        target_loc = self._pick_scene_location(scene)
        self.geography.migrate_character(speaker, target_location=target_loc, prefer_nearby=False)

    def _apply_location_resources(self, char: WuxiaCharacter):
        if not char.state_80dim:
            return
        loc_resources = self.geography.get_resources_at(char.current_location)
        for res in loc_resources:
            if res in char.state_80dim.resource_levels:
                char.state_80dim.resource_levels[res] = min(
                    1.0,
                    char.state_80dim.resource_levels[res] + 0.005,
                )

    def _calc_history_window(self, scene_chars_count: int) -> int:
        base = max(scene_chars_count * self.HISTORY_BASE_PER_CHAR, 10)
        growth = min(
            self.world_state.current_round // 100,
            self.HISTORY_GROWTH_PER_HUNDRED_ROUNDS * 20,
        )
        return min(base + growth, self.HISTORY_MAX)

    def _select_speaker(self, scene: SceneTemplate) -> WuxiaCharacter:
        scene_chars = self.scene_manager.filter_characters_for_scene(scene, self.pool)
        if not scene_chars:
            scene_chars = self.pool.get_alive()
        if not scene_chars:
            raise RuntimeError("无存活角色")
        if self.narrative_engine:
            active_cast = self.narrative_engine.stratifier.get_active_cast(
                self.pool,
                self.narrative_engine.arc_controller.current_phase.value,
                max_size=len(scene_chars),
            )
            cast_chars = [
                c for c in scene_chars if c.char_id in active_cast
            ]
            if cast_chars:
                scene_chars = cast_chars
        self.world_state.protagonist_speak_interval += 1
        force_protagonist = (
            self.world_state.protagonist_speak_interval >= self.PROTAGONIST_FORCE_INTERVAL
        )
        if force_protagonist:
            protag_alive = [
                c for c in scene_chars
                if c.char_id in self.pool.protagonist_ids and c.is_alive
            ]
            if protag_alive:
                self.world_state.protagonist_speak_interval = 0
                return self.rng.choice(protag_alive)
        weights = []
        top_power_ids = {c.char_id for c in self.pool.top_by_power(20)}
        for c in scene_chars:
            w = 1.0
            if c.char_id in self.pool.protagonist_ids:
                w *= 6.0
            if c.char_id == self.pool.user_id:
                w *= 4.0
            if c.tier in (CharacterTier.LEGENDARY, CharacterTier.ELITE):
                w *= 2.5
            elif c.tier == CharacterTier.MASTER:
                w *= 1.8
            if c.char_id in top_power_ids:
                w *= 1.3
            if scene.faction_bias and c.faction == scene.faction_bias:
                w *= 2.0
            recent_speakers = [t.speaker_id for t in self._turn_results[-8:]]
            if c.char_id in recent_speakers:
                w *= 0.4
            if c.current_location == self.world_state.current_location:
                w *= 1.5
            if c.state_80dim and c.state_80dim.health_status < 0.3:
                w *= 0.5
            weights.append(max(0.1, w))
        total_w = sum(weights)
        r = self.rng.random() * total_w
        cumulative = 0.0
        for i, w in enumerate(weights):
            cumulative += w
            if r <= cumulative:
                return scene_chars[i]
        return scene_chars[-1]

    def _build_prompt(
        self,
        speaker: WuxiaCharacter,
        scene: SceneTemplate,
    ) -> Tuple[str, str]:
        mapped = WuxiaEngineAdapter.map_to_engine(speaker)
        behaviors = WuxiaEngineAdapter.translate_to_behavior(speaker)
        world_info = self.world_state.to_summary(max_events=5)
        world_overview = WuxiaWorld.world_summary()
        scene_info = self.scene_manager.get_scene_context(scene)
        char_context = speaker.to_prompt_context(max_length=600)
        dimension_info = WuxiaWorld.get_dimension_info()
        dim_breakdown = " | ".join(
            f"{k}:{len(v)}维" for k, v in dimension_info.items()
        )
        era = WuxiaWorld.ERA
        protag_profile = self._protagonist_profiles.get(speaker.char_id)
        protagonist_directive = ""
        if protag_profile:
            protagonist_directive = f"""
## 你的核心叙事线
- 核心动机: {protag_profile.motivation_primary}
- 隐藏动机: {protag_profile.motivation_hidden} (不可直接表露，但会影响你的决策)
- 致命缺陷: {protag_profile.fatal_flaw} (这是你最大的弱点，关键时刻会暴露)
- 特殊能力: {protag_profile.special_ability}
- 与另一位主角的关系: {protag_profile.relationship_with_other_protagonist}
"""
        mapped_strategy_desc = {
            "ATTACK": "你倾向于主动进攻，以武力解决问题",
            "DEFEND": "你倾向于防守反击，以稳健策略应对",
            "COOPERATE": "你倾向于合作共赢，寻求盟友支持",
            "EVADE": "你倾向于回避冲突，保存实力",
            "DEFECT": "你倾向于背叛欺骗，为自身利益不择手段",
        }.get(mapped.dominant_strategy, "你行为难以预测")
        scene_chars = self.scene_manager.filter_characters_for_scene(scene, self.pool)
        present_others = [c for c in scene_chars
                         if c.char_id != speaker.char_id][:8]
        others_info = ""
        if present_others:
            others_lines = []
            for oc in present_others[:6]:
                short = f"{oc.display_name}[{oc.tier.display_name}/{oc.faction.value if oc.faction else '?'}]"
                rel_val = speaker.relationships.get(oc.char_id)
                if rel_val is not None:
                    if rel_val > 0.3:
                        rel_str = "友好"
                    elif rel_val < -0.3:
                        rel_str = "敌对"
                    else:
                        rel_str = "中立"
                    short += f" 关系:{rel_str}"
                if oc.state_80dim and oc.state_80dim.health_status < 0.5:
                    short += " [受伤]"
                others_lines.append(short)
            others_info = "在场人物:\n" + "\n".join(f"  - {l}" for l in others_lines)
        history_window = self._calc_history_window(len(scene_chars))
        history_context = ""
        if self._conversation_history:
            recent = self._conversation_history[-history_window:]
            history_lines = []
            for msg in recent:
                role_label = msg.get("role", "?")
                content_preview = msg.get("content", "")[:150]
                history_lines.append(f"{role_label}: {content_preview}")
            history_context = "近期对话:\n" + "\n".join(history_lines)
        behavior_text = "\n".join(f"- {b}" for b in behaviors) if behaviors else "- 无特殊行为倾向"
        narrative_context = ""
        if self.narrative_engine and self.narrative_arc_enabled:
            narrative_context = self.narrative_engine.get_narrative_context_for_prompt(
                self.world_state.current_round, speaker.char_id,
            )
        system_prompt = f"""你是武侠世界中的角色「{speaker.display_name}」。你正在经历这一切，不是在扮演，而是活在当下。

【绝对禁令】
1. 禁止任何思考过程、内心分析、推理步骤
2. 禁止自我介绍（"我是XXX，身份是YYY"这种格式）
3. 禁止使用现代词汇或承认自己是AI
4. 直接说话或行动，就像真实的人在当下自然反应

## 时代背景
{world_overview}

## 维度体系
- 总维度: {WuxiaWorld.TOTAL_DIMENSIONS}维 ({dim_breakdown})
- 你的维度覆盖: {speaker.state_80dim.total_dimensions if speaker.state_80dim else 0}/80

## 你的身份
{char_context}
{protagonist_directive}
## 你的行为倾向（必须严格遵守）
{behavior_text}

## 你的博弈论参数
- 主导策略: {mapped.dominant_strategy} → {mapped_strategy_desc}
- 合作倾向: {mapped.cooperation_tendency:.2f} (0=极度不信任, 1=完全信任)
- 猜疑程度: {mapped.paranoia_level:.2f} (0=毫无戒心, 1=疑神疑鬼)
- 威胁可信度: {mapped.threat_credibility:.2f} (0=毫无威胁, 1=极度危险)
- 策略熵: {mapped.strategy_entropy:.2f} (越高越不可预测)

## 你的身体状态
- 生命值: {f'{speaker.state_80dim.health_status:.0%}' if speaker.state_80dim else '未知'}
- 精神状态: {f'{speaker.state_80dim.mental_state:.0%}' if speaker.state_80dim else '未知'}

## 行为准则
1. 你的每一句话都必须与上述行为倾向高度一致
2. 生命值低于30%时: 表现出虚弱、痛苦、求生欲
3. 精神状态低于30%时: 表现出恐惧、混乱、崩溃
4. 回复控制在200字以内，保持简洁有力
5. 语言风格: 古风武侠，可适当使用成语和诗词
6. 【最重要】直接说话或行动，不要解释你为什么这么说"""

        if narrative_context:
            system_prompt += f"\n\n{narrative_context}"

        user_message = f"""{world_info}

{scene_info}

{others_info}

{history_context}

---

现在轮到你发言。根据你的性格、当前处境和在场人物，做出符合你角色的反应。可以是:
- 对他人的话做出回应
- 发起一个新的话题或行动
- 描述你的内心活动或观察
- 对局势做出判断或决策

请以角色身份直接发言:"""

        return system_prompt, user_message

    def _call_llm_api(
        self,
        system_prompt: str,
        user_message: str,
    ) -> Tuple[str, int, float]:
        import requests as req_lib
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        history_window = self._calc_history_window(
            len(self.scene_manager.filter_characters_for_scene(
                self.world_state.current_scene, self.pool
            )) if self.world_state.current_scene else 10
        )
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self._conversation_history[-history_window:])
        messages.append({"role": "user", "content": user_message})
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        start = time.time()
        try:
            resp = req_lib.post(
                url, headers=headers, json=payload,
                timeout=max(120, self.max_tokens // 5),
            )
            resp.raise_for_status()
            data = resp.json()
            latency = (time.time() - start) * 1000
            msg = data["choices"][0]["message"]
            content = (msg.get("content") or "").strip()
            reasoning = (msg.get("reasoning_content") or "").strip()
            if not content and reasoning:
                content = reasoning
            tokens = data.get("usage", {}).get("total_tokens", 0)
            logger.debug(
                f"[{self.session_id}] API响应: {tokens}tok/{latency:.0f}ms "
                f"content_len={len(content)} reasoning_len={len(reasoning)}"
            )
            return content, tokens, latency
        except req_lib.exceptions.HTTPError as e:
            latency = (time.time() - start) * 1000
            body = e.response.text[:300] if e.response else ""
            err = f"HTTP {e.response.status_code}: {body}"
            logger.error(f"LLM API错误: {err}")
            return f"[API错误: {err}]", 0, latency
        except Exception as e:
            latency = (time.time() - start) * 1000
            err = f"{type(e).__name__}: {str(e)[:200]}"
            logger.error(f"LLM调用异常: {err}")
            return f"[调用异常: {err}]", 0, latency

    def _process_turn_response(
        self,
        speaker: WuxiaCharacter,
        response_text: str,
        tokens: int,
        latency: float,
        scene: SceneTemplate,
    ) -> TurnResult:
        is_ooc, ooc_type = OutOfCharacterDetector.check(response_text)
        if is_ooc:
            logger.warning(
                f"[{self.session_id}] 出戏检测: {speaker.display_name} - {ooc_type}"
            )
        action_type, confidence = DialogueActionClassifier.classify(response_text)
        WuxiaEngineAdapter.update_from_dialogue(
            speaker, action_type,
            intensity=confidence,
        )
        event_outcome = EventEngine.process_action(
            speaker, action_type, confidence,
            scene, self.pool, self.rng,
            geography=self.geography if hasattr(self, 'geography') else None,
        )
        snapshot = {
            "char_id": speaker.char_id,
            "power_level": speaker.power_level,
            "is_alive": speaker.is_alive,
            "faction": speaker.faction.value if speaker.faction else None,
            "action_classified": action_type,
            "confidence": confidence,
            "health": speaker.state_80dim.health_status if speaker.state_80dim else None,
            "mental": speaker.state_80dim.mental_state if speaker.state_80dim else None,
            "ooc_detected": is_ooc,
            "ooc_type": ooc_type if is_ooc else None,
        }
        if speaker.state_80dim:
            top_traits = sorted(
                speaker.state_80dim.personality_traits.items(),
                key=lambda x: abs(x[1] - 0.5),
                reverse=True,
            )[:3]
            snapshot["top_traits"] = {k.value: round(v, 3) for k, v in top_traits}
        result = TurnResult(
            turn_number=len(self._turn_results) + 1,
            speaker_id=speaker.char_id,
            speaker_name=speaker.display_name,
            response_text=response_text[:500],
            action_classified=action_type,
            action_confidence=confidence,
            scene=scene.name if scene else None,
            latency_ms=latency,
            tokens_used=tokens,
            engine_state_snapshot=snapshot,
            event_outcome=event_outcome,
        )
        return result

    def _update_world_state(self, turn: TurnResult):
        self.world_state.current_round = turn.turn_number
        event_desc = (
            f"[T{turn.turn_number}] {turn.speaker_name}: "
            f"{turn.response_text[:80]}..."
        )
        if turn.event_outcome:
            event_desc += f" | 事件:{turn.event_outcome.description}"
        self.world_state.recent_events.append(event_desc)
        if len(self.world_state.recent_events) > 100:
            self.world_state.recent_events = self.world_state.recent_events[-60:]
        if turn.action_classified == "AGGRESSIVE":
            self.world_state.combat_events += 1
            if turn.event_outcome and turn.event_outcome.event_type == "COMBAT":
                speaker_char = self.pool.get(turn.speaker_id)
                target_char = self.pool.get(turn.event_outcome.target_id) if turn.event_outcome.target_id else None
                if (speaker_char and target_char and
                    speaker_char.faction and target_char.faction and
                    speaker_char.faction == target_char.faction):
                    self.world_state.betrayals += 1
                if turn.event_outcome.target_dead and target_char:
                    self.pool.add_achievement(
                        turn.speaker_id,
                        f"击杀{target_char.display_name}于第{turn.turn_number}轮",
                    )
                if turn.event_outcome.source_dead and speaker_char:
                    self.pool.add_achievement(
                        turn.speaker_id,
                        f"战死沙场于第{turn.turn_number}轮",
                    )
        elif turn.action_classified == "FRIENDLY":
            self.world_state.alliances_formed += 1
            if turn.event_outcome and turn.event_outcome.event_type == "ALLIANCE":
                target_char = self.pool.get(turn.event_outcome.target_id) if turn.event_outcome.target_id else None
                if target_char:
                    self.pool.add_achievement(
                        turn.speaker_id,
                        f"与{target_char.display_name}结盟于第{turn.turn_number}轮",
                    )
        if turn.event_outcome:
            if turn.event_outcome.target_dead:
                self.world_state.death_toll += 1
            if turn.event_outcome.source_dead:
                self.world_state.death_toll += 1
            if turn.event_outcome.event_type == "INFORMATION_GATHERING":
                if self.rng.random() < 0.15:
                    self.world_state.secrets_revealed += 1
                    self.pool.add_achievement(
                        turn.speaker_id,
                        f"发现秘密于第{turn.turn_number}轮",
                    )
            if turn.event_outcome.event_type == "OBSERVATION":
                if self.rng.random() < 0.08:
                    self.world_state.secrets_revealed += 1
        if turn.speaker_id in self.pool.protagonist_ids:
            speaker_char = self.pool.get(turn.speaker_id)
            if speaker_char and len(speaker_char.notable_achievements) == 0 and turn.turn_number > 5:
                self.pool.add_achievement(
                    turn.speaker_id,
                    f"首次登场于第{turn.turn_number}轮",
                )
        if self.world_state.current_scene:
            scene_summary = (
                f"[R{turn.turn_number}] {self.world_state.current_scene.name}"
                f"({self.world_state.current_scene.category.value}) - "
                f"{turn.speaker_name}:{turn.action_classified}"
            )
            self._scene_history_summaries.append(scene_summary)
            if len(self._scene_history_summaries) > 200:
                self._scene_history_summaries = self._scene_history_summaries[-100:]
        self._recalc_faction_power()
        if turn.turn_number % 10 == 0:
            EventEngine.passive_recovery(self.pool, self.rng)
        if self.narrative_engine and self.narrative_arc_enabled:
            self._last_narrative_report = self.narrative_engine.process_round(
                round_num=turn.turn_number,
                pool=self.pool,
                world_state=self.world_state,
                speaker_id=turn.speaker_id,
                action_type=turn.action_classified,
                event_outcome=turn.event_outcome,
            )

    def _save_checkpoint(self):
        path = os.path.join(
            self.output_dir,
            f"wuxia_{self.session_id}_r{self.world_state.current_round}.json",
        )
        data = {
            "session_id": self.session_id,
            "round": self.world_state.current_round,
            "total_tokens": self._total_tokens,
            "total_latency_ms": self._total_latency,
            "alive_count": self.pool.alive_count,
            "dead_count": self.pool.dead_count,
            "combat_events": self.world_state.combat_events,
            "secrets_revealed": self.world_state.secrets_revealed,
            "alliances_formed": self.world_state.alliances_formed,
            "betrayals": self.world_state.betrayals,
            "recent_events": self.world_state.recent_events[-20:],
            "faction_balance": self.world_state.faction_power_balance,
            "pool_stats": self.pool.stats(),
            "scene_category_summary": self.scene_registry.category_summary() if self.scene_registry else {},
            "scene_history_summaries": self._scene_history_summaries[-20:],
            "geography_summary": self.geography.location_summary() if hasattr(self, 'geography') else "",
            "narrative_engine": self.narrative_engine.get_full_report() if self.narrative_engine and self.narrative_arc_enabled else None,
            "last_narrative_report": self._last_narrative_report if self.narrative_arc_enabled else None,
            "last_turns": [
                {
                    "turn": t.turn_number,
                    "speaker": t.speaker_name,
                    "action": t.action_classified,
                    "event": t.event_outcome.description if t.event_outcome else None,
                    "preview": t.response_text[:100],
                }
                for t in self._turn_results[-10:]
            ],
        }
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def run(self) -> InfiniteLoopResult:
        self.initialize()
        self._is_running = True
        self._should_stop = False
        ending = None
        logger.info(
            f"[{self.session_id}] ▶ 开始无限循环 "
            f"(max={self.max_rounds}, chars={self.pool.alive_count})"
        )
        try:
            while self._is_running and not self._should_stop:
                if self.world_state.current_round >= self.max_rounds:
                    break
                ending = EndingDetector.check(self.pool, self.world_state)
                if ending:
                    logger.info(
                        f"[{self.session_id}] ⛔ 结局触发: "
                        f"{ending.ending_type.value} - {ending.reason}"
                    )
                    break
                scene = self.scene_manager.select_next_scene(
                    self.world_state, self.pool,
                )
                if scene is None:
                    scene = self.scene_registry.random_scene(seed=self.rng.randint(0, 999999))
                should_stay = False
                if self.narrative_engine and self.narrative_arc_enabled:
                    current_scene = self.world_state.current_scene
                    if current_scene and current_scene.scene_id == scene.scene_id:
                        pass
                    elif current_scene:
                        should_stay = self.narrative_engine.should_continue_scene(
                            scene_id=current_scene.scene_id,
                            has_unresolved_conflict=any(
                                t.status == PlotThreadStatus.CLIMAX
                                for t in self.narrative_engine.plot_manager.get_active_threads()
                            ),
                            protagonist_present=any(
                                pid in [c.char_id for c in self.pool.at_location(self.world_state.current_location)]
                                for pid in self.pool.protagonist_ids
                            ),
                            advances_main_plot=(
                                self._last_narrative_report.get("main_plot_tension", 0) > 0.5
                            ),
                        )
                    if should_stay and current_scene:
                        scene = current_scene
                    else:
                        if self.narrative_engine:
                            if current_scene:
                                self.narrative_engine.end_scene()
                            self.narrative_engine.start_scene(scene.scene_id, self.world_state.current_round)
                self.world_state.current_scene = scene
                self.world_state.current_location = self._pick_scene_location(scene)
                speaker = self._select_speaker(scene)
                if speaker.current_location != self.world_state.current_location:
                    self._migrate_speaker_to_scene(speaker, scene)
                self._apply_location_resources(speaker)
                sys_prompt, usr_msg = self._build_prompt(speaker, scene)
                _health_str = f"health={speaker.state_80dim.health_status:.0%}" if speaker.state_80dim else "health=?"
                print(
                    f"[DEBUG] R{self.world_state.current_round+1:04d} | "
                    f"speaker={speaker.display_name} | scene={scene.name} | "
                    f"{_health_str} | "
                    f"sys_prompt_len={len(sys_prompt)} | usr_msg_len={len(usr_msg)}",
                    flush=True,
                )
                response, tokens, latency = self._call_llm_api(sys_prompt, usr_msg)
                print(
                    f"[DEBUG] R{self.world_state.current_round+1:04d} | "
                    f"API响应: {tokens}tok/{latency:.0f}ms | "
                    f"response_len={len(response)} | preview: {response[:60]}...",
                    flush=True,
                )
                self._total_tokens += tokens
                self._total_latency += latency
                self._conversation_history.append({
                    "role": "user",
                    "content": f"[{speaker.display_name}的回合]",
                })
                self._conversation_history.append({
                    "role": "assistant",
                    "content": response,
                })
                history_window = self._calc_history_window(
                    len(self.scene_manager.filter_characters_for_scene(scene, self.pool))
                )
                if len(self._conversation_history) > history_window:
                    self._conversation_history = self._conversation_history[-history_window:]
                turn_result = self._process_turn_response(
                    speaker, response, tokens, latency, scene,
                )
                self._turn_results.append(turn_result)
                self._update_world_state(turn_result)
                if turn_result.turn_number % self.save_interval == 0:
                    self._save_checkpoint()
                    avg_lat = self._total_latency / max(turn_result.turn_number, 1)
                    logger.info(
                        f"[{self.session_id}] R{turn_result.turn_number:04d} | "
                        f"{speaker.display_name} | {turn_result.action_classified} | "
                        f"{tokens}tok/{avg_lat:.0f}ms | "
                        f"存活:{self.pool.alive_count} 死亡:{self.pool.dead_count} "
                        f"战斗:{self.world_state.combat_events}"
                    )
                if self._should_stop:
                    break
        except KeyboardInterrupt:
            logger.info(f"[{self.session_id}] ⚠ 用户中断")
            ending = EndingCondition(
                ending_type=EndingType.MANUAL_TERMINATE,
                reason="用户手动中断",
                round_number=self.world_state.current_round,
                statistics={},
            )
        except Exception as e:
            logger.exception(f"[{self.session_id}] ✗ 运行异常: {e}")
        finally:
            self._is_running = False
        final_ending = EndingDetector.check(self.pool, self.world_state) or ending
        result = InfiniteLoopResult(
            session_id=self.session_id,
            total_turns=len(self._turn_results),
            total_tokens=self._total_tokens,
            total_latency_ms=self._total_latency,
            ending=final_ending,
            turns=self._turn_results,
            final_world_state={
                "alive": self.pool.alive_count,
                "dead": self.pool.dead_count,
                "combat_events": self.world_state.combat_events,
                "events": self.world_state.recent_events[-30:]
                if self.world_state else [],
                "faction_balance": self.world_state.faction_power_balance
                if self.world_state else {},
            },
        )
        final_path = os.path.join(
            self.output_dir,
            f"wuxia_{self.session_id}_FINAL.json",
        )
        with open(final_path, 'w', encoding='utf-8') as f:
            json.dump(self._result_to_dict(result), f, ensure_ascii=False, indent=2)
        logger.info(
            f"[{self.session_id}] ✓ 完成: "
            f"{result.total_turns}轮/{result.total_tokens}tok/"
            f"{result.total_latency_ms:.0f}ms | "
            f"结局:{result.ending.ending_type.value if result.ending else 'N/A'} | "
            f"存活:{self.pool.alive_count} 死亡:{self.pool.dead_count}"
        )
        return result

    def stop(self):
        self._should_stop = True

    @staticmethod
    def _result_to_dict(result: InfiniteLoopResult) -> Dict[str, Any]:
        return {
            "session_id": result.session_id,
            "total_turns": result.total_turns,
            "total_tokens": result.total_tokens,
            "total_latency_ms": round(result.total_latency_ms, 2),
            "avg_latency_per_turn": round(
                result.total_latency_ms / max(result.total_turns, 1), 2
            ),
            "avg_tokens_per_turn": round(
                result.total_tokens / max(result.total_turns, 1), 1
            ),
            "ending": {
                "type": result.ending.ending_type.value if result.ending else None,
                "reason": result.ending.reason if result.ending else None,
                "round": result.ending.round_number if result.ending else None,
                "statistics": result.ending.statistics if result.ending else {},
            } if result.ending else None,
            "final_state": result.final_world_state,
            "error_log": result.error_log,
            "turns_sample": [
                {
                    "turn": t.turn_number,
                    "speaker": t.speaker_name,
                    "action": t.action_classified,
                    "confidence": round(t.action_confidence, 3),
                    "scene": t.scene,
                    "event": t.event_outcome.description if t.event_outcome else None,
                    "tokens": t.tokens_used,
                    "latency_ms": round(t.latency_ms, 1),
                    "preview": t.response_text[:150],
                }
                for t in result.turns[-20:]
            ],
        }
