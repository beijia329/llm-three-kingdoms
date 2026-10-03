"""人设系统（v4.0 重写）

三块内容：
1. `Personality` —— 六种性格枚举（驱动决策倾向）
2. `FACTION_PERSONALITY` —— 势力战略倾向（影响 CLIPlayer 与 LLM 提示词）
3. `GENERAL_PROFILES` —— 53 名武将的人设档案（性格 + 称号 + 特质）

🔴 v4.0 修掉的两个问题：

**问题一：`GENERAL_PERSONALITIES` 的 key 与数据完全对不上。**
原表用 `caocao` / `dongzhuo` / `guanyu` / `lvbu` 这类连写 ID，
而 `data/generals.json` 实际用的是 `cao_cao` / `dong_zhuo` / `guan_yu` 这类
下划线 ID。实测 19 个 key 里 **17 个在数据中不存在**（交集仅 2 个），
且该表从未被任何代码读取过 —— 等于武林高手名册拿错了剧本。

**问题二：53 名武将只有 19 人有性格，其余全部落到默认 `balanced`。**
且 `General.personality` 字段在数据文件里根本不存在（全为 None），
所以连"设定值"都没有真正进入游戏。

现在改为：以 `GENERAL_PROFILES` 为唯一真源（覆盖全部 53 人，ID 与数据一致），
`GENERAL_PERSONALITIES` 由它派生以兼容旧引用，
并由 `GameEngine.init_game` 把性格写回每个 `General` 实例。
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, Optional


class Personality(str, Enum):
    """武将性格"""

    AGGRESSIVE = "aggressive"     # 激进：偏好进攻
    CAUTIOUS = "cautious"         # 谨慎：偏好防守
    DIPLOMATIC = "diplomatic"     # 外交型：偏好外交手段
    AMBITIOUS = "ambitious"       # 野心家：容易叛变
    LOYAL = "loyal"               # 忠诚：不易叛变
    BALANCED = "balanced"         # 平衡：无明显倾向


# ============================================================
# 势力战略倾向
# ============================================================

FACTION_PERSONALITY: dict = {
    "han":        {"style": "cautious",    "aggression": 0.3, "diplomacy": 0.5, "expand": 0.2},
    "zhangjiao":  {"style": "aggressive",  "aggression": 0.6, "diplomacy": 0.1, "expand": 0.1},
    "dongzhuo":   {"style": "aggressive",  "aggression": 0.9, "diplomacy": 0.1, "expand": 0.0},
    "yuanshao":   {"style": "ambitious",   "aggression": 0.5, "diplomacy": 0.3, "expand": 0.2},
    "caocao":     {"style": "ambitious",   "aggression": 0.7, "diplomacy": 0.2, "expand": 0.1},
    "liubei":     {"style": "diplomatic",  "aggression": 0.5, "diplomacy": 0.5, "expand": 0.2},
    "sunjian":    {"style": "aggressive",  "aggression": 0.6, "diplomacy": 0.2, "expand": 0.2},
    "liubiao":    {"style": "cautious",    "aggression": 0.2, "diplomacy": 0.4, "expand": 0.4},
    "liuyan":     {"style": "cautious",    "aggression": 0.2, "diplomacy": 0.3, "expand": 0.5},
    "gongsunzan": {"style": "aggressive",  "aggression": 0.7, "diplomacy": 0.1, "expand": 0.2},
    "mateng":     {"style": "aggressive",  "aggression": 0.6, "diplomacy": 0.2, "expand": 0.2},
    "yuanshu":    {"style": "ambitious",   "aggression": 0.6, "diplomacy": 0.3, "expand": 0.1},
}


FACTION_LORD: Dict[str, str] = {
    "caocao": "cao_cao",
    "dongzhuo": "dong_zhuo",
    "yuanshao": "yuan_shao",
    "han": "he_jin",
    "liubei": "liu_bei",
    "sunjian": "sun_jian",
    "liubiao": "liu_biao",
    "liuyan": "liu_yan",
    "gongsunzan": "gongsun_zan",
    "mateng": "ma_teng",
    "yuanshu": "yuan_shu",
    "zhangjiao": "zhang_jiao",
}
"""势力键 → 该势力君主（话事人）的将领 ID

