import argparse
import datetime
import io
import logging
import os
import platform
import pyautogui

pyautogui.FAILSAFE = False
import signal
import sys
import time

from PIL import Image

from gui_agents.s3.agents.grounding import OSWorldACI
from gui_agents.s3.agents.agent_s import AgentS3

current_platform = platform.system().lower()

# Global flag to track pause state for debugging
paused = False


def repair_text_mojibake(text: str) -> str:
    if not isinstance(text, str):
        return text
    candidates = [text]
    for encoding in ("gbk", "gb18030", "cp936"):
        for errors in ("strict", "ignore"):
            try:
                repaired = text.encode(encoding, errors=errors).decode(
                    "utf-8", errors=errors
                )
            except UnicodeError:
                continue
            if repaired and repaired not in candidates:
                candidates.append(repaired)

    def score(value: str) -> int:
        good_chars = sum("\u4e00" <= ch <= "\u9fff" for ch in value)
        bad_markers = sum(
            value.count(marker)
            for marker in (
                "�",
                "?",
                "锟",
                "閿",
                "閹",
                "閸",
                "鍏",
                "濞",
                "瀣",
                "妞",
                "鐐",
                "鍔",
                "鍒",
                "嗕",
                "韩",
                "椋",
                "炰",
                "功",
                "浜",
                "戞",
                "枃",
                "妗",
                "鏂",
                "板",
                "缓",
                "绌",
                "櫧",
                "缁",
                "堜",
                "簬",
                "濂",
                "戒",
                "簡",
            )
        )
        return (
            good_chars * 3
            - bad_markers * 5
            + len(value.replace("?", "").replace("�", "").replace("锟", ""))
        )

    return max(candidates, key=score)


def trace_execution(message: str):
    try:
        log_dir = os.path.join(os.getcwd(), "logs")
        os.makedirs(log_dir, exist_ok=True)
        path = os.path.join(log_dir, "execution-trace.log")
        with open(path, "a", encoding="utf-8") as f:
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            f.write(f"[{timestamp}] {message}\n")
    except Exception:
        pass


def summarize_endpoint(value: str) -> str:
    if not value:
        return ""
    value = value.strip()
    if len(value) <= 80:
        return value
    return value[:60] + "..." + value[-12:]


def configure_windows_dpi_awareness():
    if platform.system() != "Windows":
        return
    try:
        import ctypes

        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
    except Exception as exc:
        logging.getLogger("desktopenv.agent").debug(
            "Could not configure Windows DPI awareness: %s", exc
        )


def get_char():
    """Get a single character from stdin without pressing Enter"""
    try:
        # Import termios and tty on Unix-like systems
        if platform.system() in ["Darwin", "Linux"]:
            import termios
            import tty

            fd = sys.stdin.fileno()
            old_settings = termios.tcgetattr(fd)
            try:
                tty.setraw(sys.stdin.fileno())
                ch = sys.stdin.read(1)
            finally:
                termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
            return ch
        else:
            # Windows fallback
            import msvcrt

            return msvcrt.getch().decode("utf-8", errors="ignore")
    except:
        return input()  # Fallback for non-terminal environments


def signal_handler(signum, frame):
    """Handle Ctrl+C signal for debugging during agent execution"""
    global paused

    if not paused:
        print("\n\n🔸 Agent-S Workflow Paused 🔸")
        print("=" * 50)
        print("Options:")
        print("  • Press Ctrl+C again to quit")
        print("  • Press Esc to resume workflow")
        print("=" * 50)

        paused = True

        while paused:
            try:
                print("\n[PAUSED] Waiting for input... ", end="", flush=True)
                char = get_char()

                if ord(char) == 3:  # Ctrl+C
                    print("\n\n🛑 Exiting Agent-S...")
                    sys.exit(0)
                elif ord(char) == 27:  # Esc
                    print("\n\n▶️  Resuming Agent-S workflow...")
                    paused = False
                    break
                else:
                    print(f"\n   Unknown command: '{char}' (ord: {ord(char)})")

            except KeyboardInterrupt:
                print("\n\n🛑 Exiting Agent-S...")
                sys.exit(0)
    else:
        # Already paused, second Ctrl+C means quit
        print("\n\n🛑 Exiting Agent-S...")
        sys.exit(0)


