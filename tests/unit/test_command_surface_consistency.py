"""命令「表面一致性」守卫

## 这个文件解决什么问题

加一条命令，原实现需要同步修改**多达 5 处平行清单**，漏改任何一处都表现为
**静默不一致**（后端认、前端不认，或 LLM 不知道有这条命令）：

| # | 位置 | 现状 |
|---|---|---|
| 1 | `game/engine.py` `execute_command` 分发 | ✅ 已收口到 `command_registry` |
| 2 | `players/llm/llm_player.py` `COMMAND_CLASSES` | ✅ 已改为查注册表 |
| 3 | `players/llm/output_parser.py` `VALID_COMMAND_TYPES` | ✅ 已改为查注册表 |
| 4 | `api/game_manager.py` `_deserialize_command` | ✅ 已改为按 `model_fields` 通用构造 |
| 5 | `web/src/constants/commands.ts`（名称 + 图标） | ⚠️ 跨语言，**无法**机械派生 |
| 6 | `players/llm/llm_player.py` `PARAM_MAPPING` | ⚠️ LLM 面向键名 ≠ 字段名，**有真实信息量**，无法派生 |

第 5、6 项**无法**从注册表机械推导（一个是 TypeScript，一个是刻意不同的
LLM 面向 schema）。既然推导不了，就**用测试把它们的完整性钉死**：
加命令时漏改会被 CI 挡住，而不是静默丢命令。

这就是本文件存在的全部意义 —— 它替代的不是代码，是**"靠人记得"**。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

import pytest

from game.command_registry import get_handler, registered_command_types
from players.llm.llm_player import PARAM_MAPPING, command_class_for
from players.llm.output_parser import OutputParser

_ROOT = Path(__file__).resolve().parents[2]
_COMMANDS_TS = _ROOT / "web" / "src" / "constants" / "commands.ts"

# 命令基类的字段，不属于各命令自己的参数
_BASE_FIELDS = {"type", "faction", "turn", "params"}


def _registered() -> List[str]:
    return registered_command_types()


def _sample_value(annotation: Any) -> Any:
    """按字段类型造一个能过校验的样例值。"""
    origin = getattr(annotation, "__origin__", None)
    args = getattr(annotation, "__args__", ())
    # Optional[str] / Union[str, None] —— 取第一个非 None 的类型
    if origin is not None and args:
        for a in args:
            if a is not type(None):  # noqa: E721
                return _sample_value(a)
    if annotation is int:
        return 1
    if annotation is float:
        return 1.0
    if annotation is bool:
        return True
    return "test_value"


def _sample_params(cmd_cls: type) -> Dict[str, Any]:
    """为某条命令造一份"看起来合法"的 params（键名 = 模型字段名）。"""
    params: Dict[str, Any] = {}
    for name, field in cmd_cls.model_fields.items():
        if name in _BASE_FIELDS:
            continue
        if field.is_required():
            params[name] = _sample_value(field.annotation)
    return params


# ============================================================
# 0. 注册表自身的健康检查（先证明被比较的集合非空）
# ============================================================


class TestRegistryHealth:
    def test_registry_is_not_empty(self):
        """注册表必须非空。

        🔴 这条不是凑数，是**防假绿**：本文件里多处断言形如
        「某个清单 == 注册表」。若注册表因为「引擎没被 import」而为空，
        那些断言会在**两侧都为空**的情况下**通过**。

        2026-10-03 实测就撞上了：`test_output_parser_whitelist_derives_from_registry`
        在注册表为空时「通过」了（`[] == []`）。同族问题见 `docs/pitfalls.md`
        的「假零命中」——**空输出 ≠ 不存在，必须有阳性对照**。

        根因已修：`game/command_registry` 现在惰性加载内置注册（幂等），
        不再依赖调用方的 import 顺序。本条断言是该修复的守卫。
        """
        types = _registered()
        assert types, "命令注册表为空 —— 惰性加载失效，本文件其余断言会假绿"
        # 阳性对照：至少应包含一个众所周知的内置命令
        assert "attack" in types
        assert "develop" in types


# ============================================================
# 1. 两处已派生的表面：必须与注册表逐字一致
# ============================================================


class TestDerivedSurfaces:
    def test_output_parser_whitelist_derives_from_registry(self):
        """LLM 输出白名单必须等于注册表（多一个/少一个都是漂移）。"""
        assert OutputParser.valid_command_types() == _registered()

    def test_command_class_for_matches_registry(self):
        """命令类查询必须返回注册表里的同一个类对象。"""
        for cmd_type in _registered():
            entry = get_handler(cmd_type)
            assert entry is not None
            assert command_class_for(cmd_type) is entry[0]

    def test_unknown_type_returns_none(self):
        assert command_class_for("no_such_command_type") is None


# ============================================================
# 2. PARAM_MAPPING（LLM 面向 schema）：无法派生，故强制完整性
# ============================================================


class TestParamMappingCompleteness:
    def test_every_registered_command_has_mapping(self):
        """每条已注册命令都必须有 LLM 参数映射。

        缺了它 → LLM 就算输出了这条命令，也会被静默丢弃
        （`command_class_for` 拿到类，但 `PARAM_MAPPING.get(..., {})` 返回空
        → 构造时缺必填字段 → 抛错被吞）。这是最隐蔽的一种漂移。
        """
        missing = [t for t in _registered() if t not in PARAM_MAPPING]
        assert not missing, f"这些命令已注册但没有 PARAM_MAPPING 条目: {missing}"

    def test_no_mapping_for_unregistered_command(self):
        """映射表里不该有幽灵条目（命令删了、映射没删）。"""
        ghosts = [t for t in PARAM_MAPPING if t not in _registered()]
        assert not ghosts, f"PARAM_MAPPING 里有未注册的命令: {ghosts}"

    def test_mapping_targets_are_real_model_fields(self):
        """每个映射目标都必须是该 Command 类的真实字段。

        写错字段名的后果：Pydantic 拒绝未知字段 → 命令构造失败 → 静默丢失。
        """
        bad: List[str] = []
        for cmd_type, mapping in PARAM_MAPPING.items():
            cmd_cls = command_class_for(cmd_type)
            assert cmd_cls is not None
            for llm_key, model_key in mapping.items():
                if model_key not in cmd_cls.model_fields:
                    bad.append(f"{cmd_type}: {llm_key} -> {model_key}（无此字段）")
        assert not bad, f"PARAM_MAPPING 指向不存在的字段: {bad}"

    def test_mapping_covers_all_required_fields(self):
        """每条命令的**必填**字段都必须能被 LLM 提供。

        若某个必填字段没有任何映射来源，LLM 永远无法构造出合法命令
        → 这条命令对 LLM 来说等于不存在。
        """
        bad: List[str] = []
        for cmd_type, mapping in PARAM_MAPPING.items():
            cmd_cls = command_class_for(cmd_type)
            assert cmd_cls is not None
            provided = set(mapping.values())
            for name, field in cmd_cls.model_fields.items():
                if name in _BASE_FIELDS:
                    continue
                if field.is_required() and name not in provided:
                    bad.append(f"{cmd_type}.{name}")
        assert not bad, f"这些必填字段无法由 LLM 提供（该命令对 LLM 不可达）: {bad}"


# ============================================================
# 3. 前端反序列化：逐条命令做真实往返
# ============================================================


class TestDeserializeRoundTrip:
    @pytest.mark.parametrize("cmd_type", _registered())
    def test_deserialize_every_registered_command(self, cmd_type: str):
        """`GameManager._deserialize_command` 必须能反序列化每一条已注册命令。

        这是「后端认命令、但前端发来的它解不出来」这类不一致的直接守卫。
        """
        from api.game_manager import GameManager

        cmd_cls = command_class_for(cmd_type)
        assert cmd_cls is not None
        params = _sample_params(cmd_cls)

        raw = {"type": cmd_type, "faction": "caocao", "turn": 3, "params": params}
        cmd = GameManager._deserialize_command(raw)

        assert isinstance(cmd, cmd_cls), (
            f"{cmd_type} 反序列化出的类型不对: {type(cmd).__name__} != {cmd_cls.__name__}"
        )
        assert cmd.faction == "caocao"
        assert cmd.turn == 3
        # 每个样例参数都应落到模型上（防止「映射写错字段名、值被丢弃」）
        for key, value in params.items():
            assert getattr(cmd, key) == value, (
                f"{cmd_type}.{key} 未被正确反序列化: "
                f"{getattr(cmd, key)!r} != {value!r}"
            )

    def test_unknown_type_falls_back_to_base_command(self):
        """未注册类型保持原语义：返回基类 Command，由引擎判为未知命令。"""
        from api.game_manager import GameManager

        cmd = GameManager._deserialize_command(
            {"type": "no_such_type", "faction": "han", "turn": 1, "params": {"x": 1}}
        )
        assert type(cmd) is not None
        assert cmd.type == "no_such_type"


# ============================================================
# 4. 前端列表（跨语言，只能在测试里对账）
# ============================================================


def _ts_declared_command_types() -> set:
    """从 `web/src/constants/commands.ts` 抽出已声明的命令类型 key。

    只做正则提取（不引入 TS 解析器）：抓 `对象字面量` 里 `标识符:` 形式的键。
    够用即可 —— 目标是「漏改会被发现」，不是做完整 TS 语义分析。
    """
    if not _COMMANDS_TS.exists():  # pragma: no cover - 文件缺失时给出明确原因
        pytest.skip(f"未找到 {_COMMANDS_TS}")
    text = _COMMANDS_TS.read_text(encoding="utf-8")

    keys: set = set()
    # 逐个 `{...}` 块抓 key（嵌套一层不影响：只会多抓，不会漏抓我们关心的键）
    for block in re.findall(r"\{([^{}]*)\}", text):
        for key in re.findall(r"[\n,]\s*([a-z_][a-z0-9_]*)\s*:", block):
            keys.add(key)
    return keys


class TestFrontendConsistency:
    def test_frontend_declares_every_registered_command(self):
        """前端 `commands.ts` 必须声明每条已注册命令。

        这是跨语言边界，**无法**由注册表自动派生，只能对账。
        漏声明的后果：前端认不出这条命令 → 不显示名称/图标，
        或事件流里出现裸英文类型名。
        """
        declared = _ts_declared_command_types()
        missing = [t for t in _registered() if t not in declared]
        assert not missing, (
            f"这些命令已注册但前端 commands.ts 未声明: {missing}；"
            f"（前端已声明: {sorted(declared)}）"
        )
