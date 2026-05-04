# 飞书 GUI Agent Technical Spec

## 1. 文档定位

本文档定义飞书 GUI Agent 的技术方案、模块拆分、数据流、阶段实现边界与非功能要求。

相关文档：

- [文档索引](../README.md)
- [PRD](../product/feishu_gui_agent_prd.md)
- [接口文档](../interfaces/feishu_gui_agent_interfaces.md)
- [主方案](../feishu_gui_agent_master_plan.md)

## 2. 系统目标

构建一个 GUI-first 的飞书桌面端测试 Agent，满足：

- 自然语言测试描述输入
- 结构化 testcase
- workflow 驱动执行
- 可插拔定位策略
- step / case 验证
- 报告输出

## 3. 总体架构

```text
Natural Language Input
  -> NL Testcase Parser
  -> Planner / Workflow Selector
  -> FeishuWorker
  -> StateDetector
  -> Locator
  -> FeishuACI
  -> Verifier
  -> ReportBuilder
  -> Test Artifacts
```

## 4. 模块拆分

### 4.1 `testcases/`

- 自然语言解析
- testcase schema 定义
- testcase 校验

### 4.2 `planner/`

- workflow 选择
- 业务参数绑定
- 进入执行前约束整理

### 4.3 `detectors/`

- 页面状态识别
- 输入框、弹窗、搜索框、发送按钮等关键状态判断

### 4.4 `locators/`

- 元素定位策略抽象
- 视觉定位
- 混合定位预留

### 4.5 `agents/`

- 飞书语义动作
- workflow 运行时上下文管理

### 4.6 `workflows/`

- 显式阶段机
- step 级 success gate / fallback / retry

### 4.7 `verifiers/`

- step 级验证
- case 级验证
- 失败分类

### 4.8 `pages/`

- 页面描述符
- 页面注册表
- key regions / anchors 元数据

### 4.9 `reports/`

- summary 生成
- report 生成
- 指标统计

### 4.10 `maintenance/`

- 锚点截图录制
- 锚点校验
- 漂移检测

## 5. 数据模型

### 5.1 TestCase

```json
{
  "id": "tc_im_send_message_001",
  "product": "im",
  "title": "在测试群发送消息并验证发送成功",
  "preconditions": ["飞书桌面端已登录"],
  "steps": [
    {"action": "open_chat", "target": "测试群"},
    {"action": "type_message", "payload": {"text": "Hello World"}},
    {"action": "send_message"}
  ],
  "assertions": ["chat_title_matched", "message_sent"]
}
```

### 5.2 FeishuState

```python
from dataclasses import dataclass


@dataclass
class FeishuState:
    page_type: str
    product: str
    chat_name: str | None
    message_input_visible: bool
    send_button_visible: bool
    search_box_visible: bool
    modal_type: str | None
    last_error_banner: str | None
    product_state: dict
```

说明：

- `FeishuState` 是跨子产品共享的基础状态结构。
- `chat_name`、`message_input_visible`、`send_button_visible` 等字段当前主要服务 `IM`，用于 M0-M2 的主路径落地。
- 从 M3 开始，`Docs`、`Calendar` 等子产品的特有状态统一放入 `product_state: dict`，避免在基类上持续堆叠大量稀疏可选字段。
- 若后续某个子产品形成稳定高频字段，再从 `product_state` 上提为共享字段。

### 5.3 PageDescriptor

```python
from dataclasses import dataclass


@dataclass
class PageDescriptor:
    page_id: str
    page_type: str
    display_name: str
    layout_hints: dict
    key_regions: dict
    text_anchors: list[str]
    supported_workflows: list[str]
    ui_version_tag: str
```

## 6. 规划决策层

Parser 最低要求：

- 识别 `product`
- 识别 `workflow intent`
- 识别 `inputs`
- 识别 `assertions`
- 支持多步骤串联

Planner 最低要求：

- 优先命中显式 workflow
- 输出稳定 `workflow` 与业务参数绑定结果
- 保留执行前需要的 `preconditions` 和 `entry_assertions`
- 不允许整条任务直接落入不受控自由执行

Planner 输出建议最小结构：

