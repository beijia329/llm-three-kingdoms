"""FastAPI 端点集成测试（REST + WebSocket）

背景
----
REST + WebSocket 是前端的**唯一入口**，但在 v4.0.0 之前
`grep -rl "TestClient\\|api.server" tests/` 零命中 —— 即所有前端可见行为
（状态结构、命令执行、回合推进、实时流）**没有任何回归保护**。
本文件补上这一层。

运行环境
--------
本文件需要 fastapi + starlette（TestClient）。项目 `./venv` **未安装 fastapi**，
请用系统解释器运行：

    export SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy
    /Library/Frameworks/Python.framework/Versions/3.12/bin/python3 \\
        -m pytest tests/integration/test_api_endpoints.py -q

在缺 fastapi 的环境（如 ./venv）下，本文件被整体 skip（不报错），
不影响其余测试的收集与运行。

硬约束
------
全部用 ``use_llm=False`` 的 CLI 模式构造对局：**不调用真实 LLM、不联网、不花钱**。
"""

from __future__ import annotations

import pytest

# fastapi/starlette 仅在系统解释器下存在；缺失时整体跳过而非让收集失败。
# （必须放在 import api.server 之前 —— 后者顶层依赖 fastapi。）
_testclient_mod = pytest.importorskip(
    "fastapi.testclient",
    reason="需要 fastapi（./venv 未安装，请用系统 python3.12 运行本文件）",
)
TestClient = _testclient_mod.TestClient

from api.server import app  # noqa: E402
from game.constants import FACTIONS  # noqa: E402

# 小规模对局：只 2 方、6 回合 —— 快、确定、且不涉及任何真实 LLM 调用
_PARTICIPANTS = ["caocao", "yuanshao"]
_BASE_CFG = {"use_llm": False, "factions": _PARTICIPANTS, "max_turns": 6, "seed": 42}


# ============================================================
# fixtures / helpers
# ============================================================

@pytest.fixture()
def client():
    """每个测试独立的 TestClient。

    用 ``with`` 进入以触发 lifespan → 初始化全局 ``_manager``；
    退出时 lifespan 收尾把 ``_manager`` 置回 None，测试间互不污染。
    """
    with TestClient(app) as c:
        yield c


def _reset(client, **overrides) -> dict:
    """按给定配置重开一局并返回新的状态字典。"""
    cfg = dict(_BASE_CFG)
    cfg.update(overrides)
    r = client.post("/api/reset", json=cfg)
    assert r.status_code == 200, r.text
    return r.json()


def _first_city_of(state: dict, faction: str) -> str:
    for cid, c in state["cities"].items():
        if c.get("faction") == faction:
            return cid
    raise AssertionError(f"势力 {faction} 开局无城市（测试前提不成立）")


def _city_of_other_faction(state: dict, faction: str) -> str:
    for cid, c in state["cities"].items():
        if c.get("faction") != faction:
            return cid
    raise AssertionError("找不到不属于该势力的城市（测试前提不成立）")


def _live_manager():
    """取当前 lifespan 建立的全局 GameManager（供直接注入内部状态用）。"""
    from api import server as _server
    assert _server._manager is not None, "lifespan 未建立 _manager"
    return _server._manager


@pytest.fixture()
def records_tmp_dir():
    """临时目录，专供战绩落盘测试使用。

    不用 pytest 内置 ``tmp_path``：本机 WorkBuddy 沙箱 shim 会拦截
    ``pytest-of-<user>`` 基目录的创建，并在该目录已存在时抛
    ``PermissionError: EEXIST`` → tmp_path 相关测试在**本地报错**（CI 不受影响）。
    改用原生 ``tempfile.mkdtemp()`` 建唯一目录，本地与 CI 均可跑通。
    """
    import shutil
    import tempfile
    from pathlib import Path

    d = Path(tempfile.mkdtemp(prefix="sanguo-records-"))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ============================================================
# GET /api/state
# ============================================================

