# 面向飞书桌面端 GUI Agent 的二开方案

## 1. 当前结论

当前阶段不把飞书 CLI、bot、开放平台接口当成主路线。

原因：

1. 当前目标场景主要是个人用户或普通桌面用户，很多能力没有可直接复用的开放接口。
2. 即便存在开放平台能力，也通常更像“主账号创建机器人后执行特定动作”，不等价于真实桌面用户操作。
3. 这个项目现在真正要解决的是 GUI 状态识别、动作稳定性、完成验证、失败恢复和回归，而不是接口接入。

因此当前二开基线应明确为：

- 主路径：`Windows + 飞书桌面端 + GUI 自动化`
- 辅路径：`code agent` 做文本生成、内容整理、局部策略辅助
- 暂不纳入主路径：飞书 CLI、bot 驱动、开放平台 API 驱动

未来如果目标场景切到企业自建应用、受控组织账号或明确依赖开放平台能力，再把 API 适配作为独立扩展层接回。

## 1.1 与项目需求的直接对应关系

`docs/项目需求.md` 的目标不是单纯“把飞书操作起来”，而是构建一个面向测试与质量评估的 CUA-Lark Agent。

因此当前设计必须显式覆盖 5 个核心能力：

1. 视觉感知：识别页面、UI 元素、界面状态和布局
2. 语义理解：把自然语言测试指令拆成可执行步骤
3. 自主操作：点击、输入、滚动、快捷键、多步串联
4. 状态验证：操作后判断结果是否符合预期
5. 评估报告：输出操作轨迹、成功率、耗时、步骤数等指标

对应到当前二开结构，应当映射为：

- 视觉感知 -> `StateDetector` + `PageRegistry` + `Visual Anchor`
- 语义理解 -> `FeishuWorker` + workflow selector + task parser
- 自主操作 -> `FeishuACI` + `gui_agents/s3/`
- 状态验证 -> `Verifier` + OCR / VLM / visual diff
- 评估报告 -> regression artifacts + report exporter

## 2. 为什么只扩 memory 不够

只扩 memory 不能解决当前核心问题。当前真正缺的是：

1. 飞书领域语义动作
2. 飞书页面状态识别
3. 任务完成验证
4. 失败恢复与回归闭环

如果继续只靠 memory，结果通常会变成：

- 每个任务都在重复 few-shot 轨迹
- UI 一改版，历史经验快速失效
- LLM 继续在通用 `click/type/hotkey` 上硬猜
- 长流程越来越脆

## 3. 基于当前仓库，应该怎么入手

建议把现有仓库视为三层：

- `launcher.py`：产品壳层
- `gui_agents/s3/`：通用 GUI 执行内核
- `sop_executor.py` + `sops/`：脚本化快捷路径

飞书二开不要继续把逻辑直接塞进 `gui_agents/s3/`，而是新增独立领域层，例如：

```text
gui_agents/feishu/
  __init__.py
  agents/
    __init__.py
    feishu_aci.py
    feishu_worker.py
  detectors/
    __init__.py
    state_detector.py
  pages/
    __init__.py
    registry.py
  workflows/
    __init__.py
    base.py
    send_message.py
    send_file.py
  verifiers/
    __init__.py
    completion_gate.py
  memory/
    __init__.py
    procedural_memory.py
  maintenance/
    __init__.py
    anchor_validator.py
    screenshot_recorder.py
```

当前不建议默认放入：

- `api_client.py`
- 以开放平台为核心的 `TaskRouter`
- 以 bot/CLI 为前提的执行分支

这些如果未来需要，应该作为可选扩展层独立加入，而不是现在写进主链。

但为了满足项目需求，建议现在就预留两个需求驱动模块：

```text
gui_agents/feishu/
  reports/
    __init__.py
    report_builder.py
  testcases/
    __init__.py
    nl_parser.py
    scenario_schema.py
```

原因：

- `reports/` 对应项目需求里的“评估报告层”
- `testcases/` 对应项目需求里的“自然语言驱动测试”

## 4. 当前阶段最值得优先做的能力

先只做最小闭环，不要一开始追求“全产品覆盖”。

建议第一阶段只稳定 3 类能力：

1. 搜索并进入目标会话
2. 发送文本消息
3. 上传文件

这三个能力一旦稳定，后续很多场景都能从这里生长出来。