```python
{
    "workflow": "send_message",
    "reason": "matched product=im and action intent=send_message",
    "workflow_params": {
        "chat_name": "测试群",
        "message_text": "Hello World",
    },
    "entry_assertions": ["chat_title_matched"],
    "preconditions": ["飞书桌面端已登录"],
    "failure_type": None,
    "failure_reason": None,
}
```

前置条件策略：

- `preconditions` 由 `FeishuWorker` 在真正执行 workflow 前统一检查，不由 Parser 直接判定。
- 当前 M0-M1 阶段允许部分前置条件通过人工保证，未自动化校验的项在运行结果中标记为 `assumed`，避免误报为已验证。
- `Planner` 负责保留 `TestCase.preconditions` 并将其透传给执行层，不负责具体检查执行。
- 若 `Planner` 在执行前就判定无法进入受控 workflow，必须返回共享 `failure_type`，不能只返回自由文本 `failure_reason`。

Planner / Workflow 边界：

- `Planner` 负责“选哪条路”，即 `workflow` 选择、业务参数绑定、进入执行前的约束。
- `Workflow` 负责“这条路每一步怎么走”，即 `next_step`、`fallback`、`retry_limit`、阶段推进。
- `FeishuWorker` 只负责编排，不拥有业务规则；业务规则落在 `Planner` 和 `Workflow`。

命名约定：

- `Planner` 的标准输出结构在本文档与接口文档中统一称为 `WorkflowPlan`。
- 若后续代码实现不单独定义类型别名，至少要保证 `Planner output` 与这里的 `WorkflowPlan` 字段保持一致。

## 6.1 FeishuWorker 执行职责

`FeishuWorker` 是执行中枢，最低职责为：

1. 接收 `TestCase`
2. 执行前置条件检查
3. 调用 `Planner / Workflow Selector`
4. 驱动 `StateDetector -> Locator -> FeishuACI -> Verifier` 的循环
5. 聚合运行上下文并交给 `ReportBuilder`

最小执行生命周期：

```text
run_testcase(testcase)
  -> check_preconditions
  -> select workflow and workflow params
  -> for each step:
       detect state
       locate target if needed
       execute action
       verify step
       fallback / retry if needed
  -> verify case
  -> build report
  -> return RuntimeContext
```

## 6.2 运行时事实模型

为支持并行开发与回归审阅，运行时统一沉淀三类事实对象：

1. `ActionLog`
2. `StepResult`
3. `RuntimeContext`

最小约束：

- `ActionLog` 记录“做了什么”。
- `StepResult` 记录“这一步是否成功，以及为什么”。
- `RuntimeContext` 聚合整次运行的前置条件、动作日志、步骤结果、失败归因和产物索引。
- `ReportBuilder`、`review`、回归工具统一从 `RuntimeContext` 取数，不直接读取 `Worker` 私有中间状态。

`RuntimeContext.failure_type` 语义：

- 当运行在执行前失败，例如 `precondition` 不满足、`workflow` 未命中时，使用顶层 `failure_type` 直接表达整次运行失败原因。
- 当运行进入步骤执行后失败，顶层 `failure_type` 取“导致整次运行终止的首个失败步骤”的 `step_results[].failure_type`。
- 当整次运行成功时，顶层 `failure_type` 为 `None`。
- `ReportBuilder` 应优先使用顶层 `failure_type` 做 case 级聚合，步骤级明细再读取 `step_results[]`。

## 7. 定位策略

### 7.1 Vision Locator

当前主路径：

- screenshot
- OCR / VLM
- visual anchors
- relative bounds

### 7.2 Accessibility Locator

当前阶段可不实现，但必须保留接口，用于未来接入：

- Electron Accessibility Tree
- 原生可访问性信息

### 7.3 Hybrid Locator

融合：

- 视觉候选
- Accessibility 候选
- 规则或权重排序

定位结果约束：

- `bbox` 统一使用 `[x1, y1, x2, y2]`。
- 定位失败时必须返回结构化失败结果，不允许用 `0` 坐标或省略字段代替失败语义。
- `page_context` 以 `PageDescriptor` 为核心，可附加运行时局部区域信息，但不能脱离页面描述符体系自行定义。
- 若定位失败但页面识别成功，`page_id` 返回当前已识别页面的 `PageDescriptor.page_id`。
- 若页面本身也无法可靠识别，`page_id` 返回 `None`。

