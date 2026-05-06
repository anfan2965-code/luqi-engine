"""
武侠战争世界观 — 80维度角色体系 + 阵营系统 + 时代背景

设计原则:
1. 80个维度分为6大域: 武学(12) + 性格(18) + 社交(15) + 战斗(15) + 资源(14) + 内核信念(6)
2. 所有维度可映射到引擎的 BeliefDimension / StrategyAction / ThreatType
3. 142场景覆盖: 门派/江湖/朝堂/边疆/秘境/暗线 6大类
4. 双主角 + AI用户 = 3个特殊角色, 其余597+为程序化生成角色
"""

from __future__ import annotations

import enum
import hashlib
import math
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Tuple


# ============================================================
# 域1: 武学体系 (12维)
# ============================================================

class MartialDomain(Enum):
    """武学领域 — 角色的武学修为分布"""
    INTERNAL_ARTS = "内功"          # 内力修为
    EXTERNAL_ARTS = "外功"          # 招式造诣
    LIGHTNESS_SKILL = "轻功"        # 身法速度
    HIDDEN_WEAPON = "暗器"          # 暗器精通
    MEDICINE = "医术"               # 医毒双修
    FORMATION = "阵法"              # 战阵布设
    SOUND_ART = "音律"              # 音波武功
    POISON_ART = "毒术"             # 用毒之道
    DISGUISE = "易容"               # 易容伪装
    DIVINATION = "占卜"             # 卜筮推演
    CRAFTING = "炼器"              # 兵器炼制
    BEAST_TAMING = "驯兽"           # 驯兽御禽


# ============================================================
# 域2: 性格特质 (18维)
# ============================================================

class PersonalityTrait(Enum):
    """性格特质 — 18维性格空间 (OCEAN扩展模型)"""

    # 大五人格核心 (5)
    OPENNESS = "开放性"            # 对新事物接受度
    CONSCIENTIOUSNESS = "尽责性"    # 责任感与条理性
    EXTRAVERSION = "外向性"         # 社交活跃度
    AGREEABLENESS = "宜人性"        # 合作与顺从
    NEUROTICISM = "神经质"          # 情绪稳定性

    # 武侠特有性格 (13)
    CALMNESS = "冷静"              # 临危不乱
    IMPULSIVENESS = "冲动"          # 行事鲁莽
    CAUTIOUSNESS = "谨慎"           # 三思后行
    BOLDNESS = "胆识"              # 敢于冒险
    KINDNESS = "善良"              # 恻隐之心
    CRUELTY = "残忍"               # 手段狠辣
    UPRIGHTNESS = "正直"           # 光明磊落
    CUNNING = "狡诈"               # 机巧诡谲
    LOYALTY = "忠诚"              # 重信守义
    REBELLION = "叛逆"             # 不服管束
    ARROGANCE = "傲慢"             # 目中无人
    MODESTY = "谦逊"               # 虚怀若谷
    SUSPICIOUSNESS = "多疑"         # 疑心重重
    NAIVETE = "轻信"               # 容易受骗
    PERSISTENCE = "执着"           # 不达目的誓不罢休
    FLEXIBILITY = "随性"           # 随遇而安
    RESILIENCE = "刚毅"            # 百折不挠
    YIELDING = "柔韧"              # 能屈能伸


# ============================================================
# 域3: 社交关系 (15维)
# ============================================================

