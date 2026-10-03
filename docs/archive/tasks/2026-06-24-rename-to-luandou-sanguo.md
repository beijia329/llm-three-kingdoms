> ⚠️ **本文档为历史记录（归档于 2026-10）。** 更名事实本身仍成立，仅供追溯；
> 文中构建脚本已更新（`build_app.sh` 已归档，现用 `build_release.sh` @ v4.1.0）。
> 引用前以**当前代码**为准。

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

---

## 🐛 运行时问题排查（2026-06-24 补充）

### 现象
双击桌面 `乱斗三国.app` 后，浏览器显示 `{"detail":"Not Found"}`（FastAPI 404）。

### 根因分析
1. **旧后端进程未停**：在代码修改之前，已有 `uvicorn` 进程（PID 45928）在运行旧版 `api/server.py`（没有 `web/dist/` 中的新内容）。
2. **App 的检测逻辑**：Launcher 脚本检测到 `~/.llm-sanguo/server.pid` 存在且进程存活时，直接 `open http://localhost:8000` 而不重启服务。
3. **`web/dist/` 是旧构建产物**：旧的 `dist/index.html` 标题仍是 `LLM三国志 - Web`，且缺少 `favicon.png`。

### 解决步骤
1. 手动 `kill 45928` 停止旧进程
2. 删除 `~/.llm-sanguo/server.pid`
3. `cd web && npm run build` 重新构建前端（Vite 自动将 `public/favicon.png` 复制到 `dist/`）
4. 重新双击 App → Launcher 重新启动 uvicorn → 浏览器正常加载前端页面

### 验证结果
```
$ curl -s http://localhost:8000/ | grep title
  <title>乱斗三国 - Web</title>

$ curl -s http://localhost:8000/favicon.png | file -
/dev/stdin: PNG image data, 222 x 222, 8-bit/color RGBA
```

### 教训
- macOS App 的重启策略是"检测到旧进程则直接打开浏览器"，**代码修改后必须手动停止旧进程**或重启电脑。
- `web/dist/` 被 `.gitignore` 忽略，发布前必须确保执行过 `npm run build`。

---

## 最终 Git 提交

```
commit 89271ea (feat/web-frontend)
Author: dongsheng
Date:   2026-06-24

feat(brand): 游戏正式更名为乱斗三国 + 接入自定义图标

- 全局替换对外显示名称：LLM三国志 → 乱斗三国
- Web前端：favicon + 页面标题 + TopBar加载文本
- macOS App：app_icon.icns（7尺寸）+ Info.plist图标声明
- Python后端：main.py / run_web.py / api/server.py 标题与描述
- Pygame渲染器：默认窗口标题
- 构建脚本：build_app.sh + build_release.sh 名称/通知/图标复制
- 文档：README / AGENTS / MAINTENANCE / 部署指南等同步更新
- 保留历史文档（superpowers/、已过时手册）原样存档

新增文件：
- assets/app_icon.icns（macOS多尺寸图标）
- web/public/favicon.png（Web标签页图标）
- docs/tasks/2026-06-24-rename-to-luandou-sanguo.md（改动总结）
```
