"""Windows + Feishu/Lark ACI extension of the upstream OSWorldACI.

Adds:
- Multi-monitor virtual screen offset in resize_coordinates()
- Enhanced grounding tracing in generate_coords()
- CJK-compatible OCR regex in get_ocr_elements()
- Feishu-specific agent actions: feishu_focus, feishu_click, feishu_type, feishu_doc_click
- Windows open() branch
"""

import re
import time
from io import BytesIO
from typing import Dict, List, Optional

from PIL import Image, ImageGrab

from gui_agents.s3.agents.grounding import OSWorldACI, agent_action
from gui_agents.s3.agents._feishu_exec import (
    REPO_ROOT,
    build_feishu_doc_click_code,
    build_feishu_doc_type_code,
    build_feishu_focus_code,
    build_feishu_safe_focus_code,
    build_feishu_uia_click_code,
    build_win32_click_code,
    build_windows_open_code,
)
from gui_agents.s3.utils.common_utils import call_llm_safe


class WindowsFeishuACI(OSWorldACI):
    """OSWorldACI extended for Windows multi-monitor + Feishu/Lark automation."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.virtual_screen_left = 0
        self.virtual_screen_top = 0
        if self.platform == "windows":
            try:
                import ctypes
                self.virtual_screen_left = ctypes.windll.user32.GetSystemMetrics(76)
                self.virtual_screen_top = ctypes.windll.user32.GetSystemMetrics(77)
            except Exception:
                pass

    # ------------------------------------------------------------------
    # Overrides
    # ------------------------------------------------------------------

    def resize_coordinates(self, coordinates: List[int]) -> List[int]:
        grounding_width = self.engine_params_for_grounding["grounding_width"]
        grounding_height = self.engine_params_for_grounding["grounding_height"]
        image_x = round(coordinates[0] * self.width / grounding_width)
        image_y = round(coordinates[1] * self.height / grounding_height)
        return [image_x + self.virtual_screen_left, image_y + self.virtual_screen_top]

    def generate_coords(self, ref_expr: str, obs: Dict) -> List[int]:
        self.grounding_model.reset()
        prompt = f"Query:{ref_expr}\nOutput only the coordinate of one point in your response.\n"
        self.grounding_model.add_message(
            text_content=prompt, image_content=obs["screenshot"], put_text_last=True
        )
        response = call_llm_safe(self.grounding_model)
        print("RAW GROUNDING MODEL RESPONSE:", response)
        numericals = re.findall(r"\d+", response)
        try:
            obs_image = Image.open(BytesIO(obs["screenshot"]))
            obs_size = obs_image.size
        except Exception:
            obs_size = None
        trace_payload = {
            "ref_expr": ref_expr,
            "response_tail": response[-400:] if isinstance(response, str) else repr(response),
            "numericals": numericals[:8],
            "obs_size": obs_size,
            "grounding_size": (
                self.engine_params_for_grounding["grounding_width"],
                self.engine_params_for_grounding["grounding_height"],
            ),
        }
        self._trace_execution("GROUNDING_RESPONSE: " + repr(trace_payload))
        assert len(numericals) >= 2
        coords = [int(numericals[0]), int(numericals[1])]
        if obs_size is not None:
            raw_x, raw_y = coords
            gw = self.engine_params_for_grounding["grounding_width"]
            gh = self.engine_params_for_grounding["grounding_height"]
            if raw_x < 0 or raw_y < 0 or raw_x > gw or raw_y > gh:
                self._trace_execution(
                    "GROUNDING_COORD_OUT_OF_RANGE: "
                    + repr({"coords": coords, "grounding_size": (gw, gh), "obs_size": obs_size, "ref_expr": ref_expr})
                )
        return coords

    def get_ocr_elements(self, b64_image_data: str):
        import pytesseract
        from collections import defaultdict
        from pytesseract import Output

        image = Image.open(BytesIO(b64_image_data))
        image_data = pytesseract.image_to_data(image, output_type=Output.DICT)
        # CJK-compatible: strip leading/trailing punctuation while preserving CJK characters
        for i, word in enumerate(image_data["text"]):
            image_data["text"][i] = re.sub(r"^\W+|\W+$", "", word, flags=re.UNICODE)

        ocr_elements = []
        ocr_table = "Text Table:\nWord id\tText\n"
        grouping_map = defaultdict(list)
        ocr_id = 0
        for i in range(len(image_data["text"])):
            block_num = image_data["block_num"][i]
            if image_data["text"][i]:
                grouping_map[block_num].append(image_data["text"][i])
                ocr_table += f"{ocr_id}\t{image_data['text'][i]}\n"
                ocr_elements.append(
                    {
                        "id": ocr_id,
                        "text": image_data["text"][i],
                        "group_num": block_num,
                        "word_num": len(grouping_map[block_num]),
                        "left": image_data["left"][i],
                        "top": image_data["top"][i],
                        "width": image_data["width"][i],
                        "height": image_data["height"][i],
                    }
                )
                ocr_id += 1
        return ocr_table, ocr_elements

    @agent_action
    def open(self, app_or_filename: str):
        """Open any application or file. The Windows path handles Feishu, browsers,
        and generic apps without calling sandbox scripts.
        Args:
            app_or_filename:str, the name of the application or filename to open
        """
        if self.platform == "linux":
            return f"import pyautogui; pyautogui.hotkey('win'); time.sleep(0.5); pyautogui.write({repr(app_or_filename)}); time.sleep(1.0); pyautogui.hotkey('enter'); time.sleep(0.5)"
        if self.platform == "darwin":
            return f"import pyautogui; import time; pyautogui.hotkey('command', 'space', interval=0.5); pyautogui.typewrite({repr(app_or_filename)}); pyautogui.press('enter'); time.sleep(1.0)"
        if self.platform == "windows":
            return build_windows_open_code(app_or_filename)
        raise AssertionError(f"Unsupported platform: {self.platform}")

    # ------------------------------------------------------------------
    # Host-side helpers (run at agent-eval time, NOT inside exec())
    # ------------------------------------------------------------------

    def _trace_execution(self, message: str) -> None:
        try:
            trace_path = REPO_ROOT / "logs" / "execution-trace.log"
            trace_path.parent.mkdir(exist_ok=True)
            with trace_path.open("a", encoding="utf-8") as f:
                f.write(message + "\n")
        except Exception:
            pass

    def _focus_feishu_now(self) -> bool:
        """Bring the Feishu/Lark window to the foreground using ctypes only.

        Safe to call host-side: uses GetTopWindow/GetWindow loop which cannot
        hang, unlike Desktop(backend='uia').
        """
        try:
            import ctypes
            import os as _os

            GW_HWNDNEXT = 2
            PQLI = 0x1000

            def _get_exe(hwnd):
                pid = ctypes.c_ulong(0)
                ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                h = ctypes.windll.kernel32.OpenProcess(PQLI, False, pid.value)
                if not h:
                    return ""
                try:
                    buf = ctypes.create_unicode_buffer(512)
                    sz = ctypes.c_ulong(512)
                    ctypes.windll.kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(sz))
                    return _os.path.basename(buf.value).lower()
                finally:
                    ctypes.windll.kernel32.CloseHandle(h)

            hwnd = ctypes.windll.user32.GetTopWindow(0)
            while hwnd:
                try:
                    if ctypes.windll.user32.IsWindowVisible(hwnd):
                        exe = _get_exe(hwnd)
                        if "feishu" in exe or "lark" in exe:
                            ctypes.windll.user32.ShowWindow(hwnd, 9)
                            ctypes.windll.user32.SetForegroundWindow(hwnd)
                            time.sleep(0.5)
                            self._trace_execution(f"FEISHU_FOCUS_NOW: ctypes hwnd={hwnd} exe={exe}")
                            return True
                except Exception:
                    pass
                hwnd = ctypes.windll.user32.GetWindow(hwnd, GW_HWNDNEXT)

            self._trace_execution("FEISHU_FOCUS_NOW: window_not_found")
            return False
        except Exception as exc:
            self._trace_execution(f"FEISHU_FOCUS_NOW_ERROR: {exc!r}")
            return False

    def _refresh_obs_screenshot(self) -> None:
        try:
            screenshot = ImageGrab.grab(all_screens=True)
            captured_size = screenshot.size
            grounding_width = self.engine_params_for_grounding["grounding_width"]
            grounding_height = self.engine_params_for_grounding["grounding_height"]
            screenshot = screenshot.resize((grounding_width, grounding_height), Image.LANCZOS)
            buffered = BytesIO()
            screenshot.save(buffered, format="PNG")
            if self.obs is None:
                self.obs = {}
            self.obs["screenshot"] = buffered.getvalue()
            self._trace_execution(
                "FEISHU_REFRESH_OBS: "
                + repr({"captured_size": captured_size, "grounding_size": (grounding_width, grounding_height)})
            )
        except Exception as exc:
            self._trace_execution(f"FEISHU_REFRESH_OBS_ERROR: {exc!r}")

    def _repair_text_mojibake(self, text: str) -> str:
        """Repair Chinese text that was UTF-8 bytes decoded as GBK."""
        if not isinstance(text, str):
            return text
        candidates = [text]
        for encoding in ("gbk", "gb18030", "cp936"):
            for errors in ("strict", "ignore"):
                try:
                    repaired = text.encode(encoding, errors=errors).decode("utf-8", errors=errors)
                except UnicodeError:
                    continue
                if repaired and repaired not in candidates:
                    candidates.append(repaired)

        def score(value: str) -> int:
            good_chars = sum("一" <= ch <= "鿿" for ch in value)
            bad_markers = sum(
                value.count(m)
                for m in ("?", "锟", "閿", "閹", "閸", "鍏", "濞", "瀣", "妞",
                          "鐐", "鍔", "鍒", "嗕", "韩", "椋", "炰", "功", "浜",
                          "戞", "枃", "妗", "鏂", "板", "缓", "绌", "櫧", "缁",
                          "堜", "簬", "濂", "戒", "簡")
            )
            return good_chars * 3 - bad_markers * 5 + len(value.replace("?", "").replace("锟", ""))

        repaired = max(candidates, key=score)
        if repaired != text:
            print("TEXT_MOJIBAKE_REPAIRED:", repr(text), "=>", repr(repaired))
        return repaired

    def _extract_feishu_target_text(self, element_description: str) -> str:
        """Extract the most likely UI element text from a natural-language description."""
        text = self._repair_text_mojibake(element_description).strip()
        quoted = []
        for match in re.finditer(r"""['"]([^'"]{1,80})['"]""", text):
            candidate = match.group(1).strip()
            if candidate:
                quoted.append(candidate)

        def normalize(value: str) -> str:
            return value.strip(" \t\r\n.,!?;:()[]{}")

        if quoted:
            quoted_candidates = [c for c in (normalize(c) for c in quoted) if c]
            if not quoted_candidates:
                return text

            def quoted_score(idx: int, value: str):
                has_cjk = any("一" <= ch <= "鿿" for ch in value)
                has_ascii = any(ch.isascii() and ch.isalnum() for ch in value)
                mixed = has_ascii and has_cjk
                return (2 if has_cjk else 0) + (1 if mixed else 0), -idx

            return max(
                ((quoted_score(i, v), v) for i, v in enumerate(quoted_candidates)),
                key=lambda x: x[0],
            )[1]

        mixed_chunks = re.findall(r"[A-Za-z0-9一-鿿]{2,20}", text)
        cjk_chunks = re.findall(r"[一-鿿]{1,20}", text)
        ascii_chunks = re.findall(r"[A-Za-z0-9][A-Za-z0-9 _-]{0,40}", text)

        candidates = []
        for candidate in mixed_chunks + cjk_chunks + ascii_chunks:
            candidate = normalize(candidate)
            if candidate and candidate not in candidates:
                candidates.append(candidate)

        if not candidates:
            return text

        def fallback_score(value: str):
            has_cjk = any("一" <= ch <= "鿿" for ch in value)
            has_ascii = any(ch.isascii() and ch.isalnum() for ch in value)
            mixed = has_ascii and has_cjk
            return (2 if has_cjk else 0) + (1 if mixed else 0), -len(value), -value.count(" ")

        return max(candidates, key=fallback_score)

    # ------------------------------------------------------------------
    # Feishu-specific agent actions
    # ------------------------------------------------------------------

    @agent_action
    def feishu_focus(self):
        """Focus the running Feishu/Lark desktop window. Use this before Feishu-specific actions.
        Args:
        """
        return build_feishu_focus_code()

    @agent_action
    def feishu_click(
        self,
        element_description: str,
        num_clicks: int = 1,
        button_type: str = "left",
    ):
        """Focus Feishu/Lark, then click an element using UIA text matching. Does not call visual grounding.
        Args:
            element_description:str, a detailed visual description of the Feishu element to click. Include exact visible text when selecting a chat, row, button, tab, or menu item.
            num_clicks:int, number of times to click the element
            button_type:str, mouse button to press, such as left, middle, or right
        """
        element_description = self._repair_text_mojibake(element_description)
        target_text = self._extract_feishu_target_text(element_description)
        self._trace_execution(
            "FEISHU_CLICK_UIA_ONLY: "
            + repr({"description": element_description, "target_text": target_text})
        )
        return build_feishu_uia_click_code(target_text, num_clicks, button_type)

    @agent_action
    def feishu_type(
        self,
        text: str,
        element_description: Optional[str] = None,
        overwrite: bool = False,
        enter: bool = False,
    ):
        """Focus Feishu/Lark and paste text, optionally clicking an element first using UIA.
        Args:
            text:str, text to paste into Feishu
            element_description:str, optional description of the Feishu input element to click before typing
            overwrite:bool, whether to select all existing text before pasting
            enter:bool, whether to press Enter after pasting
        """
        click_code = ""
        if element_description is not None:
            element_description = self._repair_text_mojibake(element_description)
            target_text = self._extract_feishu_target_text(element_description)
            self._trace_execution(
                "FEISHU_TYPE_UIA_ONLY: "
                + repr({"description": element_description, "target_text": target_text})
            )
            click_code = build_feishu_uia_click_code(target_text, 1, "left")

        overwrite_code = "pyautogui.hotkey('ctrl', 'a'); pyautogui.press('backspace');\n" if overwrite else ""
        enter_code = "pyautogui.press('enter')\n" if enter else ""

        if click_code:
            # Already clicked a specific element — don't refocus the main window
            # (that would close any floating dialog that's now open).
            focus_code = ""
        else:
            # Safe focus: only brings Feishu forward when it isn't already foreground.
            focus_code = build_feishu_safe_focus_code()

        if click_code:
            _indent = "    "
            _ow = (_indent + overwrite_code.rstrip("\n") + "\n") if overwrite_code else ""
            _en = (_indent + enter_code.rstrip("\n") + "\n") if enter_code else ""
            _paste_block = (
                f"if clicked:\n"
                f"{_ow}"
                f"{_indent}pyperclip.copy({text!r})\n"
                f"{_indent}pyautogui.hotkey('ctrl', 'v')\n"
                f"{_en}"
            )
            return focus_code + f"\nimport pyautogui\nimport pyperclip\n{click_code}\n{_paste_block}\n"

        return (
            focus_code
            + f"""
