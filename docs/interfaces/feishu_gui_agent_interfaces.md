# 飞书 GUI Agent Interface Doc

## 1. 文档定位

本文档定义飞书 GUI Agent 内部模块接口、输入输出契约和阶段边界。

这不是开放平台 API 文档，而是项目内部模块接口文档。

相关文档：

- [文档索引](../README.md)
- [主方案](../feishu_gui_agent_master_plan.md)
- [PRD](../product/feishu_gui_agent_prd.md)
- [Technical Spec](../spec/feishu_gui_agent_technical_spec.md)

## 2. 契约使用原则

1. 任何跨模块协作都先遵守本文档约定，不允许绕过接口直连内部实现。
2. 需要并行开发时，先冻结字段与返回值，再拆分任务。
3. 发生破坏性变更时，必须同步更新 `Technical Spec` 和调用方。

## 3. TestCase Parser Interface

### 输入

- `instruction: str`

### 输出

```python
{
    "id": "tc_im_send_message_001",
    "product": "im",
    "title": "在测试群发送消息并验证发送成功",
    "preconditions": ["飞书桌面端已登录"],
    "steps": [
        {
            "step_id": "step_1",
            "action": "open_chat",
            "target": "测试群",
            "payload": None,
            "assertion": "chat_opened"
        },
        {
            "step_id": "step_2",
            "action": "type_message",
            "target": "message_input",
            "payload": {"text": "Hello World"},
            "assertion": "message_input_contains_text"
        },
        {
            "step_id": "step_3",
            "action": "send_message",
            "target": "send_button",
            "payload": None,
            "assertion": "message_sent"
        }
    ],
    "assertions": ["chat_title_matched", "message_sent"]
}
```

## 4. FailureType Contract

共享失败分类枚举：

```python
FailureType = Literal[
    "recognition",
    "location",
    "action",
    "verification",
    "timeout",
    "precondition",
]
```

约定：

- `failure_type` 用于标准化统计和聚合。
- `failure_reason` 用于补充具体失败原因，可为自然语言或结构化短句。
- `failure_reason` 不能替代 `failure_type`。

## 5. Planner / Workflow Selector Interface

该输出结构统一命名为 `WorkflowPlan`。

### 输入

- `testcase: dict`
- `state: FeishuState | None`

### 输出

```python
{
    "workflow": "send_message",
    "reason": "matched product=im and action intent=send_message",
    "workflow_params": {
        "chat_name": "测试群",
        "message_text": "Hello World"
    },
    "entry_assertions": ["chat_title_matched"],
    "preconditions": ["飞书桌面端已登录"],
    "failure_type": None,
    "failure_reason": None
}
```

### `WorkflowPlan` 类型别名

```python
WorkflowPlan = dict
```

说明：

- `Planner` 保留并透传 `preconditions`，但不负责最终执行检查。
- `Planner` 若在执行前失败，`failure_type` 必须复用共享 `FailureType` 枚举。
- `Planner` 只负责选择 `workflow`、绑定业务参数、给出进入执行前的约束，不负责产出运行时 `fallback` / `retry` / 每轮下一步。
- 若未命中 workflow，`workflow` 为空，`failure_reason` 需要给出可审阅原因。

## 5.1 Shared Id Contracts

最小共享标识建议：

```python
ActionId = Literal[
    "open_chat",
    "focus_message_input",
    "type_message",
    "send_message",
]

TargetId = Literal[
    "chat_search_box",
    "chat_result_item",
    "message_input",
    "send_button",
]

AssertionId = Literal[
    "chat_title_matched",
    "message_input_contains_text",
    "message_sent",
]
```

约定：

- `Parser`、`Workflow`、`Locator`、`Verifier` 共享同一套 `ActionId / TargetId / AssertionId`。
- 新增共享标识前，先更新本文档，再允许并行开发模块引用。

## 6. StateDetector Interface

### 输入

- `observation: dict`

### 输出

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

