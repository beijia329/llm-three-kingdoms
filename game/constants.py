"""游戏常量与配置定义

本文件包含游戏中所有常量配置，包括：
- 游戏规则参数
- 经济系统参数
- 军事系统参数
- 战斗系统参数
- 将领系统参数
- 城市等级配置
- 地图配置

所有参数均参考 docs/design/data-models.md 和 docs/design/battle-system.md。
数值调整请通过 balance testing 验证。
"""

from typing import Dict, Any

# ============================================================
# 游戏规则
# ============================================================

MAX_TURNS: int = 192
"""最大回合数，192回合达到后游戏结束（184年黄巾-232年三国鼎立，每季度1回合）"""

NUM_FACTIONS: int = 12
"""势力数量（184年剧本，12方诸侯）"""

STARTING_CITIES_PER_FACTION: int = 0
"""每方初始城市数（不固定，按实际历史分配）"""

TOTAL_CITIES: int = 22
"""地图上总城市数"""

OVERTIME_EXTRA_SOLDIERS: int = 500
"""加时赛每回合自动增兵数"""

# ============================================================
# 势力定义
# ============================================================

FACTIONS: Dict[str, str] = {
    "han":        "汉室",
    "zhangjiao":  "张角",
    "dongzhuo":   "董卓",
    "yuanshao":   "袁绍",
    "caocao":     "曹操",
    "liubei":     "刘备",
    "sunjian":    "孙坚",
    "liubiao":    "刘表",
    "liuyan":     "刘焉",
    "gongsunzan": "公孙瓒",
    "mateng":     "马腾",
    "yuanshu":    "袁术",
}

FACTION_COLORS: Dict[str, str] = {
    "han":        "#FFD700",  # 金色 - 汉室正统
    "zhangjiao":  "#FFFF00",  # 明黄 - 黄巾"苍天已死，黄天当立"
    "dongzhuo":   "#8B0000",  # 深红 - 西凉铁骑
    "yuanshao":   "#FF6600",  # 橙色 - 袁绍
    "caocao":     "#0055A4",  # 蓝色 - 曹操
    "liubei":     "#00AA55",  # 绿色 - 刘备
    "sunjian":    "#CC0000",  # 红色 - 孙坚
    "liubiao":    "#8B4513",  # 棕色 - 刘表
    "liuyan":     "#9370DB",  # 紫色 - 刘焉
    "gongsunzan": "#FFFFFF",  # 白色 - 公孙瓒
    "mateng":     "#4B0082",  # 靛蓝 - 马腾
    "yuanshu":    "#FF1493",  # 粉红 - 袁术
    "neutral":    "#888888",  # 灰色（中立）
}

# ============================================================
# 城市等级配置
# ============================================================

CITY_LEVELS: Dict[int, Dict[str, Any]] = {
    1: {
        "name": "小城",
        "base_gold": 50,
        "base_food": 80,
        "max_population": 10000,
        "wall_hp": 500,
        "initial_gold": 200,
        "initial_food": 300,
        "initial_population": 5000,
        "initial_morale": 70,
        "initial_garrison": 500,
    },
    2: {
        "name": "中城",
        "base_gold": 100,
        "base_food": 150,
        "max_population": 30000,
        "wall_hp": 1000,
        "initial_gold": 400,
        "initial_food": 600,
        "initial_population": 15000,
        "initial_morale": 70,
        "initial_garrison": 1000,
    },
    3: {
        "name": "大城",
        "base_gold": 200,
        "base_food": 250,
        "max_population": 60000,
        "wall_hp": 2000,
        "initial_gold": 800,
        "initial_food": 1000,
        "initial_population": 30000,
        "initial_morale": 70,
        "initial_garrison": 2000,
    },
    4: {
        "name": "重镇",
        "base_gold": 350,
        "base_food": 400,
        "max_population": 100000,
        "wall_hp": 3500,
        "initial_gold": 1500,
        "initial_food": 1800,
        "initial_population": 60000,
        "initial_morale": 70,
        "initial_garrison": 3500,
    },
    5: {
        "name": "都城",
        "base_gold": 500,
        "base_food": 500,
        "max_population": 150000,
        "wall_hp": 5000,
        "initial_gold": 2500,
        "initial_food": 2500,
        "initial_population": 100000,
        "initial_morale": 70,
        "initial_garrison": 5000,
    },
}

# ============================================================
# 经济系统参数
# ============================================================