class SocialDimension(Enum):
    """社交关系维度 — 江湖人际网络"""
    FACTION_LOYALTY = "门派忠诚"     # 对本门的忠诚度
    MENTOR_BOND = "师徒情谊"         # 师徒/师兄弟情分
    JIANGHU_CODE = "江湖道义"        # 江湖规矩遵守度
    GRATITUDE_DEBT = "恩怨纠葛"      # 恩债/仇债
    REPUTATION = "名声"              # 江湖声望
    FACE_VALUE = "面子"              # 面子观念
    RIGHTEOUSNESS = "义气"           # 为朋友两肋插刀
    VENGEANCE_DRIVE = "复仇心"       # 报仇执念
    AMBITION_LEVEL = "野心"          # 权力欲望
    RETREAT_WISH = "隐退意愿"        # 归隐之心
    SUCCESSION_WILL = "传位意愿"     # 掌门/传承意愿
    DISCIPLE_STANDARD = "收徒标准"   # 择徒门槛
    ALLIANCE_TENDENCY = "结盟倾向"   # 联合意愿
    BETRAYAL_THRESHOLD = "背叛阈值"   # 叛变临界点
    INFORMATION_NETWORK = "情报网"    # 消息灵通程度


# ============================================================
# 域4: 战斗风格 (15维)
# ============================================================

class CombatStyle(Enum):
    """战斗风格 — 15维战斗偏好空间"""
    OFFENSIVE = "进攻型"             # 主动出击
    DEFENSIVE = "防守型"             # 稳守反击
    SPEED_FOCUS = "速度型"           # 以快打慢
    POWER_FOCUS = "力量型"           # 力压群雄
    TECHNIQUE_FOCUS = "技巧型"       # 以巧破力
    INTERNAL_FOCUS = "内力型"        # 内功主导
    EXTERNAL_FOCUS = "外放型"        # 外功显威
    MELEE_PREFERENCE = "近战"         # 短兵相接
    RANGE_PREFERENCE = "远程"         # 远程攻击
    GROUP_COMBAT = "群战"            # 以一敌众
    DUEL_PREFERENCE = "单挑"         # 一对一决斗
    ASSASSINATION = "暗杀"           # 偷袭刺杀
    FRONTLINE = "正面"              # 正面对决
    GUERRILLA = "游击"              # 游击骚扰
    WAR_OF_ATTRITION = "消耗"        # 拖延消耗
    QUICK_DECISION = "速决"          # 快战快决


# ============================================================
# 域5: 资源经济 (14维)
# ============================================================

class ResourceType(Enum):
    """资源类型 — 14种江湖资源"""
    SILVER = "银两"                  # 财富
    PILLS = "丹药"                   # 疗伤/提升
    WEAPONS = "兵器"                 # 兵器品质
    MANUALS = "秘籍"                 # 武学典籍
    TERRITORY = "地盘"               # 势力范围
    INTEL = "情报"                   # 消息网络
    CONNECTIONS = "人脉"             # 关系网
    FAME = "声望"                    # 名气大小
    DOMAIN = "势力范围"              # 实控区域
    CITIES = "城池"                  # 控制城池
    PROVISIONS = "粮草"              # 后勤补给
    MOUNTS = "马匹"                  # 坐骑/运输
    TRADE_ROUTES = "商路"            # 商业通道
    MINES = "矿脉"                   # 矿产资源


# ============================================================
# 域6: 内核信念 (映射到引擎BeliefDimension)
# ============================================================

class WuxiaBeliefDimension(Enum):
    """武侠信念维度 — 映射到引擎6维信念系统"""
    COOPERATIVITY = "合作可能"        # → BeliefDimension.COOPERATIVITY
    THREAT_LEVEL = "威胁评估"         # → BeliefDimension.THREAT_LEVEL
    COMPETENCE = "武功评估"           # → BeliefDimension.COMPETENCE
    ALIGNMENT = "正邪判断"            # → BeliefDimension.ALIGNMENT
    HONESTY = "诚信判断"             # → BeliefDimension.HONESTY
    STABILITY = "行为稳定"            # → BeliefDimension.STABILITY


# ============================================================
# 阵营系统
# ============================================================

