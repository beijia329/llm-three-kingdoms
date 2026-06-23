"""输出解析器单元测试"""

from players.llm.output_parser import OutputParser


class TestOutputParser:
    """输出解析器测试"""

    def test_parse_valid_json(self):
        """解析标准JSON"""
        parser = OutputParser()
        result = parser.parse_commands('[{"type": "develop", "params": {"city": "成都", "type": "economy"}}]')
        assert result is not None
        assert len(result) == 1
        assert result[0]["type"] == "develop"

    def test_parse_empty(self):
        """空输入返回None"""
        parser = OutputParser()
        assert parser.parse_commands("") is None
        assert parser.parse_commands("   ") is None

    def test_parse_markdown_json(self):
        """解析markdown代码块包裹的JSON"""
        parser = OutputParser()
        text = '```json\n[{"type": "recruit", "params": {"city": "成都", "troops": 500}}]\n```'
        result = parser.parse_commands(text)
        assert result is not None
        assert result[0]["type"] == "recruit"

    def test_parse_markdown_no_lang(self):
        """解析无语言标记的代码块"""
        parser = OutputParser()
        text = '```\n[{"type": "attack", "params": {"from": "成都", "to": "汉中", "troops": 1000, "general": "赵云"}}]\n```'
        result = parser.parse_commands(text)
        assert result is not None
        assert result[0]["type"] == "attack"

    def test_parse_with_surrounding_text(self):
        """解析前后有解释文字的JSON"""
        parser = OutputParser()
        text = '先分析局势...\n[{"type": "develop", "params": {"city": "成都", "type": "culture"}}]\n以上就是我的决策。'
        result = parser.parse_commands(text)
        assert result is not None
        assert result[0]["params"]["type"] == "culture"

    def test_parse_single_command(self):
        """解析单个命令（非数组）"""
        parser = OutputParser()
        result = parser.parse_commands('{"type": "develop", "params": {"city": "成都", "type": "economy"}}')
        assert result is not None
        assert len(result) == 1

    def test_parse_commands_key(self):
        """解析带commands键的对象"""
        parser = OutputParser()
        result = parser.parse_commands('{"commands": [{"type": "recruit", "params": {"city": "成都", "troops": 300}}]}')
        assert result is not None
        assert len(result) == 1

    def test_parse_single_quotes(self):
        """解析单引号JSON"""
        parser = OutputParser()
        result = parser.parse_commands("[{'type': 'develop', 'params': {'city': '成都', 'type': 'economy'}}]")
        assert result is not None
        assert result[0]["type"] == "develop"

    def test_parse_trailing_comma(self):
        """解析尾随逗号"""
        parser = OutputParser()
        result = parser.parse_commands('[{"type": "develop", "params": {"city": "成都", "type": "economy",}}]')
        assert result is not None
        assert len(result) == 1

    def test_parse_invalid(self):
        """完全无效的输入"""
        parser = OutputParser()
        result = parser.parse_commands("这是一段完全无效的文字，没有JSON")
        assert result is None

    def test_filter_valid_commands(self):
        """过滤合法命令"""
        commands = [
            {"type": "develop", "params": {"city": "成都", "type": "economy"}},
            {"type": "invalid", "params": {}},
            {"type": "recruit", "params": {"city": "成都", "troops": 500}},
        ]
        filtered = OutputParser.filter_commands(commands)
        assert len(filtered) == 2
        assert filtered[0]["type"] == "develop"

    def test_validate_develop(self):
        """校验develop命令"""
        valid, _ = OutputParser.validate_command(
            {"type": "develop", "params": {"city": "成都", "type": "economy"}}
        )
        assert valid is True

    def test_validate_develop_bad_type(self):
        """校验无效发展类型"""
        valid, err = OutputParser.validate_command(
            {"type": "develop", "params": {"city": "成都", "type": "invalid"}}
        )
        assert valid is False
        assert "无效发展类型" in err

    def test_validate_attack_missing_params(self):
        """进攻缺少参数"""
        valid, err = OutputParser.validate_command(
            {"type": "attack", "params": {"from": "成都"}}
        )
        assert valid is False
        assert "缺少必填参数" in err

    def test_validate_recruit_negative(self):
        """征兵负数"""
        valid, err = OutputParser.validate_command(
            {"type": "recruit", "params": {"city": "成都", "troops": -100}}
        )
        assert valid is False