但从项目需求出发，子产品路线不能长期只停留在 IM。

建议覆盖顺序：

1. `IM`：最适合先做消息发送、搜索、表情、文件上传
2. `Docs`：最适合验证创建文档、输入内容、标题/列表编辑
3. `Calendar`：最适合验证跨产品和状态确认

原因是这条路线能最好对应需求中的：

- 最少 2 个子产品覆盖
- M3 在 IM / Calendar / Docs 上形成可运行用例
- 后续跨产品联动测试

## 5. 当前推荐的执行路径

当前主路径应当是：

```text
User Task
  -> FeishuWorker
  -> StateDetector
  -> Workflow
  -> FeishuACI
  -> Verifier
  -> optional Code Agent
```

这里的职责要分清：

- `StateDetector` 负责“当前页面是什么、能不能继续”
- `Workflow` 负责“下一步做什么”
- `FeishuACI` 负责“如何落成 GUI 动作”
- `Verifier` 负责“这一步到底成没成”
- `Code Agent` 只做辅助，不接管飞书主流程

如果从测试框架角度补全，当前推荐的完整执行路径应当是：

```text
Natural Language Test Case
  -> Testcase Parser
  -> Workflow Selector / Planner
  -> FeishuWorker
  -> StateDetector
  -> FeishuACI
  -> Verifier
  -> Report Builder
  -> Structured Test Report
```

## 6. 先做哪些飞书语义动作

第一版 `FeishuACI` 不要贪多，先做最小动作集：

- `open_chat(chat_name)`
- `ensure_in_chat(chat_name)`
- `focus_message_input()`
- `clear_message_input()`
- `type_message(text)`
- `send_message()`
- `recover_from_modal_or_wrong_page()`

这些动作的目标不是替换所有底层 GUI 原语，而是把“飞书里稳定可复用的任务语义”抽出来。

## 7. 先做哪些状态识别字段

第一版 `FeishuStateDetector` 先保证字段够用，不追求过度智能。

建议至少输出：

```python
from dataclasses import dataclass


@dataclass
class FeishuState:
    page_type: str
    chat_name: str | None
    message_input_visible: bool
    send_button_visible: bool
    search_box_visible: bool
    modal_type: str | None
    last_error_banner: str | None
```

第一阶段只要能支撑 `SendMessageWorkflow` 就够了。

## 8. workflow 应该怎么写

不要把第一版 workflow 做成黑盒 prompt。

建议直接写成显式阶段机：

```text
INIT
  -> ENSURE_CHAT_OPEN
  -> ENSURE_INPUT_READY
  -> TYPE_MESSAGE
  -> SEND_MESSAGE
  -> VERIFY_SENT
  -> DONE
```

每一阶段都要有：

- 进入条件
- 执行动作
- 成功判定
- fallback
- 重试上限

当前主要问题不是“语言理解不够”，而是“页面操作不稳定”。因此第一版应更偏显式状态机，少依赖自由规划。

但为了满足项目需求中的“自然语言驱动测试”，建议保留一个轻量的自然语言到结构化场景转换层，例如：

```json
{
  "product": "im",
  "intent": "send_message",
  "target": "测试群",
  "payload": {
    "text": "Hello World"
  },
  "assertions": [
    "message_sent",
    "target_chat_matched"
  ]
}
```

第一阶段可以只支持少数高频模板，不必一开始就追求全自由输入。

## 9. verifier 为什么是硬需求

没有 verifier，系统就会把“看起来点了”误判为“已经完成”。

第一版 `CompletionGate` 建议只做 3 个判断：

1. 当前会话标题是目标会话
2. 输入框已清空或失焦，说明发送动作结束
3. 聊天记录里出现本次唯一 token

因此建议真实回归任务都使用唯一 token，例如：

- `smoke-feishu-20260504-1`
- `hello-codex-20260504-a`

## 10. 当前不建议把 API/CLI 写进主架构

这一点需要单独说清楚。

当前阶段不建议：

- 在主文档里把 API + GUI hybrid 写成默认路线
- 为了将来可能有的开放平台能力，在现在的主链里预埋复杂 `TaskRouter`
- 把 `FeishuAPIExecutor` 当成当前 MVP 的必要组成

更合理的做法是：

- 当前主线只设计 GUI 路径
- 如果需要内容生成或文本加工，使用 `code agent`
- 未来若业务场景明确要求开放平台能力，再单独新增：