GOLD_PER_POPULATION: float = 0.01
"""每人每回合产金系数"""

FOOD_PER_POPULATION: float = 0.015
"""每人每回合产粮系数"""

MORALE_GOLD_PENALTY: float = 0.005
"""每低落1点民心，产出减少0.5%"""

MORALE_FOOD_PENALTY: float = 0.005
"""每低落1点民心，产粮减少0.5%"""

MORALE_BONUS_THRESHOLD: int = 80
"""民心高于此值获得产出加成"""

MORALE_BONUS_RATE: float = 0.01
"""超过80民心后，每点额外增加1%产出"""

MIN_MORALE_FOR_PRODUCTION: int = 10
"""民心低于此值时，产出为0（死亡螺旋触发点）"""

POPULATION_GROWTH_BASE: float = 0.02
"""基础人口增长率（每回合2%）"""

POPULATION_GROWTH_MORALE_FACTOR: float = 0.0005
"""民心对人口增长的加成系数"""

MAX_POPULATION_GROWTH_RATE: float = 0.05
"""最大人口增长率上限"""

# ============================================================
# 军事系统参数
# ============================================================

RECRUIT_COST_GOLD: int = 1
"""每个士兵征兵消耗金钱（降低以加速扩军）"""

RECRUIT_COST_FOOD: int = 2
"""每个士兵征兵消耗粮草"""

GARRISON_FOOD_COST_PER_SOLDIER: float = 0.05
"""每个守军每回合消耗粮草（降低）"""

ARMY_FOOD_COST_PER_SOLDIER: float = 0.15
"""每个出征士兵每回合消耗粮草"""

ARMY_MARCH_SPEED: int = 4
"""每回合行军基础速度"""

# ============================================================
# 战斗系统参数
# ============================================================

# --- 围城参数 ---
WALL_DAMAGE_BASE: int = 400
"""围城每回合对城墙的基础伤害"""

WALL_DAMAGE_FORCE_MULTIPLIER_CAP: float = 4.0
"""兵力系数上限（攻击方兵力/守军）"""

COMMAND_ATTACK_BONUS_RATE: float = 0.01
"""每点统帅增加1%攻击力"""

# --- 巷战参数 ---
BASE_DAMAGE_RATE: float = 0.1
"""每回合基础伤亡比例（10%当前兵力）"""

# [主系统修复实验 2026-10-01] 0.3 → 0.1：原 +30% 巷战防御加成使守方胜率高达 72%、
# 攻方仅 ~11-17%，攻城几乎打不下、战争不决定地图。先只改这一个变量做对照。
DEFENDER_WALL_BONUS: float = 0.1
"""守城方获得+10%防御加成"""

MORALE_COMBAT_BONUS_RATE: float = 0.01
"""每点士气增加1%战斗力"""

# --- 士气参数 ---
MORALE_LOSS_PER_10_PERCENT_CASUALTY: int = 5
"""每损失10%兵力，士气-5"""

MORALE_GAIN_PER_10_PERCENT_KILL: int = 3
"""每击杀敌方10%兵力，士气+3"""

MORALE_LOSS_GENERAL_DEATH: int = 15
"""将领阵亡，士气-15"""

MORALE_LOSS_NO_FOOD: int = 10
"""断粮每回合士气-10"""

MORALE_BOOST_OUTNUMBERED: int = 10
"""以少胜多士气+10"""

MORALE_LOSS_BESIEGED: int = 3
"""城市被围每回合士气-3"""

MORALE_LOSS_SURROUNDED: int = 8
"""被包围士气-8"""

# --- 士气效果阈值 ---
MORALE_ELITE_THRESHOLD: int = 90
"""士气>=90：死战不退"""

MORALE_HIGH_THRESHOLD: int = 70
"""士气>=70：正常"""

MORALE_NORMAL_THRESHOLD: int = 50
"""士气>=50：正常"""

MORALE_LOW_THRESHOLD: int = 30
"""士气>=30：有概率逃跑"""

MORALE_CRITICAL_THRESHOLD: int = 20
"""士气>=20：高概率溃散"""

MORALE_BREAK_THRESHOLD: int = 20
"""士气低于此值开始溃散"""

ROUT_LOSS_RATE: float = 0.1
"""溃散后每回合损失10%兵力"""