# Set up signal handler for Ctrl+C
signal.signal(signal.SIGINT, signal_handler)

logger = logging.getLogger()
logger.setLevel(logging.DEBUG)

datetime_str: str = datetime.datetime.now().strftime("%Y%m%d@%H%M%S")

log_dir = "logs"
os.makedirs(log_dir, exist_ok=True)

file_handler = logging.FileHandler(
    os.path.join("logs", "normal-{:}.log".format(datetime_str)), encoding="utf-8"
)
debug_handler = logging.FileHandler(
    os.path.join("logs", "debug-{:}.log".format(datetime_str)), encoding="utf-8"
)
stdout_handler = logging.StreamHandler(sys.stdout)
sdebug_handler = logging.FileHandler(
    os.path.join("logs", "sdebug-{:}.log".format(datetime_str)), encoding="utf-8"
)

file_handler.setLevel(logging.INFO)
debug_handler.setLevel(logging.DEBUG)
stdout_handler.setLevel(logging.INFO)
sdebug_handler.setLevel(logging.DEBUG)

formatter = logging.Formatter(
    fmt="\x1b[1;33m[%(asctime)s \x1b[31m%(levelname)s \x1b[32m%(module)s/%(lineno)d-%(processName)s\x1b[1;33m] \x1b[0m%(message)s"
)
file_handler.setFormatter(formatter)
debug_handler.setFormatter(formatter)
stdout_handler.setFormatter(formatter)
sdebug_handler.setFormatter(formatter)

stdout_handler.addFilter(logging.Filter("desktopenv"))
sdebug_handler.addFilter(logging.Filter("desktopenv"))

logger.addHandler(file_handler)
logger.addHandler(debug_handler)
logger.addHandler(stdout_handler)
logger.addHandler(sdebug_handler)

platform_os = platform.system()


def show_permission_dialog(code: str, action_description: str):
    """Show a platform-specific permission dialog and return True if approved."""
    if platform.system() == "Darwin":
        result = os.system(
            f'osascript -e \'display dialog "Do you want to execute this action?\n\n{code} which will try to {action_description}" with title "Action Permission" buttons {{"Cancel", "OK"}} default button "OK" cancel button "Cancel"\''
        )
        return result == 0
    elif platform.system() == "Linux":
        result = os.system(
            f'zenity --question --title="Action Permission" --text="Do you want to execute this action?\n\n{code}" --width=400 --height=200'
        )
        return result == 0
    return False


def scale_screen_dimensions(width: int, height: int, max_dim_size: int):
    scale_factor = min(max_dim_size / width, max_dim_size / height, 1)
    safe_width = int(width * scale_factor)
    safe_height = int(height * scale_factor)
    return safe_width, safe_height


def capture_desktop_screenshot():
    if platform.system() == "Windows":
        try:
            return ImageGrab.grab(all_screens=True)
        except Exception as exc:
            logger.warning(
                "All-screen capture failed, falling back to pyautogui: %s", exc
            )
    return pyautogui.screenshot()


def run_agent(
    agent, instruction: str, scaled_width: int, scaled_height: int, max_steps: int
):
def _settle_delay(exec_code: str) -> float:
    """Return UI settle delay (seconds) based on action type.

    Navigation & page-load actions need more time before the next screenshot.
    """
    code_lower = exec_code.lower()
    # App switching / opening — heavy UI transition
    if any(k in code_lower for k in ("switch_applications", "hotkey('win'", "open(")):
        return 3.0
    # Click actions that likely trigger navigation or menu expansion
    if "click" in code_lower:
        # Longer wait for clicks that open menus, dialogs, or new pages
        if any(k in code_lower for k in ("新建", "文档", "菜单", "menu", "更多", "设置",
                                           "添加", "创建", "打开", "上传", "保存")):
            return 2.5
        return 1.5
    # Drag, scroll, type — usually instant
    if any(k in code_lower for k in ("drag", "scroll", "type", "hotkey", "press")):
        return 1.0
    # Default
    return 1.5


