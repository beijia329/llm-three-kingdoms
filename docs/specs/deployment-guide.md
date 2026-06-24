# 部署与运行指南

> 本文档说明如何安装、配置和运行乱斗三国游戏。
> 适用于开发者和评测人员。

---

## 一、环境要求

### 1.1 系统要求
- **操作系统**：Windows 10/11, macOS 12+, Linux
- **Python**：3.10 或更高版本
- **内存**：至少 4GB RAM
- **磁盘**：至少 500MB 可用空间

### 1.2 依赖包
| 包名 | 版本 | 用途 |
|------|------|------|
| pygame | 2.5+ | GUI渲染 |
| pydantic | 2.0+ | 数据校验 |
| pytest | 7.0+ | 测试框架 |
| json-repair | latest | JSON容错解析 |
| requests | latest | HTTP请求（LLM API） |

---

## 二、安装步骤

### 2.1 克隆项目
```bash
git clone <repository-url>
cd llm-sanguo-project
```

### 2.2 创建虚拟环境（推荐）
```bash
# Windows
python -m venv venv
venv\Scripts\activate

# macOS/Linux
python3 -m venv venv
source venv/bin/activate
```

### 2.3 安装依赖
```bash
pip install -r requirements.txt
```

### 2.4 验证安装
```bash
# 运行单元测试，确认环境正常
pytest tests/unit/ -v
```

如果所有测试都通过，说明安装成功。

---

## 三、配置说明

### 3.1 配置文件
配置文件位置：`config/config.yaml`

```yaml
# 游戏配置
game:
  max_turns: 24              # 最大回合数
  seed: null                 # 随机种子（null=随机）
  factions: ["wei", "shu", "wu"]  # 势力列表

# LLM配置
llm:
  provider: openrouter       # API提供商
  base_url: https://openrouter.ai/api/v1
  api_key: YOUR_API_KEY      # API密钥（也可以用环境变量）
  default_model: claude-3-opus-20240229
  timeout: 30                # 超时时间（秒）
  max_retries: 3             # 最大重试次数
  temperature: 0.7           # 温度参数

# GUI配置
gui:
  enabled: true              # 是否启用GUI
  width: 1280                # 窗口宽度
  height: 720                # 窗口高度
  fps: 60                    # 帧率

# 日志配置
logging:
  level: INFO                # 日志级别
  file: logs/game.log        # 日志文件
  replay_dir: replays/       # 回放文件目录
```

### 3.2 环境变量
也可以通过环境变量配置（优先级高于配置文件）：

```bash
# Windows
set OPENROUTER_API_KEY=your_api_key_here

# macOS/Linux
export OPENROUTER_API_KEY=your_api_key_here
```

**重要**：API密钥不要硬编码到代码里，不要提交到Git。

### 3.3 OpenRouter API Key 获取
1. 访问 https://openrouter.ai/
2. 注册账号
3. 在设置页面生成API Key
4. 充值（可以先充5美元测试）

---

## 四、运行游戏

### 4.1 运行GUI版本
```bash
python main.py
```

会打开Pygame窗口，可以人机对战或观看AI对战。

### 4.2 运行CLI版本（纯AI对战）
```bash
python main.py --mode cli --players llm:wei,llm:shu,llm:wu
```

参数说明：
- `--mode cli`：命令行模式，不显示GUI
- `--players`：指定每个势力的玩家类型
  - `llm`：LLM玩家
  - `cli`：命令行人类玩家
  - `random`：随机AI（测试用）

### 4.3 指定模型
```bash
python main.py --mode cli \
  --players llm:wei:claude-3-opus,llm:shu:gpt-4,llm:wu:gemini-pro
```

每个势力可以指定不同的模型。

### 4.4 指定种子
```bash
python main.py --seed 12345
```

相同种子 + 相同输入 = 相同结果，便于调试和复现。

---

## 五、运行测试

### 5.1 运行所有测试
```bash
pytest
```

### 5.2 只运行单元测试
```bash
pytest tests/unit/ -v
```

### 5.3 查看测试覆盖率
```bash
pytest --cov=game --cov-report=html
```

会生成 `htmlcov/index.html`，用浏览器打开查看详细覆盖率。

### 5.4 运行特定测试
```bash
# 运行战斗系统测试
pytest tests/unit/test_battle.py -v

# 运行特定测试函数
pytest tests/unit/test_battle.py::test_calculate_damage -v
```

### 5.5 并行运行测试
```bash
pytest -n auto
```

---

## 六、运行评测

### 6.1 快速评测（10局）
```bash
python tools/benchmark/run_benchmark.py \
  --models claude-3-opus gpt-4 gemini-pro \
  --games 10 \
  --output results/benchmark.json
```

### 6.2 正式评测（100局）
```bash
python tools/benchmark/run_benchmark.py \
  --models claude-3-opus gpt-4 gemini-pro \
  --games 100 \
  --output results/benchmark_full.json
```