# --- 战斗上限 ---
# [主系统修复实验 2026-10-01] 10 → 30：与守方加成下调配合，让势均力敌的战斗能收口，
# 否则大量攻城以 DRAW 结束（见 tests/ 诊断）。二者需同时作用。
MAX_BATTLE_ROUNDS: int = 30
"""最大战斗回合数，超过则平局"""

# ============================================================
# 将领系统参数
# ============================================================

LOYALTY_DECAY_PER_TURN: float = 0.5
"""每回合忠诚自然衰减"""

REWARD_LOYALTY_BONUS_PER_100_GOLD: int = 5
"""每赏赐100金增加忠诚度"""

MAX_LOYALTY_FROM_REWARD: int = 100
"""赏赐最大忠诚度上限"""

CAPTURE_SURRENDER_BASE_CHANCE: float = 0.30
"""被俘后投降基础概率30%"""

CAPTURE_SURRENDER_LOYALTY_FACTOR: float = 0.01
"""每点忠诚度降低1%投降概率"""

EXPLORE_BASE_CHANCE: float = 0.20
"""探索发现新将领基础概率20%"""

EXPLORE_MORALE_FACTOR: float = 0.002
"""每点民心增加0.2%探索概率"""

EXPLORE_COOLDOWN_TURNS: int = 3
"""探索冷却回合数"""

# --- 忠诚度阈值 ---
LOYALTY_DEVOTED_THRESHOLD: int = 90
""">=90：死忠，不可能投降"""

LOYALTY_LOYAL_THRESHOLD: int = 70
""">=70：忠诚，很难投降"""

LOYALTY_NORMAL_THRESHOLD: int = 50
""">=50：一般，有概率投降"""

LOYALTY_UNSTABLE_THRESHOLD: int = 30
""">=30：不稳，容易投降"""

# --- 忠诚度效果 ---
LOYALTY_COMBAT_BONUS_DEVOTED: float = 0.10
"""死忠战斗力+10%"""

LOYALTY_COMBAT_PENALTY_UNSTABLE: float = -0.10
"""不稳战斗力-10%"""

LOYALTY_COMBAT_PENALTY_DANGEROUS: float = -0.20
"""危险战斗力-20%"""

# ============================================================
# 将领属性参数
# ============================================================

COMMAND_COMBAT_BONUS_RATE: float = 0.01
"""每点统帅增加1%战斗力"""

POLITICS_PRODUCTION_BONUS_RATE: float = 0.005
"""每点政治增加0.5%资源产出"""

BRAVERY_CRITICAL_CHANCE_RATE: float = 0.005
"""每点勇武增加0.5%暴击率"""

INTELLIGENCE_STRATEGY_SUCCESS_RATE: float = 0.00667
"""每点智力增加0.667%计谋成功率"""

GENERAL_ATTRIBUTE_MIN: int = 1
"""将领属性最小值"""

GENERAL_ATTRIBUTE_MAX: int = 100
"""将领属性最大值"""

# ============================================================
# 外交系统参数
# ============================================================

MAX_MESSAGES_PER_TURN: int = 1
"""每回合最大外交消息数"""

RUMOR_LOYALTY_DECREASE: int = 5
"""成功散布流言降低忠诚度"""

RUMOR_BASE_SUCCESS_RATE: float = 0.50
"""流言基础成功率50%"""

RUMOR_INTELLIGENCE_FACTOR: float = 0.005
"""每点智力增加0.5%流言成功率"""

# 外交关系参数
DIPLOMACY_TRUST_MAX: int = 100
"""信任度上限"""

DIPLOMACY_TRUST_MIN: int = 0
"""信任度下限"""

DIPLOMACY_TRUST_ALLIANCE_FORM: int = 10
"""接受同盟时信任度变化"""

DIPLOMACY_TRUST_ALLIANCE_PROPOSE: int = 5
"""提出同盟时信任度变化"""

DIPLOMACY_TRUST_ALLIANCE_REJECT: int = -5
"""拒绝同盟时信任度变化"""

DIPLOMACY_TRUST_DECLARE_WAR: int = -30
"""宣战时信任度变化"""

DIPLOMACY_TRUST_BREAK_ALLIANCE: int = -50
"""破坏同盟时信任度变化"""

DIPLOMACY_TRUST_CAPTURE_CITY: int = -20
"""占领城市时信任度变化"""

DIPLOMACY_TRUST_MESSAGE_POSITIVE: int = 2
"""积极消息信任度变化"""

