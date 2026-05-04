"""Pure functions that build exec()-ready code strings for Windows Feishu automation.

All functions return strings; none depend on instance state.
"""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


def build_win32_click_code(
    x: int,
    y: int,
    num_clicks: int = 1,
    button_type: str = "left",
) -> str:
    """Return code that clicks (x, y) using raw Win32 mouse_event calls."""
    button = (button_type or "left").lower()
    if button == "right":
        down_flag = "0x0008"
        up_flag = "0x0010"
    elif button == "middle":
        down_flag = "0x0020"
        up_flag = "0x0040"
    else:
        down_flag = "0x0002"
        up_flag = "0x0004"
    clicks = max(1, int(num_clicks or 1))
    return f"""
import ctypes
import time
from pathlib import Path
try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass
screen_left = ctypes.windll.user32.GetSystemMetrics(76)
screen_top = ctypes.windll.user32.GetSystemMetrics(77)
screen_width = ctypes.windll.user32.GetSystemMetrics(78)
screen_height = ctypes.windll.user32.GetSystemMetrics(79)
screen_right = screen_left + screen_width
screen_bottom = screen_top + screen_height
if {x} < screen_left or {x} >= screen_right or {y} < screen_top or {y} >= screen_bottom:
    print("FEISHU_CLICK_SKIPPED_OUT_OF_BOUNDS:", {x}, {y}, (screen_left, screen_top, screen_right, screen_bottom))
    try:
        Path("logs").mkdir(exist_ok=True)
        with open(Path("logs") / "execution-trace.log", "a", encoding="utf-8") as f:
            f.write("FEISHU_CLICK_SKIPPED_OUT_OF_BOUNDS: " + repr(({x}, {y}, (screen_left, screen_top, screen_right, screen_bottom))) + "\\n")
    except Exception:
        pass
else:
    print("FEISHU_CLICK_COORDS:", {x}, {y}, {clicks}, {button!r})
    try:
        Path("logs").mkdir(exist_ok=True)
        with open(Path("logs") / "execution-trace.log", "a", encoding="utf-8") as f:
            f.write("FEISHU_CLICK_COORDS: " + repr(({x}, {y}, {clicks}, {button!r})) + "\\n")
    except Exception:
        pass
    ctypes.windll.user32.SetCursorPos({x}, {y})
    time.sleep(0.05)
    for _ in range({clicks}):
        ctypes.windll.user32.mouse_event({down_flag}, 0, 0, 0, 0)
        time.sleep(0.03)
        ctypes.windll.user32.mouse_event({up_flag}, 0, 0, 0, 0)
        time.sleep(0.08)
"""


def build_feishu_focus_code() -> str:
    """Return code that brings the Feishu/Lark window to the foreground.

    Uses ctypes GetTopWindow/GetWindow enumeration to avoid pywinauto UIA hangs.
    """
    return """
import ctypes
import os as _os_ff
import time

_GW_HWNDNEXT_ff = 2
_PROCESS_QUERY_LIMITED_INFORMATION_ff = 0x1000

def _get_exe_ff(hwnd):
    _pid = ctypes.c_ulong(0)
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(_pid))
    _h = ctypes.windll.kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION_ff, False, _pid.value)
    if not _h:
        return ""
    try:
        _buf = ctypes.create_unicode_buffer(512)
        _sz = ctypes.c_ulong(512)
        ctypes.windll.kernel32.QueryFullProcessImageNameW(_h, 0, _buf, ctypes.byref(_sz))
        return _os_ff.path.basename(_buf.value).lower()
    finally:
        ctypes.windll.kernel32.CloseHandle(_h)

_feishu_hwnd_ff = None
_hwnd_ff = ctypes.windll.user32.GetTopWindow(0)
while _hwnd_ff:
    try:
        if ctypes.windll.user32.IsWindowVisible(_hwnd_ff):
            _exe_ff = _get_exe_ff(_hwnd_ff)
            if "feishu" in _exe_ff or "lark" in _exe_ff:
                _feishu_hwnd_ff = _hwnd_ff
                break
    except Exception:
        pass
    _hwnd_ff = ctypes.windll.user32.GetWindow(_hwnd_ff, _GW_HWNDNEXT_ff)

if _feishu_hwnd_ff:
    ctypes.windll.user32.ShowWindow(_feishu_hwnd_ff, 9)
    ctypes.windll.user32.SetForegroundWindow(_feishu_hwnd_ff)
    print("FEISHU_FOCUS_CTYPES: focused hwnd", _feishu_hwnd_ff)
    time.sleep(0.3)
else:
    import pyautogui
    print("FEISHU_FOCUS_MISS: falling back to alt+tab")
    pyautogui.hotkey("alt", "tab")
    time.sleep(0.3)
"""


