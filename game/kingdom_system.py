"""建国称王系统

184年黄巾之乱剧本中，各方诸侯可在满足条件时称王建国。
建国后获得 Buff，但也引发其他势力的警惕（Debuff）。

触发条件：
- 控制 3+ 城 → 可称王
- 控制 5+ 城 → 自动称帝
- 控制洛阳 → 可挟天子

Buff：
- 生产 +10%
- 士气 +5

Debuff：
- 其他势力联盟倾向 +20%
"""

from __future__ import annotations

from typing import Dict, List, Optional

from game.models import City

# 建国所需城市数
KINGDOM_MIN_CITIES: int = 3
EMPEROR_MIN_CITIES: int = 5

# Buff/Debuff 数值
KINGDOM_PRODUCTION_BONUS: float = 0.10
KINGDOM_MORALE_BONUS: int = 5
KINGDOM_DIPLO_PENALTY: float = 0.20

# 历史国号映射
KINGDOM_NAMES: Dict[str, str] = {
    "caocao":     "魏",
    "liubei":     "汉",
    "sunjian":    "吴",
    "dongzhuo":   "凉",
    "yuanshao":   "赵",
    "liubiao":    "楚",
    "liuyan":     "蜀",
    "gongsunzan": "燕",
    "mateng":     "秦",
    "yuanshu":    "成",
    "han":        "汉",
    "zhangjiao":  "太平道",
}


class KingdomSystem:
    """建国称王系统"""

    def __init__(self) -> None:
        self._kingdoms: Dict[str, dict] = {}  # faction → kingdom info

    def check_kingdom_eligibility(
        self, faction: str, cities: List[City]
    ) -> Optional[dict]:
        """检查势力是否满足建国条件

        Args:
            faction: 势力键
            cities: 该势力控制的城市列表

        Returns:
            None（不满足），或 {'type': 'kingdom'/'emperor', 'name': 国号, 'buffs': {...}, 'debuffs': {...}}
        """
        owned = [c for c in cities if c.faction == faction]
        count = len(owned)
        already_kingdom = faction in self._kingdoms

        if already_kingdom:
            return None

        if count >= EMPEROR_MIN_CITIES:
            kingdom_type = "emperor"
            name = KINGDOM_NAMES.get(faction, faction)
        elif count >= KINGDOM_MIN_CITIES:
            kingdom_type = "kingdom"
            name = KINGDOM_NAMES.get(faction, faction)
        else:
            return None

        # 记录建国
        self._kingdoms[faction] = {
            "type": kingdom_type,
            "name": name,
            "turn_founded": 0,
            "buffs": {
                "production": KINGDOM_PRODUCTION_BONUS,
                "morale": KINGDOM_MORALE_BONUS,
            },
            "debuffs": {
                "diplomacy_penalty": KINGDOM_DIPLO_PENALTY,
            },
        }

        return self._kingdoms[faction]

    def get_kingdom_name(self, faction: str) -> Optional[str]:
        """获取势力的国号（如已建国）"""
        k = self._kingdoms.get(faction)
        return k["name"] if k else None

    def is_kingdom(self, faction: str) -> bool:
        """该势力是否已建国"""
        return faction in self._kingdoms

    def get_production_bonus(self, faction: str) -> float:
        """获取建国生产加成"""
        if faction in self._kingdoms:
            return self._kingdoms[faction]["buffs"]["production"]
        return 0.0

    def get_morale_bonus(self, faction: str) -> int:
        """获取建国士气加成"""
        if faction in self._kingdoms:
            return self._kingdoms[faction]["buffs"]["morale"]
        return 0

    def get_all_kingdoms(self) -> Dict[str, dict]:
        """获取所有已建国势力"""
        return dict(self._kingdoms)
