# 里程碑验收与演示指南

> 每个阶段完成后，按此文档进行验收演示。
> 目标：用具体的可运行效果证明阶段完成，而不是"我觉得做完了"

---

## 验收原则

1. **能跑起来才算数**：所有功能必须有可运行的演示
2. **有测试才算数**：核心逻辑必须有单元测试
3. **可复现才算数**：相同输入得到相同输出
4. **边界情况要测**：不仅测正常路径，还要测异常路径

---

## 阶段一：项目初始化与数据模型

### 验收标准
- [ ] 项目目录结构完整
- [ ] 依赖可以正常安装
- [ ] 所有数据模型定义完成
- [ ] 基础单元测试通过

### 演示步骤

#### Demo 1：安装依赖
```bash
pip install -r requirements.txt
```
**预期效果**：安装成功，没有报错

#### Demo 2：导入数据模型
```python
from game.models import City, Army, General, AttackCommand

# 创建一个城市
city = City(
    id="chengdu",
    name="成都",
    faction="liuyan",
    level=3,
    wall_hp=2000,
    wall_max_hp=2000,
    gold=1000,
    food=2000,
    population=50000,
    morale=70,
    garrison=2000,
    position=(100, 200)
)
print(city)
```
**预期效果**：
- 正常创建对象
- 字段校验生效（比如morale超过100会报错）
- 可以正常打印

#### Demo 3：运行单元测试
```bash
pytest tests/unit/test_models.py -v
```
**预期效果**：所有测试通过

### 完成标志
> ✅ 数据模型都定义好了
> ✅ 类型校验生效
> ✅ 测试能跑通
> ❌ 还没有游戏逻辑

---

## 阶段二：游戏引擎核心

### 验收标准
- [ ] 地图系统可用
- [ ] 资源计算正确
- [ ] 城市管理功能完整
- [ ] 将领系统可用
- [ ] 外交系统可用
- [ ] 单元测试覆盖率>70%

### 演示步骤

#### Demo 1：资源产出计算
```python
from game.systems.resource_system import ResourceSystem
from game.models import City

city = City(level=3, population=50000, morale=70, ...)
gold, food = ResourceSystem.calculate_production(city)
print(f"每回合产出：金钱{gold}，粮草{food}")
```
**预期效果**：
- 数值合理（参考constants.py的配置）
- 民心70时产出正常
- 民心降低时产出减少

#### Demo 2：城市发展与征兵
```python
# 发展经济
city_system.develop(city, "economy")
print(f"发展后人口：{city.population}")

# 征兵
city_system.recruit(city, 500)
print(f"征兵后守军：{city.garrison}，金钱：{city.gold}")

# 钱不够时征兵
city.gold = 10
result = city_system.recruit(city, 500)
print(f"钱不够征兵结果：{result}")  # 应该是False
```
**预期效果**：
- 发展城市提升对应属性
- 征兵消耗资源，增加守军
- 资源不足时操作失败

#### Demo 3：将领探索与赏赐
```python
# 探索
new_generals = general_system.explore(city, explorer_general)
print(f"发现将领：{[g.name for g in new_generals]}")

# 赏赐
print(f"赏赐前忠诚：{general.loyalty}")
general_system.reward(general, 100)
print(f"赏赐后忠诚：{general.loyalty}")
```
**预期效果**：
- 探索有概率发现新将领（有随机性，但用固定seed可复现）
- 赏赐提升忠诚度

#### Demo 4：运行单元测试
```bash
pytest tests/unit/ -v --cov=game.systems
```
**预期效果**：所有测试通过，覆盖率>70%

### 完成标志
> ✅ 所有基础系统都能用了
> ✅ 可以通过Python API操作游戏
> ✅ 资源、城市、将领、外交都有逻辑
> ❌ 还不能打仗
> ❌ 还没有完整游戏循环

---

## 阶段三：战斗系统

### 验收标准
- [ ] 军队可以移动
- [ ] 粮草消耗正确
- [ ] 攻城战流程完整
- [ ] 士气系统工作
- [ ] 胜负判定正确
- [ ] 战后处理正确
- [ ] 战斗系统测试覆盖率>85%