def build_feishu_safe_focus_code() -> str:
    """Like build_feishu_focus_code but skips SetForegroundWindow when Feishu
    is already the foreground process — prevents closing light-dismiss dialogs.

    Uses ctypes only; no pywinauto UIA.
    """
    return """
import ctypes
import os as _os_sf
import time

_PROCESS_QUERY_LIMITED_INFORMATION_sf = 0x1000
_GW_HWNDNEXT_sf = 2

_fg_sf = ctypes.windll.user32.GetForegroundWindow()
_pid_sf = ctypes.c_ulong(0)
ctypes.windll.user32.GetWindowThreadProcessId(_fg_sf, ctypes.byref(_pid_sf))
_h_sf = ctypes.windll.kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION_sf, False, _pid_sf.value)
_already_feishu = False
if _h_sf:
    try:
        _buf_sf = ctypes.create_unicode_buffer(512)
        _sz_sf = ctypes.c_ulong(512)
        ctypes.windll.kernel32.QueryFullProcessImageNameW(_h_sf, 0, _buf_sf, ctypes.byref(_sz_sf))
        _exe_sf = _os_sf.path.basename(_buf_sf.value).lower()
        _already_feishu = "feishu" in _exe_sf or "lark" in _exe_sf
    finally:
        ctypes.windll.kernel32.CloseHandle(_h_sf)

if not _already_feishu:
    _feishu_hwnd_sf = None
    _hwnd_sf = ctypes.windll.user32.GetTopWindow(0)
    while _hwnd_sf:
        try:
            if ctypes.windll.user32.IsWindowVisible(_hwnd_sf):
                _pid2_sf = ctypes.c_ulong(0)
                ctypes.windll.user32.GetWindowThreadProcessId(_hwnd_sf, ctypes.byref(_pid2_sf))
                _h2_sf = ctypes.windll.kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION_sf, False, _pid2_sf.value)
                if _h2_sf:
                    try:
                        _buf2_sf = ctypes.create_unicode_buffer(512)
                        _sz2_sf = ctypes.c_ulong(512)
                        ctypes.windll.kernel32.QueryFullProcessImageNameW(_h2_sf, 0, _buf2_sf, ctypes.byref(_sz2_sf))
                        _exe2_sf = _os_sf.path.basename(_buf2_sf.value).lower()
                        if "feishu" in _exe2_sf or "lark" in _exe2_sf:
                            _feishu_hwnd_sf = _hwnd_sf
                            break
                    finally:
                        ctypes.windll.kernel32.CloseHandle(_h2_sf)
        except Exception:
            pass
        _hwnd_sf = ctypes.windll.user32.GetWindow(_hwnd_sf, _GW_HWNDNEXT_sf)

    if _feishu_hwnd_sf:
        ctypes.windll.user32.ShowWindow(_feishu_hwnd_sf, 9)
        ctypes.windll.user32.SetForegroundWindow(_feishu_hwnd_sf)
        time.sleep(0.3)
"""