- `FeishuState` 是基础状态模型。
- `product_state` 承载子产品特有状态，例如：
  - `Docs`: `{"doc_title": "...", "editor_ready": True}`
  - `Calendar`: `{"selected_date": "2026-05-05", "time_picker_visible": True}`

## 7. Locator Interface

统一定位接口建议：

```python
class BaseLocator:
    def locate(self, target: str, state, observation, page_context=None) -> dict:
        ...
```

`page_context` 约定：

```python
{
    "page_descriptor": PageDescriptor,
    "active_region": str | None,
    "region_bounds": list[int] | None,
}
```

### 输出

```python
{
    "matched": True,
    "strategy": "vision",
    "x": 123,
    "y": 456,
    "confidence": 0.91,
    "bbox": [100, 430, 146, 482],
    "page_id": "im_chat_main"
}
```

字段约定：

- `bbox` 固定为 `[x1, y1, x2, y2]`
- `x`、`y` 表示点击中心点坐标
- `page_id` 应与 `PageDescriptor.page_id` 对齐
- 若定位失败但页面识别成功，`page_id` 返回当前页面的 `PageDescriptor.page_id`
- 若页面也无法可靠识别，`page_id` 返回 `None`

失败输出示例：

```python
{
    "matched": False,
    "strategy": "vision",
    "x": None,
    "y": None,
    "confidence": 0.0,
    "bbox": None,
    "page_id": None,
    "failure_type": "location",
    "failure_reason": "anchor text not found in current viewport"
}
```

实现类型：

- `VisionLocator`
- `AccessibilityLocator`
- `HybridLocator`

## 8. FeishuACI Interface

```python
class FeishuACI:
    def open_chat(self, chat_name: str): ...
    def ensure_in_chat(self, chat_name: str): ...
    def focus_message_input(self): ...
    def clear_message_input(self): ...
    def type_message(self, text: str): ...
    def send_message(self): ...
    def recover_from_modal_or_wrong_page(self): ...
```

## 9. FeishuWorker Interface

```python
class FeishuWorker:
    def run_testcase(self, testcase: dict) -> RuntimeContext: ...
    def check_preconditions(self, testcase: dict) -> list[dict]: ...
```

### `check_preconditions` 输出

```python
[
    {
        "name": "飞书桌面端已登录",
        "status": "passed",
        "failure_type": None,
        "failure_reason": None
    },
    {
        "name": "测试群已存在",
        "status": "assumed",
        "failure_type": None,
        "failure_reason": "not automated in M1"
    }
]
```

### `run_testcase` 最小职责

1. 执行前置条件检查
2. 获取 workflow 选择结果
3. 逐步调度 `StateDetector / Locator / FeishuACI / Verifier`
4. 聚合 `RuntimeContext`
5. 调用 `ReportBuilder`

### `run_testcase` 输出

```python
{
    "run_id": "2026-05-04_153000",
    "status": "passed",
    "workflow": "send_message",
    "precondition_results": [
        {"name": "飞书桌面端已登录", "status": "passed"}
    ],
    "step_results": [],
    "failure_type": None,
    "failure_reason": None
}
```

## 10. Workflow Interface

```python
class BaseWorkflow:
    workflow_id: str

    def next_step(self, state, runtime_context) -> dict: ...
    def is_done(self, state, runtime_context) -> bool: ...
```

### `next_step` 输出

```python
{
    "step_id": "step_2",
    "stage": "TYPE_MESSAGE",
    "action": "type_message",
    "target": "message_input",
    "params": {"text": "Hello World"},
    "success_gate": "message_input_contains_text",
    "fallback": "refocus_input",
    "retry_limit": 1
}
```

说明：

- `Workflow` 独占运行时阶段推进。
- `fallback`、`retry_limit`、具体 `next_step` 产出都属于 `Workflow`，不属于 `Planner`。

## 11. Verifier Interface

```python
class BaseVerifier:
    def verify_step(self, expected: dict, state, observation, runtime_context) -> dict: ...
    def verify_case(self, testcase: dict, runtime_context) -> dict: ...
```

### `verify_step` 输出