### 6.3 自对战测试
```bash
python tools/benchmark/run_benchmark.py \
  --self-play \
  --model claude-3-opus \
  --games 100
```

同一个模型扮演三方，测试游戏平衡性。

### 6.4 生成评测报告
```bash
python tools/analysis/generate_report.py \
  --input results/benchmark.json \
  --output results/report.md
```

---

## 七、回放功能

### 7.1 观看回放
```bash
python tools/replay/play_replay.py replays/game_123.json
```

### 7.2 列出所有回放
```bash
ls -la replays/
```

### 7.3 从回放导出数据
```bash
python tools/analysis/export_replay.py \
  --input replays/game_123.json \
  --output results/game_data.csv
```

---

## 八、目录结构说明

```
llm-sanguo-project/
├── AGENTS.md                    # AI开发规范
├── README.md                    # 项目说明
├── requirements.txt             # 依赖清单
├── main.py                      # 程序入口
│
├── config/                      # 配置文件
│   └── config.yaml
│
├── game/                        # 游戏引擎核心
│   ├── engine.py                # GameEngine主类
│   ├── models.py                # 数据模型
│   ├── constants.py             # 常量配置
│   ├── random.py                # 确定性随机数
│   ├── state_manager.py         # 状态快照管理
│   ├── state_validator.py       # 状态合法性校验
│   ├── game_logger.py           # 游戏日志
│   ├── event_bus.py             # 事件总线
│   ├── systems/                 # 子系统
│   └── battle/                  # 战斗系统
│
├── players/                     # 玩家抽象层
│   ├── base_player.py
│   ├── cli_player.py
│   ├── gui_player.py
│   └── llm/                     # LLM玩家
│
├── renderer/                    # 渲染层（Pygame GUI）
│   ├── game_renderer.py
│   ├── map_renderer.py
│   ├── ui_panel.py
│   └── replay_player.py
│
├── tests/                       # 测试
│   ├── unit/                    # 单元测试
│   ├── integration/             # 集成测试
│   ├── e2e/                     # E2E测试
│   └── balance/                 # 平衡性测试
│
├── tools/                       # 工具脚本
│   ├── benchmark/               # 评测工具
│   ├── analysis/                # 分析工具
│   └── replay/                  # 回放工具
│
├── data/                        # 游戏数据
│   ├── cities.json
│   ├── generals.json
│   └── map.json
│
├── docs/                        # 文档
│   ├── design/                  # 设计文档
│   ├── tasks/                   # 任务清单
│   ├── specs/                   # 规范文档
│   └── knowledge-base/          # 知识库
│
├── logs/                        # 日志文件
├── replays/                     # 回放文件
└── results/                     # 评测结果
```

---

## 九、常见问题

### 9.1 安装问题

**Q: pip install 失败怎么办？**
A: 试试升级pip：`pip install --upgrade pip`，然后重试。

**Q: pygame安装失败？**
A: Windows用户可以试试预编译的wheel包，或者用conda安装。

### 9.2 API问题

**Q: API调用超时？**
A: 检查网络连接，或者增加超时时间配置。

**Q: API返回错误？**
A: 检查API Key是否正确，账户是否有余额，模型名称是否正确。

**Q: 怎么降低API成本？**
A:
- 用更便宜的模型测试
- 优化Prompt，减少token消耗
- 减少重试次数
- 先小批量测试，再大批量跑

### 9.3 游戏问题

**Q: 游戏运行很慢？**
A:
- LLM调用是瓶颈，正常的
- 可以用更便宜更快的模型
- 可以减少每回合的思考时间

**Q: AI总是输出格式错误？**
A:
- 检查Prompt里的格式要求是否明确
- 看看是不是模型太弱了
- 增加解析容错（已经有五层防御了）

**Q: 怎么调试AI的决策？**
A:
- 查看日志文件
- 观看回放
- 打开debug模式，看AI的思考过程

### 9.4 测试问题

**Q: 测试失败怎么办？**
A:
- 先看错误信息
- 确认是不是环境问题
- 用 `-v` 参数看详细输出
- 用 `--pdb` 进入调试模式

**Q: 测试运行太慢？**
A:
- 用 `-n auto` 并行运行
- 只跑你改的那部分测试
- 用 `--lf` 只跑上次失败的

---

## 十、开发工作流

### 10.1 开始新任务
1. 阅读 `docs/tasks/development-tasks.md`，找到你的任务
2. 阅读相关的设计文档
3. 阅读 `AGENTS.md`，遵守开发规范
4. 按TDD方式开发：先写测试，再写实现

### 10.2 提交代码前
1. 运行所有单元测试，确保通过
2. 检查代码覆盖率
3. 检查代码风格
4. 更新相关文档

### 10.3 遇到问题
1. 先看 `docs/pitfalls.md`，有没有类似的坑
2. 再看设计文档，有没有说明
3. 还不行就记录问题，继续做确定的部分
4. 不要自己瞎猜设计

---

> **文档版本**：v2.2
> **创建日期**：2026-06-23
> **相关文档**：AGENTS.md, development-tasks.md
