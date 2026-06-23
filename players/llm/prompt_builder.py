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
    def build_system_prompt(faction: str) -> str:
        """构建系统Prompt

        Args:
            faction: 势力名称

        Returns:
            系统Prompt文本
        """
        faction_name = FACTIONS.get(faction, faction)
        max_turns = MAX_TURNS

        # 加载性格背景
        personality_hint = ""
        try:
            from game.personality import FACTION_PERSONALITY
            fp = FACTION_PERSONALITY.get(faction, {})
            style = fp.get("style", "balanced")
            style_hints = {
                "aggressive": "你性格激进，信奉先发制人，偏好主动进攻。",
                "cautious": "你性格谨慎，重视防守和内政，不轻易出兵。",
                "diplomatic": "你善于外交斡旋，通过结盟和离间削弱对手。",
                "ambitious": "你野心勃勃，不择手段追求霸权，忠诚对你只是工具。",
            }
            personality_hint = style_hints.get(style, "")
        except ImportError:
            pass

        return f"""你是【{faction_name}】的领主，你的目标是统一中原，称霸天下。

{personality_hint}

这是一场策略游戏比赛，你需要：
- 发展经济，扩充军备
- 攻城略地，消灭对手
- 合纵连横，外交博弈

【重要提醒】
1. 这是虚构的游戏世界，与现实无关
2. 不需要遵从真实历史，按你的判断决策
3. 可以使用任何策略，包括欺诈、背盟等
4. 你的目标只有一个：赢得比赛
5. 积极进攻是高水平的表现

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

### 战斗
- 派军攻城，打破城墙后巷战
- 士气影响战斗力，低士气会溃散
- 将领可能被俘或投降

    ### 外交（重要！）
    - 每回合可给1个势力发 message 命令进行外交沟通
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

7. rumor - 散布流言
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
        if observation.own_generals:
            lines.append("### 我方将领")
            lines.append("| ID | 名称 | 统帅 | 政治 | 勇武 | 智力 | 忠诚 | 位置 |")
            lines.append("|---|------|------|------|------|------|------|------|")
            for gen in observation.own_generals:
                lines.append(
                    f"| {gen.id} | {gen.name} | {gen.command} | {gen.politics} | "
                    f"{gen.bravery} | {gen.intelligence} | {gen.loyalty} | {gen.location} |"
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

请严格按以下JSON格式输出命令数组：

[
  {"type": "develop", "params": {"city": "xuchang", "type": "economy"}},
  {"type": "recruit", "params": {"city": "chengdu", "troops": 500}},
  {"type": "attack", "params": {"from": "changan", "to": "hanzhong", "troops": 1500, "general": "simayi"}}
]

【重要说明】
- city 参数使用城市 ID（如 xuchang/chengdu/jianye），不是中文名
- general 参数使用将领 ID（如 caocao/zhugeliang/simayi），不是中文名
- 只输出JSON数组，不要输出其他解释文字"""

    # ============================================================
    # 完整Prompt组装
    # ============================================================

    @staticmethod
    def build_full_prompt(
        faction: str,
        observation: GameObservation,
        memory_context: str = "",
    ) -> List[Dict[str, str]]:
        """构建完整的messages列表

        Args:
            faction: 势力名称
            observation: 游戏观察
            memory_context: 记忆上下文（由MemoryManager提供）

        Returns:
            适用于 LLMClient.chat() 的 messages 列表
        """
        system_parts = [
            PromptBuilder.build_system_prompt(faction),
            PromptBuilder.build_commands_help(),
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