```python
{
    "passed": True,
    "step_id": "step_2",
    "assertion": "message_input_contains_text",
    "evidence": ["ocr:text=Hello World"],
    "failure_type": None,
    "failure_reason": None
}
```

### `verify_case` 输出

```python
{
    "passed": True,
    "total_steps": 3,
    "passed_steps": 3,
    "failed_steps": 0,
    "failure_type": None,
    "failure_reason": None
}
```

## 12. ActionLog Interface

```python
{
    "timestamp": "2026-05-04T15:30:04+08:00",
    "step_id": "step_2",
    "stage": "TYPE_MESSAGE",
    "action": "type_message",
    "target": "message_input",
    "params": {"text": "Hello World"},
    "status": "executed"
}
```

## 13. StepResult Interface

```python
{
    "step_id": "step_2",
    "stage": "TYPE_MESSAGE",
    "action": "type_message",
    "target": "message_input",
    "status": "passed",
    "locator_result": {
        "matched": True,
        "page_id": "im_chat_main"
    },
    "verification_result": {
        "passed": True,
        "assertion": "message_input_contains_text"
    },
    "failure_type": None,
    "failure_reason": None
}
```

## 14. ReportBuilder Interface

```python
class ReportBuilder:
    def build_summary(self, testcase: dict, runtime_context: dict) -> dict: ...
    def build_markdown(self, summary: dict) -> str: ...
```

### `build_summary` 输出

```python
{
    "task_id": "tc_im_send_message_001",
    "product": "im",
    "workflow": "send_message",
    "status": "passed",
    "steps": 3,
    "duration_sec": 18.4,
    "assertions": [
        {"name": "chat_title_matched", "passed": True},
        {"name": "message_sent", "passed": True}
    ],
    "failure_type": None,
    "failure_reason": None
}
```

## 15. RuntimeContext Interface

```python
{
    "run_id": "2026-05-04_153000",
    "status": "passed",
    "workflow": "send_message",
    "workflow_params": {"chat_name": "测试群", "message_text": "Hello World"},
    "page_id": "im_chat_main",
    "precondition_results": [],
    "action_logs": [],
    "screenshots": [],
    "step_results": [],
    "failure_type": None,
    "failure_reason": None,
    "started_at": "2026-05-04T15:30:00+08:00"
}
```

约定：

- `action_logs` 使用 `ActionLog` 结构。
- `step_results` 使用 `StepResult` 结构。
- 顶层 `failure_type` 表示整次运行的 case 级失败归因。
- 若失败发生在执行前，顶层 `failure_type` 直接记录该失败。
- 若失败发生在步骤执行中，顶层 `failure_type` 取导致整次运行终止的首个失败步骤的 `step_results[].failure_type`。
- 若整次运行成功，顶层 `failure_type` 为 `None`。
- `ReportBuilder`、`review`、`regression runner` 统一消费 `RuntimeContext`，不要直接依赖 `FeishuWorker` 私有内部变量。

## 16. Maintenance Interfaces

```python
class ScreenshotRecorder:
    def record_page(self, page_id: str) -> None: ...


class AnchorValidator:
    def validate_page(self, page_id: str, screenshot: bytes) -> dict: ...
    def suggest_refresh(self, page_id: str) -> list[str]: ...
```

## 17. 产物接口

统一产物目录：

```text
artifacts/
  test_runs/
    <run_id>/
      screenshots/
      actions.jsonl
      summary.json
      report.md
```

`summary.json` 最小字段：

```python
{
    "task_id": "tc_im_send_message_001",
    "product": "im",
    "workflow": "send_message",
    "status": "passed",
    "steps": 3,
    "duration_sec": 18.4,
    "assertions": [],
    "failure_type": None,
    "failure_reason": None
}
```

## 18. 接口变更规则

1. 新增字段优先向后兼容，避免直接改名或改语义。
2. `steps[]`、`success_gate`、`fallback`、`retry_limit` 属于稳定核心字段，不应随模块实现随意漂移。
3. 任一并行开发模块若修改接口，必须在合并前完成调用方联调和文档更新。
