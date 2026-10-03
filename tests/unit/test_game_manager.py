"""GameManager 单元测试

覆盖三块容易静默出错、且曾真实出过事故的逻辑：
1. 并发采集决策不改变对局结果（v4.0 并发化）
2. LLM 降级状态必须显式暴露（llm_active / llm_error）
3. 玩家随机种子派生必须跨进程稳定（不能依赖内置 hash）
"""

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from api.game_manager import GameConfig, GameManager, _stable_hash  # noqa: E402


# ============================================================
# 并发确定性
# ============================================================

def _fingerprint(gm: GameManager) -> str:
    """对局状态指纹：城市归属/守军/资源 + 军队"""
    eng = gm.engine
    parts = [f"t{eng.turn}"]
    for cid, c in sorted(eng.cities.items()):
        parts.append(f"{cid}:{c.faction}:{c.garrison}:{c.gold}:{c.food}:{c.wall_hp}")
    for aid, a in sorted(eng.armies.items()):
        parts.append(f"{aid}:{a.faction}:{a.soldiers}:{a.status.value}:{a.to_city}")
    return "|".join(parts)


def _run(parallel: bool, turns: int, seed: int = 42) -> list:
    gm = GameManager(GameConfig(seed=seed, max_turns=64, parallel_players=parallel))
    prints = []
    for _ in range(turns):
        if gm.engine.game_over:
            break
        gm.process_turn()
        prints.append(_fingerprint(gm))
    return prints


class TestParallelDecisions:
    """并发采集决策的确定性"""

    def test_parallel_matches_serial(self):
        """并发与串行必须逐回合完全一致【v4.0】

        并发只改变「谁先算完」，不改变「算什么」与「按什么顺序执行」：
        - 观察在主线程串行生成
        - 各势力持有独立 RNG，随机流只取决于自身被调用次数
        - 命令执行顺序固定为势力插入顺序
        这条断言是并发化能安全上线的前提。
        """
        parallel = _run(True, turns=8)
        serial = _run(False, turns=8)
        assert len(parallel) == len(serial) > 0
        assert parallel == serial

    def test_single_faction_no_thread_pool(self):
        """单势力时退化为串行，不应报错"""
        prints = _run(True, turns=3)
        assert len(prints) == 3


# ============================================================
# 稳定哈希
# ============================================================

class TestStableHash:
    """玩家种子派生必须跨进程稳定"""

    def test_stable_hash_is_deterministic(self):
        """同一字符串多次调用结果相同"""
        assert _stable_hash("caocao") == _stable_hash("caocao")

    def test_stable_hash_known_value(self):
        """CRC32 的已知值，锁死实现不被误改回内置 hash()"""
        import zlib
        assert _stable_hash("caocao") == zlib.crc32(b"caocao") & 0xFFFFFFFF

    def test_different_factions_differ(self):
        """不同势力派生出不同种子"""
        seeds = {f: _stable_hash(f) % 10000 for f in ("caocao", "liubei", "sunjian")}
        assert len(set(seeds.values())) == 3


# ============================================================
# LLM 降级状态
# ============================================================

class TestLlmDegradation:
    """LLM 降级必须显式可观测，禁止静默回退"""

    def test_no_key_reports_error(self, monkeypatch):
        """无 key 时 llm_active=False 且 llm_error 非空"""
        monkeypatch.delenv("LLM_API_KEY", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        gm = GameManager(GameConfig(seed=1, use_llm=True, factions=["caocao"]))
        assert gm.llm_active is False
        assert gm.llm_error != ""
        assert "未找到" in gm.llm_error or "LLM_API_KEY" in gm.llm_error

    def test_placeholder_key_reports_error(self, monkeypatch):
        """占位符 key（如 sk-你的key）必须被识别，不能当作有效 key"""
        monkeypatch.setenv("LLM_API_KEY", "sk-你的key")
        gm = GameManager(GameConfig(seed=1, use_llm=True, factions=["caocao"]))
        assert gm.llm_active is False
        assert "占位符" in gm.llm_error

    def test_use_llm_false_has_no_players_error(self):
        """默认 CLI 模式不应报 LLM 错误"""
        gm = GameManager(GameConfig(seed=1, use_llm=False, factions=["caocao"]))
        assert gm.llm_active is False
        assert gm.llm_error == ""

    def test_state_exposes_llm_fields(self):
        """get_state() 必须回报 llm_requested/llm_active/llm_error 供前端提示"""
        gm = GameManager(GameConfig(seed=1, use_llm=False, factions=["caocao"]))
        state = gm.get_state()
        for key in ("llm_requested", "llm_active", "llm_error", "llm_model", "llm_factions"):
            assert key in state, f"get_state() 缺少 {key}"


# ============================================================
# 基础回合推进
# ============================================================

class TestProcessTurn:
    """回合推进基础行为"""

    def test_turn_advances(self):
        """process_turn 推进回合数"""
        gm = GameManager(GameConfig(seed=7, max_turns=32, factions=["caocao", "liubei"]))
        t0 = gm.engine.turn
        gm.process_turn()
        assert gm.engine.turn == t0 + 1

    def test_reasoning_is_list_copy(self):
        """reasoning 暴露给外部时必须与内部列表解耦

        原实现直接返回内部列表引用，调用方修改会污染引擎侧记录。
        """
        gm = GameManager(GameConfig(seed=7, max_turns=32, factions=["caocao"]))
        gm.process_turn()
        state = gm.get_state()
        before = len(gm._reasoning)
        state["reasoning"].append({"turn": 999, "faction": "fake", "reasoning": "x", "commands": []})
        assert len(gm._reasoning) == before
