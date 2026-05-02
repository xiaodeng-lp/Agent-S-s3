import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import subprocess
import threading
import pyautogui
import queue
import sys
import os
import re
import json

ANSI_ESCAPE = re.compile(r'\x1b\[[0-9;]*m')

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
CLI_APP = os.path.join(PROJECT_DIR, "gui_agents", "s3", "cli_app.py")
CONFIG_FILE = os.path.join(PROJECT_DIR, "config.json")

DEFAULT_CONFIG = {
    "model_api_key":  "",
    "model_id":       "",
    "model_url":      "https://ark.cn-beijing.volces.com/api/v3",
    "ground_api_key": "",
    "ground_model":   "bytedance/ui-tars-1.5-7b",
}

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
            return {**DEFAULT_CONFIG, **saved}
        except Exception:
            pass
    return DEFAULT_CONFIG.copy()

def save_config(cfg: dict):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


class Launcher:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Agent S 启动器")
        self.root.resizable(True, True)
        self.process = None
        self.output_queue = queue.Queue()
        self.agent_ready = False
        self.cfg = load_config()

        self._build_ui()
        self._auto_detect_resolution()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # ─── UI ───────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        notebook = ttk.Notebook(self.root)
        notebook.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        # Tab 1: Agent
        agent_tab = ttk.Frame(notebook)
        notebook.add(agent_tab, text="  Agent  ")
        self._build_agent_tab(agent_tab)

        # Tab 2: SOP quick-actions
        sop_tab = ttk.Frame(notebook)
        notebook.add(sop_tab, text="  快捷操作  ")
        self._build_sop_tab(sop_tab)

        self.root.update_idletasks()
        self.root.minsize(660, 600)

    # ── Agent tab ────────────────────────────────────────────────────────────

    def _build_agent_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # ── 顶部：配置区 ──
        cfg = ttk.LabelFrame(parent, text="配置", padding=8)
        cfg.grid(row=0, column=0, sticky="ew", padx=4, pady=(4, 0))
        cfg.columnconfigure(1, weight=1)

        ttk.Label(cfg, text="豆包 API Key").grid(row=0, column=0, sticky="w", pady=2)
        self.v_model_key = tk.StringVar(value=self.cfg["model_api_key"])
        ttk.Entry(cfg, textvariable=self.v_model_key, show="*", width=50).grid(row=0, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(cfg, text="豆包 Endpoint ID").grid(row=1, column=0, sticky="w", pady=2)
        self.v_model_id = tk.StringVar(value=self.cfg["model_id"])
        ttk.Entry(cfg, textvariable=self.v_model_id, width=50).grid(row=1, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(cfg, text="OpenRouter API Key").grid(row=2, column=0, sticky="w", pady=2)
        self.v_ground_key = tk.StringVar(value=self.cfg["ground_api_key"])
        ttk.Entry(cfg, textvariable=self.v_ground_key, show="*", width=50).grid(row=2, column=1, sticky="ew", padx=(8, 0))

        ttk.Label(cfg, text="定位分辨率").grid(row=3, column=0, sticky="w", pady=2)
        res_frame = ttk.Frame(cfg)
        res_frame.grid(row=3, column=1, sticky="w", padx=(8, 0))
        self.v_gw = tk.StringVar()
        self.v_gh = tk.StringVar()
        ttk.Entry(res_frame, textvariable=self.v_gw, width=6).pack(side="left")
        ttk.Label(res_frame, text=" x ").pack(side="left")
        ttk.Entry(res_frame, textvariable=self.v_gh, width=6).pack(side="left")
        self.v_screen_info = tk.StringVar()
        ttk.Label(res_frame, textvariable=self.v_screen_info, foreground="gray").pack(side="left", padx=(10, 0))

        btn_frame = ttk.Frame(cfg)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=(8, 0))
        self.btn_start = ttk.Button(btn_frame, text="▶  启动 Agent", command=self._start_agent, width=20)
        self.btn_start.pack(side="left", padx=4)
        self.btn_stop = ttk.Button(btn_frame, text="■  停止", command=self._stop_agent, width=10, state="disabled")
        self.btn_stop.pack(side="left", padx=4)
        ttk.Button(btn_frame, text="💾 保存配置", command=self._save_config, width=12).pack(side="left", padx=4)
        self.v_status = tk.StringVar(value="未启动")
        ttk.Label(btn_frame, textvariable=self.v_status, foreground="gray").pack(side="left", padx=12)

        # ── 中部：日志区 ──
        log_frame = ttk.LabelFrame(parent, text="运行日志", padding=4)
        log_frame.grid(row=1, column=0, sticky="nsew", padx=4, pady=8)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        self.log = scrolledtext.ScrolledText(log_frame, wrap="word", height=18,
                                             font=("Consolas", 9), state="disabled",
                                             bg="#1e1e1e", fg="#d4d4d4",
                                             insertbackground="white")
        self.log.grid(row=0, column=0, sticky="nsew")

        self.log.tag_config("info",    foreground="#9cdcfe")
        self.log.tag_config("action",  foreground="#4ec9b0")
        self.log.tag_config("warn",    foreground="#ce9178")
        self.log.tag_config("query",   foreground="#dcdcaa")
        self.log.tag_config("success", foreground="#6a9955")
        self.log.tag_config("normal",  foreground="#d4d4d4")

        # ── 底部：指令输入区 ──
        input_frame = ttk.LabelFrame(parent, text="任务指令", padding=6)
        input_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 4))
        input_frame.columnconfigure(0, weight=1)

        self.v_query = tk.StringVar()
        self.entry_query = ttk.Entry(input_frame, textvariable=self.v_query, font=("Microsoft YaHei", 11))
        self.entry_query.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        self.entry_query.bind("<Return>", lambda e: self._send_query())
        self.entry_query.configure(state="disabled")

        self.btn_send = ttk.Button(input_frame, text="发送", command=self._send_query, width=10, state="disabled")
        self.btn_send.grid(row=0, column=1)

    # ── SOP tab ───────────────────────────────────────────────────────────────

    def _build_sop_tab(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)

        # toolbar
        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 2))
        ttk.Button(toolbar, text="🔄 刷新列表", command=self._reload_sops).pack(side="left")
        ttk.Label(toolbar, text="  点击卡片填写参数并执行", foreground="gray").pack(side="left")

        # scrollable card area
        canvas = tk.Canvas(parent, highlightthickness=0)
        canvas.grid(row=1, column=0, sticky="nsew", padx=8, pady=4)
        vsb = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
        vsb.grid(row=1, column=1, sticky="ns", pady=4)
        canvas.configure(yscrollcommand=vsb.set)

        self._sop_frame = ttk.Frame(canvas)
        self._sop_frame_id = canvas.create_window((0, 0), window=self._sop_frame, anchor="nw")
        self._sop_frame.bind("<Configure>",
                             lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(self._sop_frame_id, width=e.width))
        # mouse wheel
        canvas.bind_all("<MouseWheel>",
                        lambda e: canvas.yview_scroll(-1 * (e.delta // 120), "units"))

        # SOP execution log
        log_frame = ttk.LabelFrame(parent, text="执行日志", padding=4)
        log_frame.grid(row=2, column=0, columnspan=2, sticky="ew", padx=8, pady=(4, 8))
        log_frame.columnconfigure(0, weight=1)

        self.sop_log = scrolledtext.ScrolledText(log_frame, wrap="word", height=8,
                                                 font=("Consolas", 9), state="disabled",
                                                 bg="#1e1e1e", fg="#d4d4d4")
        self.sop_log.grid(row=0, column=0, sticky="ew")
        self.sop_log.tag_config("ok",   foreground="#6a9955")
        self.sop_log.tag_config("err",  foreground="#ce9178")
        self.sop_log.tag_config("info", foreground="#9cdcfe")

        self._reload_sops()

    def _reload_sops(self):
        from sop_executor import list_sops
        for w in self._sop_frame.winfo_children():
            w.destroy()
        sops = list_sops()
        if not sops:
            ttk.Label(self._sop_frame,
                      text="sops/ 目录为空，请在其中添加 JSON 文件",
                      foreground="gray").pack(padx=12, pady=20)
            return
        for sop in sops:
            self._make_sop_card(sop)

    def _make_sop_card(self, sop: dict):
        card = ttk.LabelFrame(self._sop_frame,
                              text=sop.get("name", "未命名"),
                              padding=8)
        card.pack(fill="x", padx=6, pady=4)
        card.columnconfigure(1, weight=1)

        desc = sop.get("description", "")
        if desc:
            ttk.Label(card, text=desc, foreground="gray",
                      wraplength=500, justify="left").grid(
                row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

        param_vars = {}
        for i, p in enumerate(sop.get("params", []), start=1):
            ttk.Label(card, text=p["label"]).grid(row=i, column=0, sticky="w", padx=(0, 8))
            var = tk.StringVar()
            entry = ttk.Entry(card, textvariable=var, width=40)
            entry.grid(row=i, column=1, sticky="ew")
            if p.get("placeholder"):
                entry.insert(0, p["placeholder"])
                entry.configure(foreground="gray")

                def _on_focus_in(e, ent=entry, ph=p["placeholder"]):
                    if ent.get() == ph:
                        ent.delete(0, "end")
                        ent.configure(foreground="")

                def _on_focus_out(e, ent=entry, v=var, ph=p["placeholder"]):
                    if not v.get():
                        ent.insert(0, ph)
                        ent.configure(foreground="gray")

                entry.bind("<FocusIn>",  _on_focus_in)
                entry.bind("<FocusOut>", _on_focus_out)

            param_vars[p["name"]] = (var, p.get("placeholder", ""))

        row_btn = max(len(sop.get("params", [])) + 1, 1)
        ttk.Button(
            card, text="▶  立即执行",
            command=lambda s=sop, pv=param_vars: self._run_sop(s, pv)
        ).grid(row=row_btn, column=0, columnspan=2, pady=(8, 0))

    def _run_sop(self, sop: dict, param_vars: dict):
        params = {}
        for name, (var, placeholder) in param_vars.items():
            val = var.get().strip()
            if val == placeholder:
                val = ""
            params[name] = val

        # check required params
        missing = [p["label"] for p in sop.get("params", [])
                   if not params.get(p["name"]) and not p.get("optional")]
        if missing:
            messagebox.showwarning("缺少参数", f"请填写：{', '.join(missing)}")
            return

        self._sop_log_write(f"\n▶ 执行：{sop.get('name')}\n", "info")

        def worker():
            from sop_executor import run_sop
            try:
                run_sop(sop, params, log_fn=lambda m: self._sop_log_write(m + "\n"))
            except Exception as e:
                self._sop_log_write(f"✗ 执行失败：{e}\n", "err")

        threading.Thread(target=worker, daemon=True).start()

    def _sop_log_write(self, text: str, tag: str = "info"):
        self.sop_log.configure(state="normal")
        if "✅" in text or "完成" in text:
            tag = "ok"
        elif "✗" in text or "错误" in text or "失败" in text:
            tag = "err"
        self.sop_log.insert("end", text, tag)
        self.sop_log.see("end")
        self.sop_log.configure(state="disabled")

    # ─── 分辨率自动检测 ───────────────────────────────────────────────────────

    def _auto_detect_resolution(self):
        sw, sh = pyautogui.size()
        max_dim = 1920
        scale = min(max_dim / sw, max_dim / sh, 1.0)
        gw = int(sw * scale)
        gh = int(sh * scale)
        self.v_gw.set(str(gw))
        self.v_gh.set(str(gh))
        self.v_screen_info.set(f"（屏幕 {sw}×{sh}，自动缩放）")

    # ─── 启动 / 停止 ──────────────────────────────────────────────────────────

    def _start_agent(self):
        if self.process and self.process.poll() is None:
            return

        self.agent_ready = False
        self._log("正在启动 Agent S...\n", "info")

        env = os.environ.copy()
        env["PYTHONPATH"] = PROJECT_DIR
        env["PYTHONIOENCODING"] = "utf-8"

        cmd = [
            sys.executable, CLI_APP,
            "--provider", "openai",
            "--model", self.v_model_id.get().strip(),
            "--model_url", DEFAULT_CONFIG["model_url"],
            "--model_api_key", self.v_model_key.get().strip(),
            "--ground_provider", "open_router",
            "--ground_url", "https://openrouter.ai/api/v1",
            "--ground_api_key", self.v_ground_key.get().strip(),
            "--ground_model", DEFAULT_CONFIG["ground_model"],
            "--grounding_width", self.v_gw.get().strip(),
            "--grounding_height", self.v_gh.get().strip(),
        ]

        self.process = subprocess.Popen(
            cmd, env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True, encoding="utf-8", errors="replace",
            bufsize=1,
        )

        self.btn_start.configure(state="disabled")
        self.btn_stop.configure(state="normal")
        self.v_status.set("运行中...")

        threading.Thread(target=self._read_output, daemon=True).start()
        self.root.after(100, self._poll_output)

    def _stop_agent(self):
        if self.process:
            try:
                self.process.terminate()
            except Exception:
                pass
        self._set_stopped()

    def _set_stopped(self):
        self.btn_start.configure(state="normal")
        self.btn_stop.configure(state="disabled")
        self.btn_send.configure(state="disabled")
        self.entry_query.configure(state="disabled")
        self.v_status.set("已停止")
        self._log("\n─── Agent 已停止 ───\n", "warn")

    # ─── 输出读取 ─────────────────────────────────────────────────────────────

    def _read_output(self):
        buf = ""
        while True:
            ch = self.process.stdout.read(1)
            if not ch:
                if buf:
                    self.output_queue.put(buf)
                self.output_queue.put(None)
                break
            buf += ch
            if ch == "\n" or buf.endswith("Query: ") or buf.endswith("(y/n): "):
                self.output_queue.put(buf)
                buf = ""

    def _poll_output(self):
        try:
            while True:
                line = self.output_queue.get_nowait()
                if line is None:
                    self._set_stopped()
                    return
                self._handle_line(line)
        except queue.Empty:
            pass
        self.root.after(100, self._poll_output)

    def _handle_line(self, line: str):
        line = ANSI_ESCAPE.sub("", line)
        line_strip = line.strip()

        if line_strip.startswith("Query:"):
            if not self.agent_ready:
                self.agent_ready = True
                self._log("✅ Agent 就绪，请在下方输入任务\n", "success")
                self.btn_send.configure(state="normal")
                self.entry_query.configure(state="normal")
                self.entry_query.focus()
            return

        if "Would you like to provide another query" in line:
            self._write_stdin("y\n")
            return

        if "PLAN:" in line or "Step" in line:
            tag = "action"
        elif "ERROR" in line or "Error" in line or "Traceback" in line:
            tag = "warn"
        elif "REFLECTION" in line or "Response success" in line:
            tag = "info"
        elif "EXECUTING CODE" in line:
            tag = "query"
        else:
            tag = "normal"

        self._log(line, tag)

    # ─── 发送指令 ─────────────────────────────────────────────────────────────

    def _send_query(self):
        query = self.v_query.get().strip()
        if not query or not self.agent_ready:
            return
        self._log(f"\n▶ 指令：{query}\n", "query")
        self._write_stdin(query + "\n")
        self.v_query.set("")
        self.btn_send.configure(state="disabled")
        self.entry_query.configure(state="disabled")
        self.agent_ready = False

    def _write_stdin(self, text: str):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(text)
                self.process.stdin.flush()
            except Exception:
                pass

    # ─── 日志写入 ─────────────────────────────────────────────────────────────

    def _log(self, text: str, tag: str = "normal"):
        self.log.configure(state="normal")
        self.log.insert("end", text, tag)
        self.log.see("end")
        self.log.configure(state="disabled")

    # ─── 关闭 ─────────────────────────────────────────────────────────────────

    def _save_config(self):
        save_config({
            "model_api_key":  self.v_model_key.get().strip(),
            "model_id":       self.v_model_id.get().strip(),
            "model_url":      DEFAULT_CONFIG["model_url"],
            "ground_api_key": self.v_ground_key.get().strip(),
            "ground_model":   DEFAULT_CONFIG["ground_model"],
        })
        self.v_status.set("配置已保存 ✓")

    def _on_close(self):
        self._stop_agent()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    Launcher().run()
