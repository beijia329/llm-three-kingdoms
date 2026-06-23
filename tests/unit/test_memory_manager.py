"""记忆管理器单元测试"""

from players.llm.memory_manager import MemoryManager


class TestMemoryManager:
    """记忆管理器测试"""

    def test_init(self):
        """初始化"""
        mm = MemoryManager(faction="wei")
        assert mm.faction == "wei"
        assert mm.long_term == ""
        assert len(mm.medium_term) == 0
        assert len(mm.short_term) == 0

    def test_add_turn_memory(self):
        """添加回合记忆"""
        mm = MemoryManager(faction="shu")
        mm.add_turn_memory(
            turn=1,
            thought="我要发展经济",
            commands=[{"type": "develop"}],
        )
        assert len(mm.short_term) == 1
        assert mm.short_term[0]["turn"] == 1

    def test_short_term_limit(self):
        """短期记忆不超过上限"""
        mm = MemoryManager(faction="wei")
        mm.max_short_term = 2

        for i in range(5):
            mm.add_turn_memory(
                turn=i + 1,
                thought=f"思考第{i+1}回合",
                commands=[],
            )

        # 短期最多2条
        assert len(mm.short_term) <= 2
        # 最早的记忆被压缩到中期
        assert len(mm.medium_term) > 0

    def test_set_long_term(self):
        """设置长期战略"""
        mm = MemoryManager(faction="wu")
        mm.set_long_term("联魏抗蜀，先取荆州")
        assert mm.long_term == "联魏抗蜀，先取荆州"

    def test_get_context_with_all_layers(self):
        """获取包含所有层级的上下文"""
        mm = MemoryManager(faction="wei")
        mm.set_long_term("统一天下")
        mm.add_turn_memory(turn=1, thought="发展", commands=[{"type": "develop"}])

        context = mm.get_context()
        assert "长期战略" in context
        assert "统一天下" in context
        assert "第1回合" in context

    def test_get_context_empty(self):
        """空记忆返回空字符串"""
        mm = MemoryManager(faction="shu")
        context = mm.get_context()
        assert context == ""

    def test_clear(self):
        """清除记忆"""
        mm = MemoryManager(faction="wei")
        mm.set_long_term("test")
        mm.add_turn_memory(turn=1, thought="test", commands=[])
        mm.clear()

        assert mm.long_term == ""
        assert len(mm.short_term) == 0
        assert len(mm.medium_term) == 0

    def test_compress_to_medium(self):
        """压缩到中期摘要"""
        memory = {
            "turn": 5,
            "thought": "详细思考...",
            "commands": [{"type": "develop"}, {"type": "recruit"}],
            "events": ["城市被攻占"],
        }
        summary = MemoryManager._compress_to_medium(memory)
        assert "第5回合" in summary
        assert "develop" in summary
        assert "城市被攻占" in summary