def build_feishu_uia_click_code(
    target_text: str,
    num_clicks: int = 1,
    button_type: str = "left",
) -> str:
    """Return code that locates a UIA element by text inside Feishu windows and clicks it."""
    return f"""
import ctypes
import time
from pywinauto import Desktop

target_text = {target_text!r}
clicked = False
try:
    desktop = Desktop(backend="uia")

    import os as _os
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    _exe_buf = ctypes.create_unicode_buffer(512)
    _feishu_pids = set()
    _checked_pids = set()
    for _cand in desktop.windows():
        try:
            _pid = _cand.process_id()
            if _pid in _checked_pids:
                continue
            _checked_pids.add(_pid)
            _h = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, _pid)
            if _h:
                try:
                    _sz = ctypes.c_ulong(512)
                    ctypes.windll.kernel32.QueryFullProcessImageNameW(_h, 0, _exe_buf, ctypes.byref(_sz))
                    _exe = _os.path.basename(_exe_buf.value).lower()
                    if "feishu" in _exe or "lark" in _exe:
                        _feishu_pids.add(_pid)
                finally:
                    ctypes.windll.kernel32.CloseHandle(_h)
        except Exception:
            continue

    search_wins = []
    seen_handles = set()
    fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
    for candidate in desktop.windows():
        try:
            if candidate.process_id() in _feishu_pids:
                h = candidate.handle
                if h not in seen_handles:
                    search_wins.append(candidate)
                    seen_handles.add(h)
        except Exception:
            continue

    search_wins.sort(key=lambda w, _fg=fg_hwnd: 0 if (w.handle == _fg) else 1)

    candidates = []
    for win in search_wins:
        is_fg_win = (win.handle == fg_hwnd)
        try:
            for elem in win.descendants():
                try:
                    txt = (elem.window_text() or "").strip()
                    if not txt:
                        continue
                    if txt == target_text or target_text in txt:
                        rect = elem.rectangle()
                        control_type = elem.element_info.control_type
                        score = 0
                        if txt == target_text:
                            score += 1000
                        if is_fg_win:
                            score += 500
                        if control_type in ("Edit", "TabItem", "ListItem", "Button", "Text", "Document", "DataItem"):
                            score += 100
                        if control_type == "Edit":
                            score += 200
                        if rect.left < 500:
                            score += 20
                        if rect.top < 1000:
                            score += 10
                        if len(txt) <= len(target_text) + 12:
                            score += 10
                        candidates.append((score, elem, txt, control_type, rect))
                except Exception:
                    continue
        except Exception:
            continue
    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        elem = candidates[0][1]
        _num_clicks = {num_clicks!r}
        _button_type = {button_type!r}
        try:
            elem.scroll_into_view()
        except Exception:
            pass
        try:
            for _ in range(_num_clicks):
                elem.click_input(button=_button_type)
        except Exception:
            try:
                elem.invoke()
            except Exception:
                elem.click()
        clicked = True
        _result_line = "FEISHU_UIA_CLICKED: " + repr(target_text) + " txt=" + repr(candidates[0][2]) + " type=" + repr(candidates[0][3]) + " rect=" + repr(candidates[0][4])
        _top3 = []
        for _ci in range(min(3, len(candidates))):
            _top3.append("  #" + str(_ci) + " score=" + str(candidates[_ci][0]) + " txt=" + repr(candidates[_ci][2]) + " type=" + repr(candidates[_ci][3]) + " rect=" + repr(candidates[_ci][4]))
        print(_result_line)
        try:
            import pathlib as _pl
            with open(_pl.Path("logs") / "execution-trace.log", "a", encoding="utf-8") as _tf:
                _tf.write(_result_line + "\\n")
                for _l in _top3:
                    _tf.write(_l + "\\n")
        except Exception:
            pass
        time.sleep(0.5)
    else:
        _miss_line = "FEISHU_UIA_CLICK_MISS: " + repr(target_text)
        print(_miss_line)
        try:
            import pathlib as _pl
            with open(_pl.Path("logs") / "execution-trace.log", "a", encoding="utf-8") as _tf:
                _tf.write(_miss_line + "\\n")
        except Exception:
            pass
except Exception as exc:
    _err_line = "FEISHU_UIA_CLICK_ERROR: " + repr(exc)
    print(_err_line)
    try:
        import pathlib as _pl
        with open(_pl.Path("logs") / "execution-trace.log", "a", encoding="utf-8") as _tf:
            _tf.write(_err_line + "\\n")
    except Exception:
        pass
"""


