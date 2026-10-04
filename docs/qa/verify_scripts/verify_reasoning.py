"""验证一号：reasoning 累积后的 /api/state 载荷"""
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
for n in (0, 20, 100, 400):
    gm._reasoning = [{"turn": i // 12 + 1, "faction": "caocao",
                      "reasoning": sample, "commands": ["attack"]} for i in range(n)]
    sz = len(json.dumps(gm.get_state(known_hex_map_version=ver),
                        ensure_ascii=False, default=str))
    print(f"  reasoning={n:<4} 载荷 {sz:,} B  超75KB基线: {'是' if sz > 76800 else '否'}")