class Faction(Enum):
    """江湖主要阵营"""
    SHAOLIN = ("少林", "正道领袖", "佛门", "#8B4513")
    WUDANG = ("武当", "道家正统", "道教", "#4169E1")
    EMEI = ("峨眉", "女侠圣地", "佛道融合", "#FF69B4")
    KUNLUN = ("昆仑", "西域霸主", "异域", "#9370DB")
    MINGJIAO = ("明教", "反抗势力", "波斯", "#DC143C")
    BEGgar_SECT = ("丐帮", "天下第一大帮", "底层", "#DAA520")
    PALACE_SHADE = ("日月神教", "魔教总坛", "黑暗", "#2F4F4F")
    FIVE_POISON = ("五毒教", "西南毒宗", "苗疆", "#32CD32")
    TANG_SECT = ("唐门", "蜀中暗器世家", "商业", "#708090")
    IMMORTAL_ISLE = ("侠客岛", "武林至尊", "传说", "#FFD700")

    def __new__(cls, display_name, description, nature, color):
        obj = object.__new__(cls)
        obj._value_ = display_name
        obj.display_name = display_name
        obj.description = description
        obj.nature = nature
        obj.color = color
        return obj


class FactionAlignment(Enum):
    """阵营立场"""
    RIGHTEOUS = "正道"
    NEUTRAL = "中立"
    UNRIGHTEOUS = "邪道"
    CHAOTIC = "混乱"


# ============================================================
# 时代与地理
# ============================================================

@dataclass
class EraSetting:
    """时代背景设定"""
    era_name: str = "乱世纷争·江湖动荡"
    year_number: int = 1370
    dynasty: str = "大明洪武三年"
    political_situation: str = (
        "朝廷初立, 北元残余势力伺机反扑; "
        "江湖各大门派明争暗斗; "
        "海外倭寇蠢蠢欲动; "
        "西域魔教东进中原"
    )
    martial_era_phase: str = "武学鼎盛期"
    legendary_figures_active: bool = True
    secret_manuals_count: int = 47
    forbidden_techniques_known: int = 12


@dataclass
class GeographyPoint:
    """地理位置"""
    name: str
    region_type: str
    coordinates: Tuple[float, float] = (0.0, 0.0)
    controlling_faction: Optional[Faction] = None
    danger_level: float = 0.5
    resources_available: List[ResourceType] = field(default_factory=list)


FACTION_LOCATIONS = {
    Faction.SHAOLIN: ["嵩山少林寺", "少林后山", "达摩洞"],
    Faction.WUDANG: ["武当山金顶", "紫霄宫", "南岩宫"],
    Faction.EMEI: ["峨眉山金顶", "万年寺", "伏虎寺"],
    Faction.KUNLUN: ["昆仑山绝顶", "西域沙漠", "天山峡谷"],
    Faction.MINGJIAO: ["光明顶总坛", "波斯分舵", "中原据点"],
    Faction.BEGgar_SECT: ["丐帮总舵", "洛阳分舵", "江南乞丐窝"],
    Faction.PALACE_SHADE: ["黑木崖", "日月神教密室", "地下暗殿"],
    Faction.FIVE_POISON: ["五毒教总坛", "苗疆万毒谷", "西南密林"],
    Faction.TANG_SECT: ["唐家堡", "蜀中暗器堂", "成都分号"],
    Faction.IMMORTAL_ISLE: ["侠客岛", "赏罚二使驻地", "太白经纬阁"],
}

NEUTRAL_LOCATIONS = [
    "长安城", "洛阳城", "临安府", "大都", "扬州", "苏州",
    "襄阳", "雁门关", "大理", "成都", "开封", "杭州",
    "黄河渡口", "长江三峡", "龙门客栈", "天山雪峰",
]



# ============================================================
# 场景分类 (142场景的基础框架)
# ============================================================