def build_feishu_doc_click_code(button_name: str) -> str:
    """Return code that clicks a toolbar button in a Feishu cloud document in the browser.

    Uses window geometry + optional vision detection instead of visual grounding.
    """
    # (pixels_from_window_right, pixels_from_window_top)
    OFFSETS = {
        "分享": (302, 111),
        "评论": (250, 93),
        "更多": (55, 93),
        "分析": (330, 93),
    }
    log_path = str(REPO_ROOT / "logs")
    return f"""
import ctypes
import ctypes.wintypes
import time
import pathlib

button_name = {button_name!r}
_OFFSETS = {OFFSETS!r}

try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

_GW_HWNDNEXT = 2
_browser_hwnd = None
_all_browser_titles = []
_FEISHU_KEYS = ('feishu', '\\u98de\\u4e66', 'lark', 'bytedance', 'larksuite')

def _get_win_text(hwnd, _ct=ctypes):
    _l = _ct.windll.user32.GetWindowTextLengthW(hwnd)
    if _l <= 0:
        return ""
    _b = _ct.create_unicode_buffer(_l + 1)
    _ct.windll.user32.GetWindowTextW(hwnd, _b, _l + 1)
    return _b.value

def _get_win_class(hwnd, _ct=ctypes):
    _b = _ct.create_unicode_buffer(256)
    _ct.windll.user32.GetClassNameW(hwnd, _b, 256)
    return _b.value

try:
    _fg = ctypes.windll.user32.GetForegroundWindow()
    if _fg and 'Chrome_WidgetWin_1' in _get_win_class(_fg):
        _fg_title = _get_win_text(_fg)
        _all_browser_titles.append(_fg_title[:80])
        _fg_title_lower = _fg_title.lower()
        for _key in _FEISHU_KEYS:
            if _key in _fg_title_lower:
                _browser_hwnd = _fg
                break

    if _browser_hwnd is None:
        _hwnd = ctypes.windll.user32.GetTopWindow(0)
        while _hwnd:
            try:
                if ctypes.windll.user32.IsWindowVisible(_hwnd) and 'Chrome_WidgetWin_1' in _get_win_class(_hwnd):
                    _title = _get_win_text(_hwnd)
                    if _title:
                        _all_browser_titles.append(_title[:80])
                        _title_lower = _title.lower()
                        for _key in _FEISHU_KEYS:
                            if _key in _title_lower:
                                _browser_hwnd = _hwnd
                                break
                        if _browser_hwnd is not None:
                            break
            except Exception:
                pass
            _hwnd = ctypes.windll.user32.GetWindow(_hwnd, _GW_HWNDNEXT)

    if _browser_hwnd is None:
        _largest_area = 0
        _hwnd2 = ctypes.windll.user32.GetTopWindow(0)
        while _hwnd2:
            try:
                if ctypes.windll.user32.IsWindowVisible(_hwnd2) and 'Chrome_WidgetWin_1' in _get_win_class(_hwnd2):
                    _title2 = _get_win_text(_hwnd2)
                    if _title2:
                        _r2 = ctypes.wintypes.RECT()
                        ctypes.windll.user32.GetWindowRect(_hwnd2, ctypes.byref(_r2))
                        _area2 = max(0, _r2.right - _r2.left) * max(0, _r2.bottom - _r2.top)
                        if _area2 > _largest_area:
                            _largest_area = _area2
                            _browser_hwnd = _hwnd2
            except Exception:
                pass
            _hwnd2 = ctypes.windll.user32.GetWindow(_hwnd2, _GW_HWNDNEXT)
        if _browser_hwnd is not None:
            _all_browser_titles.append('FALLBACK_ANY_BROWSER:' + _get_win_text(_browser_hwnd)[:60])
except Exception as _browser_exc:
    _all_browser_titles.append('BROWSER_DETECT_ERROR:' + repr(_browser_exc)[:100])

if _browser_hwnd is None:
    _browser_hwnd = ctypes.windll.user32.GetForegroundWindow()
    _all_browser_titles.append('FINAL_FALLBACK_FG')

_r = ctypes.wintypes.RECT()

ctypes.windll.user32.ShowWindow(_browser_hwnd, 3)
ctypes.windll.user32.SetForegroundWindow(_browser_hwnd)
time.sleep(0.5)
ctypes.windll.user32.GetWindowRect(_browser_hwnd, ctypes.byref(_r))

_off = _OFFSETS.get(button_name, (170, 93))
_cx = _r.right - _off[0]
_cy = _r.top + _off[1]

ctypes.windll.user32.SetCursorPos(_cx, _cy)
time.sleep(0.05)
ctypes.windll.user32.mouse_event(0x0002, 0, 0, 0, 0)
time.sleep(0.05)
ctypes.windll.user32.mouse_event(0x0004, 0, 0, 0, 0)
time.sleep(1.5)

_log = (
    f'FEISHU_DOC_CLICKED: {{button_name!r}} at ({{_cx}}, {{_cy}})'
    f' window=({{_r.left}},{{_r.top}},{{_r.right}},{{_r.bottom}})'
    f' browser_titles={{_all_browser_titles!r}}'
)
print(_log)
try:
    _lp = pathlib.Path({log_path!r}) / "feishu-doc-click.log"
    _lp.parent.mkdir(exist_ok=True)
    with open(_lp, "a", encoding="utf-8") as _f:
        _f.write(_log + "\\n")
except Exception as _e:
    print(f"FEISHU_DOC_CLICK_LOG_ERROR: {{_e!r}}")
"""