class TestGetState:
    """状态查询：结构完整性 + 前端降级提示字段"""

    def test_state_contract_fields_present(self, client):
        state = _reset(client)
        for key in (
            "cities", "armies", "generals", "faction_stats", "events",
            "reasoning", "hex_map", "provinces", "turn", "game_over",
            "max_turns", "seed",
        ):
            assert key in state, f"/api/state 缺少前端依赖字段: {key}"
        assert state["turn"] == 1
        assert state["game_over"] is False
        assert len(state["cities"]) >= 19
        # faction_stats 必须覆盖全部势力定义（前端左右两栏据此渲染）
        assert len(state["faction_stats"]) == len(FACTIONS)

    def test_state_events_is_a_list(self, client):
        state = _reset(client)
        assert isinstance(state["events"], list)
        # 开局至少有一条"游戏开始"事件
        assert any("游戏开始" in e.get("text", "") for e in state["events"])

    def test_state_exposes_llm_degradation_fields(self, client):
        """前端「降级提示」依赖这 5 个字段，缺一前端无法正确提示用户。"""
        state = _reset(client)
        for key in ("llm_requested", "llm_active", "llm_error", "llm_model", "llm_factions"):
            assert key in state, f"缺少前端降级提示字段: {key}"
        # use_llm=False：未请求、未启用、无错误、无模型
        assert state["llm_requested"] is False
        assert state["llm_active"] is False
        assert state["llm_error"] == ""
        assert state["llm_model"] == ""
        assert state["llm_factions"] == _PARTICIPANTS

    def test_state_llm_requested_but_no_key_reports_degradation(self, client, monkeypatch):
        """use_llm=True 但无 key：必须回退 CLI **并显式给出原因**，不能静默。

        历史事故：key 缺失时前端无任何提示，用户以为在跑 LLM，
        实际已回退 CLIPlayer，决策 tab 恒空，极难排查。这条断言锁死该契约。
        """
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        state = _reset(client, use_llm=True)
        assert state["llm_requested"] is True
        assert state["llm_active"] is False        # 无 key → 回退 CLI
        assert state["llm_error"]                  # 必须非空：告知用户为什么降级
        assert state["llm_model"] == ""

    def test_state_reasoning_limit_query_param(self, client):
        """`?reasoning_limit=N` 只返回最近 N 条；省略则返回全部。"""
        _reset(client)
        mgr = _live_manager()
        mgr._reasoning = [
            {"turn": i, "faction": "caocao", "reasoning": f"r{i}", "commands": []}
            for i in range(5)
        ]
        # 省略参数 → 全部（与旧行为一致）
        assert len(client.get("/api/state").json()["reasoning"]) == 5
        # 传 2 → 末尾 2 条
        body = client.get("/api/state", params={"reasoning_limit": 2}).json()
        assert [r["reasoning"] for r in body["reasoning"]] == ["r3", "r4"]
        # 传 0 → 空（不返回）
        assert client.get("/api/state", params={"reasoning_limit": 0}).json()["reasoning"] == []


# ============================================================
# POST /api/reset
# ============================================================

class TestReset:
    """重开对局：参数生效 + 回合归位"""

    def test_reset_applies_params_and_resets_turn(self, client):
        # 先推进到非初始态，确保"归位"是真的发生了
        _reset(client, seed=42, max_turns=6)
        client.post("/api/next-turn")
        assert client.get("/api/state").json()["turn"] == 2

        state = _reset(client, seed=7, max_turns=9, factions=["caocao"])
        assert state["turn"] == 1
        assert state["game_over"] is False
        assert state["seed"] == 7
        assert state["max_turns"] == 9
        # 只给 caocao 建玩家
        assert state["llm_factions"] == ["caocao"]

    def test_reset_with_unknown_field_returns_422(self):
        """🔴 已修复（v4.0.1）：未知字段返回 422 并列出可用字段。

        原始缺陷（2026-10-03 engineering-lead 写端点测试时实测发现）：
        `POST /api/reset` 把请求体直接 `GameConfig(**config)`，传未知字段抛
        `TypeError` → **HTTP 500**。前端拿到 500 无法区分"参数写错"与"服务崩了"。

        修复：`api/server.py` 捕获 TypeError → 422，并在 detail 里回出
        **全部可用字段名**，调用方可以直接照着改。
        本测试由"固化现状（断言 500）"改为"锁定修复后行为（断言 422）"。
        """
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.post("/api/reset", json={"bogus_param": 1})
        assert r.status_code == 422
        detail = r.json().get("detail", "")
        assert "bogus_param" in detail          # 指出非法字段
        assert "faction_models" in detail       # 并列出可用字段，便于调用方自查


# ============================================================
# POST /api/next-turn
# ============================================================

