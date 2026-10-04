"""终局文案「单一真源」（v4.3.0 D1 · H1 判定口径统一）

## 为什么必须有这个模块

玩家的诉求是「判定不算统一」—— 根因是**同一结局在三处各写各的文案**
（引擎 `end_reason` → 后端事件 f-string → 前端 GameOverOverlay 的
`isUnification ? ... : ...` 映射）。三处漂移 = 口径不一致。

拍板的修复是**单一真源**：只有本模块 `format_end_copy()` 知道「哪种结局说什么」，
其余所有消费方（后端事件、`/api/state` 的 `end_title`/`end_subtitle`、前端结算卡）
**一律 verbatim 取用**，不得各自映射。

设计依据：docs/design/2026-10-04-胜负条件与对局长度.md §1.1（文案表）与 §3.4/§3.5。

## 硬约束

🔴 「一统天下」**只在 `unification` 出现**；`timeout` / `stalemate` 一律「领先胜出」。
"""

from __future__ import annotations

from typing import Optional, Tuple

from game.constants import FACTIONS

# 终局图标（**单一真源**）：映射到前端本地 SVG 资产名，**不再用 emoji**。
# 前端只做「资产名 → import 的 SVG」查表，不得自行按 end_reason 选图标。
END_ICON = {
    "unification": "crown",          # 本地 assets/icons/crown.svg
    "stalemate": "scales",           # game-icons(lorc/scales, CC BY 3.0)
    "timeout": "siege-tower",        # 本地 assets/icons/siege-tower.svg
    "tie": "shaking-hands",          # game-icons(delapouite/shaking-hands, CC BY 3.0)
}


def format_end_icon(end_reason: Optional[str], winner: Optional[str]) -> str:
    """终局图标标识（单一真源）：返回前端本地 SVG 资产名。

    - winner 为空（并列）→ "shaking-hands"
    - unification → "crown" / stalemate → "scales" / timeout（含未知）→ "siege-tower"

    🔴 前端**不得**再自行按 end_reason 选图标 —— 一律渲染本函数经
    `/api/state` 下发的 `end_icon`。
    """
    if not winner:
        return END_ICON["tie"]
    return END_ICON.get(end_reason or "", END_ICON["timeout"])



def format_end_copy(
    end_reason: Optional[str],
    winner: Optional[str],
    turn: int,
    max_turns: int,
    stalemate_turns: int = 6,
) -> Tuple[str, str]:
    """把 (end_reason, winner) 映射为 (标题, 副标题) —— **唯一真源**。

    四种结局全覆盖：

    | end_reason | winner | 标题 | 副标题 |
    |---|---|---|---|
    | unification | 势力id | 「{势力} 一统天下」 | 第 {turn} 回合 · 廓清寰宇 |
    | timeout | 势力id | 「{势力} 领先胜出」 | 第 {turn} / {max} 回合 · 时限已到，天下未定 |
    | stalemate | 势力id | 「{势力} 领先胜出」 | 连续 {N} 回合无战事 · 僵局收束，天下未定 |
    | （任一） | None | 「天下未定 · 并列」 | 同上按 end_reason 决定 |

    Args:
        end_reason: "unification" | "timeout" | "stalemate" | None（旧档）
        winner: 势力 id 或 None
        turn: 结束时回合号
        max_turns: 对局上限
        stalemate_turns: 僵局熔断阈值（副标题「连续 N 回合无战事」用）

    Returns:
        (title, subtitle)

    Note:
        `end_reason` 为 None（旧存档/异常）时按 timeout 口径输出「领先胜出」，
        **绝不**在语义未知时输出「一统天下」—— 宁可保守。
    """
    name = FACTIONS.get(winner, winner) if winner else None
    is_unification = end_reason == "unification" and bool(name)

    if name:
        title = f"{name} 一统天下" if is_unification else f"{name} 领先胜出"
    else:
        title = "天下未定 · 并列"

    if is_unification:
        subtitle = f"第 {turn} 回合 · 廓清寰宇"
    elif end_reason == "stalemate":
        subtitle = f"连续 {stalemate_turns} 回合无战事 · 僵局收束，天下未定"
    else:
        # timeout（含 end_reason=None 的旧档兜底）
        subtitle = f"第 {turn} / {max_turns} 回合 · 时限已到，天下未定"

    return title, subtitle


def format_end_event(
    end_reason: Optional[str],
    winner: Optional[str],
    turn: int,
    max_turns: int,
    stalemate_turns: int = 6,
) -> str:
    """事件流文案：`format_end_copy` 的标题 + 句末感叹号（**同一真源**，不再内联分支）。

    🔴 去 emoji：事件流是纯文本行，图标由前端按事件类型渲染（Font Awesome），
    这里**不再**嵌入 emoji（旧实现含 🏆/⚖️/⏳）。
    """
    title, _ = format_end_copy(end_reason, winner, turn, max_turns, stalemate_turns)
    return f"{title}！"