class SceneCategory(Enum):
    """场景大类 — 6类142场景"""
    SECT_INTERNAL = "门派内部"          # ~25场景: 演武/议事/修炼/刑罚/传承
    JIANGHU_ENCOUNTER = "江湖偶遇"      # ~30场景: 茶馆/客栈/古道/渡口/集市
    COURT_POLITICS = "朝堂权谋"         # ~20场景: 金銮殿/军机处/诏狱/边关
    BORDERLAND_WAR = "边疆烽火"         # ~25场景: 战场/军营/城防/斥候/和谈
    SECRET_REALM = "秘境探索"           # ~22场景: 古墓/禁地/洞天/遗迹/机关
    SHADOW_PLOT = "暗线博弈"            # ~20场景: 刺杀/卧底/投毒/离间/反间


REGION_TYPE_MAP = {
    "门派驻地": SceneCategory.SECT_INTERNAL,
    "城镇": SceneCategory.JIANGHU_ENCOUNTER,
    "京城": SceneCategory.COURT_POLITICS,
    "边关": SceneCategory.BORDERLAND_WAR,
    "秘境": SceneCategory.SECRET_REALM,
    "暗处": SceneCategory.SHADOW_PLOT,
}


class GeographySystem:
    """
    地理系统 — 管理所有地点、坐标、阵营控制、资源分布

    核心功能:
    1. 生成完整地理点位(门派驻地+城镇+边关+秘境)
    2. 基于坐标的距离计算和邻近查询
    3. 地点→场景类别映射
    4. 阵营控制区资源可用性查询
    5. 角色位置迁移(基于事件和场景变化)
    """

    def __init__(self, seed: int = 42):
        self.rng = random.Random(seed)
        self.locations: Dict[str, GeographyPoint] = {}
        self._build_all_locations()

    def _build_all_locations(self):
        for faction, loc_names in FACTION_LOCATIONS.items():
            for i, loc_name in enumerate(loc_names):
                base_x = hash(faction.name) % 80 + self.rng.uniform(-10, 10)
                base_y = (hash(faction.name) * 7) % 80 + self.rng.uniform(-10, 10)
                self.locations[loc_name] = GeographyPoint(
                    name=loc_name,
                    region_type="门派驻地",
                    coordinates=(
                        max(0, min(100, base_x + i * 5)),
                        max(0, min(100, base_y + i * 3)),
                    ),
                    controlling_faction=faction,
                    danger_level=0.4 + self.rng.random() * 0.3,
                    resources_available=self._generate_resources_for_faction(faction),
                )
        for loc_name in NEUTRAL_LOCATIONS:
            is_border = any(kw in loc_name for kw in ["关", "渡口", "三峡", "边"])
            is_capital = any(kw in loc_name for kw in ["长安", "洛阳", "临安", "大都", "开封", "杭州"])
            if is_border:
                region_type = "边关"
            elif is_capital:
                region_type = "京城"
            else:
                region_type = "城镇"
            self.locations[loc_name] = GeographyPoint(
                name=loc_name,
                region_type=region_type,
                coordinates=(
                    self.rng.uniform(5, 95),
                    self.rng.uniform(5, 95),
                ),
                controlling_faction=None,
                danger_level=0.2 + self.rng.random() * 0.5,
                resources_available=self._generate_resources_for_region(region_type),
            )
        secret_locations = [
            ("古墓深处", "秘境"), ("剑冢秘地", "秘境"), ("龙脉洞天", "秘境"),
            ("幽冥深渊", "暗处"), ("暗影巷道", "暗处"), ("地下黑市", "暗处"),
        ]
        for loc_name, region_type in secret_locations:
            self.locations[loc_name] = GeographyPoint(
                name=loc_name,
                region_type=region_type,
                coordinates=(
                    self.rng.uniform(10, 90),
                    self.rng.uniform(10, 90),
                ),
                controlling_faction=None,
                danger_level=0.6 + self.rng.random() * 0.3,
                resources_available=self._generate_resources_for_region(region_type),
            )

    def _generate_resources_for_faction(self, faction: Faction) -> List[ResourceType]:
        resources = []
        faction_resources = {
            Faction.SHAOLIN: [ResourceType.PILLS, ResourceType.MANUALS, ResourceType.FAME],
            Faction.WUDANG: [ResourceType.MANUALS, ResourceType.PILLS, ResourceType.TERRITORY],
            Faction.EMEI: [ResourceType.PILLS, ResourceType.WEAPONS, ResourceType.FAME],
            Faction.KUNLUN: [ResourceType.WEAPONS, ResourceType.MOUNTS, ResourceType.MINES],
            Faction.MINGJIAO: [ResourceType.SILVER, ResourceType.WEAPONS, ResourceType.CONNECTIONS],
            Faction.BEGgar_SECT: [ResourceType.INTEL, ResourceType.CONNECTIONS, ResourceType.PROVISIONS],
            Faction.PALACE_SHADE: [ResourceType.INTEL, ResourceType.WEAPONS, ResourceType.SILVER],
            Faction.FIVE_POISON: [ResourceType.PILLS, ResourceType.MINES, ResourceType.DOMAIN],
            Faction.TANG_SECT: [ResourceType.WEAPONS, ResourceType.SILVER, ResourceType.TRADE_ROUTES],
            Faction.IMMORTAL_ISLE: [ResourceType.MANUALS, ResourceType.PILLS, ResourceType.FAME],
        }
        base = faction_resources.get(faction, [])
        resources.extend(base)
        for res in ResourceType:
            if res not in resources and self.rng.random() < 0.15:
                resources.append(res)
        return resources

    def _generate_resources_for_region(self, region_type: str) -> List[ResourceType]:
        resources = []
        region_resources = {
            "城镇": [ResourceType.SILVER, ResourceType.PROVISIONS, ResourceType.CONNECTIONS],
            "京城": [ResourceType.SILVER, ResourceType.FAME, ResourceType.INTEL, ResourceType.CONNECTIONS],
            "边关": [ResourceType.PROVISIONS, ResourceType.MOUNTS, ResourceType.WEAPONS],
            "秘境": [ResourceType.MANUALS, ResourceType.PILLS, ResourceType.MINES],
            "暗处": [ResourceType.INTEL, ResourceType.SILVER, ResourceType.WEAPONS],
        }
        base = region_resources.get(region_type, [ResourceType.SILVER])
        resources.extend(base)
        for res in ResourceType:
            if res not in resources and self.rng.random() < 0.1:
                resources.append(res)
        return resources

    def get_location(self, name: str) -> Optional[GeographyPoint]:
        return self.locations.get(name)

    def get_nearby_locations(self, current_loc: str, distance: float = 15.0) -> List[GeographyPoint]:
        current = self.locations.get(current_loc)
        if not current:
            return []
        nearby = []
        for loc in self.locations.values():
            if loc.name == current_loc:
                continue
            dx = current.coordinates[0] - loc.coordinates[0]
            dy = current.coordinates[1] - loc.coordinates[1]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist <= distance:
                nearby.append(loc)
        nearby.sort(key=lambda l: math.sqrt(
            (current.coordinates[0] - l.coordinates[0]) ** 2 +
            (current.coordinates[1] - l.coordinates[1]) ** 2
        ))
        return nearby

    def get_scene_category_for_location(self, location_name: str) -> SceneCategory:
        loc = self.locations.get(location_name)
        if loc:
            return REGION_TYPE_MAP.get(loc.region_type, SceneCategory.JIANGHU_ENCOUNTER)
        return SceneCategory.JIANGHU_ENCOUNTER

    def get_resources_at(self, location_name: str) -> List[ResourceType]:
        loc = self.locations.get(location_name)
        return loc.resources_available if loc else []

    def get_danger_at(self, location_name: str) -> float:
        loc = self.locations.get(location_name)
        return loc.danger_level if loc else 0.5

    def migrate_character(
        self,
        char: "WuxiaCharacter",
        target_location: Optional[str] = None,
        prefer_nearby: bool = True,
        max_distance: float = 20.0,
    ) -> str:
        if target_location and target_location in self.locations:
            char.current_location = target_location
            return target_location
        if prefer_nearby:
            nearby = self.get_nearby_locations(char.current_location, max_distance)
            if nearby:
                chosen = self.rng.choice(nearby[:5])
                char.current_location = chosen.name
                return chosen.name
        all_names = list(self.locations.keys())
        chosen = self.rng.choice(all_names)
        char.current_location = chosen
        return chosen

    def location_summary(self) -> str:
        lines = [f"地理系统: {len(self.locations)}个地点"]
        by_type: Dict[str, int] = {}
        for loc in self.locations.values():
            by_type[loc.region_type] = by_type.get(loc.region_type, 0) + 1
        for rtype, count in sorted(by_type.items()):
            lines.append(f"  {rtype}: {count}个")
        controlled = sum(1 for l in self.locations.values() if l.controlling_faction)
        lines.append(f"  阵营控制: {controlled}个")
        return "\n".join(lines)


