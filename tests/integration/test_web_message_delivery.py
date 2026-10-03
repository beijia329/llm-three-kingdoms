"""Web 路径（GameManager）的外交消息投递守卫

## 这个文件解决什么问题

`CLIPlayer` 只能靠 `receive_message` 回调得知「有人提议结盟」——
它在 `players/cli_player.py:71-77` 里对消息内容做关键字匹配
（结盟/同盟/盟约/联合/互不侵犯/合兵），命中就设 `_pending_alliance`，
下一回合据此回发 `ProposeAllianceCommand`。

回调不投递 → `_pending_alliance` 恒为 `None` → 结盟提议永不发出
→ **规则-AI 模式下同盟在结构上不可能发生**。

2026-10-03 实测：三条路径里只有 CLI 投递，Web 与实验台都不投递。

    main.py CLI ai-vs-ai        ✅ 投递
    api/game_manager.py（Web）   ❌ 不投递  ← 本文件守卫的修复
    tests/balance/pacing_lib.py ❌ 不投递  ← 已另行修复

同一条对局路径的两变体实测（`tests/balance/exp19_diplomacy_reachability.py`）：

    不投递：外交消息 560 条｜结盟提议 0 次｜同盟 0 对
    投递：  外交消息 521 条｜结盟提议 92 次｜同盟 47 对

## 判据

改坏验证（把 `_deliver_message` 的调用注释掉 / 让它直接 return）：
本文件必须**变红**。仅断言"消息发出去了"是不够的——
必须断言**目标玩家的待接受状态被置位**、以及**同盟真的形成了**
（后者才是玩家可见的结果）。
"""

from __future__ import annotations

from typing import Any

import pytest

from api.game_manager import GameConfig, GameManager
from game.models import DiplomaticStatus, MessageCommand


@pytest.fixture
def manager() -> GameManager:
    """规则-AI 模式的 GameManager（use_llm=False → CLIPlayer）。

    ⚠️ 本作 v4.1.2 起结盟有两道门槛（史实硬禁 + 信任度 ≥ 45），
    且 `CLIPlayer` 只有 `diplomacy > 0.3` 的势力才会**回应**结盟提议。
    故势力组合必须挑「互相信任度够 + 有人愿意回应」的一组：

        汉室(0.5) / 刘备(0.5) / 刘表(0.4)  ← 三者都 > 0.3，都能回应
        han×liubei=55、han×liubiao=60、liubei×liubiao=60  ← 全部 ≥ 45

    （早先用「曹操/刘备/袁绍」：曹×刘信任 35 已被结构性挡住，
      而该组里只有刘备一个能回应 → 结盟永远不可能发生。）

    只取 3 个势力，跑得快，且足够产生外交互动。
    """
    return GameManager(
        GameConfig(seed=42, max_turns=48, use_llm=False,
                   factions=["han", "liubei", "liubiao"])
    )


class TestDeliverMessageUnit:
    """`_deliver_message` 本身的行为（直连、确定性）。"""

    def test_message_sets_pending_alliance_on_target(self, manager: GameManager):
        """发一条含"结盟"字样的消息 → 目标玩家的待接受状态必须被置位。

        这是整条链的第一环。之前 Web 路径缺的正是这一步。
        """
        sender, target = "caocao", "liubei"
        target_player = manager._players[target]
        # 前置：确认初始未置位（否则断言无意义）
        assert getattr(target_player, "_pending_alliance", None) is None

        cmd = MessageCommand(
            type="message", faction=sender, turn=1, params={},
            to=target, content="提议结盟共抗强敌",
        )
        result = manager.engine.execute_command(cmd)
        assert result.success, "前置失败：消息命令未执行成功"

        manager._deliver_message(sender, cmd, result)

        assert getattr(target_player, "_pending_alliance", None) == sender, (
            "目标玩家的 _pending_alliance 未被置位 —— "
            "Web 路径没有投递外交消息，规则-AI 永远结不了盟"
        )

    def test_non_message_command_is_ignored(self, manager: GameManager):
        """非 message 命令不应触发投递（避免误伤其他命令）。"""
        target_player = manager._players["liubei"]
        before = getattr(target_player, "_pending_alliance", None)

        class FakeCmd:
            type = "develop"
            to = "liubei"

        class FakeResult:
            success = True

        manager._deliver_message("caocao", FakeCmd(), FakeResult())  # type: ignore[arg-type]
        assert getattr(target_player, "_pending_alliance", None) == before

    def test_failed_message_is_not_delivered(self, manager: GameManager, monkeypatch):
        """执行失败的消息不投递（与 main.py 的 `if result.success` 口径一致）。"""
        target_player = manager._players["liubei"]

        class FakeCmd:
            type = "message"
            to = "liubei"
            content = "提议结盟"

        class FakeResult:
            success = False

        manager._deliver_message("caocao", FakeCmd(), FakeResult())  # type: ignore[arg-type]
        assert getattr(target_player, "_pending_alliance", None) is None


class TestAllianceReachableInWebPath:
    """端到端：Web 路径下同盟必须真的能形成（这才是玩家可见的结果）。"""

    def test_alliance_forms_within_turns(self, manager: GameManager):
        """跑若干回合，必须出现同盟。

        🔴 这是本文件的核心断言，也是「改坏必须变红」的那条：
        把 `_deliver_message` 的投递去掉，同盟必为 0（见 exp19 变体 A 实测）。
        """
        seen_alliance = False
        for _ in range(48):
            manager.process_turn()
            rels = manager.engine._diplomacy_relation_system.get_all_relations()
            if any(r.status == DiplomaticStatus.ALLIANCE for r in rels.values()):
                seen_alliance = True
                break
            if manager.engine.game_over:
                break

        assert seen_alliance, (
            "Web 路径跑满 48 回合都没出现任何同盟 —— "
            "外交消息未投递给 CLIPlayer，规则-AI 结构性无法结盟"
        )

    def test_war_also_forms_as_positive_control(self, manager: GameManager):
        """阳性对照：战争必须发生。

        若连战争都没有，说明外交状态压根没被推动，
        上面那条『没有同盟』的断言就不能用来判定『同盟不可达』
        （本项目纪律：零观测必须先有阳性对照，见 docs/pitfalls.md）。
        """
        seen_war = False
        for _ in range(48):
            manager.process_turn()
            rels = manager.engine._diplomacy_relation_system.get_all_relations()
            if any(r.status == DiplomaticStatus.WAR for r in rels.values()):
                seen_war = True
                break
            if manager.engine.game_over:
                break

        assert seen_war, "阳性对照未命中：48 回合内连战争都没发生，本轮结论不可用"
