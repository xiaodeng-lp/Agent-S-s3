# Contribute

本文档是当前仓库的协作与提交流程约束，重点覆盖：

- 契约冻结与 reopen 规则
- 多 track 并行开发
- `git worktree` 使用方式
- merge / rebase / review 门禁
- 提交前最小检查

相关文档：

- [README.md](./README.md)
- [docs/README.md](./docs/README.md)
- [docs/feishu_gui_agent_master_plan.md](./docs/feishu_gui_agent_master_plan.md)
- [docs/process/feishu_gui_agent_parallel_dev_playbook.md](./docs/process/feishu_gui_agent_parallel_dev_playbook.md)
- [AGENTS.md](./AGENTS.md)

## 1. 基本原则

1. 小步提交，小 PR，单一目标。
2. 先定边界和契约，再做跨模块实现。
3. 共享契约先冻结，模块实现再并行。
4. Track 之间允许并行，Track 内部默认串行。
5. 高耦合模块最后集成，不提前混写。
6. 提交前先跑本地最小检查，不把明显会挂的改动直接交给 CI。

## 2. Contract Freeze And Reopen

并行 coding 的前提是共享契约冻结，而不是其他模块已经写完。

冻结清单至少包含：

- `docs/spec/`
- `docs/interfaces/`
- 当前 milestone scope
- track 拆分图
- 依赖矩阵

冻结记录至少包含：

- freeze commit SHA
- freeze 日期
- owner
- reviewer
- 适用 tracks

并行开发启动条件：

1. freeze 记录可追溯。
2. 共享结构命名已统一。
3. 各 track 的输入输出边界已经写入文档。

如果冻结后还要改共享契约，按 `freeze-v2` 执行：

1. 标出受影响的 track 和文件。
2. 暂停这些文件上的 coding。
3. 先更新 spec/interfaces。
4. 重新 review 并确认新的 freeze SHA。
5. 受影响分支 rebase 到新的 freeze 基线后再继续。

## 3. Track Layout

默认拆分如下：

| Track | 模块 | 内部顺序 | 主要产出 |
| --- | --- | --- | --- |
| A | `testcases/`, `planner/` | `testcases -> planner` | `TestCase`, `WorkflowPlan` |
| B | `pages/`, `detectors/`, `locators/` | `pages -> detectors -> locators` | `PageDescriptor`, `FeishuState`, `LocatorResult` |
| C | `workflows/`, `verifiers/` | `workflows -> verifiers` | workflow stage machine, `StepResult` |
| D | `reports/`, `maintenance/` | `reports -> maintenance` | `RuntimeContext` artifacts, report outputs |
| Serial | `feishu_worker` + `s3` 高耦合文件 | 最后执行 | 集成链路 |

默认并行顺序：

1. 第一波启动 `Track A + Track B + Track C`
2. `Track D` 在 `RuntimeContext` 结构稳定后接入
3. `Serial Track` 在 A/B/C/D 完成最小验证后开始

## 4. Track Handoff Gates

只有“顺序”还不够，必须有 handoff gate。

Track A handoff：

- `testcases/` done 条件：schema、正例、反例、preconditions 字段、断言字段都已固定
- `planner/` start 条件：`TestCase` 已冻结
- `planner/` done 条件：workflow 选路结果、params、preconditions 透传、失败原因输出已固定

Track B handoff：

- `pages/` done 条件：`page_id`、页面锚点、detector 消费字段已固定
- `detectors/` start 条件：`PageDescriptor` 已冻结
- `detectors/` done 条件：`FeishuState` 公共字段与扩展策略已固定
- `locators/` start 条件：`FeishuState`、`PageDescriptor` 已冻结
- `locators/` done 条件：成功/失败返回、`bbox` 格式、`page_id` 失败路径、`matched=false` 语义已固定

Track C handoff：

- `workflows/` start 条件：`WorkflowPlan`、`FeishuACI` 接口已冻结
- `workflows/` done 条件：stage name、retry、fallback、阶段输出已固定
- `verifiers/` start 条件：workflow stage 与 detector 输出已冻结
- `verifiers/` done 条件：`StepResult`、`failure_type`、断言失败语义已固定

Track D handoff：

- `reports/` start 条件：`RuntimeContext`、`ActionLog`、`StepResult` 已冻结
- `reports/` done 条件：`summary.json`、`report.md`、artifact 路径约定已固定
- `maintenance/` start 条件：report artifact 结构已稳定

Serial Track handoff：

- start 条件：A/B/C 至少完成模块级验证，D 如被依赖则完成对应契约
- done 条件：总装链路能从 `WorkflowPlan` 跑到 `RuntimeContext`

## 5. Dependency Stop-Go Rules

共享契约改动时，不是所有轨道都要停，按依赖矩阵处理：

