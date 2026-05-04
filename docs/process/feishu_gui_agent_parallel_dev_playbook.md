# 飞书 GUI Agent 并行开发执行规范

## 1. 目的

本文档回答一个问题：在多人和多 coding agent 协作下，如何把飞书 GUI Agent 做成“模块解耦、可并行实现、可 review、可回归”的工程。

相关文档：

- [文档索引](../README.md)
- [主方案](../feishu_gui_agent_master_plan.md)
- [Technical Spec](../spec/feishu_gui_agent_technical_spec.md)
- [Interface Doc](../interfaces/feishu_gui_agent_interfaces.md)
- [CONTRIBUTE.md](../../CONTRIBUTE.md)

## 2. 并行开发前提

只有同时满足以下条件，才允许并行 coding：

1. 模块边界已经写入 `Technical Spec`
2. 输入输出契约已经写入 `Interface Doc`
3. 写入范围互不重叠
4. 已经完成模块级手动 plan

缺一项都不要并行。

## 2.1 契约冻结与并行 Coding 的关系

并行 coding 的前提不是“别人代码已经写完”，而是“共享契约已经冻结”。

明确规则：

1. 先在主分支完成共享契约冻结
2. 再启动各个 track 的并行 coding
3. 各个 track 在实现阶段只依赖已冻结的契约结构，不依赖其他 track 的实现代码

这意味着：

- `Track A` 可以先按 `TestCase` 和 `WorkflowPlan` 契约实现
- `Track B` 可以先按 `FeishuState`、`PageDescriptor`、`LocatorResult` 契约实现
- `Track C` 可以先按 `WorkflowPlan`、`FeishuACI` 方法签名、`Verifier` 契约实现

特别说明：

- `Track C` 依赖 `planner/` 和 `agents/` 的是“契约”，不是它们的实现代码
- 因此只要 `interfaces` 和 `spec` 已冻结，`Track A + Track B + Track C` 就可以同时开始 coding
- `Serial Track` 之所以最后做，是因为它承担总装集成，而不是因为前置契约不足

## 3. 角色分工

- `Planner`：选择 workflow，绑定业务参数，保留前置条件和进入执行前断言。
- `Workflow`：定义运行时阶段推进、fallback、retry。
- `FeishuWorker`：串联模块，不承载业务规则。
- `Verifier`：输出标准化步骤级和用例级结果。
- `ReportBuilder`：只消费 `RuntimeContext`，不消费 `Worker` 私有状态。

## 4. 推荐拆分方式

这里不是“四选一”。

默认方案是：

- `Track A / B / C / D` 可以同时推进
- `Serial Track` 必须在上游契约冻结后再接入

也就是说，推荐拆分方式不是给出多个可选套餐，而是给出一套默认并行分工。

执行约束：

1. 每个 track 同一时刻只允许一个 owner 负责同一文件
2. 不同 track 可以同时 coding
3. 若某个 track 需要改共享契约，先暂停相关 track，先改文档再继续
4. `Serial Track` 不参与第一波并行 coding

推荐默认编组：

- 1 人 / 1 agent：只做 `Track A`
- 2 人 / 2 agents：并行 `Track A + Track B`
- 3 人 / 3 agents：并行 `Track A + Track B + Track C`
- 4 人及以上：并行 `Track A + Track B + Track C + Track D`

当前项目建议默认采用：

1. 第一阶段并行 `Track A + Track B + Track C`
2. `Track D` 在 `RuntimeContext` 契约冻结后接入
3. `Serial Track` 最后接入

### Track A

- `gui_agents/feishu/testcases/`
- `gui_agents/feishu/planner/`

目标：把自然语言稳定收敛为 `workflow + workflow_params + preconditions`

Track 内部顺序：

1. `testcases/`
2. `planner/`

说明：

- `planner/` 依赖 `testcases/` 的输入模型
- Track A 内部默认串行，不建议同时实现这两个子目录

### Track B

- `gui_agents/feishu/pages/`
- `gui_agents/feishu/detectors/`
- `gui_agents/feishu/locators/`

目标：稳定产出 `FeishuState` 和 `LocatorResult`

Track 内部顺序：

1. `pages/`
2. `detectors/`
3. `locators/`

说明：

- `detectors/` 依赖页面描述与关键区域元数据
- `locators/` 依赖 `FeishuState` 与 `PageDescriptor`
- Track B 对外可并行于其他 track，但内部按此顺序推进

### Track C

- `gui_agents/feishu/workflows/`
- `gui_agents/feishu/verifiers/`

目标：按单 workflow 落地阶段机和步骤级验证

Track 内部顺序：

1. `workflows/`
2. `verifiers/`

说明：

- `workflows/` 依赖 `WorkflowPlan` 和 `FeishuACI` 契约
- `verifiers/` 依赖 `workflows/` 的阶段定义以及 `detectors/` 的状态契约
- Track C 内部也不是全并行，建议先固定 workflow，再补 verifier

### Track D

- `gui_agents/feishu/reports/`
- `gui_agents/feishu/maintenance/`

目标：沉淀 `RuntimeContext` 产物、截图、报告和维护能力

Track 内部顺序：

1. `reports/`
2. `maintenance/`

说明：

- `reports/` 先围绕 `RuntimeContext`、`ActionLog`、`StepResult` 落地
- `maintenance/` 在页面和截图产物稳定后再补

### Serial Track

- `gui_agents/feishu/agents/feishu_worker.py`
- `gui_agents/s3/agents/worker.py`
- `gui_agents/s3/agents/grounding.py`