import pyautogui
import pyperclip
{overwrite_code}pyperclip.copy({text!r})
pyautogui.hotkey('ctrl', 'v')
{enter_code}
"""
        )

    @agent_action
    def feishu_doc_click(self, button_name: str):
        """Click a toolbar button in a Feishu cloud document open in the browser.
        Uses the foreground browser window's geometry instead of visual grounding.
        Only use this when the Feishu cloud doc is open in a browser window.
        Args:
            button_name:str, exact name of the toolbar button, e.g. "分享", "评论", "更多", "分析"
        """
        button_name = self._repair_text_mojibake(button_name)
        self._trace_execution("FEISHU_DOC_CLICK: " + repr({"button_name": button_name}))
        return build_feishu_doc_click_code(button_name)

    @agent_action
    def feishu_doc_type(self, text: str):
        """Paste text into the currently focused element in the browser WITHOUT clicking.

        Use this after feishu_doc_click("分享") when the share popup's search input is
        already focused. Do NOT use agent.type(element_description, text) in that context
        because the click to locate the element dismisses the light-dismiss popup.
        Args:
            text:str, the text to paste into the focused input field
        """
        text = self._repair_text_mojibake(text)
        self._trace_execution("FEISHU_DOC_TYPE: " + repr({"text": text}))
        return build_feishu_doc_type_code(text)
