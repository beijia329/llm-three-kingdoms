"""输出解析器（五层防御）

解析LLM输出的JSON命令，提供多层容错机制。

防御层级：
L1: Prompt约束（预防，由PromptBuilder负责）
L2: 语法约束 - 正则提取JSON
L3: 智能提取 - json_repair 修复
L4: Schema校验 - Pydantic校验
L5: 重试+降级 - 自动重试和兜底

参考设计文档：docs/design/llm-integration.md 第三章
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from json_repair import repair_json

logger = logging.getLogger(__name__)


class OutputParser:
    """LLM输出解析器

    将LLM返回的文本解析为结构化的命令列表。
    支持多种格式容错。
    """

    # ============================================================
    # 主入口
    # ============================================================

    def parse_response(
        self,
        text: str,
    ) -> Tuple[Optional[List[Dict[str, Any]]], str]:
        """解析LLM输出，同时提取「决策理由」与「命令列表」

        兼容两种格式：
        - 新格式（推荐）：``{"reasoning": "...", "commands": [...]}``
          → reasoning 取对象里的 reasoning 字段
        - 旧格式：裸 JSON 数组 ``[...]``（或单个命令对象 / ``{"commands":[...]}``）
          → reasoning 为空；若数组前后带文字，则把 JSON 之前的文字作为 reasoning 兜底

        另外兼容 markdown 代码块包裹（```json ... ```）与 ``思考：...\\n[...]`` 这类
        前后夹带解释文字的输出。

        Args:
            text: LLM返回的文本

        Returns:
            (命令列表, reasoning文本)。
            解析失败时命令列表为 None，reasoning 为 ""。
        """
        if not text or not text.strip():
            logger.warning("LLM输出为空")
            return None, ""

        # L2: 尝试直接解析
        commands, reasoning = self._try_direct_parse(text)
        if commands is not None:
            return commands, reasoning

        # L2: 提取markdown代码块
        commands, reasoning = self._try_extract_code_block(text)
        if commands is not None:
            return commands, reasoning

        # L2: 提取JSON数组/对象
        commands, reasoning = self._try_extract_json_structure(text)
        if commands is not None:
            return commands, reasoning

        # L3: json_repair 修复
        commands, reasoning = self._try_repair_parse(text)
        if commands is not None:
            return commands, reasoning

        # 全部失败
        logger.error("LLM输出解析全部失败:\n%s", text[:500])
        return None, ""

    def parse_commands(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """解析LLM输出，提取命令列表（向后兼容接口）

        内部委托给 :meth:`parse_response`，仅返回命令列表。
        需要同时拿到 decision reasoning 时请改用 ``parse_response``。

        Args:
            text: LLM返回的文本

        Returns:
            命令列表（每个命令是 dict），解析失败返回 None
        """
        commands, _ = self.parse_response(text)
        return commands

    # ============================================================
    # 解析策略
    #
    # 每个策略返回 (commands, reasoning)：
    #   - commands 为 None 表示该策略未命中
    #   - commands 为 [] 或 [...] 表示命中
    # ============================================================

    @staticmethod
    def _normalize(
        data: Any,
        prefix_text: str = "",
    ) -> Tuple[Optional[List[Dict[str, Any]]], str]:
        """        将解析出的JSON数据规范化为 (commands, reasoning)

        - dict 且含 commands 数组 → 新格式：commands=data["commands"]，
          reasoning 优先取对象内 reasoning/thought/strategy，缺失时回退 prefix_text
        - dict 无 commands 且无 type（典型为被截断、只剩 reasoning 的对象）→
          commands=[]，reasoning 取对象内的 reasoning/thought/strategy（保住决策理由）
        - 其他 dict（含 type 的单命令对象）→ [data]，reasoning=prefix_text
        - list → 旧格式裸数组：commands=data，reasoning=prefix_text

        Args:
            data: json.loads 后的数据
            prefix_text: JSON 之前夹带的解释文字（兜底 reasoning）

        Returns:
            (命令列表, reasoning文本)；无法规范化时 (None, "")
        """
        if isinstance(data, dict):
            if isinstance(data.get("commands"), list):
                embedded = (
                    data.get("reasoning")
                    or data.get("thought")
                    or data.get("strategy")
                    or ""
                )
                if not isinstance(embedded, str):
                    embedded = str(embedded)
                embedded = embedded.strip()
                return data["commands"], embedded or prefix_text
            # 无有效 commands 字段：以 type 是否存在区分「单命令对象」与「被截断的响应」
            if "type" not in data:
                embedded = (
                    data.get("reasoning")
                    or data.get("thought")
                    or data.get("strategy")
                    or ""
                )
                if not isinstance(embedded, str):
                    embedded = str(embedded)
                embedded = embedded.strip()
                if embedded or "reasoning" in data or "thought" in data:
                    return [], (embedded or prefix_text)
            return [data], prefix_text
        if isinstance(data, list):
            return data, prefix_text
        return None, ""

    @staticmethod
    def _extract_leading_text(text: str, json_start: int) -> str:
        """提取JSON之前的文字，作为 reasoning 兜底

        会去掉 markdown 代码围栏与“思考：/策略：/reasoning:”这类引导标签。

        Args:
            text: 完整文本
            json_start: JSON 子串在 text 中的起始下标

        Returns:
            清洗后的前置文字；无有效内容时返回 ""
        """
        prefix = text[:json_start]
        if not prefix.strip():
            return ""
        # 去掉 markdown 代码围栏标记
        prefix = prefix.replace("```json", "").replace("```JSON", "").replace("```", "")
        prefix = prefix.strip()
        # 去掉“思考：/策略：/reasoning:”等引导标签
        prefix = re.sub(
            r'^(思考|策略|理由|分析|判断|reasoning|thinking)\s*[:：]\s*',
            '',
            prefix,
            flags=re.IGNORECASE,
        ).strip()
        return prefix

    @staticmethod
    def _try_direct_parse(text: str) -> Tuple[Optional[List[Dict[str, Any]]], str]:
        """尝试直接解析JSON

        Args:
            text: 待解析文本

        Returns:
            (命令列表, reasoning)，未命中返回 (None, "")
        """
        stripped = text.strip()
        try:
            data = json.loads(stripped)
        except json.JSONDecodeError:
            return None, ""
        return OutputParser._normalize(data, "")

    @staticmethod
    def _try_extract_code_block(text: str) -> Tuple[Optional[List[Dict[str, Any]]], str]:
        """从markdown代码块中提取JSON

        匹配 ```json 或 ``` 包裹的内容。代码块之前的文字作为 reasoning 兜底。

        Args:
            text: 待解析文本

        Returns:
            (命令列表, reasoning)，未命中返回 (None, "")
        """
        # 匹配 ```json ... ``` 或 ``` ... ```
        patterns = [
            r'```(?:json)\s*\n?([\s\S]*?)\n?```',
            r'```\s*\n?([\s\S]*?)\n?```',
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                content = match.group(1).strip()
                try:
                    data = json.loads(content)
                except json.JSONDecodeError:
                    continue
                prefix = OutputParser._extract_leading_text(text, match.start(1))
                commands, reasoning = OutputParser._normalize(data, prefix)
                if commands is not None:
                    return commands, reasoning
        return None, ""

    @staticmethod
    def _try_extract_json_structure(text: str) -> Tuple[Optional[List[Dict[str, Any]]], str]:
        """从文本中提取JSON数组或对象

        使用正则匹配最外层的 [] 或 {}。优先识别含 commands 字段的对象（新格式），
        避免外层对象的 reasoning 被内层 commands 数组的正则误吞。

        Args:
            text: 待解析文本

        Returns:
            (命令列表, reasoning)，未命中返回 (None, "")
        """
        obj_match = re.search(r'\{[\s\S]*\}', text)

        # 1) 优先匹配新格式对象 {"reasoning":..., "commands":[...]}
        if obj_match:
            try:
                data = json.loads(obj_match.group())
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict) and (
                "commands" in data or "reasoning" in data or "thought" in data
            ):
                prefix = OutputParser._extract_leading_text(text, obj_match.start())
                commands, reasoning = OutputParser._normalize(data, prefix)
                if commands is not None:
                    return commands, reasoning

        # 2) 匹配数组（旧格式裸数组）
        array_match = re.search(r'\[[\s\S]*\]', text)
        if array_match:
            try:
                data = json.loads(array_match.group())
            except json.JSONDecodeError:
                data = None
            if isinstance(data, list):
                prefix = OutputParser._extract_leading_text(text, array_match.start())
                return data, prefix

        # 3) 单个命令对象（旧格式）
        if obj_match:
            try:
                data = json.loads(obj_match.group())
            except json.JSONDecodeError:
                data = None
            if isinstance(data, dict):
                prefix = OutputParser._extract_leading_text(text, obj_match.start())
                commands, reasoning = OutputParser._normalize(data, prefix)
                if commands is not None:
                    return commands, reasoning

        return None, ""

    @staticmethod
    def _try_repair_parse(text: str) -> Tuple[Optional[List[Dict[str, Any]]], str]:
        """使用json_repair修复后解析

        处理单引号、尾随逗号、注释等常见问题。

        Args:
            text: 待解析文本

        Returns:
            (命令列表, reasoning)，未命中返回 (None, "")
        """
        # 尝试修复整个文本
        try:
            repaired = repair_json(text)
            data = json.loads(repaired)
            commands, reasoning = OutputParser._normalize(data, "")
            if commands is not None:
                return commands, reasoning
        except Exception:
            pass

        # 尝试只修复JSON部分
        try:
            match = re.search(r'[\{\[][\s\S]*[\}\]]', text)
            if match:
                repaired = repair_json(match.group())
                data = json.loads(repaired)
                prefix = OutputParser._extract_leading_text(text, match.start())
                commands, reasoning = OutputParser._normalize(data, prefix)
                if commands is not None:
                    return commands, reasoning
        except Exception:
            pass

        return None, ""

    # ============================================================
    # 命令校验
    # ============================================================

    @classmethod
    def valid_command_types(cls) -> List[str]:
        """LLM 输出允许的命令类型（**由命令注册表派生**）。

        原实现是一份手写的平行清单，加一条命令必须来这儿同步一次，
        漏改的后果是「引擎认、但 LLM 的输出被解析器判为非法」。
        现直接读 `game.command_registry`，新增命令（含 mod 注册的命令）
        自动进入白名单。

        🔴 必须**惰性读取**：注册发生在 `game/engine.py` 模块底部，
        若在 import 期就取快照，会遇到「引擎尚未 import → 注册表为空」。
        """
        from game.command_registry import registered_command_types

        return registered_command_types()

    @staticmethod
    def validate_command(
        cmd: Dict[str, Any],
    ) -> Tuple[bool, str]:
        """校验单个命令的合法性

        Args:
            cmd: 命令字典

        Returns:
            (是否合法, 错误信息)
        """
        # 检查类型
        cmd_type = cmd.get("type", "")
        if cmd_type not in OutputParser.valid_command_types():
            return False, f"无效命令类型: {cmd_type}"

        # 检查参数
        params = cmd.get("params", {})
        if not isinstance(params, dict):
            return False, "params 必须是字典"

        # 各命令的必填参数
        required_params = {
            "develop": ["city", "type"],
            "recruit": ["city", "troops"],
            "attack": ["from", "to", "troops", "general"],
            "reward": ["general", "gold"],
            "explore": ["city"],
            "message": ["to", "content"],
            "rumor": ["city"],
            "propose_alliance": ["to"],
            "declare_war": ["to"],
        }

        missing = [
            p for p in required_params.get(cmd_type, [])
            if p not in params
        ]
        if missing:
            return False, f"缺少必填参数: {missing}"

        # 数值校验（含类型规整：float→int）
        if cmd_type == "recruit":
            troops = params.get("troops", 0)
            if isinstance(troops, float):
                troops = int(troops)
                params["troops"] = troops
            if not isinstance(troops, int) or troops <= 0:
                return False, "troops 必须是正整数"

        if cmd_type == "attack":
            troops = params.get("troops", 0)
            if isinstance(troops, float):
                troops = int(troops)
                params["troops"] = troops
            if not isinstance(troops, int) or troops <= 0:
                return False, "troops 必须是正整数"

        if cmd_type == "reward":
            gold = params.get("gold", 0)
            if isinstance(gold, float):
                gold = int(gold)
                params["gold"] = gold
            if not isinstance(gold, int) or gold <= 0:
                return False, "gold 必须是正整数"

        # develop type 校验
        if cmd_type == "develop":
            dev_type = params.get("type", "")
            if dev_type not in ("economy", "military", "culture"):
                return False, f"无效发展类型: {dev_type}"

        return True, ""

    @staticmethod
    def filter_commands(
        commands: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """过滤非法命令，只保留合法的

        Args:
            commands: 原始命令列表

        Returns:
            合法命令列表
        """
        valid: List[Dict[str, Any]] = []
        for cmd in commands:
            is_valid, error = OutputParser.validate_command(cmd)
            if is_valid:
                valid.append(cmd)
            else:
                logger.warning("过滤非法命令: %s (%s)", cmd, error)
        return valid
