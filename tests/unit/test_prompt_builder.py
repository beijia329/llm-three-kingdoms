"""Prompt构建器单元测试"""

from game.models import City, Army, General, GameObservation, CityInfo, DiplomacyMessage
from game.constants import CITY_LEVELS
from game.hex_grid import HexCoord
from players.llm.prompt_builder import PromptBuilder


class TestPromptBuilder:
    """Prompt构建器测试"""

    def test_build_system_prompt(self):
        """构建系统Prompt"""
        prompt = PromptBuilder.build_system_prompt("wei")
        assert "魏国" in prompt
        assert "发展经济" in prompt
        assert "24回合" in prompt

    def test_system_prompt_different_faction(self):
        """不同势力的Prompt"""
        shu = PromptBuilder.build_system_prompt("shu")
        assert "蜀国" in shu

    def test_build_commands_help(self):
        """构建命令说明"""
        help_text = PromptBuilder.build_commands_help()
        assert "develop" in help_text
        assert "recruit" in help_text
        assert "attack" in help_text
        assert "message" in help_text

    def test_build_thinking_prompt(self):
        """构建思维链引导"""
        prompt = PromptBuilder.build_thinking_prompt()
        assert "形势分析" in prompt
        assert "战略判断" in prompt
        assert "输出格式" in prompt
        assert "JSON" in prompt

    def test_build_state_prompt(self):
        """构建状态Prompt"""
        obs = _make_test_observation()
        state = PromptBuilder.build_state_prompt(obs)
        assert "成都" in state
        assert "第5/24回合" in state

    def test_build_full_prompt(self):
        """构建完整Prompt"""
        obs = _make_test_observation()
        messages = PromptBuilder.build_full_prompt(
            faction="shu",
            observation=obs,
            memory_context="## 历史摘要\n第1回合...",
        )
        assert len(messages) == 2
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert "蜀国" in messages[0]["content"]
        assert "成都" in messages[1]["content"]
        assert "第1回合" in messages[1]["content"]


def _make_test_observation() -> GameObservation:
    """创建测试观察"""
    lc = CITY_LEVELS[3]
    city = City(
        id="chengdu", name="成都", faction="shu", level=3,
        wall_hp=lc["wall_hp"], wall_max_hp=lc["wall_hp"],
        gold=1200, food=3500, population=30000, morale=72, garrison=3000,
        position=HexCoord(0, 0), neighbors=["hanzhong"],
        generals=["zhugeliang", "zhaoyun"],
    )
    general = General(
        id="zhugeliang", name="诸葛亮", faction="shu",
        command=92, politics=98, bravery=35, intelligence=100,
        loyalty=100, location="chengdu",
    )
    return GameObservation(
        faction="shu",
        turn=5,
        max_turns=24,
        own_cities=[city],
        own_armies=[],
        own_generals=[general],
        known_cities=[
            CityInfo(id="xuchang", name="许昌", faction="wei", level=5),
        ],
        visible_armies=[],
        map_topology={"chengdu": ["hanzhong"], "hanzhong": ["chengdu"]},
        received_messages=[
            DiplomacyMessage(
                id="m1", from_faction="wei", to_faction="shu",
                content="我们结盟吧", turn=3,
            )
        ],
        sent_messages=[],
        recent_events=[],
    )