class TestNextTurn:
    """推进回合：返回结构 + 状态迁移 + 终局"""

    def test_next_turn_advances_and_returns_summary(self, client):
        _reset(client)
        r = client.post("/api/next-turn")
        assert r.status_code == 200
        body = r.json()
        for key in ("turn", "battles_fought", "game_over", "winner", "ai_events"):
            assert key in body, f"/api/next-turn 缺少字段: {key}"
        assert isinstance(body["turn"], int)
        assert isinstance(body["battles_fought"], int)
        assert body["battles_fought"] >= 0
        assert body["game_over"] is False
        # 返回的 turn 是"本回合刚处理完的那一回合"；引擎回合号已前进一步
        assert body["turn"] == 1
        assert client.get("/api/state").json()["turn"] == 2

    def test_next_turn_reaches_game_over_within_max_turns(self, client):
        _reset(client, max_turns=4)
        last = None
        for _ in range(10):  # 安全上限，避免死循环
            last = client.post("/api/next-turn").json()
            if last["game_over"]:
                break
        assert last is not None and last["game_over"] is True
        # winner 为 None（平局）或合法势力键
        assert last["winner"] is None or last["winner"] in FACTIONS
        assert client.get("/api/state").json()["game_over"] is True


# ============================================================
# POST /api/command
# ============================================================

class TestCommand:
    """命令执行：成功路径 + 非法参数/非法目标被拒"""

    def test_develop_own_city_succeeds(self, client):
        state = _reset(client)
        city = _first_city_of(state, "caocao")
        r = client.post("/api/command", json={
            "type": "develop", "faction": "caocao", "turn": 1,
            "params": {"city": city, "develop_type": "economy"},
        })
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is True, body
        assert body["type"] == "develop"

    def test_unknown_command_type_rejected(self, client):
        _reset(client)
        body = client.post("/api/command", json={
            "type": "no_such_command", "faction": "caocao", "turn": 1, "params": {},
        }).json()
        assert body["success"] is False
        assert "未知命令类型" in body.get("description", "")

    def test_missing_required_param_rejected_without_crash(self, client):
        """缺参数应在 API 层被捕获为 success=False，而不是 500 崩服务。"""
        _reset(client)
        r = client.post("/api/command", json={
            "type": "develop", "faction": "caocao", "turn": 1, "params": {},
        })
        assert r.status_code == 200
        body = r.json()
        assert body["success"] is False
        assert "error" in body

    def test_develop_enemy_city_rejected(self, client):
        """对他方城市下令发展 → 引擎级校验拒绝（不是异常，是干净的失败）。"""
        state = _reset(client)
        enemy_city = _city_of_other_faction(state, "caocao")
        body = client.post("/api/command", json={
            "type": "develop", "faction": "caocao", "turn": 1,
            "params": {"city": enemy_city, "develop_type": "economy"},
        }).json()
        assert body["success"] is False
        assert "不属于" in body.get("description", "")


# ============================================================
# WebSocket /ws/game
# ============================================================

class TestWebSocket:
    """实时流：连接握手 + 命令往返 + 错误路径

    注意：服务端在连接后**首发消息类型是 "state"**（不是 "init"）。
    "init" 是**客户端 → 服务端**消息（用于携带 seed / 阵营 / LLM 配置重建对局），
    服务端并无名为 "init" 的下行消息。此处按真实行为断言。
    """

    def test_receives_initial_state_on_connect(self, client):
        _reset(client)
        with client.websocket_connect("/ws/game") as ws:
            msg = ws.receive_json()
        assert msg["type"] == "state"
        assert "data" in msg
        assert msg["data"]["turn"] == 1
        assert "cities" in msg["data"]

    def test_command_message_roundtrip(self, client):
        state = _reset(client)
        city = _first_city_of(state, "caocao")
        with client.websocket_connect("/ws/game") as ws:
            ws.receive_json()  # 初始 state
            ws.send_json({"type": "command", "command": {
                "type": "develop", "faction": "caocao", "turn": 1,
                "params": {"city": city, "develop_type": "economy"},
            }})
            result = ws.receive_json()
            followup = ws.receive_json()
        assert result["type"] == "command_result"
        assert result["data"]["success"] is True
        # 命令执行后服务端会补推一次状态
        assert followup["type"] == "state"

    def test_client_init_message_rebuilds_game(self, client):
        """客户端 init 消息按 seed/max_turns/factions 重建对局。"""
        with client.websocket_connect("/ws/game") as ws:
            ws.receive_json()  # 初始 state
            ws.send_json({
                "type": "init", "seed": 123, "max_turns": 5,
                "factions": ["caocao"], "use_llm": False,
            })
            msg = ws.receive_json()
        assert msg["type"] == "state"
        assert msg["data"]["turn"] == 1
        assert msg["data"]["seed"] == 123
        assert msg["data"]["max_turns"] == 5
        assert msg["data"]["llm_factions"] == ["caocao"]

    def test_unknown_message_type_returns_error(self, client):
        _reset(client)
        with client.websocket_connect("/ws/game") as ws:
            ws.receive_json()
            ws.send_json({"type": "definitely_not_a_type"})
            msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "未知消息类型" in msg["message"]

    def test_invalid_json_returns_error(self, client):
        _reset(client)
        with client.websocket_connect("/ws/game") as ws:
            ws.receive_json()
            ws.send_text("{ not valid json")
            msg = ws.receive_json()
        assert msg["type"] == "error"
        assert "JSON" in msg["message"]


