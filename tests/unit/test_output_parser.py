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

    # ============================================================
    # parse_response：reasoning + commands 双返回
    # ============================================================

    def test_parse_response_new_format(self):
        """新格式：对象含 reasoning 与 commands"""
        parser = OutputParser()
        text = (
            '{"reasoning": "曹操势大，我应先固守荆州，再联孙抗曹。", '
            '"commands": [{"type": "develop", "params": {"city": "chengdu", "type": "economy"}}]}'
        )
        commands, reasoning = parser.parse_response(text)
        assert commands is not None
        assert len(commands) == 1
        assert commands[0]["type"] == "develop"
        assert reasoning == "曹操势大，我应先固守荆州，再联孙抗曹。"

    def test_parse_response_new_format_empty_commands(self):
        """新格式：commands 可为空数组"""
        parser = OutputParser()
        text = '{"reasoning": "本回合只观望，攒钱。", "commands": []}'
        commands, reasoning = parser.parse_response(text)
        assert commands == []
        assert reasoning == "本回合只观望，攒钱。"

    def test_parse_response_old_format_array(self):
        """旧格式：裸JSON数组 → reasoning 为空"""
        parser = OutputParser()
        commands, reasoning = parser.parse_response(
            '[{"type": "develop", "params": {"city": "成都", "type": "economy"}}]'
        )
        assert commands is not None
        assert len(commands) == 1
        assert reasoning == ""

    def test_parse_response_old_format_commands_key(self):
        """旧格式：只有 commands 键的对象 → reasoning 为空"""
        parser = OutputParser()
        commands, reasoning = parser.parse_response(
            '{"commands": [{"type": "recruit", "params": {"city": "成都", "troops": 300}}]}'
        )
        assert commands is not None
        assert len(commands) == 1
        assert reasoning == ""

    def test_parse_response_markdown_new_format(self):
        """markdown 代码块包裹的新格式"""
        parser = OutputParser()
        text = (
            '```json\n'
            '{"reasoning": "先发育，不打无准备之仗。", '
            '"commands": [{"type": "recruit", "params": {"city": "jianye", "troops": 800}}]}\n'
            '```'
        )
        commands, reasoning = parser.parse_response(text)
        assert commands is not None
        assert commands[0]["type"] == "recruit"
        assert reasoning == "先发育，不打无准备之仗。"

    def test_parse_response_prefix_text_as_reasoning(self):
        """旧格式数组前带文字 → 文字作为 reasoning 兜底（且去掉“思考：”标签）"""
        parser = OutputParser()
        text = (
            '思考：我判断袁绍威胁最大，先与其结盟，集中兵力打曹操。\n'
            '[{"type": "propose_alliance", "params": {"to": "yuanshao"}}]'
        )
        commands, reasoning = parser.parse_response(text)
        assert commands is not None
        assert commands[0]["type"] == "propose_alliance"
        assert reasoning == "我判断袁绍威胁最大，先与其结盟，集中兵力打曹操。"

    def test_parse_response_embedded_reasoning_preferred_over_prefix(self):
        """对象内 reasoning 优先于对象前的文字"""
        parser = OutputParser()
        text = (
            '以下是我的决策：\n'
            '{"reasoning": "北伐汉中，扩大纵深。", '
            '"commands": [{"type": "attack", "params": {"from": "changan", "to": "hanzhong", "troops": 1500, "general": "simayi"}}]}'
        )
        commands, reasoning = parser.parse_response(text)
        assert commands is not None
        assert commands[0]["type"] == "attack"
        assert reasoning == "北伐汉中，扩大纵深。"

    def test_parse_response_reasoning_only_object(self):
        """对象只有 reasoning（commands 缺失/被截断）→ 空命令但保住 reasoning"""
        parser = OutputParser()
        commands, reasoning = parser.parse_response(
            '{"reasoning": "当前兵力不足，本回合先攒钱。"}'
        )
        assert commands == []
        assert reasoning == "当前兵力不足，本回合先攒钱。"

    def test_parse_response_truncated_object_recovers_reasoning(self):
        """被截断的新格式对象（命令数组未闭合）→ 尽量保住 reasoning"""
        parser = OutputParser()
        text = (
            '{"reasoning": "先发展经济提升产出，兵不够不打仗。", '
            '"commands": [{"type": "develop", "params": {"city": "xuchang"'
        )
        commands, reasoning = parser.parse_response(text)
        assert commands is not None
        assert reasoning == "先发展经济提升产出，兵不够不打仗。"

    def test_parse_response_empty_input(self):
        """空输入 → (None, "")"""
        parser = OutputParser()
        assert parser.parse_response("") == (None, "")
        assert parser.parse_response("   ") == (None, "")

    def test_parse_response_invalid_input(self):
        """无JSON → (None, "")"""
        parser = OutputParser()
        assert parser.parse_response("完全无效的文字") == (None, "")

    def test_parse_commands_still_compatible(self):
        """parse_commands 旧接口仍只返回命令列表"""
        parser = OutputParser()
        result = parser.parse_commands(
            '{"reasoning": "x", "commands": [{"type": "develop", "params": {"city": "成都", "type": "economy"}}]}'
        )
        assert isinstance(result, list)
        assert result[0]["type"] == "develop"

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

    def test_validate_propose_alliance(self):
        """校验 propose_alliance 命令"""
        valid, _ = OutputParser.validate_command(
            {"type": "propose_alliance", "params": {"to": "caocao"}}
        )
        assert valid is True

    def test_validate_propose_alliance_missing_to(self):
        """propose_alliance 缺少 to 参数"""
        valid, err = OutputParser.validate_command(
            {"type": "propose_alliance", "params": {}}
        )
        assert valid is False
        assert "缺少必填参数" in err

    def test_validate_declare_war(self):
        """校验 declare_war 命令"""
        valid, _ = OutputParser.validate_command(
            {"type": "declare_war", "params": {"to": "yuanshao"}}
        )
        assert valid is True

    def test_validate_declare_war_missing_to(self):
        """declare_war 缺少 to 参数"""
        valid, err = OutputParser.validate_command(
            {"type": "declare_war", "params": {}}
        )
        assert valid is False
        assert "缺少必填参数" in err
