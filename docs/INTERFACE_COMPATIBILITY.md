# 接口兼容性指南

## 快速查询表

### CLI 参数（向后兼容 ✅）

```bash
python gui_agents/s3/cli_app.py \
  --provider openai \
  --model <豆包_model_id> \
  --model_url https://ark.cn-beijing.volces.com/api/v3 \
  --model_api_key <YOUR_KEY> \
  --ground_provider doubao_ark \
  --ground_url https://ark.cn-beijing.volces.com/api/v3 \
  --ground_api_key <YOUR_KEY> \
  --ground_model doubao-seed-1-6-vision-250815 \
  --grounding_width 1000 \
  --grounding_height 1000 \
  --budget 25
```

**变化:**
- `--ground_provider` 新增 `doubao_ark` 选项（兼容 `open_router`, `openai`）
- `--ground_model` 默认改为豆包（兼容旧值）
- `--grounding_width/height` 改为固定 1000×1000（自动）

---

### Python API（部分破坏性 ⚠️）

#### 旧代码
```python
from gui_agents.s3.agents.grounding import OSWorldACI
agent = OSWorldACI(...)
agent.click("按钮")
```

#### 新代码
```python
from gui_agents.s3.agents.grounding_feishu import WindowsFeishuACI as OSWorldACI
agent = OSWorldACI(...)
agent.click("按钮")  # 兼容
agent.feishu_click("飞书按钮")  # 新增
```

**关键变化:**
- ✅ `cli_app.py` 自动处理了切换，用户代码无需改动
- ⚠️ 若直接 `import OSWorldACI`，需改为 `import WindowsFeishuACI`
- ✅ 所有旧方法保留（`click`, `type`, `hotkey` 等）
- ✨ 新增 5 个飞书方法（见下表）

---

### Agent 动作方法

#### 新增方法（仅 Windows）

| 方法 | 签名 | 返回值 | 使用场景 |
|------|------|--------|---------|
| `feishu_focus()` | `-> str` | 可 exec 代码 | 启动任务前，确保窗口在前台 |
| `feishu_click(text, num_clicks, button)` | `(str, int, str) -> str` | 可 exec 代码 | 飞书桌面端 UI 点击（UIA） |
| `feishu_type(text, element, overwrite, enter)` | `(str, str?, bool, bool) -> str` | 可 exec 代码 | 输入框/消息 |
| `feishu_doc_click(button_name)` | `(str) -> str` | 可 exec 代码 | 云文档工具栏按钮 |
| `feishu_doc_type(text)` | `(str) -> str` | 可 exec 代码 | 云文档分享弹窗输入 |

#### 旧方法（兼容 ✅）

```python
agent.click("描述")          # ✅ 仍可用（视觉定位）
agent.type(text, "描述")     # ✅ 仍可用
agent.hotkey(['ctrl', 'a'])  # ✅ 仍可用
agent.wait(1.0)              # ✅ 仍可用
```

---

### Procedural Memory（规则更新）

#### 旧规则
```python
# 不推荐
agent.feishu_doc_send()  # ❌ 已删除
agent.click("发送")       # ⚠️ 不稳定（豆包模型前）
```

#### 新规则 (#17 step e)
```python
# 新建议
agent.click("发送 button")   # ✅ 豆包模型现在可靠
```

**完整规则见:** `gui_agents/s3/memory/procedural_memory.py` 行 #12–#27

---

## 迁移检查清单

### 如果你的代码用过...

- [ ] `from gui_agents.s3.agents.grounding import OSWorldACI`
  → 改为 `from gui_agents.s3.agents.grounding_feishu import WindowsFeishuACI as OSWorldACI`

- [ ] `agent.feishu_doc_send()`
  → 改为 `agent.click("发送 button")`

- [ ] OpenRouter 硬编码
  → 改为豆包（见上面的 CLI 参数表）

- [ ] 旧 procedural_memory 规则（#17 e 段）
  → 自动更新，无需改动

---

## 问题排查

### 豆包模型返回 "array index out of bounds"
→ 确保 `--grounding_width 1000 --grounding_height 1000`（必需）

### feishu_click() 找不到元素
→ 元素必须在 UIA 树中可见
  - 检查: `element.window_text()` 返回正确的中文
  - 若在浏览器，改用 `feishu_doc_click()` 或 `agent.click()`

### Windows 多显示器坐标错误
→ 检查 `virtual_screen_left/top`（自动检测）
  - 若显示器位置特殊，可手动调整 `grounding_feishu.py` line 43-45

### SOP 执行失败
→ 检查 `sops/*.json` 格式
  → 参数用 `{{name}}` 语法填充（见 `sops/飞书发消息.json` 示例）

---

## 贡献指南

### 添加新 Feishu 动作

```python
# grounding_feishu.py

@agent_action
def my_feishu_action(self, param: str):
    """简述功能"""
    return build_my_feishu_action_code(param)

# _feishu_exec.py

def build_my_feishu_action_code(param: str) -> str:
    """返回 exec() 可执行的代码串"""
    return f"""
import ctypes
import time
# ... 你的代码 ...
print("MY_ACTION_RESULT:", {param!r})
"""
```

**关键点:**
- 返回的字符串必须能被 `exec()` 执行
- 包含完整的 import（包括 `ctypes`, `time`, `pyautogui` 等）
- 用 f-string 注入参数（参数化）
- 末尾用 `print()` 输出结果供 logging

### 添加新 SOP 模板

```json
{
  "name": "我的工作流",
  "description": "简述",
  "params": [
    {"name": "target", "label": "目标", "placeholder": "例如：小李", "optional": false}
  ],
  "steps": [
    {"type": "hotkey", "keys": ["ctrl", "alt", "f"], "comment": "唤起搜索"},
    {"type": "type", "text": "{{target}}"},
    {"type": "press", "key": "enter"}
  ]
}
```

**支持的 step 类型:**
- `hotkey` — 快捷键
- `type` — 键盘输入
- `press` — 单键
- `wait` — 延迟
- `click` — 点击 (x, y)
- `http` — API 调用
- `ai_click` — 图像匹配点击

---

**最后更新:** 2026-05-04