def build_feishu_doc_type_code(text: str) -> str:
    """Return code that pastes text into the currently focused element in the browser.

    Does NOT click — use after feishu_doc_click() when the popup input is already
    focused. Clicking would dismiss light-dismiss popups like the share search field.
    """
    log_path = str(REPO_ROOT / "logs")
    return f"""
import ctypes
import ctypes.wintypes
import time
import pathlib
import pyperclip

try:
    ctypes.windll.user32.SetProcessDPIAware()
except Exception:
    pass

_GW_HWNDNEXT = 2
_browser_hwnd = None
_FEISHU_KEYS = ('feishu', '\\u98de\\u4e66', 'lark', 'bytedance', 'larksuite')

def _get_win_text_dt(hwnd, _ct=ctypes):
    _l = _ct.windll.user32.GetWindowTextLengthW(hwnd)
    if _l <= 0:
        return ""
    _b = _ct.create_unicode_buffer(_l + 1)
    _ct.windll.user32.GetWindowTextW(hwnd, _b, _l + 1)
    return _b.value

def _get_win_class_dt(hwnd, _ct=ctypes):
    _b = _ct.create_unicode_buffer(256)
    _ct.windll.user32.GetClassNameW(hwnd, _b, 256)
    return _b.value

try:
    _fg = ctypes.windll.user32.GetForegroundWindow()
    if _fg and 'Chrome_WidgetWin_1' in _get_win_class_dt(_fg):
        _fg_title = _get_win_text_dt(_fg).lower()
        for _key in _FEISHU_KEYS:
            if _key in _fg_title:
                _browser_hwnd = _fg
                break

    if _browser_hwnd is None:
        _hwnd = ctypes.windll.user32.GetTopWindow(0)
        while _hwnd:
            try:
                if ctypes.windll.user32.IsWindowVisible(_hwnd) and 'Chrome_WidgetWin_1' in _get_win_class_dt(_hwnd):
                    _title = _get_win_text_dt(_hwnd).lower()
                    for _key in _FEISHU_KEYS:
                        if _key in _title:
                            _browser_hwnd = _hwnd
                            break
                    if _browser_hwnd is not None:
                        break
            except Exception:
                pass
            _hwnd = ctypes.windll.user32.GetWindow(_hwnd, _GW_HWNDNEXT)

    if _browser_hwnd is None:
        _largest_area = 0
        _hwnd2 = ctypes.windll.user32.GetTopWindow(0)
        while _hwnd2:
            try:
                if ctypes.windll.user32.IsWindowVisible(_hwnd2) and 'Chrome_WidgetWin_1' in _get_win_class_dt(_hwnd2):
                    _title2 = _get_win_text_dt(_hwnd2)
                    if _title2:
                        _r2 = ctypes.wintypes.RECT()
                        ctypes.windll.user32.GetWindowRect(_hwnd2, ctypes.byref(_r2))
                        _area2 = max(0, _r2.right - _r2.left) * max(0, _r2.bottom - _r2.top)
                        if _area2 > _largest_area:
                            _largest_area = _area2
                            _browser_hwnd = _hwnd2
            except Exception:
                pass
            _hwnd2 = ctypes.windll.user32.GetWindow(_hwnd2, _GW_HWNDNEXT)
except Exception:
    pass

if _browser_hwnd is None:
    _browser_hwnd = ctypes.windll.user32.GetForegroundWindow()

# SetForegroundWindow without any mouse click so popup focus is preserved
ctypes.windll.user32.SetForegroundWindow(_browser_hwnd)
time.sleep(0.2)

pyperclip.copy({text!r})
ctypes.windll.user32.keybd_event(0x11, 0, 0, 0)   # Ctrl down
ctypes.windll.user32.keybd_event(0x56, 0, 0, 0)   # V down
time.sleep(0.05)
ctypes.windll.user32.keybd_event(0x56, 0, 0x0002, 0)  # V up
ctypes.windll.user32.keybd_event(0x11, 0, 0x0002, 0)  # Ctrl up
time.sleep(0.3)

try:
    _lp = pathlib.Path({log_path!r}) / "execution-trace.log"
    _lp.parent.mkdir(exist_ok=True)
    with open(_lp, "a", encoding="utf-8") as _f:
        _f.write("FEISHU_DOC_TYPED: " + repr({text!r}) + " browser_hwnd=" + str(_browser_hwnd) + "\\n")
except Exception:
    pass
"""