```text
gui_agents/feishu/integrations/
  open_platform/
    __init__.py
    executor.py
    models.py
```

并通过 feature flag 或显式配置接入，而不是污染主工作流。

需要强调的是：这并不意味着需求文档里的开放平台资源无价值。

当前更合理的用法是：

- 用开放平台文档帮助理解产品功能边界
- 不把开放平台调用当成当前 GUI 测试主链
- 如果未来要做企业版扩展，再单独接入

## 11. 推荐的分阶段推进

### 阶段 0：先稳住运行基线

目标：

- 现有 `launcher.py` 和 `gui_agents/s3/cli_app.py` 可以稳定启动
- 每次运行都能保留 step 截图和日志
- 有一个可重复执行的真实 smoke case
- 开始固化统一的测试产物目录和报告元数据

退出条件：

- 能稳定复现一条固定消息发送任务
- 失败时能判断是识别错、点偏、输入错位还是发送未完成
- 每次运行都能产出结构化结果，例如 `summary.json`

### 阶段 1：最小飞书闭环

目标：

- `FeishuStateDetector`
- `FeishuACI`
- `SendMessageWorkflow`
- `CompletionGate`
- `ReportBuilder` 的最小版本

退出条件：

- 在固定目标会话里高成功率发送唯一 token 消息
- 能输出单条测试用例的轨迹、成功/失败、耗时、步骤数

### 阶段 2：增强恢复与第二个 workflow

目标：

- `ensure_in_chat(chat_name)`
- 错页恢复
- 弹窗恢复
- 第二个 workflow，如 `SendFileWorkflow`
- 第二个子产品 workflow，如 `DocsCreateAndEditWorkflow`

退出条件：

- 至少 2 个 workflow 能稳定回归
- 至少覆盖 2 个子产品

### 阶段 3：锚点维护与回归体系

目标：

- `PageRegistry`
- `Visual Anchor Store`
- `AnchorValidator`
- 截图刷新工具
- regression runner
- structured report exporter

退出条件：

- UI 漂移时能被发现，而不是静默失败
- 回归运行后能自动汇总成功率、耗时、步骤数

### 阶段 4：对齐项目需求的多产品覆盖

目标：

- `IM` 至少 2 条可运行用例
- `Docs` 至少 2 条可运行用例
- `Calendar` 至少 2 条可运行用例

建议示例：

- IM：发送消息、文件上传
- Docs：创建文档、编辑标题/列表
- Calendar：创建会议、邀请参会人

退出条件：

- 基本满足 `docs/项目需求.md` 里 M3 的覆盖方向

### 阶段 5：进阶能力

目标：

- 异常场景处理
- 自愈式执行
- 跨产品联动测试
- 录制回放

建议优先级：

1. 异常处理
2. 自愈
3. 跨产品联动
4. 录制回放

原因是这条顺序最贴近需求里的 M5，而且对真实可用性提升最大。

## 12. 评估报告层为什么必须现在设计

项目需求里“评估报告层”是必做，不是锦上添花。

因此即使第一阶段功能很少，也建议从一开始就统一测试产物结构，例如：

```text
artifacts/
  test_runs/
    2026-05-04_153000/
      screenshots/
      actions.jsonl
      summary.json
      report.md
```

`summary.json` 建议至少包含：

- `task_id`
- `product`
- `workflow`
- `status`
- `steps`
- `duration_sec`
- `assertions`
- `failure_reason`

`report.md` 建议至少包含：

- 用例描述
- 执行轨迹摘要
- 验证结果
- 成功率/耗时/步骤数
- 截图链接

## 13. memory 应该服务什么

memory 仍然有价值，但位置要靠后。

适合记的内容：

- 某类会话命名习惯
- 某类页面稳定锚点描述
- 某类失败后的恢复策略摘要
- 某个 workflow 的高成功率路径

不适合让 memory 单独承担的内容：

- 页面状态判断
- 输入框定位逻辑
- 任务完成判断
- 新语义动作定义

## 14. 一句话原则

先把飞书需求拆成“自然语言测试用例 + 状态 + 语义动作 + workflow + verifier + report + fallback”，再考虑 memory 和未来可选的开放平台扩展。

当前项目要做的是“真实桌面 GUI agent”，不是“bot 套壳”。