| 变更源 | 受影响方 | 停止范围 |
| --- | --- | --- |
| `TestCase` / `WorkflowPlan` | A 的下游、C、Serial | 暂停依赖这些结构的文件 |
| `PageDescriptor` / `FeishuState` | B 的下游、C、D、Serial | 暂停消费这些结构的文件 |
| workflow stage / verifier 结果 | C 的下游、D、Serial | 暂停相关链路 |
| `RuntimeContext` | D、Serial | 暂停报告和集成消费端 |

规则：

1. 只暂停受影响文件，不必全仓停工。
2. 是否受影响由契约 owner 明确判定。
3. 无法确认时，默认按“受影响”处理。

## 6. Branch And Worktree

当前默认分支是 `master`。它是集成基线，不是功能开发分支。

推荐布局：

```bash
git fetch origin
git worktree list
git worktree add ../agent-s-master master
git worktree add ../agent-s-track-a -b feat/track-a master
git worktree add ../agent-s-track-b -b feat/track-b master
git worktree add ../agent-s-track-c -b feat/track-c master
git worktree add ../agent-s-track-d -b feat/track-d master
git worktree add ../agent-s-serial -b feat/serial-integration master
```

操作规则：

1. `master` worktree 保持干净，只做同步、冻结和集成检查。
2. 一个 worktree 只对应一个活跃分支和一个 owner。
3. 一个分支只在一个 worktree 中主动开发。
4. 开新 worktree 前先执行 `git worktree list`。
5. 合并完成后及时 `git worktree remove <path>`。
6. 不共享会冲突的 `.venv`、缓存或生成产物目录。
7. 临时评审或修补使用 `review/<topic>` 或 `fix/<topic>`。

如果旧分支和当前默认分支没有共同祖先：

1. 不要直接 `git rebase master`
2. 从当前默认分支新切一个兼容分支
3. 用 `cherry-pick`、按路径 checkout、手工补丁移植所需改动
4. 把新分支当成后续 PR 基线

## 7. Merge And Rebase Flow

标准流程：

1. 在默认分支完成契约冻结
2. 从同一个 freeze SHA 切出 `Track A / B / C`
3. 契约文档 PR 先合入
4. 各 track 分支开发并做最小验证
5. 合并前先同步默认分支，再 rebase 自己的 feature 分支
6. A/B/C 合入后，再切或刷新 `Track D`
7. `feat/serial-integration` 从上游 track 合流后的最新基线切出
8. `Serial Track` 最后合并

rebase 规则：

1. rebase 前先 `git status`
2. 有未提交改动先 commit 或 stash
3. rebase 后如果改到了已 review 的冲突区域，必须重新 review
4. 分支已推远端时使用 `git push --force-with-lease`
5. 不接受基于旧 freeze SHA 且未重新 rebase 的陈旧 PR 直接合并

## 8. Manual Plan Requirement

开始 coding 前，每个模块都要有短 plan：

```text
Module:
Owner:
Files:
Depends on:
Outputs:
Verification:
Out of Scope:
Risks:
```

没有 plan，不进入 coding。

## 9. Review Gates

Gate 1 Self-check：

- plan 已写
- 契约变更已同步文档
- 本地最小检查已跑
- 验证证据已附上

Gate 2 Module review：

- reviewer 检查模块边界
- reviewer 检查契约一致性
- reviewer 检查 fallback / failure path

Gate 3 Integration review：

- 触发条件：高耦合文件、多 track 合流、`feishu_worker`、`worker.py`、`grounding.py`、`cli_app.py`、`procedural_memory.py`
- 要求 reviewer 独立于该改动 owner
- 要明确集成风险和回滚方式

## 10. Local Checks

当前仓库最小门禁以 Python 格式检查为主。

Python 改动至少执行：

```bash
python -m black --check gui_agents/s3/agents gui_agents/s3/cli_app.py launcher.py
```

如果做了手工补丁或新增模块，建议再执行：

```bash
python - <<'PY'
import py_compile
for path in [
    "launcher.py",
    "gui_agents/s3/cli_app.py",
]:
    py_compile.compile(path, doraise=True)
print("compile ok")
PY
```

文档改动至少自查：

1. 链接是否正确
2. 文档之间口径是否一致
3. 契约命名是否冲突

## 11. PR Template Expectations

PR 描述至少写清：

- What
- Why
- Files
- Track
- Interface changes
- Verification
- Risks / Follow-ups

并行开发相关 PR 额外写清：

- Depends on
- Blocked by
- Freeze SHA

## 12. Current Minimum Execution Rule

当前仓库在测试体系未完善前，最低执行口径是：

1. 先冻结契约
2. 先并行 `Track A + Track B + Track C`
3. `Track D` 后接
4. `Serial Track` 最后集成
5. 高耦合文件必须走 Gate 3