### 演示步骤

#### Demo 1：军队行军
```python
# 创建一支军队
army = Army(
    from_city="chengdu",
    to_city="hanzhong",
    soldiers=3000,
    food=5000,
    total_distance=2
)

# 推进一回合
army_movement.process_movement(army)
print(f"进度：{army.progress}，剩余粮草：{army.food}")

# 再推进一回合（到达）
army_movement.process_movement(army)
print(f"是否到达：{army.progress >= 1}")
```
**预期效果**：
- 军队每回合推进正确的进度
- 粮草每回合消耗
- 到达目的地后状态正确

#### Demo 2：断粮惩罚
```python
army.food = 0
army.morale = 80
for i in range(5):
    army_movement.process_movement(army)
    print(f"第{i+1}回合：士气={army.morale}，兵力={army.soldiers}")
```
**预期效果**：
- 断粮后士气持续下降
- 士气低于20后开始损失兵力
- 最终可能全军覆没

#### Demo 3：完整攻城战
```python
# 设置战斗双方
attacker = Army(soldiers=5000, morale=80, general=high_command_general)
defender_city = City(wall_hp=2000, garrison=3000, ...)

# 运行战斗
result = battle_resolver.resolve_siege(attacker, defender_city, rng)

print(f"战斗结果：{result.result}")
print(f"攻方伤亡：{result.attacker_casualties}")
print(f"守方伤亡：{result.defender_casualties}")
print(f"被俘将领：{result.captured_generals}")
```
**预期效果**：
- 战斗完整执行（围城→破墙→巷战）
- 双方都有伤亡
- 有明确的胜负结果
- 攻方胜利的话城市会易主

#### Demo 4：士气影响测试
```python
# 高士气 vs 低士气
attacker_high = Army(soldiers=3000, morale=90)
attacker_low = Army(soldiers=3000, morale=30)
defender = City(garrison=3000, ...)

result_high = battle_resolver.resolve_siege(attacker_high, defender, rng)
result_low = battle_resolver.resolve_siege(attacker_low, defender, rng)

print(f"高士气伤亡：{result_high.attacker_casualties}")
print(f"低士气伤亡：{result_low.attacker_casualties}")
# 低士气的伤亡应该明显更高
```
**预期效果**：
- 士气明显影响战斗力
- 低士气方伤亡更高

#### Demo 5：战斗单元测试
```bash
pytest tests/unit/test_battle.py -v
```
**预期效果**：所有测试通过

### 完成标志
> ✅ 可以打仗了！
> ✅ 战斗流程完整
> ✅ 士气、粮草、俘虏等机制都工作
> ✅ 数值基本合理
> ❌ 还没整合到完整游戏里

---

## 阶段四：Engine整合

### 验收标准
- [ ] GameEngine主类可用
- [ ] 完整回合流程
- [ ] 胜利判定正确（终局：占地最多者胜；中途控 5 城称帝为阶段性 Buff，非终局胜负）
- [ ] 信息迷雾工作
- [ ] 初始游戏数据完整
- [ ] CLI玩家可用
- [ ] 可以跑完整一局

### 演示步骤

#### Demo 1：初始化游戏
```python
engine = GameEngine(seed=42)
engine.init_game()

print(f"当前回合：{engine.turn}")

from game.constants import FACTIONS
print("各势力初始城池数（共 22 城，12 方各 1~2 城）：")
for fid, fname in FACTIONS.items():
    n = len([c for c in engine.cities.values() if c.faction == fid])
    if n:
        print(f"  {fname}（{fid}）：{n} 城")
print(f"总城池：{len(engine.cities)}")
```
**预期效果**：
- 游戏正常初始化
- 每方 1~2 座城市，共 22 城
- 初始资源、将领都到位

