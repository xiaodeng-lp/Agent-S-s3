# OpenAI API 模型参数参考

> 基于 OpenAI 最新 Chat Completions API，适用于所有 OpenAI-compatible 提供商（火山引擎、OpenRouter、Azure 等）。
> 最后更新：2026-05

---

## 参数速查表

| 参数 | 类型 | 作用 | 产品侧影响 | 推荐默认值 |
|---|---|---|---|---|
| `model` | string | 选择模型 | 决定能力上限、响应速度、成本 | 主力模型 + 便宜模型分层路由 |
| `messages` | array | 对话上下文 | 决定任务内容和上下文窗口占用 | 做好上下文裁剪，保留关键帧 |
| `reasoning_effort` | string | 推理强度（GPT-5/o-series） | 影响复杂任务准确率、延迟、成本 | 普通 `low`/`medium`，复杂 `high`，关键 `xhigh` |
| `max_output_tokens` | int | 最大输出长度 | 控成本、防废话、防截断 | 常规 1024–4096，代码 8192 |
| `temperature` | float | 随机性/创造性 | 影响输出稳定性和多样性 | 工具/问答 0.1–0.3，创作 0.7–1.0 |
| `top_p` | float | 核采样（nucleus sampling） | 类似 temperature 的另一种采样控制 | 一般不与 temperature 同时调整 |
| `text.format` | object | 结构化输出（JSON Schema） | 决定是否稳定返回 JSON | 产品后端强烈建议定义 JSON Schema |
| `text.verbosity` | string | 输出详略程度 | 影响回答长短和 token 消耗 | 默认 `medium`，助手类可 `low` |
| `tools` / `tool_choice` | array/string | 函数调用、web_search、file_search、code_interpreter | Agent 产品核心能力 | 工具型产品必配 |
| `stream` | bool | 流式返回 | 影响首字响应时间，提升用户感知 | 面向用户 UI 建议开启 |
| `previous_response_id` | string | 多轮上下文关联 | 决定对话连续性（替代 conversation ID） | 多轮对话产品需要维护 |
| `store` | bool | 是否存储 response 到平台 | 影响调试追踪、数据复现、隐私合规 | 内部调试可开，隐私敏感场景谨慎 |
| `service_tier` | string | 服务等级 | 影响延迟和成本 | 默认 `auto`，高优先级请求调 `flex` |
| `instructions` | string | 全局 system prompt | 决定 Agent 角色、行为边界、输出风格 | 必须固定维护，按场景版本化 |

---

## 核心参数详解

### 1. `model` — 模型选择

```
调用: model="gpt-5.4" | "doubao-seed-2.0-pro" | "claude-sonnet-4-6"
```

- **主力模型**: 处理复杂推理、多步规划、跨应用操作
- **便宜模型**: 简单分类、摘要、格式校验等可降级任务
- **推荐策略**: 按任务复杂度分层路由，实现成本/质量平衡

### 2. `reasoning_effort` — 推理强度控制（GPT-5 / o-series）

```
调用: reasoning_effort="low" | "medium" | "high" | "xhigh"
取值: low < medium < high < xhigh
```

| 级别 | 适用场景 | 延迟 | 成本 |
|---|---|---|---|
| `low` | 简单确认、状态检查、固定流程操作 | 低 | 低 |
| `medium` | 常规 GUI 操作、单步定位点击 | 中 | 中 |
| `high` | 多步规划、上下文理解、元素识别 (默认) | 较高 | 较高 |
| `xhigh` | 跨窗口切换、多应用协同、失败重试 | 高 | 高 |

**本项目策略**:
- 默认: `high`
- 跨窗口/切换应用/复杂定位: 自动升级 `xhigh`
- Step 执行失败后重试: 自动升级 `xhigh`

### 3. `messages` — 上下文管理

```
调用: messages=[{"role": "system", "content": [...]}, {"role": "user", "content": [...]}]
```

- 包含 `system` prompt（角色定义）、历史多模态消息（文本+截图）
- **关键**: 做好上下文裁剪，`max_trajectory_length` 控制保留的图像轮次
- 超过模型上下文窗口会导致截断或拒绝

### 4. `temperature` + `top_p` — 输出控制

| 参数 | 范围 | 含义 |
|---|---|---|
| `temperature` | 0–2 | 越高越随机，越低越确定 |
| `top_p` | 0–1 | 核采样累积概率阈值 |

- **不要同时调整两者**，选其一即可
- 定位/工具调用: `temperature=0`, `top_p=0.7`（豆包官方推荐）
- 创造性任务: `temperature=0.7`

### 5. `text.format` — 结构化输出

```json
{
  "text": {
    "format": {
      "type": "json_schema",
      "name": "action_output",
      "schema": { ... }
    }
  }
}
```

- 强制模型按 JSON Schema 输出，避免解析失败
- Agent action 输出（Thought + Action 格式）建议用此约束

### 6. `max_output_tokens` — 输出长度限制

- 防止模型过度输出造成延迟和成本浪费
- GUI Agent: 1024–4096 足够覆盖 Thought + Action 输出
- Code Agent: 可增大到 8192

### 7. `tools` — 工具/函数调用

```json
{
  "tools": [
    { "type": "function", "function": { "name": "click", ... } },
    { "type": "web_search" },
    { "type": "file_search" }
  ],
  "tool_choice": "auto"
}
```

- 本项目通过 ACI (Agent-Computer Interface) 封装 pyautogui 操作
- 无需 native function calling，通过生成代码间接调用

### 8. `stream` — 流式输出

- 开启后 SSE 逐 token 返回
- 优势: 首字延迟极低，用户体验好
- 劣势: 解析复杂度增加
- 本项目的 Launcher GUI 目前使用非流式，日志行缓冲读取

---

## 本项目模型路由

### 主模型 (生成/规划)

| Provider | URL | 模型 | 特点 |
|---|---|---|---|
| 火山引擎 ARK | `https://ark.cn-beijing.volces.com/api/v3` | doubao-seed-2.0-pro | 默认主力 |
| OpenAI Compatible | `https://right.codes/codex/v1` | gpt-5.4 | 支持 reasoning_effort |

### 定位模型 (Grounding/坐标生成)

| Provider | URL | 模型 | 坐标空间 |
|---|---|---|---|
| 火山引擎 ARK | `https://ark.cn-beijing.volces.com/api/v3` | doubao-seed-1-6-vision-250815 | 0-1000 归一化 |
| OpenRouter | `https://openrouter.ai/api/v1` | bytedance/ui-tars-1.5-7b | 图像像素坐标 |

---

## 参考链接

- [OpenAI Chat Completions API](https://platform.openai.com/docs/api-reference/chat/create)
- [火山引擎豆包视觉模型](https://www.volcengine.com/docs/82379/1584296)
- [GPT-5 reasoning_effort 指南](https://platform.openai.com/docs/guides/reasoning)