def run_agent(agent, instruction: str, scaled_width: int, scaled_height: int, max_steps: int = 15):
    global paused
    obs = {}
    traj = "Task:\n" + instruction
    subtask_traj = ""
    for step in range(max_steps):
        # Check if we're in paused state and wait
        while paused:
            time.sleep(0.1)
        # Get screen shot using pyautogui
        screenshot = pyautogui.screenshot()
        screenshot = screenshot.resize((scaled_width, scaled_height), Image.LANCZOS)

        # Save the screenshot to a BytesIO object
        buffered = io.BytesIO()
        screenshot.save(buffered, format="PNG")

        # Get the byte value of the screenshot
        screenshot_bytes = buffered.getvalue()
        # Convert to base64 string.
        obs["screenshot"] = screenshot_bytes

        # Check again for pause state before prediction
        while paused:
            time.sleep(0.1)

        print(f"\n🔄 Step {step + 1}/{max_steps}: Getting next action from agent...")
        t_predict_start = time.time()

        # Get next action code from the agent
        info, code = agent.predict(instruction=instruction, observation=obs)

        t_predict_elapsed = time.time() - t_predict_start
        print(f"🧠 模型思考 {t_predict_elapsed:.1f}s")

        if "done" in code[0].lower() or "fail" in code[0].lower():
            if platform.system() == "Darwin":
                os.system(
                    f'osascript -e \'display dialog "Task Completed" with title "OpenACI Agent" buttons "OK" default button "OK"\''
                )
            elif platform.system() == "Linux":
                os.system(
                    f'zenity --info --title="OpenACI Agent" --text="Task Completed" --width=200 --height=100'
                )

            break

        if "next" in code[0].lower():
            continue

        if "wait" in code[0].lower():
            print("⏳ Agent requested wait...")
            time.sleep(5)
            continue

        else:
            print("EXECUTING CODE:", code[0])

            # Check for pause state before execution
            while paused:
                time.sleep(0.1)

            # Pre-exec settle: brief buffer before action
            settle_pre = 0.5 if step > 0 else 0.0
            if settle_pre > 0:
                time.sleep(settle_pre)

            # Ask for permission before executing
            exec(code[0])

            # Post-exec dynamic settle: longer for navigation-triggering actions
            settle_post = _settle_delay(code[0])
            print(f"⏳ 等待 UI 稳定 ({settle_pre + settle_post:.1f}s)...")
            time.sleep(settle_post)

            # Update task and subtask trajectories
            if "reflection" in info and "executor_plan" in info:
                traj += (
                    "\n\nReflection:\n"
                    + str(info["reflection"])
                    + "\n\n----------------------\n\nPlan:\n"
                    + info["executor_plan"]
                )


