"""SOP executor — runs JSON-defined workflows without Agent S inference."""
import json
import os
import re
import time
import urllib.request

import pyautogui

SOP_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sops")

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05


# ── helpers ──────────────────────────────────────────────────────────────────

def list_sops() -> list[dict]:
    """Return parsed SOP dicts sorted by filename."""
    sops = []
    if not os.path.isdir(SOP_DIR):
        return sops
    for fname in sorted(os.listdir(SOP_DIR)):
        if fname.endswith(".json"):
            path = os.path.join(SOP_DIR, fname)
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                data["_file"] = path
                sops.append(data)
            except Exception:
                pass
    return sops


def _fill(text: str, params: dict) -> str:
    for k, v in params.items():
        text = text.replace(f"{{{{{k}}}}}", v)
    return text


# ── step runners ─────────────────────────────────────────────────────────────

def _run_step(step: dict, params: dict, log_fn=None):
    def log(msg):
        if log_fn:
            log_fn(msg)

    t = step.get("type")

    if t == "hotkey":
        keys = step["keys"]
        log(f"  hotkey: {'+'.join(keys)}")
        pyautogui.hotkey(*keys)

    elif t == "type":
        text = _fill(step["text"], params)
        log(f"  type: {text!r}")
        pyautogui.write(text, interval=0.03)

    elif t == "press":
        key = step["key"]
        log(f"  press: {key}")
        pyautogui.press(key)

    elif t == "wait":
        sec = float(step.get("seconds", 1))
        log(f"  wait: {sec}s")
        time.sleep(sec)

    elif t == "click":
        x, y = int(step["x"]), int(step["y"])
        log(f"  click: ({x}, {y})")
        pyautogui.click(x, y)

    elif t == "http":
        url = _fill(step["url"], params)
        method = step.get("method", "GET").upper()
        body = _fill(json.dumps(step.get("body", {})), params).encode()
        headers = step.get("headers", {"Content-Type": "application/json"})
        req = urllib.request.Request(url, data=body if method != "GET" else None,
                                     headers=headers, method=method)
        log(f"  http {method}: {url}")
        with urllib.request.urlopen(req, timeout=10) as resp:
            log(f"  → {resp.status}")

    elif t == "ai_click":
        # Falls back to pyautogui.locateOnScreen if image path provided,
        # otherwise logs a warning (requires Agent S for full support).
        img = step.get("image")
        if img and os.path.exists(img):
            loc = pyautogui.locateOnScreen(img, confidence=0.8)
            if loc:
                cx, cy = pyautogui.center(loc)
                log(f"  ai_click found at ({cx}, {cy})")
                pyautogui.click(cx, cy)
            else:
                log(f"  ai_click: image not found on screen")
        else:
            log(f"  ai_click: skipped (no image or Agent S not running)")

    else:
        log(f"  unknown step type: {t!r}")


# ── main entry ────────────────────────────────────────────────────────────────

def run_sop(sop: dict, params: dict, log_fn=None):
    """Execute all steps of an SOP, substituting params."""
    def log(msg):
        if log_fn:
            log_fn(msg)

    log(f"▶ SOP: {sop.get('name', '?')}")
    for i, step in enumerate(sop.get("steps", [])):
        log(f"[{i+1}/{len(sop['steps'])}] {step.get('type', '?')}"
            + (f" — {step.get('comment', '')}" if step.get("comment") else ""))
        try:
            _run_step(step, params, log_fn)
        except Exception as e:
            log(f"  ✗ 错误: {e}")
            raise
    log("✅ SOP 完成")