# ============================================================
# 新增端点（v4.0.1，此前同样零测试）
# ============================================================

class TestModelEndpoints:
    """模型清单端点（v4.0.1）"""

    def test_models_listing(self, client):
        r = client.get("/api/models")
        if r.status_code == 404:
            pytest.skip("/api/models 未实现（v4.0.1 特性未合入）")
        assert r.status_code == 200
        body = r.json()
        for key in ("providers", "models", "default_provider", "default_model"):
            assert key in body, f"/api/models 缺少字段: {key}"
        assert "deepseek" in body["providers"]


class TestModelRecordsEndpoint:
    """跨局模型战绩端点：文件缺失 / 损坏 / 正常聚合 三条路径

    ⚠️ v4.0.1 新增端点；404 时 skip，避免与并行特性合入/回退耦合。
    `data/model_records.json` 是**运行时产物**（已被 .gitignore 忽略），
    首次启动时很可能不存在 —— 必须保证"文件缺失时返回空榜单"而非报错。
    """

    @staticmethod
    def _body_or_skip(resp):
        if resp.status_code == 404:
            pytest.skip("/api/model_records 未实现（v4.0.1 特性未合入）")
        assert resp.status_code == 200
        return resp.json()

    def test_records_empty_when_file_missing(self, client, monkeypatch, records_tmp_dir):
        import api.game_manager as gm_mod
        monkeypatch.setattr(gm_mod, "MODEL_RECORDS_PATH", records_tmp_dir / "absent.json")
        body = self._body_or_skip(client.get("/api/model_records"))
        assert body["total_matches"] == 0
        assert body["leaderboard"] == []
        assert body["recent"] == []

    def test_records_empty_when_file_corrupted(self, client, monkeypatch, records_tmp_dir):
        import api.game_manager as gm_mod
        bad = records_tmp_dir / "corrupt.json"
        bad.write_text("{ this is not json", encoding="utf-8")
        monkeypatch.setattr(gm_mod, "MODEL_RECORDS_PATH", bad)
        body = self._body_or_skip(client.get("/api/model_records"))
        assert body["total_matches"] == 0
        assert body["leaderboard"] == []

    def test_records_aggregate_from_file(self, client, monkeypatch, records_tmp_dir):
        import json as _json
        import api.game_manager as gm_mod
        p = records_tmp_dir / "records.json"
        p.write_text(_json.dumps({"matches": [
            {"results": [
                {"model": "deepseek-flash", "rank": 1, "cities": 5, "winner": True},
                {"model": "gpt-x", "rank": 2, "cities": 3, "winner": False},
            ]},
            {"results": [
                {"model": "deepseek-flash", "rank": 2, "cities": 2, "winner": False},
                {"model": "gpt-x", "rank": 1, "cities": 6, "winner": True},
            ]},
        ]}, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(gm_mod, "MODEL_RECORDS_PATH", p)
        body = self._body_or_skip(client.get("/api/model_records"))
        assert body["total_matches"] == 2
        lb = {row["model"]: row for row in body["leaderboard"]}
        assert lb["deepseek-flash"]["matches"] == 2
        assert lb["deepseek-flash"]["wins"] == 1
        assert lb["deepseek-flash"]["win_rate"] == 0.5
        assert lb["deepseek-flash"]["avg_cities"] == 3.5   # (5+2)/2
        assert lb["gpt-x"]["wins"] == 1
        assert lb["gpt-x"]["win_rate"] == 0.5
        # 胜率并列 → 按模型名稳定排序（deterministic）
        assert [row["model"] for row in body["leaderboard"]] == ["deepseek-flash", "gpt-x"]
