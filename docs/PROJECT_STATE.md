# Project State

Last updated: 2026-05-04 (session 6)

## Goal

Make `H:\Agent-S-s3` reliably control Feishu/Lark on Windows using Agent S S3.

---

## File structure (agents)

| File | Lines | Role |
|------|-------|------|
| `gui_agents/s3/agents/grounding.py` | 655 | **Upstream-identical** — `OSWorldACI` base class + `ACI`, `agent_action`, constants. Do not add Windows code here. |
| `gui_agents/s3/agents/_feishu_exec.py` | 634 | **Pure exec-code builders** — stateless functions that return `exec()`-ready Python strings. No `self` dependency. |
| `gui_agents/s3/agents/grounding_feishu.py` | 406 | **`WindowsFeishuACI(OSWorldACI)`** — Windows overrides + all Feishu `@agent_action` methods. Import this everywhere. |

Entry points (`cli_app.py`, `run.py`, `run_local.py`) all import:
```python
from gui_agents.s3.agents.grounding_feishu import WindowsFeishuACI as OSWorldACI
```

---

## Current implementation state

### `gui_agents/s3/agents/grounding_feishu.py`

`WindowsFeishuACI(OSWorldACI)` overrides and extends the upstream base class.

#### Overrides from `OSWorldACI`
- `__init__`: adds `virtual_screen_left` / `virtual_screen_top` from `GetSystemMetrics(76/77)` for multi-monitor coordinate offset.
- `resize_coordinates`: applies the virtual-screen offset so clicks land on the correct monitor.
- `generate_coords`: same as upstream + execution tracing + out-of-range logging.
- `get_ocr_elements`: uses `re.sub(r"^\W+|\W+$", "", word, flags=re.UNICODE)` (CJK-safe) instead of upstream's ASCII-only regex.
- `open`: adds a `platform == "windows"` branch via `build_windows_open_code()`.

#### Host-side helpers (run at eval() time, not inside exec())
- `_trace_execution(message)` — writes to `logs/execution-trace.log`.
- `_focus_feishu_now()` — **ctypes-based**, safe: uses `GetTopWindow`/`GetWindow` enumeration + `QueryFullProcessImageNameW`. Does NOT call `Desktop(backend="uia")` (which would hang).
- `_refresh_obs_screenshot()` — re-grabs desktop and updates `self.obs`.
- `_repair_text_mojibake(text)` — fixes GBK-decoded-as-UTF-8 Chinese text.
- `_extract_feishu_target_text(description)` — extracts most likely UIA element text from natural-language description.

#### Feishu-specific agent actions

Three Feishu-specific agent actions are defined on `WindowsFeishuACI`:

#### `feishu_focus()`
Calls `build_feishu_focus_code()` (from `_feishu_exec.py`) which generates exec code that:
- Enumerates top-level windows with `GetTopWindow`/`GetWindow` + `QueryFullProcessImageNameW` (no pywinauto UIA)
- Calls `ShowWindow(hwnd, 9)` + `SetForegroundWindow(hwnd)` on the first Feishu/Lark process

Use at task start or whenever Feishu is not the foreground window.

#### `feishu_click(element_description, num_clicks=1, button_type="left")`
At **eval() time**: extracts `target_text` via `_extract_feishu_target_text()`, no focus side-effects.  
Returns exec code from `build_feishu_uia_click_code(target_text, ...)` (from `_feishu_exec.py`).

**Critical rule**: does NOT call `_focus_feishu_now()` or prepend `_build_feishu_focus_code()`.
Reason: Feishu dialogs (创建日程, date picker, confirm boxes) are light-dismiss — focusing the
main OS window closes them. The UIA search handles scope internally.

#### `feishu_type(text, element_description=None, overwrite=False, enter=False)`
At **eval() time**: if `element_description` given, extracts target_text, no focus side-effects.  
Returns exec code:
- If `element_description` given: UIA click code + `if clicked:` guarded paste block
  — `if clicked:` guard prevents blind Ctrl+V when UIA misses (e.g. CSS placeholder text)