def build_windows_open_code(app_or_filename: str) -> str:
    """Return code that opens an app or file on Windows.

    Handles Feishu (direct exe launch + UIA focus), browsers (foreground existing
    window), and generic apps (Win+Search).
    """
    return f"""
import os
import time
import ctypes
import pyautogui
import pyperclip

app_name = {repr(app_or_filename)}
lower_name = app_name.lower()
is_feishu = ("\\u98de\\u4e66" in app_name) or "feishu" in lower_name or "lark" in lower_name
is_browser = False
for _browser_name in ("edge", "microsoft edge", "chrome", "browser"):
    if _browser_name in lower_name:
        is_browser = True
        break

def _focus_existing_browser():
    browser_exe_tokens = ("msedge", "chrome")
    wanted_tokens = ("feishu", "\\u98de\\u4e66", "lark", "bytedance", "larksuite")
    if "chrome" in lower_name and "edge" not in lower_name:
        browser_exe_tokens = ("chrome",)
    elif "edge" in lower_name or "microsoft edge" in lower_name:
        browser_exe_tokens = ("msedge",)

    def _window_title(hwnd):
        length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
        return buf.value

    def _window_exe(hwnd):
        pid = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid.value)
        if not handle:
            return ""
        try:
            buf = ctypes.create_unicode_buffer(260)
            size = ctypes.c_ulong(260)
            ctypes.windll.kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size))
            return buf.value.lower()
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)

    candidates = []
    hwnd = ctypes.windll.user32.GetTopWindow(0)
    while hwnd:
        try:
            if ctypes.windll.user32.IsWindowVisible(hwnd):
                exe = _window_exe(hwnd)
                is_target_browser_exe = any(token in exe for token in browser_exe_tokens)
                if is_target_browser_exe:
                    title = _window_title(hwnd)
                    if title:
                        priority = 0 if any(t in title.lower() for t in wanted_tokens) else 1
                        candidates.append((priority, hwnd, title))
        except Exception:
            pass
        hwnd = ctypes.windll.user32.GetWindow(hwnd, 2)

    if not candidates:
        print("WINDOWS_OPEN_EXISTING_BROWSER_MISS:", repr(app_name))
        return False

    candidates.sort(key=lambda item: item[0])
    _, hwnd, title = candidates[0]
    ctypes.windll.user32.ShowWindow(hwnd, 9)
    ctypes.windll.user32.SetForegroundWindow(hwnd)
    print("WINDOWS_OPEN_EXISTING_BROWSER:", repr(app_name), repr(title))
    time.sleep(0.5)
    return True

if is_feishu:
    feishu_path = os.path.expandvars(r"%LOCALAPPDATA%\\Feishu\\app\\Feishu.exe")
    if os.path.exists(feishu_path):
        os.startfile(feishu_path)
        time.sleep(1.0)
    else:
        pyautogui.hotkey("win")
        time.sleep(0.5)
        pyperclip.copy(app_name)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")
        time.sleep(1.0)
    # Focus the newly launched (or existing) Feishu window with ctypes
    _GW_HWNDNEXT_open = 2
    _PQLI_open = 0x1000
    _feishu_hwnd_open = None
    _hwnd_open = ctypes.windll.user32.GetTopWindow(0)
    while _hwnd_open:
        try:
            if ctypes.windll.user32.IsWindowVisible(_hwnd_open):
                _pid_open = ctypes.c_ulong(0)
                ctypes.windll.user32.GetWindowThreadProcessId(_hwnd_open, ctypes.byref(_pid_open))
                _h_open = ctypes.windll.kernel32.OpenProcess(_PQLI_open, False, _pid_open.value)
                if _h_open:
                    try:
                        _buf_open = ctypes.create_unicode_buffer(512)
                        _sz_open = ctypes.c_ulong(512)
                        ctypes.windll.kernel32.QueryFullProcessImageNameW(_h_open, 0, _buf_open, ctypes.byref(_sz_open))
                        _exe_open = os.path.basename(_buf_open.value).lower()
                        if "feishu" in _exe_open or "lark" in _exe_open:
                            _feishu_hwnd_open = _hwnd_open
                            break
                    finally:
                        ctypes.windll.kernel32.CloseHandle(_h_open)
        except Exception:
            pass
        _hwnd_open = ctypes.windll.user32.GetWindow(_hwnd_open, _GW_HWNDNEXT_open)

    if _feishu_hwnd_open:
        ctypes.windll.user32.ShowWindow(_feishu_hwnd_open, 9)
        ctypes.windll.user32.SetForegroundWindow(_feishu_hwnd_open)
        print("FEISHU_OPEN_CTYPES: focused hwnd", _feishu_hwnd_open)
    else:
        print("FEISHU_OPEN_CTYPES_MISS")
else:
    if not (is_browser and _focus_existing_browser()):
        pyautogui.hotkey("win")
        time.sleep(0.5)
        pyperclip.copy(app_name)
        pyautogui.hotkey("ctrl", "v")
        pyautogui.press("enter")

time.sleep(1.0)
"""