DIPLOMACY_ALLIANCE_DURATION: int = 12
"""同盟默认持续回合数（12回合=3年）"""

DIPLOMACY_ALLIANCE_COMBAT_BONUS: float = 0.10
"""同盟共同对敌战斗力加成10%"""

DIPLOMACY_TRUCE_DURATION: int = 6
"""停战默认持续回合数"""

# ============================================================
# 地图参数
# ============================================================

MAP_WIDTH: int = 800
"""地图渲染宽度（像素）"""

MAP_HEIGHT: int = 600
"""地图渲染高度（像素）"""

CITY_RENDER_RADIUS: int = 20
"""城市渲染半径（像素）"""

MIN_DISTANCE_BETWEEN_CITIES: int = 60
"""城市间最小渲染距离（像素）"""

# ============================================================
# 游戏初始状态
# ============================================================

INITIAL_GOLD: int = 1000
"""每个势力初始总金钱"""

INITIAL_FOOD: int = 1500
"""每个势力初始总粮草"""

INITIAL_GENERALS_PER_FACTION: int = 3
"""每个势力初始将领数"""

# ============================================================
# 开发与调试参数
# ============================================================

DEBUG_MODE: bool = False
"""调试模式开关"""

LOG_LEVEL: str = "INFO"
"""日志级别: DEBUG/INFO/WARNING/ERROR"""

AI_THINKING_TIMEOUT_SECONDS: int = 30
"""LLM思考超时秒数"""

AI_MAX_RETRIES: int = 3
"""LLM失败最大重试次数"""

# ============================================================
# 六角格地图
# ============================================================

HEX_SIZE: int = 32
"""六角格边长（像素）"""

HEX_MAP_WIDTH: int = 200
"""六角格地图宽度（格子数）"""

HEX_MAP_HEIGHT: int = 120
"""六角格地图高度（格子数）"""

# ============================================================
# 地形参数
# ============================================================

TERRAIN_MOVE_COST: Dict[str, float] = {
    "grass": 1.0,
    "grassland": 1.0,
    "plain": 1.0,
    "forest": 1.5,
    "dense_forest": 2.0,
    "hill": 2.0,
    "mountain": float("inf"),
    # 🔴 peak 于 2026-10-03 由 inf 改为 3.0（v3.1 平衡修复，P0）
    # 这是 A* 寻路真正使用的权表 —— 改 game/tile.py 的 is_passable() 不生效，
    # 因为 find_path 走的是 terrain_move_cost() → 本表。两处必须同步改。
    # 原为 inf 导致 31 城 465 城对中 114 对（24.5%）永久不可达，
    # 刘备(白帝)/刘焉(成都) 被完全孤立，北海/临淄两座中立城无人能到。
    # 山脉(mountain)继续保持 inf 作为天然屏障，仅放开山峰。
    "peak": 3.0,
    "desert": 1.5,
    "marsh": 2.5,
    "tundra": 1.5,
    "snow": 2.0,
    "water": float("inf"),
    "deep_water": float("inf"),
    "river": 2.0,
}
"""地形移动消耗倍数"""

TERRAIN_DEFENSE_BONUS: Dict[str, float] = {
    "grass": 0.0,
    "grassland": -0.05,
    "plain": 0.0,
    "forest": 0.10,
    "dense_forest": 0.20,
    "hill": 0.20,
    "mountain": 0.40,
    "peak": 0.50,
    "desert": -0.10,
    "marsh": 0.05,
    "tundra": -0.05,
    "snow": -0.10,
    "water": 0.0,
    "deep_water": 0.0,
    "river": 0.0,
}
"""地形防御加成率（0.10 = +10%）"""

# 基础产出：仅金钱/粮草/人口
TERRAIN_YIELDS: Dict[str, Dict[str, float]] = {
    "grass": {"gold": 0.5, "food": 3.0, "pop": 1.5},
    "grassland": {"gold": 0.0, "food": 2.5, "pop": 1.0},
    "plain": {"gold": 0.0, "food": 3.0, "pop": 1.0},
    "forest": {"gold": 0.0, "food": 1.5, "pop": 0.5},
    "dense_forest": {"gold": 0.0, "food": 2.0, "pop": 0.3},
    "hill": {"gold": 1.5, "food": 0.5, "pop": 0.3},
    "mountain": {"gold": 1.0, "food": 0.0, "pop": 0.0},
    "peak": {"gold": 0.5, "food": 0.0, "pop": 0.0},
    "desert": {"gold": 0.0, "food": 0.2, "pop": 0.1},
    "marsh": {"gold": 0.0, "food": 1.5, "pop": 0.3},
    "tundra": {"gold": 0.0, "food": 0.5, "pop": 0.2},
    "snow": {"gold": 0.0, "food": 0.0, "pop": 0.0},
    "water": {"gold": 0.5, "food": 1.0, "pop": 0.0},
    "deep_water": {"gold": 0.0, "food": 0.5, "pop": 0.0},
    "river": {"gold": 0.5, "food": 2.0, "pop": 0.5},
}
"""地形基础产出（每格每回合）"""