- If no `element_description`: `_build_feishu_safe_focus_code()` + unconditional paste
  — safe focus skips `set_focus()` if Feishu is already the foreground process

**Critical rule**: does NOT call `_focus_feishu_now()` at eval time.
Reason: eval() runs before exec(); set_focus() at eval time closes any open Feishu dialog.

#### `build_feishu_safe_focus_code()` (in `_feishu_exec.py`, used by `feishu_type`)
Checks via `QueryFullProcessImageNameW` whether the foreground window belongs to Feishu/Lark.
If yes, skips `SetForegroundWindow()`. If no, enumerates windows and focuses Feishu.
Uses ctypes only — no pywinauto UIA. Prevents light-dismiss dialogs from closing when
`feishu_type()` is called without `element_description` while a dialog is open.

#### `build_feishu_uia_click_code(target_text, ...)` (in `_feishu_exec.py`)
Generates exec code that:
1. Enumerates all top-level windows and calls `QueryFullProcessImageNameW` on each PID
2. Collects PIDs of processes whose exe name contains "feishu" or "lark"
3. Builds `search_wins` = all windows belonging to those PIDs
   — covers main window, every dialog, every popup, every Electron sub-process
   — excludes VS Code, launcher (python.exe), QQ, Chrome, etc.
4. Calls `GetForegroundWindow()` to identify the active window; sorts `search_wins` so
   the foreground window is first (`lambda w, _fg=fg_hwnd: 0 if w.handle == _fg else 1`
   — default-arg capture required to avoid exec() closure NameError)
5. Searches descendants of every window in `search_wins` for `target_text`
6. Scores candidates:
   - Exact match: +1000
   - In foreground window: +500 (prevents background windows from winning)
   - Control type in (Edit/TabItem/ListItem/Button/Text/Document/DataItem): +100
   - Edit specifically: +200 additional
   - Position heuristics (left<500: +20, top<1000: +10, short text: +10)
7. Top-3 candidates built with explicit `for` loop (not list comprehension — list comprehensions
   inside `exec()` create a nested scope that cannot see outer local variables)
8. Clicks the top-scoring element via `click_input()` → `invoke()` → `click()`
9. Writes `FEISHU_UIA_CLICKED` / `FEISHU_UIA_CLICK_MISS` / `FEISHU_UIA_CLICK_ERROR` to
   `logs/execution-trace.log` with top-3 candidate details

#### `feishu_doc_click(button_name)`
Agent action for clicking toolbar buttons in a Feishu cloud document open in the browser.  
Uses foreground window rect + right-edge offset instead of visual grounding or UIA.

Calls `build_feishu_doc_click_code(button_name)` (from `_feishu_exec.py`) which generates exec code that:
1. `SetProcessDPIAware()` — ensures physical pixel coords
2. `EnumWindows` — finds the Edge/Chrome window whose title contains "feishu"/"飞书"/"lark" (avoids GetForegroundWindow() which may point to a different window at exec time)
3. `SetForegroundWindow()` on that window + 350ms sleep (ensures browser is focused before the click)
4. `GetWindowRect()` on the found browser window — gets precise bounds
5. Looks up `(offset_from_right, offset_from_top)` in the OFFSETS table:
   - 分享: (170, 93), 评论: (250, 93), 更多: (55, 93), 分析: (330, 93)
   - Default for unknown button: (170, 93)
6. Clicks at `(rect.right - offset_x, rect.top + offset_y)` via ctypes mouse_event
7. Writes `FEISHU_DOC_CLICKED: button_name at (cx, cy) window=(l,t,r,b) browser_titles=[...]` to `logs/feishu-doc-click.log` (separate file to avoid execution-trace.log lock)