# ============================================================
# 双主角定义
# ============================================================

@dataclass
class ProtagonistProfile:
    """主角配置"""
    id: str
    name: str
    title: str
    faction: Faction
    faction_alignment: FactionAlignment
    base_martial_power: float
    personality_core: Dict[PersonalityTrait, float]
    backstory_summary: str
    motivation_primary: str
    motivation_hidden: str
    fatal_flaw: str
    special_ability: str
    relationship_with_other_protagonist: str = "未知"


# ============================================================
# 用户角色(AI模拟用户)
# ============================================================

@dataclass
class UserProfile:
    """AI模拟的用户角色"""
    id: str = "USER_PLAYER"
    name: str = "无名侠客"
    title: str = "江湖过客"
    faction: Faction = Faction.BEGgar_SECT
    base_martial_power: float = 35.0
    is_user_controlled: bool = True
    initial_personality: Dict[PersonalityTrait, float] = field(default_factory=dict)


# ============================================================
# 80维完整角色状态
# ============================================================

@dataclass
class Character80DimState:
    """
    80维角色完整状态
    
    维度分布:
    - martial_domains: 12 (武学)
    - personality_traits: 18 (性格)
    - social_dims: 15 (社交)
    - combat_styles: 15 (战斗)
    - resource_levels: 14 (资源)
    - belief_dims: 6 (内核信念)
    总计: 80维
    """
    char_id: str = ""
    
    martial_domains: Dict[MartialDomain, float] = field(default_factory=dict)
    personality_traits: Dict[PersonalityTrait, float] = field(default_factory=dict)
    social_dims: Dict[SocialDimension, float] = field(default_factory=dict)
    combat_styles: Dict[CombatStyle, float] = field(default_factory=dict)
    resource_levels: Dict[ResourceType, float] = field(default_factory=dict)
    belief_dims: Dict[WuxiaBeliefDimension, float] = field(default_factory=dict)

    overall_martial_rank: int = 0
    alive: bool = True
    current_location: str = ""
    current_faction: Optional[Faction] = None
    health_status: float = 1.0
    mental_state: float = 1.0

    @property
    def total_dimensions(self) -> int:
        return (
            len(self.martial_domains) +
            len(self.personality_traits) +
            len(self.social_dims) +
            len(self.combat_styles) +
            len(self.resource_levels) +
            len(self.belief_dims)
        )



