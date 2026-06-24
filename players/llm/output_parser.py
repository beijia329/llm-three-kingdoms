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

    def parse_commands(self, text: str) -> Optional[List[Dict[str, Any]]]:
        """解析LLM输出，提取命令列表

        Args:
            text: LLM返回的文本

        Returns:
            命令列表（每个命令是 dict），解析失败返回 None
        """
        if not text or not text.strip():
            logger.warning("LLM输出为空")
            return None

        # L2: 尝试直接解析
        result = self._try_direct_parse(text)
        if result is not None:
            return result

        # L2: 提取markdown代码块
        result = self._try_extract_code_block(text)
        if result is not None:
            return result

        # L2: 提取JSON数组/对象
        result = self._try_extract_json_structure(text)
        if result is not None:
            return result

        # L3: json_repair 修复
        result = self._try_repair_parse(text)
        if result is not None:
            return result

        # 全部失败
        logger.error("LLM输出解析全部失败:\n%s", text[:500])
        return None

    # ============================================================
    # 解析策略
    # ============================================================

    @staticmethod
    def _try_direct_parse(text: str) -> Optional[List[Dict[str, Any]]]:
        """尝试直接解析JSON

        Args:
            text: 待解析文本

        Returns:
            解析成功返回命令列表，失败返回None
        """
        text = text.strip()
        try:
            data = json.loads(text)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "commands" in data:
                return data["commands"]
            if isinstance(data, dict):
                return [data]
        except json.JSONDecodeError:
            pass
        return None

    @staticmethod
    def _try_extract_code_block(text: str) -> Optional[List[Dict[str, Any]]]:
        """从markdown代码块中提取JSON

        匹配 ```json 或 ``` 包裹的内容。

        Args:
            text: 待解析文本

        Returns:
            解析成功返回命令列表，失败返回None
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
                    if isinstance(data, list):
                        return data
                    if isinstance(data, dict) and "commands" in data:
                        return data["commands"]
                    if isinstance(data, dict):
                        return [data]
                except json.JSONDecodeError:
                    continue
        return None

    @staticmethod
    def _try_extract_json_structure(text: str) -> Optional[List[Dict[str, Any]]]:
        """从文本中提取JSON数组或对象

        使用正则匹配最外层的 [] 或 {}。

        Args:
            text: 待解析文本

        Returns:
            解析成功返回命令列表，失败返回None
        """
        # 先尝试匹配数组
        array_match = re.search(r'\[[\s\S]*\]', text)
        if array_match:
            try:
                data = json.loads(array_match.group())
                if isinstance(data, list):
                    return data
            except json.JSONDecodeError:
                pass

        # 再尝试匹配对象
        obj_match = re.search(r'\{[\s\S]*\}', text)
        if obj_match:
            try:
                data = json.loads(obj_match.group())
                if isinstance(data, dict) and "commands" in data:
                    return data["commands"]
                if isinstance(data, dict):
                    return [data]
            except json.JSONDecodeError:
                pass

        return None

    @staticmethod
    def _try_repair_parse(text: str) -> Optional[List[Dict[str, Any]]]:
        """使用json_repair修复后解析

        处理单引号、尾随逗号、注释等常见问题。

        Args:
            text: 待解析文本

        Returns:
            解析成功返回命令列表，失败返回None
        """
        try:
            # 尝试修复整个文本
            repaired = repair_json(text)
            data = json.loads(repaired)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and "commands" in data:
                return data["commands"]
            if isinstance(data, dict):
                return [data]
        except Exception:
            pass

        # 尝试只修复JSON部分
        try:
            match = re.search(r'[\{\[][\s\S]*[\}\]]', text)
            if match:
                repaired = repair_json(match.group())
                data = json.loads(repaired)
                if isinstance(data, list):
                    return data
                if isinstance(data, dict) and "commands" in data:
                    return data["commands"]
                if isinstance(data, dict):
                    return [data]
        except Exception:
            pass

        return None

    # ============================================================
    # 命令校验
    # ============================================================

    VALID_COMMAND_TYPES: List[str] = [
        "develop", "recruit", "attack", "reward",
        "explore", "message", "rumor",
        "propose_alliance", "declare_war",
    ]

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
        if cmd_type not in OutputParser.VALID_COMMAND_TYPES:
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
