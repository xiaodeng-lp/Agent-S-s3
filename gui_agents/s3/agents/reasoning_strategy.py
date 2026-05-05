"""
Auto-switch reasoning effort for GPT/o-series models.

The configured default remains the baseline. Complex cross-window or
cross-application steps can escalate to a higher effort, and retrying after a
failed step always escalates to ``xhigh``.
"""

from enum import Enum
from typing import Optional


class ReasoningEffort(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    XHIGH = "xhigh"


EFFORT_ORDER = {
    ReasoningEffort.LOW: 0,
    ReasoningEffort.MEDIUM: 1,
    ReasoningEffort.HIGH: 2,
    ReasoningEffort.XHIGH: 3,
}


COMPLEX_PATTERNS = [
    "切换应用",
    "切换窗口",
    "切换到",
    "切换程序",
    "跨窗口",
    "跨应用",
    "复制到",
    "粘贴到",
    "移动到",
    "分享到",
    "同步到",
    "发送到",
    "转发到",
    "从消息",
    "从云文档",
    "从日历",
    "到云文档",
    "到日历",
    "到邮箱",
    "到审批",
    "导入到",
    "导出到",
    "另存为",
    "上传文件",
    "发送文件",
    "批量处理",
    "批量操作",
    "批处理",
    "合并文件",
    "合并文档",
    "switch app",
    "switch application",
    "switch window",
    "switch to",
    "alt+tab",
    "win+tab",
]


def _contains_complex_pattern(text: str) -> bool:
    text_lower = text.lower()
    return any(pattern.lower() in text_lower for pattern in COMPLEX_PATTERNS)


def _max_effort(left: ReasoningEffort, right: ReasoningEffort) -> ReasoningEffort:
    if EFFORT_ORDER[left] >= EFFORT_ORDER[right]:
        return left
    return right


def detect_complexity(
    task: str,
    last_action: Optional[str] = None,
    step_failed: bool = False,
    screenshot_complex: bool = False,
) -> Optional[ReasoningEffort]:
    if step_failed or screenshot_complex:
        return ReasoningEffort.XHIGH

    if last_action and _contains_complex_pattern(last_action):
        return ReasoningEffort.XHIGH

    return None


def reasoning_effort_for_step(
    task: str,
    step: int,
    last_action: Optional[str] = None,
    last_step_failed: bool = False,
    screenshot_complex: bool = False,
    default_effort: ReasoningEffort = ReasoningEffort.MEDIUM,
) -> ReasoningEffort:
    del step

    if last_step_failed:
        return ReasoningEffort.XHIGH

    detected = detect_complexity(
        task=task,
        last_action=last_action,
        step_failed=last_step_failed,
        screenshot_complex=screenshot_complex,
    )
    if detected is None:
        return default_effort
    return _max_effort(default_effort, detected)
