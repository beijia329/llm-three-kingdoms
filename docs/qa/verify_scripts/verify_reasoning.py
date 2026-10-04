"""验证二号：reasoning 不再随 /api/state 每帧下发（B2）

修复前：get_state() 把全量 reasoning 塞进 state，自动推进下每帧 ~200KB，
与围观台要流畅直接冲突。

修复后（B2）：
- get_state() 默认不含 reasoning（reasoning=None 时根本不进包）；
- 新增 get_reasoning(limit) + REST /api/reasoning，前端「决策」Tab 按需拉取。

本脚本验证两点：
1) 即使 reasoning 累积到 400 条，默认 get_state() 载荷仍稳定 < 75KB；
2) get_reasoning(limit) 按要求返回条数，get_reasoning() 返回全量。
"""
import sys, json
sys.path.insert(0, "/Users/dongsheng/Documents/llm-sanguo-project")
from api.game_manager import GameConfig, GameManager, MAX_REASONING_HISTORY

gm = GameManager(config=GameConfig(seed=42, max_turns=48, use_llm=False))
for _ in range(24):
    gm.process_turn()
ver = gm.get_state(known_hex_map_version=None)["hex_map_version"]
sample = ("当前兖州三城粮草充裕但兵力分散，西面已结盟，贸然东进恐遭夹击；"
          "南面新丧，城防空虚，若能速取可断上游之势。故本回合以内政积蓄为主，"
          "同时遣一军南下探虚实，待秋收后再决进退。") * 3
print(f"MAX_REASONING_HISTORY = {MAX_REASONING_HISTORY}")

max_sz = 0
for n in (0, 20, 100, 400):
    gm._reasoning = [{"turn": i // 12 + 1, "faction": "caocao",
                      "reasoning": sample, "commands": ["attack"]} for i in range(n)]
    sz = len(json.dumps(gm.get_state(known_hex_map_version=ver),
                        ensure_ascii=False, default=str))
    max_sz = max(max_sz, sz)
    print(f"  reasoning={n:<4} 默认 state 载荷 {sz:,} B  超75KB基线: {'是 ❌' if sz > 76800 else '否 ✅'}")

print(f"  >>> 默认 state 最大载荷 {max_sz:,} B "
      f"({'【❌ 仍超标】' if max_sz > 76800 else '【✅ B2 已修复】'})")

# 按需端点：get_reasoning(limit) 返回最近 limit 条，get_reasoning() 返回全量
gm._reasoning = [{"turn": i + 1, "faction": "caocao",
                  "reasoning": sample, "commands": ["attack"]} for i in range(400)]
full = gm.get_reasoning()
limited = gm.get_reasoning(limit=20)
print(f"  get_reasoning()        返回 {len(full)} 条（期望 400）"
      f" -> {'✅' if len(full) == 400 else '❌'}")
print(f"  get_reasoning(limit=20) 返回 {len(limited)} 条（期望 20）"
      f" -> {'✅' if len(limited) == 20 else '❌'}")
# 截断取的是「最近」：最后一条应是 turn=400
last_is_newest = limited[-1]["turn"] == 400
print(f"  截断取最近: limited[-1].turn={limited[-1]['turn']} -> {'✅' if last_is_newest else '❌'}")
print(f"  >>> 按需端点: {'【✅ 正常】' if len(full)==400 and len(limited)==20 and last_is_newest else '【❌ 异常】'}")
