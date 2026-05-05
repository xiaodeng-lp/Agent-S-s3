# Feishu CUA 基线建立 — 2026-05-04

作者：hu_ray

## 背景

在原始 Agent-S3 通用 GUI Agent 代码基础上，建立面向飞书桌面端的稳定基线。本次开发覆盖执行时序修复、推理策略优化、环境检测、工程规范化。

Git 分支：`feat/reflection-optimize`，远程 `https://github.com/HuXiangyu123/Agent-S-s3`。

---

## 变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `gui_agents/s3/cli_app.py` | 修改 | `_settle_delay()` 动态等待、pre+post exec sleep、模型思考计时、`--reasoning_effort`、`--reflection_mode` |
| `gui_agents/s3/agents/worker.py` | 修改 | `reflection_mode` 控制、`_should_reflect()` 策略、reasoning_effort 默认 medium |
| `gui_agents/s3/agents/reasoning_strategy.py` | 新建→修改 | 推理强度自动切换，默认 HIGH→MEDIUM |
| `launcher.py` | 大幅修改 | 主模型选择器、指令历史 Combobox、平台/DPI 检测、首次运行自动配置、重新检测按钮 |
| `gui_agents/s3/agents/grounding.py` | 修改 | Doubao 坐标缩放修复（ground_coord_scale）、resize_coordinates 分支 |
| `test_models.py` | 新建 | 模型连通性与参数校验脚本 |
| `docs/feishu_tools_skills_architecture.md` | 新建 | Tools/Skills + SOP + Visual Anchor 架构指导意见 |
| `docs/openai_api_parameters.md` | 新建 | OpenAI API 参数参考文档 |
| `env.txt.example` | 新建 | 配置文件模板（含所有键的注释说明） |
| `AGENTS.md` | 新建 | 项目约束与协作规则 |
| `CLAUDE.md` | 新建 | 指向 AGENTS.md 的软链接 |
| `README.md` | 重写 | 飞书二开项目 README |
| `command_history.json` | 新建 | 指令历史持久化（含两条候选指令） |
| `dev_log/` | 新建 | 开发日志目录与规范 |

---

## 关键决策

### 1. 执行时序：pre+post exec sleep
**决策**：`exec()` 前后均加 sleep。pre 0.5s 缓冲，post 按动作类型 1.0–3.0s。
**理由**：原代码 sleep 放在 exec() 前完全无效——截图在 sleep 后才发生。post-exec sleep 确保下一轮截图时 UI 已稳定。pre-exec 0.5s 缓冲防止连续快速操作。

### 2. 反射模式默认 on_failure
**决策**：新增 `reflection_mode` 参数，默认 `on_failure`（仅步骤失败时反射）。
**理由**：每步反射调用 LLM 耗时 15–25s。绝大多数步骤正常执行，反射信息价值有限。实测 `on_failure` 模式工作正常，每步节省约 15–25s。

### 3. 推理强度默认 medium
**决策**：GPT reasoning_effort 默认从 high 降为 medium，仅复杂操作（跨窗口/应用切换）和步骤失败时升级为 xhigh。
**理由**：飞书日常操作（点击、输入、发送）不需要 xhigh 推理。medium 足以应对大部分场景，仅在复杂路由和失败恢复时提升。

### 4. 首次运行自动环境检测
**决策**：启动器首次运行时自动检测平台、DPI、屏幕分辨率，计算推荐落地分辨率，持久化到 config.json。
**理由**：避免用户手工填写分辨率参数，消除 DPI 缩放导致的坐标偏差。提供「重新检测环境」按钮支持手动刷新。

### 5. Feishu 领域层独立于 S3
**决策**：AGENTS.md 约束 Feishu 专用逻辑放在 `gui_agents/feishu/`，不污染 S3 通用内核。
**理由**：S3 是通用 GUI 执行引擎。Feishu 的页面注册表、SOP、视觉锚点属于领域知识，应与通用内核解耦。

---

## 验证

- [x] 启动器 GUI 正常启动，主模型选择器切换正常工作
- [x] 环境检测函数输出正确（Windows 10, DPI 1.5, 3840x2160）
- [x] 反射 on_failure 模式执行正常，跳过日志正确输出
- [x] 指令历史下拉框显示候选指令，发送后持久化
- [x] `test_models.py` 全部 4 项测试通过
- [x] 语法检查全部通过（cli_app, worker, launcher, reasoning_strategy）
- [x] Git 3 个 commit 成功推送到远程

---

## 风险 & 后续

- `on_failure` 反射模式无法捕获"代码执行成功但 UI 效果错误"的情况（如点错按钮），后续可用 verifier 补位
- 落地模型每次步骤调用 2 次（格式校验 + 最终执行），可缓存第一次的结果消除重复调用
- Page Registry + Visual Anchor Store 架构已设计，待实现
- DPI 检测目前仅支持 Windows（GetDpiForMonitor），macOS/Linux 使用 tkinter 兜底
