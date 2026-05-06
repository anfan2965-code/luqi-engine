"""
武侠角色池 — 600+程序化生成角色 + 场景模板(142个)

设计原则:
1. 角色按阵营/层级分布, 确保生态平衡
2. 每个角色拥有完整80维状态
3. 142场景覆盖6大类别, 支持动态组合
4. 角色间关系通过关系图自动推导
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, List, Optional, Set, Tuple

from .world import (
    Character80DimState,
    CombatStyle,
    Faction,
    FactionAlignment,
    FACTION_LOCATIONS,
    MartialDomain,
    NEUTRAL_LOCATIONS,
    PersonalityTrait,
    ProtagonistProfile,
    ResourceType,
    SceneCategory,
    SocialDimension,
    WuxiaBeliefDimension,
    WuxiaWorld,
)


# ============================================================
# 角色层级
# ============================================================

class CharacterTier(Enum):
    """角色层级 — 决定初始武力和影响力"""
    LEGENDARY = ("传说级", 90, 100)
    ELITE = ("精英级", 70, 89)
    MASTER = ("高手级", 50, 69)
    SKILLED = ("熟练级", 30, 49)
    NOVICE = ("初学级", 10, 29)
    MORTAL = ("凡人", 1, 9)

    def __new__(cls, display_name, min_power, max_power):
        obj = object.__new__(cls)
        obj._value_ = display_name
        obj.display_name = display_name
        obj.min_power = min_power
        obj.max_power = max_power
        return obj


# ============================================================
# 角色身份类型 (20种)
# ============================================================

class RoleType(Enum):
    SECT_LEADER = "掌门"
    ELDER = "长老"
    CORE_DISCIPLE = "核心弟子"
    OUTER_DISCIPLE = "外门弟子"
    GUARDIAN = "护法"
    ENFORCER = "执法者"
    SPY = "暗探"
    MERCHANT = "商贾"
    HEALER = "医者"
    SCHOLAR = "文人"
    WANDERER = "浪人"
    ASSASSIN = "刺客"
    GENERAL = "将军"
    OFFICIAL = "官员"
    BANDIT = "山贼"
    PIRATE = "水匪"
    MONK = "僧侣"
    NUN = "尼姑"
    TAOIST = "道士"
    HERMIT = "隐士"
    NOMAD = "游牧"


# ============================================================
# 姓名生成器 (确定性+多样性)
# ============================================================

class NameGenerator:
    """程序化姓名生成器"""

    SURNAMES_RAW = (
        "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
        "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳酆鲍史唐"
        "费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄"
        "和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁"
        "杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍"
        "虞万支柯昝管卢莫经房裘缪干解应宗丁宣贲邓郁单杭洪包诸左石崔吉钮龚"
        "程嵇邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓"
        "牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹束龙"
        "叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴夔胥能苍双"
        "闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿通边扈燕冀郏浦尚农"
        "温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘"
        "匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空"
        "曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公仉督晋楚闫法汝鄢"
        "涂钦归海岳帅缑亢况后有琴商牟佘佴伯赏墨哈谯笗年爱阳佟言福南火铁迟"
    )

    GIVEN_MALE_CHARS = (
        "伟强磊军勇峰刚毅俊杰涛明辉鹏飞宇浩然昊天泽远博文武志诚信义忠孝仁德礼智"
        "风云雷电霜雪冰剑影刀锋芒锐啸狂傲孤凌霄寒烟暮晨曦星河月夜梦魂魄血铁骨铮"
        "青松翠竹梅兰菊荷莲芙蓉牡丹芍药海棠樱长空万里千山百川四海九州天地玄黄宇宙"
        "无痕无声无形无名无为无心无念无欲无求天行健地势坤君子自强不息厚德载物"
    )

    GIVEN_FEMALE_CHARS = (
        "婉清雅静娴淑慧敏灵秀英华若兰芷萱蓉月霞云露霜雪冰晶玉珠翠碧瑶琼瑛琳琅"
        "蝶舞凤鸾莺燕鹊鸿雁鹤鹭鸥鹂鹦鹉画眉红粉黛紫青绿蓝白黑金银铜铁玉石珍珠"
        "思忆念怀恋盼望期希愿祈祷祝福庆贺嘉晴雨风云雾霭虹霓霞光星辰日月山河川"
        "柔韧坚强勇敢聪慧善良正直忠诚守信谦虚幽兰空谷幽篁幽泉幽潭幽涧幽壑幽径幽居"
    )

    FACTION_PREFIXES = {
        Faction.SHAOLIN: ["玄", "慧", "空", "悟", "觉", "圆", "妙", "善"],
        Faction.WUDANG: ["清", "虚", "道", "太", "纯", "阳", "真", "灵"],
        Faction.EMEI: ["静", "慈", "普", "圆", "妙", "慧", "定", "明"],
        Faction.KUNLUN: ["昆仑", "天山", "西域", "漠北", "塞外"],
        Faction.MINGJIAO: ["明", "烈", "焰", "圣", "教", "法", "光明"],
        Faction.BEGgar_SECT: ["洪", "帮", "丐", "江湖", "浪", "侠"],
        Faction.PALACE_SHADE: ["影", "夜", "冥", "幽", "暗", "煞", "血"],
        Faction.FIVE_POISON: ["毒", "蛊", "虫", "蛇", "蝎", "蛛", "瘴"],
        Faction.TANG_SECT: ["唐", "蜀", "暗", "机", "弩", "针"],
        Faction.IMMORTAL_ISLE: ["岛主", "使者", "赏罚", "太白"],
    }

    _surname_cache: Optional[List[str]] = None

    @classmethod
    def _get_surnames(cls) -> List[str]:
        if cls._surname_cache is None:
            cls._surname_cache = list(cls.SURNAMES_RAW)
        return cls._surname_cache

    @classmethod
    def generate(
        cls,
        faction: Optional[Faction] = None,
        gender: str = "random",
        seed: int = 0,
        is_monastic: bool = False,
    ) -> Tuple[str, str]:
        rng = random.Random(seed)
        surname = rng.choice(cls._get_surnames())

        actual_gender = gender if gender != "random" else rng.choice(["male", "female"])
        char_pool = cls.GIVEN_MALE_CHARS if actual_gender == "male" else cls.GIVEN_FEMALE_CHARS

        given = "".join(rng.choice(char_pool) for _ in range(rng.randint(1, 2)))

        if is_monastic and faction and faction in cls.FACTION_PREFIXES:
            dharma = rng.choice(cls.FACTION_PREFIXES[faction])
            num = rng.choice("一二三四五六七八九")
            monastic_name = f"{dharma}{given}{num}师"
            return monastic_name, monastic_name

        full_name = f"{surname}{given}"
        courtesy_chars = "子轩逸涵博文哲睿泽辰峻熙翰瑜瑾煜祺皓佑哲"
        courtesy = "".join(rng.choice(courtesy_chars) for _ in range(rng.randint(1, 2)))

        return full_name, courtesy


# ============================================================
# 单个角色定义
# ============================================================

@dataclass
class WuxiaCharacter:
    """单个武侠角色 — 含80维状态"""
    char_id: str
    name: str
    courtesy_name: str = ""
    title: str = ""
    tier: CharacterTier = CharacterTier.SKILLED
    role_type: RoleType = RoleType.WANDERER
    faction: Optional[Faction] = None
    faction_alignment: FactionAlignment = FactionAlignment.NEUTRAL
    gender: str = "unknown"
    age: int = 25
    state_80dim: Optional[Character80DimState] = None
    martial_rank: int = 0
    is_alive: bool = True
    current_location: str = "未知"
    relationships: Dict[str, float] = field(default_factory=dict)
    backstory_seed: str = ""
    notable_achievements: List[str] = field(default_factory=list)

    @property
    def display_name(self) -> str:
        if self.courtesy_name:
            return f"{self.name}(字{self.courtesy_name})" if not self.title else f"{self.name}(字{self.courtesy_name}·{self.title})"
        return f"{self.name}({self.title})" if self.title else self.name

    @property
    def power_level(self) -> float:
        if self.state_80dim:
            total = sum(self.state_80dim.martial_domains.values())
            count = len(self.state_80dim.martial_domains)
            return (total / max(count, 1)) * 100
        return float((self.tier.min_power + self.tier.max_power) / 2)

    def get_faction_color(self) -> str:
        return self.faction.color if self.faction else "#888888"

    def to_prompt_context(self, max_length: int = 800) -> str:
        parts = [
            f"【{self.display_name}】",
        ]
        if self.courtesy_name:
            parts.append(f"表字: {self.courtesy_name}")
        parts.append(f"身份: {self.role_type.value}")
        faction_color = self.get_faction_color()
        faction_str = self.faction.value if self.faction else '散人'
        parts.append(f"阵营: {faction_str}[{self.faction_alignment.value}] 阵营色:{faction_color}")
        parts.append(f"武力等级: {self.tier.display_name}(约{int(self.power_level)})")
        if self.state_80dim:
            dim_count = self.state_80dim.total_dimensions
            parts.append(f"维度覆盖: {dim_count}/80维已激活")
            top_traits = sorted(
                self.state_80dim.personality_traits.items(),
                key=lambda x: abs(x[1] - 0.5),
                reverse=True,
            )[:4]
            parts.append(f"核心性格: {', '.join(f'{k.value}:{v:.2f}' for k, v in top_traits)}")

            top_martial = sorted(
                self.state_80dim.martial_domains.items(),
                key=lambda x: x[1],
                reverse=True,
            )[:3]
            martial_str = ", ".join(k.value for k, v in top_martial if v > 0.6)
            if martial_str:
                parts.append(f"擅长: {martial_str}")

            top_social = sorted(
                self.state_80dim.social_dims.items(),
                key=lambda x: abs(x[1] - 0.5),
                reverse=True,
            )[:2]
            if top_social:
                social_str = ", ".join(f'{k.value}:{v:.2f}' for k, v in top_social)
                parts.append(f"社交特征: {social_str}")
        if self.current_location and self.current_location != "未知":
            parts.append(f"当前位置: {self.current_location}")
        if self.backstory_seed:
            parts.append(f"背景: {self.backstory_seed[:120]}")

        result = "\n".join(parts)
        return result if len(result) <= max_length else result[:max_length - 3] + "..."


# ============================================================
# 角色池管理器 (600+角色)
# ============================================================

class CharacterPool:
    """
    600+角色池
    
    功能:
    - 按阵营/层级分布生成角色
    - 维护索引和状态
    - 支持筛选/查询/生死管理
    - 动态增减
    """

    TIER_DISTRIBUTION = [
        (CharacterTier.LEGENDARY, 0.01),
        (CharacterTier.ELITE, 0.05),
        (CharacterTier.MASTER, 0.15),
        (CharacterTier.SKILLED, 0.30),
        (CharacterTier.NOVICE, 0.34),
        (CharacterTier.MORTAL, 0.15),
    ]

    ALIGNMENT_MAP = {
        Faction.SHAOLIN: FactionAlignment.RIGHTEOUS,
        Faction.WUDANG: FactionAlignment.RIGHTEOUS,
        Faction.EMEI: FactionAlignment.RIGHTEOUS,
        Faction.KUNLUN: FactionAlignment.NEUTRAL,
        Faction.MINGJIAO: FactionAlignment.UNRIGHTEOUS,
        Faction.PALACE_SHADE: FactionAlignment.CHAOTIC,
        Faction.FIVE_POISON: FactionAlignment.UNRIGHTEOUS,
        Faction.TANG_SECT: FactionAlignment.NEUTRAL,
        Faction.IMMORTAL_ISLE: FactionAlignment.CHAOTIC,
        Faction.BEGgar_SECT: FactionAlignment.NEUTRAL,
    }

    BACKSTORY_TEMPLATES = [
        "自幼在{faction}长大, 见惯了刀光剑影。",
        "本是普通人, 因一场变故踏入江湖, 从此身不由己。",
        "出身名门, 却因家族恩怨流落江湖, 苦练武艺以求自保。",
        "曾是某大门派弃徒, 怀揣秘籍独自行走天下。",
        "来历不明, 江湖上无人知晓其真实身份和过往。",
        "本想远离江湖纷争, 却总被卷入是非之中。",
    ]

    def __init__(
        self,
        target_count: int = 620,
        protagonists: Optional[List[ProtagonistProfile]] = None,
        user_profile=None,
        seed: int = 42,
    ):
        self.target_count = target_count
        self.seed = seed
        self.rng = random.Random(seed)
        self._characters: Dict[str, WuxiaCharacter] = {}
        self._protagonist_ids: Set[str] = set()
        self._user_id: Optional[str] = None
        self._death_count = 0

        self._init_specials(protagonists, user_profile)
        self._generate_bulk(target_count)

    def _init_specials(self, protagonists, user_profile):
        """初始化主角和用户"""
        if protagonists:
            for idx, proto in enumerate(protagonists):
                char = self._build_protagonist(proto, idx)
                self._characters[char.char_id] = char
                self._protagonist_ids.add(char.char_id)

        if user_profile:
            from .world import UserProfile
            up = user_profile if isinstance(user_profile, UserProfile) else UserProfile()
            state = WuxiaWorld.create_default_80dim(up.id, seed=hash(up.id))
            state.martial_domains[MartialDomain.INTERNAL_ARTS] = up.base_martial_power / 100
            state.current_faction = up.faction
            state.overall_martial_rank = int(up.base_martial_power)

            uc = WuxiaCharacter(
                char_id=up.id, name=up.name, title=up.title,
                tier=CharacterTier.MASTER, role_type=RoleType.WANDERER,
                faction=up.faction, gender="unknown", age=22,
                state_80dim=state, martial_rank=int(up.base_martial_power),
            )
            self._characters[up.id] = uc
            self._user_id = up.id

    def _build_protagonist(self, proto: ProtagonistProfile, index: int) -> WuxiaCharacter:
        state = WuxiaWorld.create_default_80dim(proto.id, seed=hash(proto.id))
        for trait, val in proto.personality_core.items():
            if trait in state.personality_traits:
                state.personality_traits[trait] = val
        hp = proto.base_martial_power / 100
        for d in [MartialDomain.INTERNAL_ARTS, MartialDomain.EXTERNAL_ARTS]:
            if d in state.martial_domains:
                state.martial_domains[d] = min(hp, 0.95)
        state.belief_dims[WuxiaBeliefDimension.COOPERATIVITY] = 0.35
        state.current_faction = proto.faction
        state.overall_martial_rank = int(proto.base_martial_power)

        tier = CharacterTier.LEGENDARY if proto.base_martial_power >= 85 else CharacterTier.ELITE
        roles = [RoleType.SECT_LEADER, RoleType.ASSASSIN]

        return WuxiaCharacter(
            char_id=proto.id, name=proto.name, title=proto.title,
            tier=tier, role_type=roles[min(index, len(roles) - 1)],
            faction=proto.faction, faction_alignment=proto.faction_alignment,
            gender="男" if index == 0 else "未知", age=28 + index * 2,
            state_80dim=state, martial_rank=int(proto.base_martial_power),
            backstory_seed=proto.backstory_summary,
        )

    def _generate_bulk(self, target_count: int):
        special_n = len(self._characters)
        remaining = max(0, target_count - special_n)
        for i in range(remaining):
            tier = self._weighted_pick(self.TIER_DISTRIBUTION, self.rng.random())
            faction = self._pick_faction(i, remaining)
            char = self._gen_one(i + special_n, tier, faction, self.seed + i * 7919)
            self._characters[char.char_id] = char

    @staticmethod
    def _weighted_pick(weighted: List[Tuple[Any, float]], rv: float) -> Any:
        cum = 0.0
        for item, w in weighted:
            cum += w
            if rv < cum:
                return item
        return weighted[-1][0]

    def _pick_faction(self, index: int, total: int) -> Optional[Faction]:
        all_f = list(Faction)
        base = index % len(all_f)
        spread = (index * 7 + self.seed) % total
        if spread < total * 0.25:
            return None
        return all_f[base]

    def _gen_one(
        self, index: int, tier: CharacterTier,
        faction: Optional[Faction], seed: int,
    ) -> WuxiaCharacter:
        rng = random.Random(seed)
        cid = f"C_{index:04d}"
        is_mono = faction in (Faction.SHAOLIN, Faction.WUDANG, Faction.EMEI)
        name, courtesy = NameGenerator.generate(
            faction=faction, seed=seed, is_monastic=is_mono,
        )
        role = rng.choice(list(RoleType))
        align = self.ALIGNMENT_MAP.get(faction, FactionAlignment.NEUTRAL)

        state = WuxiaWorld.create_default_80dim(cid, seed=seed)
        pr = (tier.min_power + rng.random() * (tier.max_power - tier.min_power)) / 100
        for d in state.martial_domains:
            state.martial_domains[d] = max(0.05, pr + rng.gauss(0, 0.15))

        dominant = rng.sample(list(PersonalityTrait), min(4, len(PersonalityTrait)))
        for dt in dominant:
            state.personality_traits[dt] = min(0.95, max(0.05, rng.gauss(0.7, 0.15)))

        state.current_faction = faction
        state.overall_martial_rank = int(tier.min_power + rng.random() * (tier.max_power - tier.min_power))
        loc_pool = FACTION_LOCATIONS.get(faction, NEUTRAL_LOCATIONS)
        backstory = rng.choice(self.BACKSTORY_TEMPLATES).format(
            faction=faction.value if faction else "江湖",
        )

        return WuxiaCharacter(
            char_id=cid, name=name, courtesy_name=courtesy,
            tier=tier, role_type=role, faction=faction,
            faction_alignment=align, gender=rng.choice(["男", "女"]),
            age=max(16, int(rng.gauss(30, 10))),
            state_80dim=state, martial_rank=state.overall_martial_rank,
            current_location=rng.choice(loc_pool), backstory_seed=backstory,
        )

    # ---- 查询接口 ----

    @property
    def all_characters(self) -> List[WuxiaCharacter]:
        return list(self._characters.values())

    @property
    def alive_count(self) -> int:
        return sum(1 for c in self._characters.values() if c.is_alive)

    @property
    def dead_count(self) -> int:
        return sum(1 for c in self._characters.values() if not c.is_alive)

    @property
    def protagonist_ids(self) -> Set[str]:
        return set(self._protagonist_ids)

    @property
    def user_id(self) -> Optional[str]:
        return self._user_id

    def get(self, char_id: str) -> Optional[WuxiaCharacter]:
        return self._characters.get(char_id)

    def get_alive(self) -> List[WuxiaCharacter]:
        return [c for c in self._characters.values() if c.is_alive]

    def by_faction(self, faction: Faction) -> List[WuxiaCharacter]:
        return [c for c in self._characters.values()
                if c.faction == faction and c.is_alive]

    def by_tier(self, tier: CharacterTier) -> List[WuxiaCharacter]:
        return [c for c in self._characters.values()
                if c.tier == tier and c.is_alive]

    def at_location(self, loc: str) -> List[WuxiaCharacter]:
        return [c for c in self._characters.values()
                if c.current_location == loc and c.is_alive]

    def top_by_power(self, n: int = 10) -> List[WuxiaCharacter]:
        return sorted(self.get_alive(), key=lambda c: c.power_level, reverse=True)[:n]

    def mark_dead(self, char_id: str):
        c = self._characters.get(char_id)
        if c:
            c.is_alive = False
            self._death_count += 1

    def add_achievement(self, char_id: str, achievement: str):
        c = self._characters.get(char_id)
        if c:
            c.notable_achievements.append(achievement)
            if c.state_80dim:
                c.state_80dim.social_dims[SocialDimension.REPUTATION] = min(
                    1.0, c.state_80dim.social_dims.get(SocialDimension.REPUTATION, 0.5) + 0.05
                )

    def stats(self) -> Dict[str, Any]:
        alive = self.get_alive()
        fc: Dict[str, int] = {}
        tc: Dict[str, int] = {}
        for c in alive:
            fn = c.faction.value if c.faction else "散人"
            fc[fn] = fc.get(fn, 0) + 1
            tn = c.tier.display_name
            tc[tn] = tc.get(tn, 0) + 1
        return {
            "total": len(self._characters),
            "alive": len(alive),
            "dead": self._death_count,
            "special": len(self._protagonist_ids) + (1 if self._user_id else 0),
            "factions": fc,
            "tiers": tc,
            "avg_power": round(sum(c.power_level for c in alive) / max(len(alive), 1), 1),
        }


# ============================================================
# 142场景系统
# ============================================================

@dataclass
class SceneTemplate:
    scene_id: str
    name: str
    category: SceneCategory
    description: str
    danger_level: float
    possible_actions: List[str]
    required_tiers: List[CharacterTier]
    faction_bias: Optional[Faction] = None
    atmosphere_keywords: List[str] = field(default_factory=list)


class SceneRegistry:
    """142场景注册表 — 6大类"""

    _scenes: List[SceneTemplate] = []
    _initialized = False

    @classmethod
    def ensure_init(cls):
        if cls._initialized:
            return
        cls._initialized = True
        cls._build_all()

    @classmethod
    def _add(cls, **kw):
        cls._scenes.append(SceneTemplate(**kw))

    @classmethod
    def _build_all(cls):
        cls._build_sect_internal(25)
        cls._build_jianghu_encounter(30)
        cls._build_court_politics(20)
        cls._build_borderland_war(25)
        cls._build_secret_realm(22)
        cls._build_shadow_plot(20)

    @classmethod
    def _make_scenes(cls, prefix: str, cat: SceneCategory, danger: float, data: list):
        for sid, name, desc, actions, tiers, fb, kw in data:
            cls._add(
                scene_id=sid, name=name, description=desc,
                possible_actions=actions, required_tiers=tiers,
                faction_bias=fb, atmosphere_keywords=kw,
                category=cat, danger_level=danger,
            )

    @classmethod
    def _build_sect_internal(cls, n: int):
        cat = SceneCategory.SECT_INTERNAL
        base = dict(category=cat, danger_level=0.3)
        data = [
            ("S001","演武场比试","门内弟子切磋武艺",["挑战","观战","暗中出手"],[CharacterTier.NOVICE,CharacterTier.SKILLED],None,["汗水","兵器碰撞"]),
            ("S002","议事大厅","掌门召集核心成员商议大事",["发言","反对","附议","沉默"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["严肃","低语"]),
            ("S003","藏经阁","门派典籍存放地",["借阅","偷看","抄录","守护"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["书香","寂静"]),
            ("S004","禁地入口","闯入者死罪",["尝试进入","守卫","举报"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["阴冷","警告牌"]),
            ("S005","刑罚堂","处置违规弟子",["受审","辩护","求情","执行"],[CharacterTier.SKILLED,CharacterTier.ELITE],None,["刑具","威压"]),
            ("S006","后山修炼地","闭关突破之所",["闭关","打扰","守护","窥探"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["鸟鸣","流水"]),
            ("S007","炼丹房","炼制丹药",["炼丹","偷药","学习","破坏"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["药香","火焰"]),
            ("S008","兵器库","存放兵器和暗器",["领取","偷取","检查","设防"],[CharacterTier.ELITE],None,["金属光泽","寒气"]),
            ("S009","传功堂","长老传授绝学",["听讲","提问","演示","记录"],[CharacterTier.NOVICE,CharacterTier.SKILLED],None,["教导声","恭敬"]),
            ("S010","药园","种植珍稀药材",["采药","照料","看守","盗取"],[CharacterTier.SKILLED],None,["草药香","虫鸣"]),
            ("S011","祖师堂","供奉历代祖师",["祭拜","忏悔","立誓","发现秘密"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["檀香","庄严"]),
            ("S012","膳食堂","弟子日常用餐",["用餐","交谈","打探消息","下毒"],[CharacterTier.NOVICE,CharacterTier.SKILLED],None,["饭菜香","嘈杂"]),
            ("S013","客房","接待外宾或伤员",["休息","监视","潜入","会面"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["整洁","安静"]),
            ("S014","校场操练","大规模集合训练",["参与","指挥","观察","捣乱"],[CharacterTier.NOVICE,CharacterTier.SKILLED],None,["号令声","整齐步伐"]),
            ("S015","密室","极少数人知道的存在",["发现","探索","封锁","利用"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["黑暗","机关"]),
            ("S016","钟鼓楼","报时与警报之处",["撞钟","登楼","观望","破坏"],[CharacterTier.SKILLED],None,["钟声","风声"]),
            ("S017","洗剑池","清洗兵器之池",["洗剑","感悟","比试","投剑"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["清水","倒影"]),
            ("S018","碑林","刻有武学心得的石碑群",["观摩","拓印","领悟","破坏"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["石碑","苔藓"]),
            ("S019","水牢","关押重犯的地牢",["被囚","提审","越狱","看守"],[CharacterTier.SKILLED,CharacterTier.ELITE],None,["潮湿","滴水声"]),
            ("S020","观星台","观测星象推算吉凶",["观星","占卜","讨论","独处"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["星空","寒风"]),
            ("S021","练功房","个人专属修炼空间",["苦修","突破","被打扰","指导他人"],list(CharacterTier),None,["汗味","专注"]),
            ("S022","外门驻地","外门弟子居住区",["生活","结交","竞争","离开"],[CharacterTier.NOVICE,CharacterTier.SKILLED],None,["简陋","喧闹"]),
            ("S023","内门区域","核心弟子活动范围",["进出","训练","会议","任务分配"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["肃静","高级建筑"]),
            ("S024","山门","门派正门守卫森严",["出入","守门","挑战","迎接"],list(CharacterTier),None,["石阶","匾额"]),
            ("S025","后厨","准备食物的后勤区",["帮忙","偷吃","打听消息","下毒"],[CharacterTier.NOVICE,CharacterTier.MORTAL],None,["烟火气","忙碌"]),
        ]
        keys = ["scene_id","name","description","possible_actions","required_tiers","faction_bias","atmosphere_keywords"]
        for row in data:
            cls._add(category=cat, danger_level=0.3, **dict(zip(keys, row)))

    @classmethod
    def _build_jianghu_encounter(cls, n: int):
        cat = SceneCategory.JIANGHU_ENCOUNTER
        data = [
            ("J001","荒野客栈","偏僻路上落脚点三教九流汇聚",["入住","打尖","打听","埋伏"],list(CharacterTier),None,["灯火","酒香"]),
            ("J002","茶馆","市井消息集散地",["喝茶","听书","搭讪","斗殴"],list(CharacterTier),None,["茶香","说书声"]),
            ("J003","古道驿站","官道上休息站",["歇脚","换马","遇袭","护送"],list(CharacterTier),None,["马粪味","官差"]),
            ("J004","渡口","江河渡口南北要道",["渡江","拦截","追踪","逃脱"],list(CharacterTier),None,["水声","雾气"]),
            ("J005","集市","热闹贸易场所",["购物","卖艺","寻人","混入人群"],list(CharacterTier),None,["叫卖声","拥挤"]),
            ("J006","破庙","避雨过夜废弃庙宇",["躲雨","遭遇","休息","发现"],list(CharacterTier),None,["漏雨","蛛网"]),
            ("J007","竹林","隐蔽天然战场",["穿行","埋伏","追击","疗伤"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["竹叶","光影"]),
            ("J008","悬崖边","险要地形决斗好去处",["对峙","跳崖","救援","逼问"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["呼啸风声","深渊"]),
            ("J009","酒楼","江湖人士聚集饮酒之地",["喝酒","拼酒","听闻消息","闹事"],[CharacterTier.SKILLED,CharacterTier.ELITE],None,["酒气","豪迈笑声"]),
            ("J010","赌坊","三教九流出没赌博场所",["参赌","出千","讨债","砸场"],[CharacterTier.SKILLED],None,["骰子声","紧张"]),
            ("J011","青楼","情报交换销金窟",["寻欢","打听","保护","刺杀"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["脂粉香","丝竹声"]),
            ("J012","当铺","销赃典当物品之所",["典当","赎回","识别赃物","盘问"],list(CharacterTier),None,["柜台高耸","算盘声"]),
            ("J013","药铺","购买药材治疗伤势",["买药","治伤","辨认毒药","套话"],list(CharacterTier),None,["中药味","坐堂大夫"]),
            ("J014","铁匠铺","打造修理兵器",["铸剑","修理","定制","鉴定"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["敲击声","火花"]),
            ("J015","书院","文人雅士聚集可能藏有秘籍",["读书","访友","搜寻秘籍","辩论"],list(CharacterTier),None,["读书声","墨香"]),
            ("J016","戏台","热闹表演场所易混迹",["看戏","表演","跟踪","动手"],list(CharacterTier),None,["锣鼓声","化妆间"]),
            ("J017","桥上","狭窄通道易冲突",["过桥","拦路","决斗","跳河"],list(CharacterTier),None,["流水","对峙"]),
            ("J018","树林深处","适合伏击秘密会面",["埋伏","会面","逃亡","搜索"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["树影","鸟惊飞"]),
            ("J019","温泉","意外相遇疗伤之所",["泡汤","偶遇","疗伤","偷袭"],list(CharacterTier),None,["热气腾腾","放松"]),
            ("J020","瀑布旁","壮观景色下战场",["观赏","练功","决斗","隐藏"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["轰鸣水声","水雾"]),
            ("J021","乱葬岗","阴森之地可能藏秘密",["经过","寻找","挖掘","遭遇"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["腐臭","乌鸦"]),
            ("J022","码头","水路交通枢纽",["登船","候船","走私","追捕"],list(CharacterTier),None,["汽笛","货物"]),
            ("J023","山间小路","偏僻山路易遇劫匪",["行走","被劫","反击","绕道"],list(CharacterTier),None,["崎岖","林木"]),
            ("J024","雪地","恶劣天气遭遇战",["跋涉","追踪","战斗","躲避"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["白雪","寒冷"]),
            ("J025","沙漠","缺水环境生存考验",["穿越","迷路","遭遇沙匪","发现绿洲"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["烈日","黄沙"]),
            ("J026","沼泽","危险地形易陷落",["穿越","被困","施救","设陷阱"],[CharacterTier.SKILLED],None,["泥泞","蚊虫"]),
            ("J027","废墟","古代遗迹可能藏宝或危险",["探索","发掘","遭遇守卫","发现线索"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["断壁残垣","神秘"]),
            ("J028","花海","美丽但可能有毒区域",["穿行","中毒","采摘","隐藏"],list(CharacterTier),None,["花香","色彩斑斓"]),
            ("J029","悬崖洞穴","隐蔽藏身处",["藏身","发现","疗伤","囚禁"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["阴暗","回声"]),
            ("J030","风雨亭","路边凉亭经典遭遇点",["避雨","偶遇","歇脚","留字"],list(CharacterTier),None,["雨声","石桌"]),
        ]
        for row in data:
            keys = ["scene_id","name","description","possible_actions","required_tiers","faction_bias","atmosphere_keywords"]
            d = dict(zip(keys, row))
            cls._add(category=cat, danger_level=0.5, **d)

    @classmethod
    def _build_court_politics(cls, n: int):
        cat = SceneCategory.COURT_POLITICS
        data = [
            ("C001","金銮殿","皇帝召见群臣最高殿堂",["觐见","奏报","弹劾","跪拜"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["龙椅","威严"]),
            ("C002","军机处","军事决策中枢",["汇报","献策","调兵","密谋"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["地图","军报"]),
            ("C003","诏狱","关押政治犯特别监狱",["被囚","审讯","营救","拷问"],[CharacterTier.SKILLED,CharacterTier.ELITE],None,["阴暗","刑具"]),
            ("C004","边关","军事前线指挥部",["驻守","迎敌","求援","撤退"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["烽火","战鼓"]),
            ("C005","御书房","皇帝批阅奏折私密空间",["呈递","密谈","偷听","闯入"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["墨香","烛光"]),
            ("C006","东厂提督府","特务机构总部",["汇报","领命","调查","被调查"],[CharacterTier.ELITE],None,["绣春刀","恐惧"]),
            ("C007","六部衙门","中央政府各部门办公地",["办事","疏通","告状","查阅档案"],[CharacterTier.SKILLED,CharacterTier.ELITE],None,["公文","官印"]),
            ("C008","王府","藩王私人宅邸",["拜访","赴宴","密谋","试探"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["奢华","侍卫"]),
            ("C009","科举考场","选拔人才场所",["参考","监考","作弊","阅卷"],[CharacterTier.SKILLED],None,["号舍","墨臭"]),
            ("C010","国子监","最高学府",["求学","讲学","辩论","藏书"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["书声","古朴"]),
            ("C011","钦天监","观测天象制定历法机构",["观测","预报","进谏","伪造天象"],[CharacterTier.ELITE],None,["仪器","星图"]),
            ("C012","鸿胪寺","外交礼仪机构",["接待外使","翻译","宴会","刺探"],[CharacterTier.SKILLED,CharacterTier.ELITE],None,["多语言","礼服"]),
            ("C013","大理寺","最高司法审判机构",["审理","上诉","复核","翻案"],[CharacterTier.ELITE],None,["法槌","卷宗"]),
            ("C014","翰林院","储备人才编撰史书机构",["编撰","修史","起草诏书","议论时政"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["笔墨","古籍"]),
            ("C015","锦衣卫指挥使司","皇家特务组织",["执行任务","汇报","监视","反侦察"],[CharacterTier.ELITE],None,["飞鱼服","冷酷"]),
            ("C016","户部银库","国家财政重地",["盘点","贪污","巡查","失窃"],[CharacterTier.ELITE],None,["白银","账簿"]),
            ("C017","兵部武库","军队武器装备库",["领取","检查","盗窃","守护"],[CharacterTier.ELITE],None,["盔甲","森严"]),
            ("C018","礼部贡院","举行重大典礼场所",["参加典礼","筹备","观礼","捣乱"],[CharacterTier.SKILLED,CharacterTier.ELITE],None,["隆重","乐队"]),
            ("C019","工部营造司","负责建筑工程部门",["监督工程","验收","贪腐","设计"],[CharacterTier.SKILLED,CharacterTier.ELITE],None,["图纸","工匠"]),
            ("C020","内阁值房","大学士们办公地方",["票拟","商议","传旨","密议"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["文房四宝","权力"]),
        ]
        for row in data:
            keys = ["scene_id","name","description","possible_actions","required_tiers","faction_bias","atmosphere_keywords"]
            d = dict(zip(keys, row))
            cls._add(category=cat, danger_level=0.7, **d)

    @classmethod
    def _build_borderland_war(cls, n: int):
        cat = SceneCategory.BORDERLAND_WAR
        data = [
            ("B001","两军阵前","正式开战战场",["冲锋","指挥","投降","突围"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["喊杀声","鲜血"]),
            ("B002","中军大帐","主帅指挥中心",["议事","献策","传达命令","刺杀"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["地图","烛光"]),
            ("B003","城墙之上","防守方最后防线",["守城","督战","救援","弃城"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["箭矢如雨","惨叫"]),
            ("B004","斥候营地","侦察兵前哨站",["侦查","回报","被捕","传递情报"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["伪装","警惕"]),
            ("B005","粮草大营","后勤补给基地",["押运","守护","烧毁","抢夺"],[CharacterTier.SKILLED],None,["粮袋","炊烟"]),
            ("B006","野战医院","救治伤员临时营地",["治疗","护送伤员","混入","窃药品"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["呻吟","血腥味"]),
            ("B007","谈判帐篷","双方停战协商之地",["谈判","威胁","签约","撕毁协议"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["紧张","文书"]),
            ("B008","峡谷伏击点","易守难攻地理优势位置",["设伏","中伏","突围","反包围"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["狭窄","峭壁"]),
            ("B009","渡口战场","江河上争夺战",["夺船","水战","断桥","追击"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["水花四溅","混乱"]),
            ("B010","夜袭营地","夜间突袭目标",["突袭","预警","防守","放火"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["火光","惊慌"]),
            ("B011","骑兵冲锋阵地","骑兵作战主战场",["骑射","冲锋","阻击","设拒马"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["马蹄声","尘土"]),
            ("B012","攻城器械阵地","投石车攻城锤操作区",["操作","破坏","防守","修复"],[CharacterTier.SKILLED],None,["巨响","碎石"]),
            ("B013","后方补给线","运输物资要道",["护送","劫掠","设卡","绕道"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["车队","警戒"]),
            ("B014","战俘营","关押俘虏地方",["被俘","看守","策划越狱","审讯"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["栅栏","绝望"]),
            ("B015","烽火台","传递军情信号塔",["点火","守台","传递信号","摧毁"],[CharacterTier.SKILLED],None,["狼烟","高处"]),
            ("B016","战地祭坛","战前誓师或战后祭祀",["誓师","祭祀","鼓舞士气","破坏"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["香火","庄重"]),
            ("B017","伤兵收容所","大量伤员集中地",["救助","寻找亲人","统计伤亡","传播瘟疫"],[CharacterTier.SKILLED],None,["哀嚎","死亡气息"]),
            ("B018","间谍交接点","情报人员秘密会面处",["交接情报","跟踪","逮捕","反跟踪"],[CharacterTier.ELITE],None,["隐蔽","快速"]),
            ("B019","战略要隘","控制全局关键地理位置",["占据","争夺","防守","放弃"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["险要","决定性"]),
            ("B020","溃败后撤退路线","战败方逃生之路",["撤退","追击","掩护","断后"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["混乱","恐慌"]),
            ("B021","休战区","双方暂时停火缓冲地带",["休整","交换俘虏","互市","暗中准备"],[CharacterTier.SKILLED,CharacterTier.MASTER],None,["相对平静","警惕"]),
            ("B022","水军港口","水上力量基地",["造船","训练","出海","防御"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["船只","海风"]),
            ("B023","山地要塞","依山而建坚固堡垒",["驻守","围攻","坚守","投降"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["石墙","居高临下"]),
            ("B024","草原战场","广阔平原骑兵对决",["骑战","迂回","包围","追击"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["辽阔","马群"]),
            ("B025","雪地战场","极端天气下战争",["冒雪作战","冻伤","利用天气","等待时机"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["暴风雪","白色"]),
        ]
        for row in data:
            keys = ["scene_id","name","description","possible_actions","required_tiers","faction_bias","atmosphere_keywords"]
            d = dict(zip(keys, row))
            cls._add(category=cat, danger_level=0.8, **d)

    @classmethod
    def _build_secret_realm(cls, n: int):
        cat = SceneCategory.SECRET_REALM
        data = [
            ("R001","古墓入口","传说中的古代墓葬入口",["进入","勘察","设陷阱","守候"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["阴冷","石刻"]),
            ("R002","地下迷宫","错综复杂地下通道",["探索","迷路","找出口","遭遇机关"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["黑暗","回声"]),
            ("R003","洞天福地","蕴含灵气的仙境",["修炼","发现","争夺","守护"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["灵气充沛","祥和"]),
            ("R004","上古遗迹","远古文明留下的废墟",["考古","获取遗物","触发陷阱","解读文字"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["古老","神秘符号"]),
            ("R005","机关密室","布满精密机关的房间",["破解","触发","被困","找到宝藏"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["齿轮声","暗箭"]),
            ("R006","毒瘴山谷","充满毒气的危险地带",["穿越","中毒","寻找解药","利用毒障"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["彩色雾气","枯骨"]),
            ("R007","冰洞","终年不化的冰穴",["探索","发现冰封之物","寒冷考验","冰壁雕刻"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["蓝色光芒","极寒"]),
            ("R008","熔岩地带","地下熔岩流动的危险区域",["穿越","利用热度修炼","躲避岩浆","发现矿脉"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["红色光芒","高温"]),
            ("R009","幻境","制造幻觉的神秘空间",["陷入幻觉","识破幻象","利用幻境","被困"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["扭曲现实","困惑"]),
            ("R010","藏宝密室","隐藏珍贵物品的秘密房间",["发现","开启","守护","争夺"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["金银珠宝","机关锁"]),
            ("R011","剑冢","埋藏名剑的圣地",["拔剑","试剑","领悟剑意","剑灵显现"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["剑气","无数剑柄"]),
            ("R012","药王谷","生长珍稀药材的山谷",["采集","发现新药","遇到守护兽","中毒"],[CharacterTier.MASTER,CharacterTier.ELITE],None,["异香","宁静"]),
            ("R013","武林禁地","被各大门派共同封印的区域",["试图进入","被封印者召唤","封印松动","重新封印"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["强大封印","能量波动"]),
            ("R014","海底宫殿","水下遗迹或龙宫",["潜水探索","水中战斗","发现宝物","氧气耗尽"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["蓝色水域","压力"]),
            ("R015","天空之城","悬浮在空中的古城",["飞行到达","探索","发现飞行术","坠落风险"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["云端","俯瞰大地"]),
            ("R016","时间裂隙","时间流速异常的空间",["进入","时间加速减速","看到过去未来","逃离"],[CharacterTier.LEGENDARY],None,["时间扭曲","头痛"]),
            ("R017","镜像世界","与现实相反的平行空间",["穿越","遇见镜像自己","寻找回归方法","真假难辨"],[CharacterTier.LEGENDARY],None,["左右颠倒","不安"]),
            ("R018","灵魂空间","精神意识可以进入的特殊领域",["入定","心灵对话","面对心魔","获得顿悟"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["虚无","内心投影"]),
            ("R019","元素之心","五行元素的源头所在",["吸收元素之力","元素化身","元素失控","平衡恢复"],[CharacterTier.LEGENDARY],None,["纯粹元素","巨大能量"]),
            ("R020","传承之地","接受前辈传承的场所",["接受传承","测试资格","传承失败","获得绝学"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["前辈残魂","知识洪流"]),
            ("R021","封魔之地","镇压妖魔的地点",["加固封印","魔气泄露","被魔侵染","释放消灭"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["黑色气息","诱惑"]),
            ("R022","轮回之境","涉及生死轮回的神秘之地",["见证轮回","改变命运","代价巨大","不可逆"],[CharacterTier.LEGENDARY],None,["生死界限模糊","抉择"]),
        ]
        for row in data:
            keys = ["scene_id","name","description","possible_actions","required_tiers","faction_bias","atmosphere_keywords"]
            d = dict(zip(keys, row))
            cls._add(category=cat, danger_level=0.75, **d)

    @classmethod
    def _build_shadow_plot(cls, n: int):
        cat = SceneCategory.SHADOW_PLOT
        data = [
            ("P001","深夜刺杀","目标人物就寝时的暗杀行动",["潜入","刺杀","被发现","逃脱"],[CharacterTier.ELITE],None,["月光","利刃出鞘"]),
            ("P002","毒酒宴席","在宴会上下毒的机会",["下毒","识破","替死","调查"],[CharacterTier.ELITE],None,["美酒佳肴","暗流涌动"]),
            ("P003","离间计实施","挑拨两个势力关系的行动",["散布谣言","伪造证据","被发现","成功离间"],[CharacterTier.ELITE],None,["谎言","信任崩塌"]),
            ("P004","卧底暴露","卧底身份即将被发现的危机时刻",["掩饰","灭口","逃跑","反将一军"],[CharacterTier.ELITE],None,["质问目光","心跳加速"]),
            ("P005","反间计","识破敌方间谍并反向利用",["发现间谍","假意信任","传递假情报","最终揭发"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["心理博弈","戏剧性反转"]),
            ("P006","投毒水源","对敌方水源进行投毒",["投放","被发现","解毒","报复"],[CharacterTier.ELITE],None,["无色无味","潜伏期"]),
            ("P007","绑架要挟","绑架重要人物进行要挟",["绑架","看守","营救","交换"],[CharacterTier.ELITE],None,["蒙眼","捆绑"]),
            ("P008","伪造书信","伪造重要文书嫁祸他人",["伪造","送达","被识破","成功嫁祸"],[CharacterTier.ELITE],None,["笔迹模仿","精心布局"]),
            ("P009","美人计","利用美色接近目标的计划",["接近","获取情报","动真情","暴露"],[CharacterTier.ELITE],None,["魅力","危险游戏"]),
            ("P010","连环计","多个阴谋环环相扣的复杂计划",["布局第一步","推进","出现变数","调整应对"],[CharacterTier.LEGENDARY],None,["复杂","牵一发动全身"]),
            ("P011","暗杀名单","包含多名目标清除计划的清单",["执行","保护目标","泄露名单","名单本身是诱饵"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["名字划掉","紧迫"]),
            ("P012","叛徒审判","对被抓捕叛徒的公开审判",["指控","辩护","行刑","劫法场"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["愤怒"," crowd情绪"]),
            ("P013","密谋聚会","多方势力秘密协商的大场面",["参会","监听","破坏","达成交易"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["面具","利益交换"]),
            ("P014","真相揭露","一个惊天秘密即将公之于众",["揭露","掩盖","利用真相","承受后果"],[CharacterTier.LEGENDARY],None,["震撼","连锁反应"]),
            ("P015","最后一击","针对最大对手的终极行动",["准备","执行","失败代价","成功后的空虚"],[CharacterTier.LEGENDARY],None,["毕生心血","命运转折"]),
            ("P016","双重身份","一个人拥有两个对立身份的困境",["维持伪装","濒临暴露","选择一方","两边都不选"],[CharacterTier.ELITE,CharacterTier.LEGENDARY],None,["分裂","无法回头"]),
            ("P017","棋局博弈","以整个江湖为棋盘的宏大布局",["落子","对方应对","意外变数","终局"],[CharacterTier.LEGENDARY],None,["棋子即人命","冷酷"]),
            ("P018","血脉秘密","关于主角身世的惊天秘密",["发现","验证","接受否认","利用"],[CharacterTier.LEGENDARY],None,["家族","血仇"]),
            ("P019","终极对决","正邪双方的最终决战",["集结","决战前夜","开战","结局"],[CharacterTier.LEGENDARY],None,["史诗感","命运交汇"]),
            ("P020","新的开始","一切结束后的重建时刻",["重建秩序","隐退","传承","新的威胁萌芽"],[CharacterTier.LEGENDARY],None,["和平曙光","希望"]),
        ]
        for row in data:
            keys = ["scene_id","name","description","possible_actions","required_tiers","faction_bias","atmosphere_keywords"]
            d = dict(zip(keys, row))
            cls._add(category=cat, danger_level=0.85, **d)

    # ---- 查询接口 ----

    @classmethod
    def all_scenes(cls) -> List[SceneTemplate]:
        cls.ensure_init()
        return list(cls._scenes)

    @classmethod
    def by_category(cls, cat: SceneCategory) -> List[SceneTemplate]:
        return [s for s in cls.all_scenes() if s.category == cat]

    @classmethod
    def by_danger(cls, lo: float, hi: float) -> List[SceneTemplate]:
        return [s for s in cls.all_scenes() if lo <= s.danger_level <= hi]

    @classmethod
    def random_scene(cls, seed: int = 0) -> SceneTemplate:
        return random.Random(seed).choice(cls.all_scenes())

    @classmethod
    def count(cls) -> int:
        return len(cls.all_scenes())

    @classmethod
    def category_summary(cls) -> Dict[str, int]:
        out: Dict[str, int] = {}
        for s in cls.all_scenes():
            out[s.category.value] = out.get(s.category.value, 0) + 1
        return out


# ============================================================
# 工厂函数
# ============================================================

def create_wuxia_world(
    character_count: int = 620,
    protagonists: Optional[List[ProtagonistProfile]] = None,
    user_profile=None,
    seed: int = 42,
) -> Tuple[CharacterPool, SceneRegistry]:
    """创建完整的武侠世界"""
    pool = CharacterPool(
        target_count=character_count,
        protagonists=protagonists,
        user_profile=user_profile,
        seed=seed,
    )
    registry = SceneRegistry()
    registry.ensure_init()
    return pool, registry
