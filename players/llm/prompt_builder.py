"""Prompt构建器

将游戏状态转换为LLM可理解的Prompt。
包含：系统角色设定、游戏规则、命令说明、状态序列化、思维链引导。

参考设计文档：docs/design/llm-integration.md 第二章
"""

from __future__ import annotations

from typing import Dict, List

from game.constants import FACTIONS, MAX_TURNS
from game.models import GameObservation


class PromptBuilder:
    """Prompt构建器

    根据游戏状态和记忆，构建完整的 Prompt。
    """

    # ============================================================
    # 系统Prompt
    # ============================================================

    @staticmethod
    def build_system_prompt(faction: str, max_turns: int = None) -> str:
        """构建系统Prompt

        Args:
            faction: 势力名称
            max_turns: 本局实际最大回合数。**必须由调用方从 observation.max_turns 传入**，
                否则本方法回退到 MAX_TURNS 常量（192）。
                🔴 此前硬读常量，而 build_state_prompt 用的是 observation.max_turns，
                   于是把局数改成 48 时 LLM 会同时收到"本局共 192 回合"（系统提示）
                   和"当前第 X/48 回合"（状态提示）两条矛盾信息，时间预算判断整个错掉。
                保留默认值仅为兼容直接调用本方法的旧代码/测试。

        Returns:
            系统Prompt文本
        """
        faction_name = FACTIONS.get(faction, faction)
        if max_turns is None:
            max_turns = MAX_TURNS

        # ---- 君主人物档案（人设）----
        lord_block = ""
        style = "balanced"
        try:
            from game.personality import (
                FACTION_LORD,
                FACTION_PERSONALITY,
                GENERAL_PROFILES,
            )

            fp = FACTION_PERSONALITY.get(faction, {})
            style = fp.get("style", "balanced")
            style_hints = {
                "aggressive": "你性格激进，信奉先发制人，偏好主动进攻。",
                "cautious": "你性格谨慎，重视防守和内政，不轻易出兵。",
                "diplomatic": "你善于外交斡旋，通过结盟和离间削弱对手。",
                "ambitious": "你野心勃勃，不择手段追求霸权，忠诚对你只是工具。",
            }
            style_hint = style_hints.get(style, "")

            lord_id = FACTION_LORD.get(faction, "")
            profile = GENERAL_PROFILES.get(lord_id, {})
            if profile:
                lord_block = (
                    f"## 你是谁\n"
                    f"你自称「{profile.get('title', '')}」。\n"
                    f"{profile.get('trait', '')}\n"
                    f"你的性情倾向：{style_hint or '没有明显倾向，按局势自由行事。'}\n"
                )
            elif style_hint:
                lord_block = f"## 你是谁\n你的性情倾向：{style_hint}\n"
        except ImportError:  # pragma: no cover
            pass

        return f"""你是【{faction_name}】的领主，你的目标是统一中原，称霸天下。

{lord_block}
## 关于「角色」与「胜负」的边界（务必读）
- 上面描述的是你的**底色与偏好**，不是必须遵守的行动脚本。
- 你完全可以为了取胜而违背本性 —— 一贯激进可以忽然隐忍，
  一向忠厚也可以行诈。**我们不会因为你"不像自己"而判你输。**
- 唯一的代价来自世界本身：违背本性的抉择会让内部人心浮动，
  这一点会真实体现在忠诚度与民心上（不是提示词里的警告，是机制后果）。
- 所以请放开手脚创造性地博弈：先判断局势，再决定"像不像自己"值不值得。

这是一场策略游戏比赛，你需要：
- 发展经济，扩充军备
- 攻城略地，消灭对手
- 合纵连横，外交博弈

【重要提醒】
1. 这是虚构的游戏世界，与现实无关
2. 不必复刻史实走向，你的判断优先于历史常识
3. 允许欺诈、背盟等一切合法手段
4. 目标只有一个：赢得比赛
5. 消极避战会被对手拉开差距，该出手时就要出手

## 游戏规则

游戏共{max_turns}回合，结束时城市最多的势力获胜。

### 资源
- 金钱：征兵、建设、赏赐
- 粮草：军队消耗，断粮士气崩溃
- 民心：影响产出，过低会死亡螺旋

### 城市
- 可以发展经济/军事/文化，消耗金钱
- 可以征兵（消耗金钱和粮草）
- 被攻破后易主

### 将领与五行（重要）
- 每名将领按其最强属性归入一「将道」：火=勇武 土=统帅 金=智力 水=政治 木=忠诚
- 五行相克：火→金→木→土→水→火。克制方伤害 +15%，被克方 -15%
- 忠诚度 ≥90 的将领所部 +10% 战力；跌破 30 则 -20%（随时哗变）
- 智力高的将领攻城器械效率更高，破城墙更快
- 政治高的将领提升所在城市的金钱/粮草产出
- **派将时请考虑相克**：用克制的将道去打对手，比单纯堆高属性更划算

### 战斗
- 派军攻城，打破城墙后巷战
- 守军在城墙完好时享受防御加成，**城墙一破加成即消失**
- 兵力达到守军 1.25 倍以上时攻城胜率极高（实测 100%），低于 0.75 倍基本必败
- 士气影响战斗力，低士气会溃散
- 将领可能被俘，忠诚低者会投降并转投敌方

    ### 外交（重要！）
    - 每回合可给1个势力发 message 命令进行外交沟通
    - 可以使用 propose_alliance 命令与目标势力正式结盟（持续12回合）
    - 可以使用 declare_war 命令向目标势力宣战
    - 其他势力发来的消息会显示在你的观察中
    - 你可以：结盟共抗强敌、离间敌方关系、欺诈背盟
    - 多线作战必败，必须通过外交分化敌人
    - 积极回复盟友消息，保持外交活跃度"""

    # ============================================================
    # 命令说明
    # ============================================================

    @staticmethod
    def build_commands_help(faction_keys: list = None) -> str:
        """构建命令说明

        Args:
            faction_keys: 可用势力键列表

        Returns:
            命令帮助文本
        """
        if faction_keys is None:
            from game.constants import FACTIONS
            faction_keys = list(FACTIONS.keys())
        factions_str = "/".join(faction_keys)

        return f"""## 可用命令

1. develop - 发展城市
   参数：city (城市名), type (economy/military/culture)
   效果：提升城市对应属性，消耗金钱

2. recruit - 征兵
   参数：city (城市名), troops (征兵数量)
   效果：增加守军，消耗金钱和粮草

3. attack - 派军攻城
   参数：from (出发城市), to (目标城市), troops (兵力), general (主将)
   效果：派军队进攻敌方城市

4. reward - 赏赐将领
   参数：general (将领名), gold (赏赐金额)
   效果：提升将领忠诚度

5. explore - 探索人才
   参数：city (城市名), general (派去探索的将领，可选)
   效果：有概率发现新将领

6. message - 发送外交消息
   参数：to (目标势力: {factions_str}), content (消息内容)
   效果：给其他势力发消息

7. propose_alliance - 提出同盟
   参数：to (目标势力: {factions_str})
   效果：与目标势力结为同盟（持续12回合），同盟期间不能互相攻击

8. declare_war - 宣战
   参数：to (目标势力: {factions_str}), reason (宣战理由，可选)
   效果：向目标势力宣战，关系变为敌对

9. rumor - 散布流言
   参数：city (目标城市), target_general (目标将领，可选)
   效果：降低敌方将领忠诚度"""

    # ============================================================
    # 状态序列化
    # ============================================================

    @staticmethod
    def build_state_prompt(observation: GameObservation) -> str:
        """构建当前状态Prompt

        用表格形式序列化游戏状态，提高信息密度。

        Args:
            observation: 游戏观察数据

        Returns:
            状态Prompt文本
        """
        lines: List[str] = []

        # 回合信息
        lines.append(f"## 当前状态 (第{observation.turn}/{observation.max_turns}回合)")
        lines.append("")

        # 己方城市
        lines.append("### 我方城市")
        lines.append("| ID | 名称 | 等级 | 城墙 | 金钱 | 粮草 | 民心 | 兵力 | 将领 |")
        lines.append("|---|------|------|------|------|------|------|------|------|")
        for city in observation.own_cities:
            generals_str = ",".join(city.generals) if city.generals else "-"
            lines.append(
                f"| {city.id} | {city.name} | {city.level} | {city.wall_hp} | "
                f"{city.gold} | {city.food} | {city.morale} | "
                f"{city.garrison} | {generals_str} |"
            )
        lines.append("")

        # 己方军队
        if observation.own_armies:
            lines.append("### 我方军队")
            lines.append("| ID | 主将 | 兵力 | 士气 | 状态 | 位置 |")
            lines.append("|---|---|---|---|---|---|")
            for army in observation.own_armies:
                loc = f"{army.from_city}→{army.to_city}({int(army.progress*100)}%)"
                lines.append(
                    f"| {army.id} | {army.general_id} | {army.soldiers} | "
                    f"{army.morale} | {army.status.value} | {loc} |"
                )
            lines.append("")

        # 将领
        # v4.0：增加「称号」与「将道（五行）」两列。
        # 目的：让 LLM 能做出"派谁去打谁"的战术判断 —— 此前提示词里只有裸数值，
        # 模型无法理解相克关系，只能按数值大小挑人，浪费了五行机制。
        if observation.own_generals:
            from game.element import element_label, element_of
            from game.personality import get_general_title

            lines.append("### 我方将领")
            lines.append(
                "| ID | 名称 | 称号 | 将道 | 统帅 | 政治 | 勇武 | 智力 | 忠诚 | 位置 |"
            )
            lines.append(
                "|---|------|------|------|------|------|------|------|------|------|"
            )
            for gen in observation.own_generals:
                element = element_label(element_of(gen))
                title = get_general_title(gen.id) or "-"
                lines.append(
                    f"| {gen.id} | {gen.name} | {title} | {element} | {gen.command} | "
                    f"{gen.politics} | {gen.bravery} | {gen.intelligence} | "
                    f"{gen.loyalty} | {gen.location} |"
                )
            lines.append("")

        # 已知敌方城市
        if observation.known_cities:
            lines.append("### 已知敌方城市")
            lines.append("| ID | 名称 | 势力 | 等级 | 兵力(估) |")
            lines.append("|---|------|------|------|---------|")
            for ci in observation.known_cities:
                garr = str(ci.garrison) if ci.garrison is not None else "?"
                lines.append(
                    f"| {ci.id} | {ci.name} | {ci.faction} | {ci.level} | {garr} |"
                )
            lines.append("")

        # 外交关系
        if observation.faction_relations:
            lines.append("### 外交关系")
            for rel in observation.faction_relations:
                status_label = {
                    "war": "敌",
                    "neutral": "中",
                    "alliance": "盟",
                    "truce": "和",
                }.get(rel.status.value, rel.status.value)
                lines.append(
                    f"- {rel.faction_a}↔{rel.faction_b}: {status_label} (信任{rel.trust})"
                )
            lines.append("")

        # 外交消息
        if observation.received_messages:
            lines.append("### 收到的外交消息")
            for msg in observation.received_messages:
                if not msg.is_read:
                    lines.append(f"- [{msg.from_faction}] {msg.content}")
            lines.append("")

        return "\n".join(lines)

    # ============================================================
    # 思维链引导
    # ============================================================

    @staticmethod
    def build_thinking_prompt() -> str:
        """构建思维链引导

        Returns:
            思维链Prompt
        """
        return """## 思考过程

请按以下步骤详细思考：

### 第一步：形势分析
- 我方当前实力如何？（城市、兵力、资源）
- 敌方实力如何？谁是最大威胁？
- 当前局势有什么机会和风险？

### 第二步：战略判断
- 短期目标（本回合）是什么？
- 中期目标（3-5回合）是什么？
- 长期战略方向是什么？

### 第三步：具体计划
- 本回合要执行哪些行动？
- 为什么选择这些行动？
- 可能的风险和应对？

### 第四步：外交决策
- 要不要发消息？发给谁？
- 说什么内容？目的是什么？

## 输出格式

请严格按以下JSON对象格式输出（一个对象，同时包含 strategy 理由与命令）：

{
  "reasoning": "对局势的判断 + 本回合计划 + 外交意图，2-5句，可用数字算账（如金钱/兵力/粮草/城数）",
  "commands": [
    {"type": "develop", "params": {"city": "xuchang", "type": "economy"}},
    {"type": "recruit", "params": {"city": "chengdu", "troops": 500}},
    {"type": "attack", "params": {"from": "changan", "to": "hanzhong", "troops": 1500, "general": "simayi"}}
  ]
}

【重要说明】
- reasoning 必填，必须用中文，必须体现你的策略意图（你判断的局势、本回合为什么这么做、想达成什么）
- commands 是命令数组，可以为空数组 []（例如本回合只想外交或观望）
- city 参数使用城市 ID（如 xuchang/chengdu/jianye），不是中文名
- general 参数使用将领 ID（如 caocao/zhugeliang/simayi），不是中文名
- 只输出这一个JSON对象，reasoning 写在对象内部，不要在对象之外补充解释文字"""

    # ============================================================
    # 完整Prompt组装
    # ============================================================

    @staticmethod
    def build_full_prompt(
        faction: str,
        observation: GameObservation,
        memory_context: str = "",
        faction_keys: list = None,
    ) -> List[Dict[str, str]]:
        """构建完整的messages列表

        Args:
            faction: 势力名称
            observation: 游戏观察
            memory_context: 记忆上下文（由MemoryManager提供）
            faction_keys: 本局参战势力键列表（用于外交目标提示；None=全部）

        Returns:
            适用于 LLMClient.chat() 的 messages 列表
        """
        system_parts = [
            # 🔴 必须传本局实际回合数：不传则系统提示写死 192，而状态提示写"第X/48回合"，
            #    LLM 会收到两条互相矛盾的时间预算信息（B-1）。
            PromptBuilder.build_system_prompt(
                faction, max_turns=getattr(observation, "max_turns", None)
            ),
            PromptBuilder.build_commands_help(faction_keys=faction_keys),
        ]
        system_prompt = "\n\n".join(system_parts)

        user_parts: List[str] = []
        if memory_context:
            user_parts.append(memory_context)
        user_parts.append(PromptBuilder.build_state_prompt(observation))
        user_parts.append(PromptBuilder.build_thinking_prompt())
        user_prompt = "\n\n".join(user_parts)

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