用途：LLM 提示词里要告诉模型"你扮演的是谁"，需要把势力键映射到人物档案。
注意势力键与将领 ID 的命名规范不同（caocao vs cao_cao），不能直接拼接。
"""


# ============================================================
# 武将人设档案（53 人，ID 与 data/generals.json 一致）
# ============================================================
#
# 字段说明：
#   personality  六种性格之一，直接驱动决策倾向
#   title        称号（史书/演义评价或民间称谓）
#   trait        一句话特质，会作为「人物底色」写进 LLM 提示词
#
GENERAL_PROFILES: Dict[str, Dict[str, str]] = {
    # ---- 曹操部 ----
    "cao_cao": {
        "personality": "ambitious", "title": "治世之能臣，乱世之奸雄",
        "trait": "唯才是举、多疑善断，宁我负人休教人负我；强于用人而难全然信人。",
    },
    "xiahou_dun": {
        "personality": "loyal", "title": "独眼苍狼",
        "trait": "曹氏宗亲，忠勇刚烈，治军严整，可为先锋亦可安民。",
    },
    "xiahou_yuan": {
        "personality": "aggressive", "title": "虎步关右",
        "trait": "用兵尚疾，常出敌不意；勇则有余，谋则稍逊，须防轻进。",
    },
    "cao_ren": {
        "personality": "cautious", "title": "铁壁将军",
        "trait": "沉稳持重，最擅守城，兵少亦能坚拒；进取非其所长。",
    },
    "xun_yu": {
        "personality": "diplomatic", "title": "王佐之才",
        "trait": "善于调和上下、安定后方，主张先固根本再图远略。",
    },
    "dian_wei": {
        "personality": "loyal", "title": "古之恶来",
        "trait": "勇力绝人，护卫主公寸步不离，然不善统军治民。",
    },
    "xu_chu": {
        "personality": "loyal", "title": "虎痴",
        "trait": "质朴寡言、死忠不二，临阵敢死，不为言语所动。",
    },
    "guo_jia": {
        "personality": "balanced", "title": "鬼才",
        "trait": "算无遗策而放达不羁，敢行险着，判断敌情时常胜人一筹。",
    },

    # ---- 董卓部 ----
    "dong_zhuo": {
        "personality": "aggressive", "title": "西凉豺狼",
        "trait": "恃强凌弱、好财货、以威压人；部众虽众，人心不附。",
    },
    "li_ru": {
        "personality": "ambitious", "title": "毒士",
        "trait": "善于构陷与借势，主张以恶名换实效，不忌手段。",
    },
    "hua_xiong": {
        "personality": "aggressive", "title": "西凉骁将",
        "trait": "勇而骄，好阵前逞威，遇强手易轻敌。",
    },
    "li_jue": {
        "personality": "aggressive", "title": "凉州悍将",
        "trait": "剽悍好斗，长于劫掠，短于经略，无长远之计。",
    },
    "cheng_pu": {
        "personality": "cautious", "title": "江东宿将",
        "trait": "历事三世的宿将，稳重老成，最重军中资历与秩序。",
    },
    "xu_rong": {
        "personality": "balanced", "title": "凉州良将",
        "trait": "用兵有法，能审时度势，不轻进亦不轻退。",
    },
    "niu_fu": {
        "personality": "cautious", "title": "董氏姻亲",
        "trait": "因人得位，才具平庸，行事但求无过。",
    },

    # ---- 公孙瓒部 ----
    "gongsun_zan": {
        "personality": "aggressive", "title": "白马将军",
        "trait": "轻骑袭扰见长，性刚愎、记仇，与袁绍势不两立。",
    },
    "zhao_yun_early": {
        "personality": "loyal", "title": "常山赵子龙",
        "trait": "勇而有谋、持重不苟，主择而事，认主之后生死不弃。",
    },
    "tian_yu": {
        "personality": "cautious", "title": "御边良牧",
        "trait": "善抚边民、稳守要地，主张固本而非浪战。",
    },

    # ---- 汉室 ----
    "he_jin": {
        "personality": "cautious", "title": "外戚大将军",
        "trait": "位高而寡断，优柔畏事，遇强则退，须借他人之力行事。",
    },
    "huangfu_song": {
        "personality": "balanced", "title": "汉末第一名将",
        "trait": "持重善战、识大体，平乱不留后患，为诸将所服。",
    },
    "zhu_jun": {
        "personality": "loyal", "title": "宿将朱公",
        "trait": "忠勤老成，善抚士卒，治军严整而不苛。",
    },
    "lu_zhi": {
        "personality": "balanced", "title": "儒将卢公",
        "trait": "文武兼备、通经明理，重名节，主张以正道平乱。",
    },

    # ---- 刘备部 ----
    "liu_bei": {
        "personality": "diplomatic", "title": "汉室宗亲",
        "trait": "以仁义与宗亲之名为号召，善结人心、能屈能伸；不轻弃盟友。",
    },
    "guan_yu": {
        "personality": "loyal", "title": "义绝",
        "trait": "义薄云天而性矜高，重盟约、轻士大夫；傲气有时误事。",
    },
    "zhang_fei": {
        "personality": "aggressive", "title": "万人之敌",
        "trait": "暴烈勇猛、敬重君子而不恤小人，临阵可当一面。",
    },
    "jian_yong": {
        "personality": "diplomatic", "title": "能言善辩",
        "trait": "口才出众、善作说客，长于周旋而短于统兵。",
    },

    # ---- 刘表部 ----
    "liu_biao": {
        "personality": "cautious", "title": "八俊之一",
        "trait": "坐拥荆襄而志在自守，喜清谈名士、恶征战，最忌外兵入荆。",
    },
    "kuai_liang": {
        "personality": "balanced", "title": "荆州谋主",
        "trait": "明察时势、善守成，主张保境安民，不轻启战端。",
    },
    "huang_zu": {
        "personality": "aggressive", "title": "江夏太守",
        "trait": "粗猛好战、御下有威，善守江防而少谋略。",
    },
    "cai_mao": {
        "personality": "ambitious", "title": "荆襄水师都督",
        "trait": "握水军之利、善察风向，惯于依附强者以自保。",
    },

    # ---- 刘焉部 ----
    "liu_yan": {
        "personality": "cautious", "title": "益州牧",
        "trait": "据险自守、经营益州，欲作一方之尊，对外事态度保守。",
    },
    "yan_yan": {
        "personality": "loyal", "title": "巴郡老将",
        "trait": "刚直不屈、老而弥坚，宁可断头不肯降人。",
    },

    # ---- 马腾部 ----
    "zhang_ren": {
        "personality": "loyal", "title": "蜀中名将",
        "trait": "忠勇有谋、善设伏，护卫主君不惜性命。",
    },
    "ma_teng": {
        "personality": "aggressive", "title": "西凉锦马超之父",
        "trait": "西凉豪杰、骑战凌厉，重义气而轻朝廷。",
    },
    "pang_de": {
        "personality": "loyal", "title": "白马将军",
        "trait": "勇烈不屈、亲冒矢石，宁可战死不肯受辱。",
    },
    "han_sui": {
        "personality": "ambitious", "title": "西凉十部之雄",
        "trait": "反复无常、善于权衡，一切以自保与扩张为先。",
    },

    # ---- 孙坚部 ----
    "sun_jian": {
        "personality": "aggressive", "title": "江东猛虎",
        "trait": "勇烈果决、每战身先，喜好扩地进取，须防孤军深入。",
    },
    "huang_gai": {
        "personality": "loyal", "title": "江东宿将",
        "trait": "历事三主的宿将，忠勇能忍，为大局甘受重苦。",
    },
    "han_dang": {
        "personality": "loyal", "title": "江东旧部",
        "trait": "随主起兵的老部曲，稳健可靠，长于野战和守土。",
    },

    # ---- 袁绍部 ----
    "yuan_shao": {
        "personality": "ambitious", "title": "四世三公",
        "trait": "名门之资、好谋而无断，重门第排场，决断常失于迟疑。",
    },
    "yan_liang": {
        "personality": "aggressive", "title": "河北上将军",
        "trait": "勇冠河北而骄纵，惯于正面强攻，缺少应变。",
    },
    "wen_chou": {
        "personality": "aggressive", "title": "河北骁将",
        "trait": "勇烈好战，与颜良并称，急躁而少谋。",
    },
    "tian_feng": {
        "personality": "balanced", "title": "河北智士",
        "trait": "刚直敢谏、料事精准，宁逆主意也要说真话。",
    },
    "ju_shou": {
        "personality": "balanced", "title": "河北谋主",
        "trait": "深谋远虑、善于持重，主张缓图渐进而非速战。",
    },
    "shen_pei": {
        "personality": "loyal", "title": "河北直臣",
        "trait": "刚烈廉洁、执法不阿，宁死不降，做事不留余地。",
    },

    # ---- 袁术部 ----
    "yuan_shu": {
        "personality": "ambitious", "title": "仲家皇帝",
        "trait": "仗四世三公之名而骄奢，急于名分，好大喜功而不恤民力。",
    },
    "ji_ling": {
        "personality": "aggressive", "title": "淮南第一将",
        "trait": "力大善战、忠于其主，为袁术手中最硬的刀。",
    },
    "zhang_xun": {
        "personality": "cautious", "title": "淮南大将",
        "trait": "循规蹈矩、听命行事，不善于变通。",
    },
    "qiao_rui": {
        "personality": "balanced", "title": "淮南偏将",
        "trait": "寻常将佐，能守成而不能开创。",
    },

    # ---- 黄巾 ----
    "zhang_jiao": {
        "personality": "ambitious", "title": "天公将军",
        "trait": "以符水教义聚众数十万，善造势与煽动，志在改朝换代。",
    },
    "zhang_bao": {
        "personality": "loyal", "title": "地公将军",
        "trait": "与兄共举大事，忠信于教门，长于号召而短于用兵。",
    },
    "zhang_liang": {
        "personality": "loyal", "title": "人公将军",
        "trait": "黄巾三兄弟之末，能统众而缺乏机变。",
    },
    "bo_cai": {
        "personality": "aggressive", "title": "黄巾悍将",
        "trait": "勇猛敢战、部众众多，但缺纪律与谋略。",
    },
}

# 由档案派生的性格索引（保留旧名以兼容既有引用）
GENERAL_PERSONALITIES: Dict[str, Personality] = {
    gid: Personality(profile["personality"])
    for gid, profile in GENERAL_PROFILES.items()
}


# ============================================================
# 查询接口
# ============================================================

def get_general_profile(general_id: str) -> Optional[Dict[str, str]]:
    """取武将人设档案（不存在返回 None）"""
    return GENERAL_PROFILES.get(general_id)


def get_general_trait(general_id: str) -> str:
    """取武将特质描述（用于 LLM 提示词；无档案返回空串）"""
    profile = GENERAL_PROFILES.get(general_id)
    return profile.get("trait", "") if profile else ""


def get_general_title(general_id: str) -> str:
    """取武将称号（无档案返回空串）"""
    profile = GENERAL_PROFILES.get(general_id)
    return profile.get("title", "") if profile else ""


# ============================================================
# 倾向计算
# ============================================================

def get_aggression_weight(faction: str, general_personality: str = "balanced") -> float:
    """计算进攻倾向权重

    Args:
        faction: 势力键
        general_personality: 将领性格

    Returns:
        0.0-1.0 的进攻权重
    """
    base = FACTION_PERSONALITY.get(faction, {}).get("aggression", 0.5)
    # 性格修正
    modifiers = {
        "aggressive": 0.2,
        "cautious": -0.2,
        "ambitious": 0.1,
        "diplomatic": -0.15,
        "loyal": 0.0,
        "balanced": 0.0,
    }
    mod = modifiers.get(general_personality, 0.0)
    return max(0.0, min(1.0, base + mod))