## 8. workflow 规范

workflow 必须是显式阶段机。

每个阶段至少包含：

- `entry_condition`
- `semantic_action`
- `success_gate`
- `fallback`
- `retry_limit`

workflow 约束：

- 每个 workflow 文件只负责一个业务场景，例如 `send_message`。
- `Workflow` 内部不得重新选择其他 workflow；切换场景必须回到 `Planner` 层。
- 同一时刻只允许一个 agent 负责同一 workflow 文件，避免多 agent 争抢阶段机定义。

## 9. 报告与产物

产物目录建议：

```text
artifacts/
  test_runs/
    <run_id>/
      screenshots/
      actions.jsonl
      summary.json
      report.md
```

`summary.json` 建议字段：

- `task_id`
- `product`
- `workflow`
- `status`
- `steps`
- `duration_sec`
- `assertions`
- `failure_type`
- `failure_reason`

失败语义约定：

- `failure_type` 是面向聚合统计的标准枚举。
- `failure_reason` 是面向人读和排障的自由文本说明。
- `ReportBuilder` 只按 `failure_type` 做分类统计，不直接依赖自由文本。

## 10. 非功能要求

- 可回归
- 可定位失败原因
- 可维护
- 允许模块级并行开发
- 主链不被开放平台能力污染

## 11. 模块依赖与并行开发

| 模块 | 主要输出 | 直接依赖 | 并行开发建议 |
| --- | --- | --- | --- |
| `testcases/` | `TestCase` schema、parser | 无 | 可先行，作为其他模块输入基线 |
| `planner/` | workflow 选择、业务参数绑定 | `TestCase` | 与 `detectors/`、`pages/` 并行，但先冻结输入输出 |
| `pages/` | `PageDescriptor`、页面元数据 | 无 | 可与 `detectors/` 并行 |
| `detectors/` | `FeishuState` | `pages/` | 可与 `locators/` 并行 |
| `locators/` | 统一定位结果 | `pages/`、`FeishuState` | 先实现 `VisionLocator`，其余保留接口 |
| `agents/` | `FeishuACI`、`FeishuWorker`、运行时调度 | `planner/`、`locators/`、`detectors/`、`verifiers/` | 尽量串行，属于高耦合层 |
| `workflows/` | 显式阶段机、fallback、retry | `planner/`、`agents/` | 可按单 workflow 分模块并行 |
| `verifiers/` | step/case 验证结果 | `detectors/`、`workflows/` | 可与 `reports/` 并行 |
| `reports/` | `summary.json`、`report.md` | `verifiers/`、运行日志 | 低耦合，适合独立开发 |
| `maintenance/` | anchor 校验、截图录制 | `pages/`、`detectors/` | 与主执行链解耦，独立推进 |

并行开发规则：

1. 先冻结接口，再并行 coding；不要一边改接口一边多模块同时实现。
2. 高耦合模块优先串行：`gui_agents/s3/agents/worker.py`、`grounding.py`、未来的 `gui_agents/feishu/agents/feishu_worker.py`。
3. 任一模块若需要跨边界新增字段，先更新 `interfaces`，再进入实现。
4. workflow 应按单一职责拆分，避免多个 agent 共同修改同一 workflow 文件。

## 12. 实施顺序建议

1. 先定 `TestCase`、`WorkflowPlan`、`FeishuState`、`LocatorResult`、`ActionLog`、`StepResult`、`RuntimeContext` 这些基础契约。
2. 再做 `testcases/` 与 `planner/`，保证自然语言输入先收敛成结构化计划。
3. 随后并行推进 `pages/`、`detectors/`、`locators/`。
4. 在状态识别和定位稳定后，再按单一场景并行补 `workflows/` 与 `verifiers/`。
5. `FeishuWorker` 在各模块契约冻结后再串行接入。
6. 最后处理 `reports/`、异常、自愈、跨产品联动等进阶能力。