# ============================================================
# 世界工厂
# ============================================================

class WuxiaWorld:
    """
    武侠世界工厂
    
    负责:
    1. 初始化80维空间
    2. 定义142场景模板
    3. 管理10大阵营
    4. 生成地理点位
    5. 配置双主角
    """

    ERA = EraSetting()
    ALL_FACTIONS = list(Faction)
    ALL_MARTIAL_DOMAINS = list(MartialDomain)
    ALL_PERSONALITY_TRAITS = list(PersonalityTrait)
    ALL_SOCIAL_DIMENSIONS = list(SocialDimension)
    ALL_COMBAT_STYLES = list(CombatStyle)
    ALL_RESOURCE_TYPES = list(ResourceType)
    ALL_BELIEF_DIMENSIONS = list(WuxiaBeliefDimension)
    ALL_SCENE_CATEGORIES = list(SceneCategory)

    TOTAL_DIMENSIONS = (
        len(ALL_MARTIAL_DOMAINS) +
        len(ALL_PERSONALITY_TRAITS) +
        len(ALL_SOCIAL_DIMENSIONS) +
        len(ALL_COMBAT_STYLES) +
        len(ALL_RESOURCE_TYPES) +
        len(ALL_BELIEF_DIMENSIONS)
    )

    PROTAGONIST_1 = ProtagonistProfile(
        id="PROTAGONIST_A",
        name="萧凌风",
        title="断剑浪子",
        faction=Faction.WUDANG,
        faction_alignment=FactionAlignment.RIGHTEOUS,
        base_martial_power=72.0,
        personality_core={
            PersonalityTrait.CALMNESS: 0.85,
            PersonalityTrait.UPRIGHTNESS: 0.90,
            PersonalityTrait.LOYALTY: 0.95,
            PersonalityTrait.SUSPICIOUSNESS: 0.40,
            PersonalityTrait.PERSISTENCE: 0.88,
            PersonalityTrait.REBELLION: 0.30,
            PersonalityTrait.KINDNESS: 0.65,
            PersonalityTrait.ARROGANCE: 0.20,
        },
        backstory_summary=(
            "武当弃徒, 因揭发掌门勾结倭寇而被逐出师门。"
            "手持一把无锋断剑, 行走江湖专打不平。"
            "身负师门绝学《太极残篇》, 却因心魔未解无法突破最后一层。"
            "心中最大的执念是查明父母当年被灭门的真相。"
        ),
        motivation_primary="追寻灭门真相, 洗清师门污名",
        motivation_hidden="内心渴望重建一个真正的正义之门",
        fatal_flaw="过于执着于'正道'二字, 难以接受灰色地带",
        special_ability="剑意化形 — 剑招未出, 杀气已至",
        relationship_with_other_protagonist="亦敌亦友",
    )

    PROTAGONIST_2 = ProtagonistProfile(
        id="PROTAGONIST_B",
        name="夜无痕",
        title="影杀",
        faction=Faction.PALACE_SHADE,
        faction_alignment=FactionAlignment.UNRIGHTEOUS,
        base_martial_power=78.0,
        personality_core={
            PersonalityTrait.CUNNING: 0.92,
            PersonalityTrait.CAUTIOUSNESS: 0.88,
            PersonalityTrait.SUSPICIOUSNESS: 0.85,
            PersonalityTrait.CRUELTY: 0.55,
            PersonalityTrait.LOYALTY: 0.70,
            PersonalityTrait.FLEXIBILITY: 0.82,
            PersonalityTrait.ARROGANCE: 0.45,
            PersonalityTrait.NAIVETE: 0.10,
        },
        backstory_summary=(
            "日月神教右使, 从死人堆里爬出来的幸存者。"
            "幼年全家被所谓'正道'灭门, 被教主收养后训练成顶尖杀手。"
            "擅长易容和暗杀, 江湖上无人见过其真面目。"
            "表面效忠教主, 实则在寻找机会颠覆整个魔教体系。"
        ),
        motivation_primary="颠覆日月神教, 建立新秩序",
        motivation_hidden="渴望被真正认可, 而非恐惧",
        fatal_flaw="不相信任何人, 包括自己",
        special_ability="影遁 — 在光影交错间消失无踪",
        relationship_with_other_protagonist="最危险的对手, 也是唯一理解自己的人",
    )

    USER_PROFILE = UserProfile(
        initial_personality={
            PersonalityTrait.OPENNESS: 0.70,
            PersonalityTrait.BOLDNESS: 0.65,
            PersonalityTrait.KINDNESS: 0.60,
            PersonalityTrait.LOYALTY: 0.75,
            PersonalityTrait.CAUTIOUSNESS: 0.50,
        },
    )

    @classmethod
    def create_default_80dim(cls, char_id: str, seed: Optional[int] = None) -> Character80DimState:
        """创建默认初始化的80维角色状态"""
        rng = random.Random(seed or hash(char_id) % (2**32))

        state = Character80DimState(char_id=char_id)

        for domain in cls.ALL_MARTIAL_DOMAINS:
            state.martial_domains[domain] = rng.random()

        for trait in cls.ALL_PERSONALITY_TRAITS:
            state.personality_traits[trait] = rng.random()

        for dim in cls.ALL_SOCIAL_DIMENSIONS:
            state.social_dims[dim] = rng.uniform(0.2, 0.8)

        for style in cls.ALL_COMBAT_STYLES:
            state.combat_styles[style] = rng.random()

        for res in cls.ALL_RESOURCE_TYPES:
            state.resource_levels[res] = rng.uniform(0.1, 0.9)

        for bel in cls.ALL_BELIEF_DIMENSIONS:
            state.belief_dims[bel] = rng.uniform(0.3, 0.7)

        return state

    @classmethod
    def get_dimension_info(cls) -> Dict[str, List[Tuple[str, int]]]:
        """返回各域的维度列表及数量"""
        return {
            "martial": [(d.value, d.name) for d in cls.ALL_MARTIAL_DOMAINS],
            "personality": [(t.value, t.name) for t in cls.ALL_PERSONALITY_TRAITS],
            "social": [(d.value, d.name) for d in cls.ALL_SOCIAL_DIMENSIONS],
            "combat": [(s.value, s.name) for s in cls.ALL_COMBAT_STYLES],
            "resource": [(r.value, r.name) for r in cls.ALL_RESOURCE_TYPES],
            "belief": [(b.value, b.name) for b in cls.ALL_BELIEF_DIMENSIONS],
        }

    @classmethod
    def world_summary(cls) -> str:
        """生成世界概要文本"""
        lines = [
            f"=== {cls.ERA.era_name} ===",
            f"年代: {cls.ERA.dynasty}({cls.ERA.year_number}年)",
            f"武学阶段: {cls.ERA.martial_era_phase}",
            f"局势: {cls.ERA.political_situation}",
            f"",
            f"维度体系: {cls.TOTAL_DIMENSIONS}维",
            f"  武学{len(cls.ALL_MARTIAL_DOMAINS)} | "
            f"性格{len(cls.ALL_PERSONALITY_TRAITS)} | "
            f"社交{len(cls.ALL_SOCIAL_DIMENSIONS)} | "
            f"战斗{len(cls.ALL_COMBAT_STYLES)} | "
            f"资源{len(cls.ALL_RESOURCE_TYPES)} | "
            f"信念{len(cls.ALL_BELIEF_DIMENSIONS)}",
            f"",
            f"阵营: {len(cls.ALL_FACTIONS)}大门派",
            f"  {' | '.join(f.value for f in cls.ALL_FACTIONS)}",
            f"",
            f"双主角:",
            f"  A: {cls.PROTAGONIST_1.name}({cls.PROTAGONIST_1.title}) - "
            f"{cls.PROTAGONIST_1.faction.value}[{cls.PROTAGONIST_1.faction_alignment.value}]",
            f"  B: {cls.PROTAGONIST_2.name}({cls.PROTAGONIST_2.title}) - "
            f"{cls.PROTAGONIST_2.faction.value}[{cls.PROTAGONIST_2.faction_alignment.value}]",
            f"  用户: {cls.USER_PROFILE.name}({cls.USER_PROFILE.title})",
        ]
        return "\n".join(lines)