目标：只在上游契约冻结后接入

说明：

- `Serial Track` 不与第一波 track 同时写集成逻辑
- 它的输入是 A/B/C/D 已冻结并经过最小验证的模块契约与实现

## 4.1 为什么这样拆

- `Track A` 负责把自然语言收敛成可执行计划，是其他模块的输入基线
- `Track B` 负责页面与定位事实，是执行链最核心的环境感知层
- `Track C` 负责把业务场景落成阶段机，是 workflow 级能力主战场
- `Track D` 负责报告与维护，依赖前面三条链路产出稳定事实模型
- `Serial Track` 是高耦合总装层，不适合作为第一波并行开发对象

## 5. 每个模块的手动 Plan 模板

每次 coding 前，plan 至少包含：

1. 目标文件
2. 依赖的上游契约
3. 本模块输出给谁消费
4. 最小验证方式
5. 风险和不做项

推荐格式：

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

## 6. 联调顺序

1. `Parser -> Planner`
2. `Pages/Detector -> Locator`
3. `Workflow -> Verifier`
4. `Worker -> RuntimeContext`
5. `ReportBuilder`

不要一开始就让 `Worker` 直接串所有模块。

## 6.1 Git Worktree 协作

推荐每个主要分支使用独立 worktree，避免来回 checkout 干扰本地开发。

worktree 与 track 的关系：

1. 共享契约冻结在主分支 worktree 完成
2. 每个 track 在独立 worktree 中 coding
3. `Serial Track` 在最后单独开 worktree 做总装集成

推荐基础流程：

```text
主分支冻结契约
  -> 为 Track A / B / C / D 分别创建独立分支与 worktree
  -> 各 track 在各自 worktree 中 coding
  -> 完成最小验证后合回集成分支
  -> Serial Track 独立 worktree 做总装联调
```

示例：

```bash
git fetch origin
git worktree add ../agent-s-main main
git worktree add ../agent-s-feat feat/your-branch
```

推荐目录角色：

- `../agent-s-main`：只用于同步和查看最新 `main`
- `../agent-s-feat`：只用于当前 feature 开发

若需要多人或多 agent 并行，可继续增加：

```bash
git worktree add ../agent-s-track-a feat/track-a
git worktree add ../agent-s-track-b feat/track-b
git worktree add ../agent-s-track-c feat/track-c
git worktree add ../agent-s-track-d feat/track-d
git worktree add ../agent-s-serial feat/serial-integration
```

推荐映射：

- `../agent-s-track-a` 对应 `Track A`
- `../agent-s-track-b` 对应 `Track B`
- `../agent-s-track-c` 对应 `Track C`
- `../agent-s-track-d` 对应 `Track D`
- `../agent-s-serial` 对应 `Serial Track`

推荐起点：

```bash
git checkout main
git pull --rebase origin main

git checkout -b feat/track-a
git checkout -b feat/track-b
git checkout -b feat/track-c
git checkout -b feat/track-d
git checkout -b feat/serial-integration
```

更稳妥的做法是：

1. 先在主分支合入契约冻结文档
2. 再从同一个 base commit 切出 `feat/track-a`、`feat/track-b`、`feat/track-c`
3. `feat/track-d` 在 `RuntimeContext` 稳定后再切
4. `feat/serial-integration` 最后再切

约定：

1. 一个 worktree 只对应一个分支
2. 一个分支只在一个 worktree 中进行主动开发
3. 不要在 `main` worktree 直接写功能代码
4. 所有 track 分支都应从同一个“契约已冻结”的 base commit 切出

## 6.2 Main 同步节奏

推荐节奏：

1. 在 `main` worktree 执行 `git pull --rebase origin main`
2. 切到各自 feature 分支所在 worktree
3. 执行 `git rebase main`
4. 解决冲突后继续开发

推荐命令：

```bash
cd ../agent-s-main
git pull --rebase origin main

cd ../agent-s-feat
git rebase main
```

规则：

- rebase 前先 `git status`
- 本地未提交改动先 `commit` 或 `stash`
- rebase 后若分支已推远端，使用 `git push --force-with-lease`

## 7. 合并门禁

以下任一条件不满足，不合并：

1. 跨模块契约变更未同步更新文档
2. 没有最小验证样例
3. 同时修改高耦合文件和多个上游契约
4. `review` 不能说明失败归因如何进入 `failure_type`
5. 不满足 [CONTRIBUTE.md](../../CONTRIBUTE.md) 中的最小本地检查要求

## 8. Review 重点

Review 不要只看“能不能跑”，而要重点看：

1. 是否破坏模块边界
2. 是否引入新的隐式共享状态
3. 是否绕过 `RuntimeContext`
4. 是否把业务规则塞进 `Worker`
5. 是否让同一 workflow 被多个实现源共同定义

## 9. 当前建议执行顺序

1. 先冻结 `WorkflowPlan`（即 Planner output）、`ActionLog`、`StepResult`、`RuntimeContext`
2. 再做 `IM` 的单一 workflow 端到端打通
3. 再复制模式到 `Docs` 和 `Calendar`
4. 最后再做跨产品联动与自愈

当前推荐落地节奏：

1. 先冻结契约
2. 并行启动 `Track A + Track B + Track C`
3. `Track D` 在运行时事实模型稳定后接入
4. `Serial Track` 最后接入并做总装联调

一句话口径：

- “Track 之间并行，Track 内部串行；契约先冻结，集成最后做。”
