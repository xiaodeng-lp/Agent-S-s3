# 飞书 GUI Agent 并行开发 Playbook

本文件是并行开发的操作手册。架构边界看 `master_plan`，提交规范看 `CONTRIBUTE.md`，这里专门回答“怎么并行做、什么时候停、怎么合流”。

相关文档：

- [主方案](../feishu_gui_agent_master_plan.md)
- [PRD](../product/feishu_gui_agent_prd.md)
- [Technical Spec](../spec/feishu_gui_agent_technical_spec.md)
- [Interface Doc](../interfaces/feishu_gui_agent_interfaces.md)
- [CONTRIBUTE.md](../../CONTRIBUTE.md)

## 1. 一句话口径

Track 之间并行，Track 内部串行；契约先冻结，总装最后做。

## 2. 并行前置条件

只有同时满足下面条件，才允许并行 coding：

1. 模块边界已经写入 `spec`
2. 输入输出契约已经写入 `interfaces`
3. 当前 milestone scope 已固定
4. 每个模块已有手动 plan

缺一项，都不要开并行 coding。

## 3. Contract Freeze Gate

### 3.1 冻结目标

最少冻结这些内容：

- `TestCase`
- `WorkflowPlan`
- `FeishuState`
- `PageDescriptor`
- `LocatorResult`
- `ActionLog`
- `StepResult`
- `RuntimeContext`
- 当前 track map
- 当前 milestone scope

### 3.2 冻结记录

冻结记录最少包含：

- freeze SHA
- freeze 日期
- owner
- reviewer
- 受影响 tracks

建议把这段记录写到冻结 PR 描述中。

### 3.3 并行启动条件

当且仅当共享契约冻结后，`Track A + Track B + Track C` 才能同时开始 coding。原因是它们依赖的是契约结构，不是其他 track 的实现代码。

特别说明：

- `Track C` 依赖 `planner/` 和 `agents/` 的是契约，不是实现
- `Track D` 依赖运行时事实模型，因此默认第二波再接
- `Serial Track` 最后做，是因为它负责总装，不是因为契约不足

### 3.4 Freeze Reopen

冻结后如果还要改共享契约，按 `freeze-v2` 处理：

1. 标记变更源和受影响 track
2. 暂停受影响文件上的 coding
3. 先更新 `spec` 与 `interfaces`
4. 重新 review
5. 生成新的 freeze SHA
6. 相关分支 rebase 到新基线后再继续

## 4. Track 拆分与交接门禁

### 4.1 Track Map

| Track | 模块 | Consumes | Produces | Start Gate | Done Gate | Blocks |
| --- | --- | --- | --- | --- | --- | --- |
| A | `testcases/`, `planner/` | 项目需求、PRD | `TestCase`, `WorkflowPlan` | freeze 完成 | 结构、样例、失败输出固定 | C, Serial |
| B | `pages/`, `detectors/`, `locators/` | 页面知识、视觉事实 | `PageDescriptor`, `FeishuState`, `LocatorResult` | freeze 完成 | 页面、状态、定位返回固定 | C, D, Serial |
| C | `workflows/`, `verifiers/` | `WorkflowPlan`, `FeishuACI`, `FeishuState` | workflow 阶段机、`StepResult` | A/B 契约冻结 | stage、retry、failure_type 固定 | D, Serial |
| D | `reports/`, `maintenance/` | `RuntimeContext`, `ActionLog`, `StepResult` | `summary.json`, `report.md`, artifact 约定 | 运行时事实模型冻结 | 报告与产物结构固定 | Serial |
| Serial | `feishu_worker` + `s3` 高耦合文件 | A/B/C/D 稳定实现 | 端到端集成链路 | A/B/C 完成最小验证 | 从 plan 到 runtime context 全链路可跑 | 最终发布 |

### 4.2 Track A

内部顺序：

1. `testcases/`
2. `planner/`

handoff gate：

- `testcases/` done：schema、preconditions、assertions、正反例齐全
- `planner/` start：`TestCase` 已冻结
- `planner/` done：`WorkflowPlan`、workflow 选路、params、preconditions 透传、失败原因已固定

### 4.3 Track B

内部顺序：

1. `pages/`
2. `detectors/`
3. `locators/`

handoff gate：

- `pages/` done：`page_id`、anchor、detector 消费字段已固定
- `detectors/` start：`PageDescriptor` 已冻结
- `detectors/` done：`FeishuState` 公共字段和扩展策略已固定
- `locators/` start：`FeishuState`、`PageDescriptor` 已冻结
- `locators/` done：成功返回、失败返回、`bbox` 格式、`page_id` 失败语义已固定

### 4.4 Track C

内部顺序：

1. `workflows/`
2. `verifiers/`

handoff gate：

