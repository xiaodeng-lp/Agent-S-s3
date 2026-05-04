# 合并说明 (2026-05-04)

## 本次改动概览

本次合并的主线目标是让 Agent S S3 在 Windows 上更可靠地控制飞书/Lark，并将视觉定位、Windows 执行层、飞书操作规则整理成可审查、可继续维护的结构。

核心审查范围：

1. Grounding 模型切换到豆包视觉模型
2. Windows + 飞书专项支持
3. Procedural Memory 改为 OSCAR 格式并补充飞书规则

---

## 1. Grounding 模型切换到豆包视觉模型

**WHAT:**

- 从 OpenRouter UI-TARS 1.5 (7B) 切换到豆包视觉模型 `doubao-seed-1-6-vision-250815`
- Grounding 输出按 1000x1000 归一化坐标解释
- `launcher.py` 增加/保留 grounding provider、模型、URL、API key 的配置入口

**WHY:**

- 豆包视觉模型对中文 UI 的定位表现更稳定
- 1000x1000 归一化坐标更适合当前 grounding 模型输出格式
- Windows 多显示器场景下，坐标换算统一由 `WindowsFeishuACI.resize_coordinates()` 处理

**需要审查:**

- `launcher.py` 的默认 grounding provider、model、url 是否符合团队实际配置
- `gui_agents/s3/cli_app.py` 传入的 `--ground_provider`、`--grounding_width`、`--grounding_height` 是否和模型输出约定一致
- 多显示器下的截图尺寸与点击落点是否一致

---

## 2. Windows + 飞书专项支持

**新增/拆分文件:**

- `gui_agents/s3/agents/grounding.py`
  - 保持 upstream-identical，不放 Windows/飞书专项代码
- `gui_agents/s3/agents/grounding_feishu.py`
  - `WindowsFeishuACI(OSWorldACI)` 子类
  - Windows 多显示器坐标偏移
  - 飞书专项 agent actions
- `gui_agents/s3/agents/_feishu_exec.py`
  - 纯函数库，生成可 `exec()` 的 Python 代码串
  - Win32/ctypes 窗口操作
  - 飞书桌面端 UIA 元素定位
  - 飞书云文档浏览器工具栏的窗口几何点击

**主要动作:**

| 动作 | 场景 | 定位方式 |
|------|------|----------|
| `feishu_focus()` | 任务开始或飞书未前台时 | Win32 窗口枚举 + 前台切换 |
| `feishu_click(text)` | 飞书桌面端按钮、标签、弹窗元素 | UIA 元素树 |
| `feishu_type(text, element_description)` | 飞书桌面端输入框 | UIA 点击后剪贴板粘贴 |
| `feishu_doc_click(button_name)` | 浏览器里的飞书云文档工具栏 | 浏览器窗口右边缘几何偏移 |
| `feishu_doc_type(text)` | 云文档分享弹窗输入 | 保持当前焦点并粘贴 |

**WHY:**

- 飞书桌面端原生控件适合 UIA 定位，能避开视觉模型在相似文本、侧栏区域上的误点
- 飞书弹窗有 light-dismiss 行为，不能在 eval 阶段或输入前盲目重新 focus 主窗口
- 飞书云文档运行在浏览器 web 内容中，UIA 不稳定；工具栏按钮保留几何点击路径，正文内容仍交给视觉 grounding
- `_feishu_exec.py` 虽然是纯函数库，但承担的是执行层隔离，不是替代豆包视觉定位的主路径

**需要审查:**

- `gui_agents/s3/agents/grounding_feishu.py` 是否只承载 Windows/飞书扩展，没有污染 upstream `grounding.py`
- `_feishu_exec.py` 生成的 exec 代码是否只做执行动作，不依赖 `self`
- `feishu_click()` / `feishu_type()` 是否避免在 eval 阶段关闭飞书轻消弹窗
- `feishu_doc_click()` 的右边缘偏移是否仍符合当前浏览器窗口布局

---

## 3. Procedural Memory 改为 OSCAR 格式

**WHAT:**

- Agent 响应格式调整为 5 段：
  - `(Observe)`
  - `(State Verification)`
  - `(Next Action)`
  - `(Expected Next State)`
  - `(Grounded Action)`
- 增加 Windows/飞书专项操作规则，指导模型在桌面端、浏览器云文档、分享弹窗等场景选择合适动作

**WHY:**

- 每轮动作前显式验证 UI 状态，减少按旧计划盲走
- 把已验证的飞书 edge cases 写入 procedural memory，减少重复试错
- 让浏览器云文档、桌面端飞书、轻消弹窗分别走不同操作策略

**需要审查:**

- `gui_agents/s3/memory/procedural_memory.py` 中规则是否过度约束模型
- 云文档新建、标题输入、分享弹窗这三条流程是否仍符合当前飞书 UI
- `Expected Next State` 是否会改善下一轮状态检查，而不是增加冗余文本

---

## 4. 其他说明

- SOP 快捷操作面板是正交功能，不作为本次主干合并审查重点。
- 删除了蓝色像素扫描相关 workaround 代码，豆包视觉定位到位后不再作为主路径维护。

---

## 5. 文件变更统计

```text
16 files changed, 1566 insertions(+), 1012 deletions(-)

新增:
 - gui_agents/s3/agents/_feishu_exec.py
 - gui_agents/s3/agents/grounding_feishu.py

修改:
 - launcher.py
 - gui_agents/s3/cli_app.py
 - gui_agents/s3/memory/procedural_memory.py

相关但非主线:
 - sop_executor.py
 - sops/*.json

删除:
 - 蓝色像素扫描 workaround 代码
```

---

## 6. 后续建议

1. 补充飞书动作测试用例
   - 覆盖发消息、新建云文档、分享云文档三个高频场景
   - 优先验证日志中的 `FEISHU_UIA_CLICKED`、`FEISHU_UIA_CLICK_MISS`、`FEISHU_DOC_CLICKED`

2. 建立 SOP 模板说明
   - 如果继续保留 SOP 面板，单独维护 `sops/README.md`
   - 不把 SOP 流程和 Agent 主路径混在同一份 merge notes 里

---

**Merge 日期:** 2026-05-04  
**Reviewed by:** 待审查
