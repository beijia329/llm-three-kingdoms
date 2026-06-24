# 2026-06-24 游戏更名：LLM三国志 → 乱斗三国

## 改动目的
将游戏对外显示名称统一从 **LLM三国志** 改为 **乱斗三国**，并接入用户指定的图标资源。

---

## 图标处理

### 源文件
- **原始图标**：`~/Downloads/乱斗三国_type.skyfont.com_alpha.png`
- **规格**：222×222 px，8-bit RGBA，透明背景

### 生成产物
| 文件 | 位置 | 用途 |
|------|------|------|
| `favicon.png` | `web/public/favicon.png` | Web 前端标签页图标（Vite 自动复制到 dist） |
| `app_icon.icns` | `assets/app_icon.icns` | macOS .app 图标（16/32/64/128/256/512/1024 多尺寸） |

> icns 使用 Python Pillow 手动生成，包含完整的 macOS 图标尺寸集合（icp4 ~ ic10）。

---

## 改动的文件（17 个）

### Web 前端
- `web/index.html` — 页面标题 + 添加 `<link rel="icon">`
- `web/src/components/TopBar.tsx` — 加载中标题

### Python 后端
- `main.py` — 入口描述、各模式运行标题
- `run_web.py` — 启动器描述、服务启动标题
- `api/server.py` — FastAPI title/description、根路径消息

### Pygame 渲染层
- `renderer/game_renderer.py` — 默认窗口标题

### macOS 构建脚本
- `build_app.sh` — APP_NAME、Info.plist 显示名、CFBundleIconFile、图标复制、所有 osascript 通知标题
- `build_release.sh` — 同上 + 使用说明文本

### 文档与配置
- `README.md` — 项目标题
- `AGENTS.md` — 文档标题
- `MAINTENANCE.md` — 文档标题
- `requirements.txt` — 注释标题
- `verify.sh` — 脚本注释与输出标题
- `施工指南.md` — 文档标题
- `docs/specs/deployment-guide.md` — 运行说明
- `docs/knowledge-base/README.md` — 知识库标题
- `docs/handoff/agent-handoff-log.md` — 桌面 App 路径说明

---

## 新增的文件（2 个）

- `assets/app_icon.icns` — macOS 多尺寸图标（428,372 bytes）
- `web/public/favicon.png` — Web 图标（8,993 bytes）

---

## 保留未改的文件（历史记录，无需修改）

- `LLM三国志施工手册（已过时）.md` — 明确标注"已过时"
- `docs/superpowers/plans/2026-06-23-civ-style-hex-map-plan.md` — 历史设计文档
- `docs/superpowers/prompts/2026-06-23-deepseek-execution-prompt.md` — 历史 prompt 记录
- `docs/superpowers/specs/2026-06-23-civ-style-hex-map-design.md` — 历史设计 spec

> 以上文件作为项目历史存档保留原名，不影响当前产品对外展示。

---

## 技术说明

- **Bundle ID 未改**：`com.llm-sanguo.launcher` 保持不变，避免破坏已有 macOS 安装的路径/权限。
- **数据路径未改**：`~/.llm-sanguo/venv` 等本地数据目录保持不变，确保老用户升级无缝。
- **npm 包名未改**：`llm-sanguo-web` 作为内部技术标识保留。