#### Demo 2：执行命令+处理回合
```python
# 执行 liuyan（刘焉）势力的命令（成都为其初始城）
commands = [
    {"type": "develop", "params": {"city": "chengdu", "type": "economy"}},
    {"type": "recruit", "params": {"city": "chengdu", "troops": 500}},
]
engine.execute_commands("liuyan", commands)

# 处理一回合
engine.process_turn()

print(f"回合：{engine.turn}")
print(f"成都金钱：{engine.cities['chengdu'].gold}")
```
**预期效果**：
- 命令正常执行
- 回合处理正常
- 资源、兵力按规则变化

#### Demo 3：信息迷雾
```python
# 获取 liubei（刘备）势力的观察数据
obs = engine.get_observation("liubei")

print("liubei（刘备）知道的城市：")
for city in obs.known_cities:
    print(f"  {city.name} - 兵力：{city.garrison if hasattr(city, 'garrison') else '未知'}")
```
**预期效果**：
- 己方城市信息完整
- 相邻敌方城市有部分信息
- 远方城市信息很少或没有

#### Demo 4：跑完整一局（随机AI）
```bash
python -m tests.integration.test_full_game
```
**预期效果**：
- 完整跑 192 回合（184→232 年）
- 不会崩溃
- 最后有胜利者
- 状态全程合法

#### Demo 5：CLI模式试玩
```bash
python main.py --mode cli --faction caocao
```
**预期效果**：
- 可以用命令行输入指令
- 可以发展城市、征兵、出征
- 可以看到游戏状态

### 完成标志
> 🎮 可以玩游戏了！
> ✅ 完整的游戏循环
> ✅ 192 回合能分出胜负
> ✅ 有信息迷雾
> ✅ CLI模式可玩
> ❌ 还没有AI玩家
> ❌ 还没有GUI

---

## 阶段五：LLM接入

### 验收标准
- [ ] 可以调用LLM API
- [ ] Prompt构建完整
- [ ] 输出解析稳定（成功率>95%）
- [ ] 记忆系统工作
- [ ] LLM可以正常对战
- [ ] 有降级和容错机制

### 演示步骤

#### Demo 1：Prompt构建
```python
obs = engine.get_observation("liubei")
prompt = prompt_builder.build_full_prompt("liubei", obs)
print(prompt)
```
**预期效果**：
- Prompt结构完整（角色+规则+状态+格式）
- 状态表格化，清晰易读
- 有思维链引导
- 格式要求明确

#### Demo 2：输出解析测试
```python
# 测试各种格式
test_cases = [
    '[{"type": "attack", ...}]',  # 标准JSON
    '```json\n[{"type": "attack"}]\n```',  # markdown包裹
    "[{'type': 'attack'}]",  # 单引号
    "思考：...\n命令：[{...}]",  # 前后有文字
]

for i, test in enumerate(test_cases):
    result = output_parser.parse_commands(test)
    print(f"测试{i+1}: {'成功' if result else '失败'}")
```
**预期效果**：
- 标准格式100%成功
- 常见容错格式大部分成功
- 完全乱的才会失败
- 整体成功率>95%

#### Demo 3：LLM单步决策
```python
player = LLMPlayer("liubei", llm_client, ...)
commands = player.get_commands(observation)
print(f"LLM输出命令：{commands}")
```
**预期效果**：
- LLM返回合法的命令
- 命令格式正确
- 有思考过程（思维链）

#### Demo 4：12方 LLM 对战
```bash
# 12方各自由 LLM 决策；--model 指定统一模型，--provider 可切换（默认 deepseek）
python main.py --mode ai-vs-ai --model deepseek-v4-flash
```
**预期效果**：
- 12方 AI 能完整打完一局（192 回合）
- 不会因为解析错误卡住
- AI会发展、会打仗、会发消息
- 一局大概10-30分钟（取决于模型速度）

#### Demo 5：容错测试
- 模拟LLM返回垃圾文本
- 验证系统能优雅降级（跳过回合，不崩溃）

### 完成标志
> 🤖 AI能自己玩了！
> ✅ 12方 LLM 能完整对战
> ✅ 输出解析稳定
> ✅ 有记忆，不会每回合忘光
> ✅ 出错了能降级，不崩溃
> ❌ 还是命令行模式
> ❌ 平衡性可能还不好

---

## 阶段六：GUI与回放