- `workflows/` start：`WorkflowPlan`、`FeishuACI` 已冻结
- `workflows/` done：stage、retry、fallback、阶段输出已固定
- `verifiers/` start：workflow stage 和 detector 输出已冻结
- `verifiers/` done：`StepResult`、`failure_type`、断言失败语义已固定

### 4.5 Track D

内部顺序：

1. `reports/`
2. `maintenance/`

handoff gate：

- `reports/` start：`RuntimeContext`、`ActionLog`、`StepResult` 已冻结
- `reports/` done：`summary.json`、`report.md`、artifact path 已固定
- `maintenance/` start：报告和产物结构稳定

### 4.6 Serial Track

只在最后启动。

start gate：

- A/B/C 已完成模块级最小验证
- D 如被依赖，则对应契约已稳定
- 高耦合文件 owner 已明确

done gate：

- 端到端链路能从 `WorkflowPlan` 跑到 `RuntimeContext`
- 关键失败路径能落到统一 `failure_type`

## 5. Dependency Pause Matrix

| 变更源 | 影响 | 停止范围 |
| --- | --- | --- |
| `TestCase` / `WorkflowPlan` | C, Serial | 暂停消费 plan 的文件 |
| `PageDescriptor` / `FeishuState` | B 下游, C, D, Serial | 暂停消费页面与状态结构的文件 |
| workflow stage / verifier 结果 | D, Serial | 暂停报告和集成相关文件 |
| `RuntimeContext` | D, Serial | 暂停所有运行时产物消费者 |

规则：

1. 只暂停受影响文件，不做全仓停工。
2. 受影响范围由契约 owner 判断。
3. 判断不清时按“受影响”处理。

## 6. 推荐并行顺序

默认建议：

1. 先冻结契约
2. 并行启动 `Track A + Track B + Track C`
3. `Track D` 在 `RuntimeContext` 契约稳定后接入
4. `Serial Track` 最后做总装联调

为什么这样拆：

- `Track A` 负责把自然语言收敛为可执行计划
- `Track B` 负责页面与定位事实
- `Track C` 负责 workflow 阶段机和步骤验证
- `Track D` 负责把运行时事实沉淀成可评估产物
- `Serial Track` 是高耦合层，不适合第一波并行

## 7. Worktree Operating Rules

当前默认分支是 `master`。建议每个主分支使用独立 worktree。

推荐示例：

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

角色映射：

- `../agent-s-master`: 只做同步、冻结、集成检查
- `../agent-s-track-a`: Track A
- `../agent-s-track-b`: Track B
- `../agent-s-track-c`: Track C
- `../agent-s-track-d`: Track D
- `../agent-s-serial`: Serial Track

操作规则：

1. `master` worktree 保持干净
2. 一个 worktree 只对应一个活跃分支
3. 一个分支只在一个 worktree 中主动开发
4. 不共享会冲突的 `.venv`、缓存或生成产物
5. 开新 worktree 前先跑 `git worktree list`
6. 分支合并后及时 `git worktree remove`
7. 阻塞修补使用 `review/<topic>` 或 `fix/<topic>` 分支，不要直接在 `master` 上改

## 8. Merge / Rebase Canonical Flow

标准合流顺序：

1. 在 `master` 完成 freeze PR
2. 从同一个 freeze SHA 切出 `Track A / B / C`
3. A/B/C 开发并各自完成最小验证
4. 合并前先更新 `master`
5. 各自 feature 分支 rebase 到最新 `master`
6. 通过 review 后按依赖顺序合并
7. `Track D` 需要时再切出并合入
8. `feat/serial-integration` 从上游合流后的新基线切出
9. `Serial Track` 最后合并

rebase 规则：

1. rebase 前先 `git status`
2. 有未提交改动先 commit 或 stash
3. rebase 改到已 review 的冲突区域时必须重新 review
4. 远端分支更新使用 `git push --force-with-lease`
5. 不接受未 rebase 到最新基线的陈旧 PR

特殊规则：

如果旧分支和当前默认分支没有共同祖先，不做常规 rebase，改为从当前默认分支新切分支后手工移植需要的改动。

## 9. Review Gate Ladder

### Gate 1 Self-check

必须具备：

- 手动 plan
- 文档同步
- 最小本地验证
- 验证证据

### Gate 2 Module Review

重点检查：

- 模块边界是否被破坏
- 契约是否一致
- fallback / failure path 是否完整

### Gate 3 Integration Review

触发条件：

- `feishu_worker`
- `worker.py`
- `grounding.py`
- `cli_app.py`
- `procedural_memory.py`
- 多 track 合流

要求：

- reviewer 独立于 owner
- 明确集成风险
- 明确回滚方式

## 10. 当前建议执行节奏

1. 先冻结 `WorkflowPlan`、`ActionLog`、`StepResult`、`RuntimeContext`
2. 先做 IM 单产品端到端链路
3. 再复制模式到 Docs 和 Calendar
4. 最后做跨产品联动和更复杂的自愈能力