**Why not visual grounding**: `agent.click("分享 button at top right")` returns ~(846, 93) — grounding model misidentifies the button position.  
**Why not UIA**: The button lives in browser web content (not a native window) — `descendants()` on Edge scans thousands of DOM nodes and is too slow/unreliable.  
**Calibration**: Check `FEISHU_DOC_CLICKED` in `logs/feishu-doc-click.log` for exact `(cx, cy)` and `window=(l,t,r,b)`. Correct offset = `window.right - actual_button_x`. Adjust `_build_feishu_doc_click_code` OFFSETS dict if needed.

#### `_extract_feishu_target_text(description)` (method on `WindowsFeishuACI`)
Extracts the most likely UIA element text from a natural-language description.
Prefers quoted CJK strings, falls back to longest CJK chunk.

---

### `gui_agents/s3/memory/procedural_memory.py`

#### OSCAR 5-section response format
1. `(Observe)` — screen-first, no plan history references
2. `(State Verification)` — As expected / Behind / Ahead; Ahead can skip future steps
3. `(Next Action)`
4. `(Expected Next State)` — one-sentence prediction
5. `(Grounded Action)`

#### Windows / Feishu guidelines (end of prompt)
- **#12**: On Windows, prefer `agent.open()` for opening/foregrounding apps
- **#13**: Use `feishu_focus()` at task start, `feishu_click()` for clicks, `feishu_type()` for input.
  After clicking "保存" in a schedule dialog, a "确定创建日程吗？" confirmation popup may appear —
  click `agent.feishu_click("确定")` before `agent.done()`.
- **#14** (new in session 3): When Feishu opens content in a web browser (e.g. clicking "云文档"),
  UIA helpers won't find browser elements. Switch to `agent.click()` and `agent.type()` for all
  browser-based Feishu interactions — these use visual grounding coordinates and work for any app.
- **#15** (new in session 3, revised in session 4): Cloud doc creation sequence:
  `feishu_click("云文档")` → `feishu_click("新建")` → `feishu_click("文档")` → `feishu_click("新建空白文档")`.
  Step (d) uses feishu_click (UIA) NOT agent.click (visual grounding).
  Root cause of visual grounding failure: grounding model returns ~(516,360) which falls in the
  sidebar nav area (云文档 TabItem is at L379-R535); this lands on "推荐" or other nav items.
  The popup opened via 新建→文档 is the foreground window, so UIA foreground +500 correctly
  prefers the popup card over any same-named document in the background file list.
  Fallback: if FEISHU_UIA_CLICK_MISS, use `agent.hotkey(['Return'])` to confirm default card.
- **#16** (new in session 4, revised session 6): After new Feishu cloud doc opens in browser, title field is auto-focused.
  Do NOT use `agent.click()` to locate it — grounding returns toolbar coords (~428, 171) and breaks focus.
  Use `agent.type(text="title", overwrite=False, enter=False)` directly (**overwrite=False**, NOT True),
  then `agent.hotkey(['Return'])` to move to body, then `agent.type(text="body content")`.
  Root cause of overwrite=True failure: Ctrl+A in the browser Feishu editor triggers full-editor
  select-all (not just title field), shifting focus to the cover placeholder above the title and
  causing an unwanted cover image to be auto-inserted. Title field is empty on creation so
  overwrite is never needed.

---

### `gui_agents/s3/agents/worker.py`

- `_parse_expected_next_state(plan)` extracts the `(Expected Next State)` sentence.
- `self.last_expected_state` initialized in `reset()`.
- Each turn (turn > 0) injects `"Expected state from last action: ..."` into the generator message.
- After `call_llm_formatted`, stores the new expected state for the next turn.

---

### `gui_agents/s3/cli_app.py`

- stdin/stdout/stderr reconfigured to UTF-8.
- Desktop capture uses full virtual desktop (`ImageGrab.grab(all_screens=True)`).
- `--budget` argument added (default 30); passed as `code_agent_budget` to `OSWorldACI`.

---

### `launcher.py`

- Owns configuration for: main model API key/endpoint/model-id, grounding provider/key/model/url.
- Starts `gui_agents/s3/cli_app.py` with `--budget 30` explicitly.

