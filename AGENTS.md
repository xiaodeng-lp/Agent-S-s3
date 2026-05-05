# AGENTS

## Purpose

本仓库是基于 `Agent-S` 的飞书桌面端 GUI Agent 二次开发。
当前主线路线是 `Windows + 飞书桌面端 + GUI-first`，不是飞书开放平台 CLI、bot 或 API-first。

## Source Of Truth

涉及需求、架构、模块边界时，按下面顺序阅读：

1. `docs/项目需求.md`
2. `docs/feishu_gui_agent_master_plan.md`
3. `docs/product/feishu_gui_agent_prd.md`
4. `docs/spec/feishu_gui_agent_technical_spec.md`
5. `docs/interfaces/feishu_gui_agent_interfaces.md`
6. `CONTRIBUTE.md`

## Core Rules

1. 任何模块改动都走 `analysis -> manual plan -> coding -> review`。
2. 人和模型都理解手动 plan 之前，不进入 coding。
3. 共享契约变更时，文档必须与实现同 PR 或更早落地。
4. Feishu 业务逻辑优先落在 `gui_agents/feishu/`，不要持续污染 `gui_agents/s3/`。
5. 高耦合文件串行开发，低耦合模块才并行开发。
6. 默认假设飞书开放平台能力不可用，除非任务明确要求。

## Contract Freeze Gate

并行 coding 的启动条件不是“别人代码写完了”，而是“共享契约冻结了”。

冻结至少包含：

- `docs/spec/`
- `docs/interfaces/`
- track 拆分与依赖关系
- 当前 milestone scope

冻结记录至少包含：

- freeze commit SHA
- freeze 日期
- owner
- reviewer

冻结后如果共享契约还要改，按 `freeze-v2` 处理：

1. 暂停受影响 track 的相关文件开发。
2. 先更新 spec/interfaces。
3. 重新 review。
4. 再恢复 coding。

## Ownership Boundaries

默认并行轨道：

- `Track A`: `gui_agents/feishu/testcases/` -> `gui_agents/feishu/planner/`
- `Track B`: `gui_agents/feishu/pages/` -> `gui_agents/feishu/detectors/` -> `gui_agents/feishu/locators/`
- `Track C`: `gui_agents/feishu/workflows/` -> `gui_agents/feishu/verifiers/`
- `Track D`: `gui_agents/feishu/reports/` -> `gui_agents/feishu/maintenance/`
- `Serial Track`: `gui_agents/feishu/agents/feishu_worker.py` 以及 `s3` 高耦合集成文件

默认顺序：

1. 第一波并行 `Track A + Track B + Track C`
2. `Track D` 在运行时事实模型稳定后接入
3. `Serial Track` 最后做总装

## High-Coupling Files

以下文件默认串行开发，并且需要集成级 review：

- `gui_agents/s3/agents/worker.py`
- `gui_agents/s3/agents/grounding.py`
- `gui_agents/s3/cli_app.py`
- `gui_agents/s3/memory/procedural_memory.py`
- `gui_agents/feishu/agents/feishu_worker.py`

## Planning Standard

每个模块开工前都要有短 plan，至少包含：

- target files
- owner
- depends on
- outputs
- verification
- risks / rollback

## Worktree Rules

1. 默认分支当前是 `master`，它是集成基线，不是日常功能开发分支。
2. `master` worktree 保持干净，只做同步、冻结、集成检查。
3. 一个 worktree 只对应一个活跃分支。
4. 一个分支只在一个 worktree 中主动开发。
5. 开新 worktree 前先看 `git worktree list`。
6. 合并完成后及时 `git worktree remove` 清理废弃 worktree。
7. 需要临时联调或修补时，新开 `review/<topic>` 或 `fix/<topic>`，不要直接在 `master` worktree 改。
8. 如果旧分支和当前默认分支没有共同祖先，不要直接 `rebase`，改为从当前默认分支新切分支后手动移植改动。

## Merge And Review Rules

1. 先冻结契约，再切并行分支。
2. A/B/C 从同一个 freeze SHA 切出。
3. track 分支合并前先同步默认分支，再 rebase 到最新基线。
4. rebase 改到了已 review 的冲突区域，必须重新 review。
5. `Serial Track` 从 A/B/C/D 合入后的新基线切出，并最后合并。

Review 分三层：

- Gate 1 Self-check: plan、最小验证、证据齐全
- Gate 2 Module review: 看边界、契约、失败路径
- Gate 3 Integration review: 高耦合文件或多 track 合流必过

## Delivery Standard

每个完成模块都应交付：

- 明确边界
- 成功判定或 verifier
- fallback / failure handling
- 最小回归证据
- 简短 review 结论与剩余风险