# 参考 FreeCiv struct terrain property[MG_COUNT] 设计
# 4 个生成权重属性，控制地图生成时的分布
# altitude: "deep" | "low" | "mid" | "high" | "peak"
# temperature: "tropical" | "temperate" | "cold" | "frozen"
# humidity: "wet" | "normal" | "dry"
# vegetation: "none" | "sparse" | "dense"
TERRAIN_PROPERTIES: Dict[str, Dict[str, str]] = {
    "grass":        {"altitude": "low",   "temperature": "temperate", "humidity": "wet",    "vegetation": "dense"},
    "grassland":    {"altitude": "low",   "temperature": "temperate", "humidity": "normal", "vegetation": "sparse"},
    "plain":        {"altitude": "low",   "temperature": "temperate", "humidity": "normal", "vegetation": "none"},
    "forest":       {"altitude": "low",   "temperature": "temperate", "humidity": "wet",    "vegetation": "dense"},
    "dense_forest": {"altitude": "low",   "temperature": "tropical",  "humidity": "wet",    "vegetation": "dense"},
    "hill":         {"altitude": "mid",   "temperature": "temperate", "humidity": "normal", "vegetation": "sparse"},
    "mountain":     {"altitude": "high",  "temperature": "temperate", "humidity": "dry",    "vegetation": "none"},
    "peak":         {"altitude": "peak",  "temperature": "cold",      "humidity": "dry",    "vegetation": "none"},
    "desert":       {"altitude": "low",   "temperature": "tropical",  "humidity": "dry",    "vegetation": "none"},
    "marsh":        {"altitude": "low",   "temperature": "temperate", "humidity": "wet",    "vegetation": "dense"},
    "tundra":       {"altitude": "low",   "temperature": "cold",      "humidity": "normal", "vegetation": "sparse"},
    "snow":         {"altitude": "mid",   "temperature": "frozen",    "humidity": "normal", "vegetation": "none"},
    "water":        {"altitude": "deep",  "temperature": "temperate", "humidity": "wet",    "vegetation": "none"},
    "deep_water":   {"altitude": "deep",  "temperature": "temperate", "humidity": "wet",    "vegetation": "none"},
    "river":        {"altitude": "low",   "temperature": "temperate", "humidity": "wet",    "vegetation": "none"},
}
"""地形生成权重属性（仿 FreeCiv struct terrain property[MG_COUNT]）"""

CITY_TERRITORY_RADIUS: Dict[int, int] = {
    1: 1,
    2: 2,
    3: 2,
    4: 3,
    5: 3,
}
"""城市控制区半径（按城市等级）"""

# ============================================================
# 季节参数
# ============================================================

SEASON_FOOD_BONUS: Dict[str, float] = {
    "spring": 1.10,
    "summer": 1.05,
    "autumn": 1.15,
    "winter": 0.90,
}
"""季节粮草产出倍率"""

SEASON_MOVEMENT_FACTOR: Dict[str, float] = {
    "spring": 1.0,
    "summer": 1.0,
    "autumn": 1.0,
    "winter": 0.8,
}
"""季节军队移动力倍率"""

# ============================================================
# 影响力系统参数
# ============================================================

INFLUENCE_DECAY_PER_HEX: float = 0.4
"""影响力每向外一格衰减比例（40%）"""

INFLUENCE_OWN_BUFF_RATE: float = 0.05
"""己方高影响力地块产出加成（5%）"""

INFLUENCE_ENEMY_DEBUFF_RATE: float = 0.10
"""敌方高影响力地块产出减成（10%）"""

INFLUENCE_ENEMY_DOMINANCE_RATIO: float = 2.0
"""敌方影响力达到己方 2 倍时触发 debuff"""