def main():
    parser = argparse.ArgumentParser(description="Run AgentS3 with specified model.")
    parser.add_argument(
        "--provider",
        type=str,
        default="openai",
        help="Specify the provider to use (e.g., openai, anthropic, etc.)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-5-2025-08-07",
        help="Specify the model to use (e.g., gpt-5-2025-08-07)",
    )
    parser.add_argument(
        "--model_url",
        type=str,
        default="",
        help="The URL of the main generation model API.",
    )
    parser.add_argument(
        "--model_api_key",
        type=str,
        default="",
        help="The API key of the main generation model.",
    )
    parser.add_argument(
        "--model_temperature",
        type=float,
        default=None,
        help="Temperature to fix the generation model at (e.g. o3 can only be run with 1.0)",
    )

    # Grounding model config: Self-hosted endpoint based (required)
    parser.add_argument(
        "--ground_provider",
        type=str,
        required=True,
        help="The provider for the grounding model",
    )
    parser.add_argument(
        "--ground_url",
        type=str,
        required=True,
        help="The URL of the grounding model",
    )
    parser.add_argument(
        "--ground_api_key",
        type=str,
        default="",
        help="The API key of the grounding model.",
    )
    parser.add_argument(
        "--ground_model",
        type=str,
        required=True,
        help="The model name for the grounding model",
    )
    parser.add_argument(
        "--grounding_width",
        type=int,
        required=True,
        help="Width of screenshot image after processor rescaling",
    )
    parser.add_argument(
        "--grounding_height",
        type=int,
        required=True,
        help="Height of screenshot image after processor rescaling",
    )
    parser.add_argument(
        "--ground_coord_scale",
        type=int,
        default=None,
        help="Coordinate range the grounding model outputs (1000 for Doubao). "
             "Only needed for models that output in normalized coords.",
    )

    # AgentS3 specific arguments
    parser.add_argument(
        "--max_trajectory_length",
        type=int,
        default=8,
        help="Maximum number of image turns to keep in trajectory",
    )
    parser.add_argument(
        "--enable_reflection",
        action="store_true",
        default=True,
        help="Enable reflection agent to assist the worker agent",
    )
    parser.add_argument(
        "--reflection_mode",
        type=str,
        default="on_failure",
        choices=["full", "reduced", "on_failure", "off"],
        help="Reflection frequency: full (every step), reduced (every other), "
             "on_failure (only after failed steps), off (disabled)",
    )
    parser.add_argument(
        "--reasoning_effort",
        type=str,
        default="medium",
        choices=["low", "medium", "high", "xhigh"],
        help="Reasoning effort for GPT/o-series models (low/medium/high/xhigh)",
    )
    parser.add_argument(
        "--budget",
        type=int,
        default=15,
        help="Maximum number of steps (default: 15)",
    )

    args = parser.parse_args()

    # Re-scales screenshot size to ensure it fits in UI-TARS context limit
    screen_width, screen_height = pyautogui.size()
    max_dim = max(args.grounding_width, args.grounding_height)
    scaled_width, scaled_height = scale_screen_dimensions(
        screen_width, screen_height, max_dim_size=max_dim
    )

    # Load the general engine params
    engine_params = {
        "engine_type": args.provider,
        "model": args.model,
        "base_url": args.model_url,
        "api_key": args.model_api_key,
        "temperature": getattr(args, "model_temperature", None),
        "reasoning_effort": args.reasoning_effort,
        "reflection_mode": args.reflection_mode,
    }

    # Load the grounding engine from a custom endpoint
    engine_params_for_grounding = {
        "engine_type": args.ground_provider,
        "model": args.ground_model,
        "base_url": args.ground_url,
        "api_key": args.ground_api_key,
        "grounding_width": args.grounding_width,
        "grounding_height": args.grounding_height,
    }
    if args.ground_coord_scale is not None:
        engine_params_for_grounding["ground_coord_scale"] = args.ground_coord_scale

    grounding_agent = OSWorldACI(
        platform=current_platform,
        engine_params_for_generation=engine_params,
        engine_params_for_grounding=engine_params_for_grounding,
        width=screen_width,
        height=screen_height,
    )

    agent = AgentS3(
        engine_params,
        grounding_agent,
        platform=current_platform,
        max_trajectory_length=args.max_trajectory_length,
        enable_reflection=args.enable_reflection,
    )

    while True:
        query = input("Query: ")

        agent.reset()

        # Run the agent on your own device
        run_agent(agent, query, scaled_width, scaled_height, args.budget)

        response = input("Would you like to provide another query? (y/n): ")
        if response.lower() != "y":
            break


if __name__ == "__main__":
    main()
