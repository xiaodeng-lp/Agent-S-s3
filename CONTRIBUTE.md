# Contribute

本文件是当前仓库的贡献与协作约束，覆盖：

- 分支与 `git worktree` 协作
- 并行开发原则
- PR 粒度与合并门禁
- 提交前本地检查
- 文档与契约同步要求

相关文档：

- [README.md](./README.md)
- [docs/README.md](./docs/README.md)
- [docs/process/feishu_gui_agent_parallel_dev_playbook.md](./docs/process/feishu_gui_agent_parallel_dev_playbook.md)
- [AGENTS.md](./AGENTS.md)

说明：

- 当前按你的要求先使用 `CONTRIBUTE.md`。
- 若后续希望 GitHub 自动展示贡献指南，建议再同步一份到 `CONTRIBUTING.md` 或 `.github/CONTRIBUTING.md`。

## 1. 贡献原则

参考成熟开源仓库的共识做法，当前仓库采用以下基本原则：

1. 小步提交，小 PR，单一目的。
2. 先同步 `main`，再在独立功能分支上开发。
3. 先更新契约和文档，再做跨模块实现。
4. 提交 PR 前先跑本地检查，不把明显会挂的改动直接交给 CI。
5. 对高耦合模块采取串行集成，对低耦合模块允许并行开发。

## 2. 分支与 Worktree

推荐分支命名：

- `feat/<topic>`
- `fix/<topic>`
- `docs/<topic>`
- `chore/<topic>`
- `feat/track-a`
- `feat/track-b`
- `feat/track-c`
- `feat/track-d`
- `feat/serial-integration`
- `review/<topic>`
- `backup/<topic>`

推荐 worktree 布局：

```bash
git fetch origin
git worktree add ../agent-s-main main
git worktree add ../agent-s-track-a feat/track-a
git worktree add ../agent-s-track-b feat/track-b
git worktree add ../agent-s-track-c feat/track-c
git worktree add ../agent-s-track-d feat/track-d
git worktree add ../agent-s-serial feat/serial-integration
```

规则：

1. `main` worktree 只负责同步和查看集成结果，不直接写功能代码。
2. 一个 worktree 只对应一个分支。
3. 一个分支只在一个 worktree 中主动开发。
4. 所有 track 分支应从同一个“契约已冻结”的 base commit 切出。

## 3. 并行开发原则

当前并行开发口径是：

- Track 之间并行
- Track 内部串行
- 契约先冻结
- 总装最后做

默认并行轨道：

1. `Track A`: `testcases/ -> planner/`
2. `Track B`: `pages/ -> detectors/ -> locators/`
3. `Track C`: `workflows/ -> verifiers/`
4. `Track D`: `reports/ -> maintenance/`
5. `Serial Track`: `feishu_worker` 与 `s3` 高耦合集成

执行规则：

1. 只有在 `spec` 与 `interfaces` 中完成共享契约冻结后，`Track A + Track B + Track C` 才能同时开始 coding。
2. 同一时刻只允许一个 owner 修改同一个文件。
3. 若某个 track 需要改共享契约，先暂停相关 track，先改文档并重新 review。
4. `Serial Track` 不参与第一波并行 coding，只做最后集成。

## 4. 先文档后实现

以下变更必须先更新文档，再进入实现：

1. 新增或修改共享数据结构
2. 新增或修改模块输入输出
3. 新增或修改 `FailureType`、`ActionId`、`TargetId`、`AssertionId`
4. 变更 Track 边界或联调顺序

对应文档：

- 产品范围、里程碑：`docs/product/`
- 架构和模块边界：`docs/spec/`
- 模块契约：`docs/interfaces/`
- 并行协作流程：`docs/process/`

## 5. 手动 Plan 要求

开始 coding 前，每个模块都要先有手动 plan。

最小模板：

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

没有手动 plan，不进入代码实现。

## 6. PR 粒度

建议每个 PR 只做一类事情：

1. 只改契约文档
2. 只落一个 Track 的一个阶段
3. 只做一个 workflow
4. 只做一个 verifier
5. 只做一次 Serial 集成修正

避免：

- 一个 PR 同时改契约、实现、集成和报告
- 一个 PR 同时跨多个高耦合目录
- 一个 PR 混入无关重构

## 7. 提交前本地检查

当前仓库已经存在的自动检查门禁主要是：

- `.github/workflows/lint.yml`
- `black --check gui_agents`

因此，提交前最小本地检查为：

### 7.1 Python 代码改动

若修改了 `gui_agents/`、`launcher.py`、`sop_executor.py` 或其他 Python 执行路径，至少执行：

```bash
python -m pip install --upgrade pip
pip install -e .[dev]
black --check gui_agents
```

若格式检查失败，可先本地修复：

```bash
black gui_agents
```

### 7.2 文档改动

若是纯文档 PR，可不跑 Python 运行检查，但应自查：

1. 链接是否正确
2. 文档之间是否口径一致
3. 新增命名是否与现有契约重复或冲突

### 7.3 行为改动

若修改了以下内容之一：

- `planner`
- `workflows`
- `detectors`
- `locators`
- `verifiers`
- `reports`
- `feishu_worker`

除格式检查外，还必须提供至少一条最小验证证据：

1. 运行命令
2. 结果摘要
3. 失败或限制说明

可接受的证据示例：

- 命令行输出摘要
- `summary.json` / `report.md` 路径
- 截图产物路径
- “仅文档与骨架，无运行环境，未执行集成测试”的明确说明

## 8. PR 描述模板

建议 PR 描述至少包含：

```text
What:
Why:
Files:
Track:
Interface changes:
Verification:
Risks / Follow-ups:
```

若是并行开发相关 PR，再补：

```text
Depends on:
Blocked by:
```

## 9. 合并门禁

以下任一条件不满足，不应合并：

1. 跨模块契约变更未同步更新文档
2. 本地最小检查未完成
3. CI 已知会失败但未说明原因
4. 无最小验证证据
5. 同时修改多个高耦合模块但没有单独说明集成风险

## 10. Review 重点

Review 时优先看这些问题：

1. 是否破坏模块边界
2. 是否把业务规则塞进 `Worker`
3. 是否引入新的隐式共享状态
4. 是否绕过 `RuntimeContext`
5. 是否在同一 workflow 上出现多个实现来源
6. 是否遗漏本地检查或验证证据

## 11. 当前仓库的最小执行口径

在仓库测试体系还未完善前，当前最小可执行要求是：

1. 契约先冻结
2. `Track A + Track B + Track C` 先并行
3. `Track D` 后接
4. `Serial Track` 最后集成
5. Python 代码 PR 至少本地跑 `black --check gui_agents`
6. 行为改动必须带最小验证说明

## 12. 参考实践

本文件参考了这些成熟仓库/平台的常见做法：

- GitHub Docs 的贡献指南设计建议
- CPython 对分支、PR、测试和贡献流程的要求
- pytest 对本地验证和贡献流程的要求
- Kubernetes 对小 PR、清晰描述和贡献流程的要求

建议后续若仓库测试矩阵完善，再把这里的“最小检查”升级为“必须通过的本地脚本集合”。