### 验收标准
- [ ] 地图可视化
- [ ] 城市状态显示
- [ ] 军队行军动画
- [ ] UI信息面板
- [ ] 事件日志
- [ ] 外交消息显示
- [ ] 回放系统可用
- [ ] 播放控制（播放/暂停/快进/倒退）

### 演示步骤

#### Demo 1：地图界面
```bash
python main.py --mode gui
```
**预期效果**：
- 显示游戏地图
- 22座城市按位置分布
- 不同势力用不同颜色
- 城市大小反映等级

#### Demo 2：城市详情
- 点击城市
- 显示详细信息（等级、资源、兵力、将领）
- 信息清晰易读

#### Demo 3：行军动画
- 派出一支军队
- 看到军队图标在地图上移动
- 有进度感

#### Demo 4：战斗效果
- 战斗发生时
- 有视觉提示（闪光/震动/文字）
- 能看到战斗结果

#### Demo 5：回放系统
```bash
python main.py --mode replay --file replay.json
```
**预期效果**：
- 能加载回放文件
- 有播放/暂停按钮
- 有进度条，可以拖动
- 可以快进、倒退
- 可以跳转到指定回合

#### Demo 6：完整观看一局AI对战
- 启动AI对战
- 实时观看
- 或者看完回放
- 体验流畅，信息清晰

### 完成标志
> 🎨 有画面了！
> ✅ 地图、UI、动画都有了
> ✅ 能看完整的对战回放
> ✅ 像看一场赛博斗蛐蛐比赛
> ✅ 体验流畅，不卡顿
> ❌ 平衡性可能还需要调
> ❌ 可能还有一些小bug

---

## 阶段七：测试与优化

### 验收标准
- [ ] 核心模块测试覆盖率>80%
- [ ] 集成测试通过
- [ ] 各势力胜率分布合理（12方基准：健康区间[3%,16%]，OP嫌疑阈值>16.67%即2×公平份额，无方0胜，平局率<10%；见 tests/balance/run_simulation.py）
- [ ] 连续跑10局不崩溃
- [ ] 没有明显的OP策略
- [ ] 性能达标（一局不超过30分钟）

### 演示步骤

#### Demo 1：测试覆盖率
```bash
pytest --cov=game --cov=players.llm tests/
```
**预期效果**：
- 整体覆盖率>80%
- 核心模块（战斗、解析器）>85%
- 所有测试通过

#### Demo 2：10局稳定性测试
```bash
python -m tests.stability.run_10_games
```
**预期效果**：
- 10局全部跑完
- 没有崩溃
- 没有卡死
- 每局都有胜利者

#### Demo 3：平衡性报告
```bash
python -m tests.balance.run_simulation --games 100
```
**预期效果**：
- 输出各势力胜率统计
- 12方胜率落入健康区间[3%,16%]，最高方≤16.67%（2×公平份额），无方0胜，平局率<10%
- 有详细的胜负原因分析

#### Demo 4：极端策略测试
- 测试全经济流是否无敌
- 测试速攻流是否无解
- 测试龟缩流能不能赢

**预期效果**：没有任何一种策略是必胜的

### 完成标志
> ✨ 项目基本完成了！
> ✅ 测试充分，bug少
> ✅ 平衡性达标
> ✅ 可以稳定运行
> ✅ 可以用来做模型对比评测了

---

## 最终验收清单

项目全部完成的标志：

- [ ] 可以用GUI看完整的AI对战回放
- [ ] 12方势力能正常对战
- [ ] 各势力胜率分布合理（12方基准：健康区间[3%,16%]，OP嫌疑阈值>16.67%即2×公平份额，无方0胜，平局率<10%；见 tests/balance/run_simulation.py）
- [ ] 连续跑10局不崩溃
- [ ] 核心模块测试覆盖率>80%
- [ ] 有完整的使用文档
- [ ] 有完整的开发文档
- [ ] 代码符合规范

---

> **文档版本**：v2.3
> **创建日期**：2026-06-23
> **最后更新**：2026-10-01（v2.3：12 方势力 key、192 回合、22 城、胜利条件澄清；API key 改 LLM_API_KEY）
