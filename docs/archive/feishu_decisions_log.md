# Decisions Log

## 2026-05-03

### 1. Keep Agent S's visual grounding model for Feishu clicks

Decision:
- Do not switch the whole Feishu interaction path to the UI-TARS visual locator.
- Use Agent S grounding for coordinates, with Feishu-specific execution helpers.

Reason:
- The user explicitly wanted Agent S's own visual model to stay in charge of visual judgment.

### 2. Add Feishu-specific helper actions

Decision:
- Add `feishu_focus()`, `feishu_click(...)`, and `feishu_type(...)` as dedicated actions.

Reason:
- Generic desktop actions were too unstable for Feishu workflows.
- Dedicated helpers let the agent focus, refresh, and click in a more controlled way.

### 3. Use a Windows UIA fallback for named Feishu controls

Decision:
- When the target text is clear enough, try the Feishu UI automation tree before falling back to coordinates.

Reason:
- The wrong-click issue was repeatedly landing on `推荐` instead of `消息`.
- UIA provides stable control names for Feishu tabs and buttons.

### 4. Refresh the screenshot after focusing Feishu

Decision:
- Re-grab the desktop screenshot after the Feishu window is brought forward.

Reason:
- Earlier coordinates were computed from stale or obscured content.

### 5. Keep the launcher as the config entry point

Decision:
- Leave `launcher.py` as the place where the user enters API keys and starts the agent.

Reason:
- The existing Windows workflow already centers on the launcher UI and `config.json`.

### 6. Document the current state in repo files

Decision:
- Add `AGENTS.md`, `docs/PROJECT_STATE.md`, and `docs/DECISIONS.md`.

Reason:
- The user is switching to a new window and wants the current state preserved without re-explaining the whole history.

## 2026-05-04

### 7. Use Feishu browser geometry for the doc Share button

Decision:
- Keep `agent.feishu_doc_click("分享")` as the browser-doc toolbar path.
- Detect the blue Share button from the current screenshot when possible, with a right-edge offset fallback.

Reason:
- Visual grounding repeatedly returned a point near the document header center rather than the real top-right Share button.
- UIA does not expose the Feishu cloud document toolbar inside Edge reliably.
- Manual verification on 2026-05-04 clicked `(1625, 103)`, opened the popup, selected `bot功能测试`, clicked `发送`, and produced `邀请成员成功`.

### 9. Split grounding.py into three files (session 6)

Decision:
- `grounding.py` (655 lines) — kept byte-for-byte identical to upstream `Agent-S-s3-upstream`. No Windows code.
- `_feishu_exec.py` (634 lines) — stateless pure functions that return exec()-ready code strings (`build_feishu_focus_code`, `build_feishu_safe_focus_code`, `build_feishu_uia_click_code`, `build_feishu_doc_click_code`, `build_win32_click_code`, `build_windows_open_code`).
- `grounding_feishu.py` (406 lines) — `WindowsFeishuACI(OSWorldACI)` with Windows overrides + Feishu `@agent_action` methods.
- Entry points import `from gui_agents.s3.agents.grounding_feishu import WindowsFeishuACI as OSWorldACI`.

Reason:
- The 1600-line single-file `grounding.py` was unmaintainable and incompatible with upstream.
- Upstream project was 600 lines; our fork had ballooned to 1600 lines making diffs impossible.
- Pure builder functions have no `self` dependency and belong outside class scope.
- Keeping `grounding.py` upstream-identical means future upstream merges only touch that one file.

Also fixed in this session:
- Focus builder functions (`build_feishu_focus_code`, `build_feishu_safe_focus_code`) rewritten to use ctypes `GetTopWindow`/`GetWindow` enumeration instead of `Desktop(backend="uia")` — eliminates pywinauto UIA hang risk in exec()-executed code.
- `_focus_feishu_now()` (host-side) also rewritten to ctypes for the same reason.

### 8. Avoid Esc inside the browser share popup

Decision:
- For the browser share popup, click the invite input, paste the target, press Enter to select the first candidate, then click `发送`.
- Do not use Esc as a preedit cleanup step in this popup.

Reason:
- Esc closes the share popup. The next paste can then land in the document title field, which was reproduced during manual verification.