---

## Key bugs fixed across sessions

| Bug | Root cause | Fix |
|-----|-----------|-----|
| `NameError: fg_hwnd` in lambda inside exec | Lambda in exec() cannot close over local vars | Default-arg capture: `lambda w, _fg=fg_hwnd:` |
| `NameError: candidates` in list comprehension inside exec | List comp creates nested scope in exec context | Replace with explicit for-loop |
| Feishu dialogs close on `feishu_type()` without element | `_build_feishu_focus_code()` calls `set_focus()`, closing light-dismiss dialogs | New `_build_feishu_safe_focus_code()` skips set_focus if Feishu already foreground |
| Blind Ctrl+V pastes to wrong window on UIA miss | No guard around paste when click fails | `if clicked:` guard in `feishu_type()` element path |
| Budget exhaustion at step 20 | Default `code_agent_budget=20` | Raised to 30 via `--budget` CLI arg |
| Browser-based Feishu (云文档) blocks agent | UIA helpers can't find browser content | Guideline #14: use `agent.click()`/`agent.type()` for browser context |

---

## Known working flows (as of 2026-05-03 session 3)

- `feishu_focus()` → `feishu_click("创建日程")` → `feishu_type("今日进展", "添加主题 input")` → subject typed
- `feishu_click("2026年5月3日")` → date picker opens without closing dialog
- OSCAR `(State Verification)` fires correctly on first step ("First step — no expected state.")
- "确定创建日程吗？" confirmation popup handled by guideline #13

## Key bugs fixed across sessions (updated)

| Bug | Root cause | Fix |
|-----|-----------|-----|
| `agent.click("分享")` lands on doc header center | Grounding returns ~(846,93) = center of header bar; actual 分享 is at far right | New `feishu_doc_click("分享")` uses window rect right-edge offset (session 4) |

---

## Open items

- **Browser share flow verified manually**: `agent.open("Microsoft Edge")` reused the existing Feishu Edge window; `agent.feishu_doc_click("分享")` clicked `(1625, 103)` via `method=vision_blue_button` and opened the share popup; pasting `bot功能测试`, pressing Enter, and clicking `发送` produced the green success toast `邀请成员成功`.
- **Share popup caution**: do not press `Esc` after opening the browser share popup. `Esc` closes the popup, so later `Ctrl+A`/paste can modify the document title instead of the share target field.
- **Cloud doc creation — browser editing not yet re-verified**: guideline #16 added (auto-focus title, no click). Run a clean end-to-end test to confirm title typing + body typing works.
- **Browser-based Feishu**: guideline #14 added; `agent.click()` path uses UI-TARS visual grounding, not yet tested against actual 云文档 browser session
- **Short/ambiguous UIA text** (e.g. `"4"` in date picker): foreground +500 is main tiebreaker — check `FEISHU_UIA_CLICKED` top-3 in execution-trace.log if clicks land wrong
- **"添加主题" placeholder**: CSS placeholder is not exposed in UIA `window_text()`; `if clicked:` guard prevents damage on miss, but agent still wastes 1-2 retry steps
- **Double grounding calls per agent.click()**: CODE_VALID_FORMATTER in worker.py evals the action at validation time AND execution time, triggering generate_coords twice. Minor API overhead, not blocking.

## How to verify

1. Run `启动.bat` (or `python launcher.py`).
2. Watch `logs/normal-*.log` for `(Observe)` / `(State Verification)` / `(Expected Next State)` sections.
3. Watch `logs/execution-trace.log` for:
   - `FEISHU_CLICK_UIA_ONLY` — what target_text was extracted
   - `FEISHU_UIA_CLICKED` — what element was actually clicked (+ top-3 candidates)
   - `FEISHU_UIA_CLICK_MISS` — nothing found (check target_text extraction)
   - `GROUNDING_RESPONSE` — visual grounding model output when `agent.click()` is used
