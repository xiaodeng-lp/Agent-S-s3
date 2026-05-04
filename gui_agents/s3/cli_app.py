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
import traceback

from PIL import Image, ImageGrab

from gui_agents.s3.agents.grounding_feishu import WindowsFeishuACI as OSWorldACI
from gui_agents.s3.agents.agent_s import AgentS3

current_platform = platform.system().lower()

try:
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

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
    global paused
    obs = {}
    traj = "Task:\n" + instruction
    subtask_traj = ""
    for step in range(max_steps):
        # Check if we're in paused state and wait
        while paused:
            time.sleep(0.1)
        # Get screen shot. On Windows, capture the full virtual desktop so
        # applications on secondary monitors are visible to the visual model.
        screenshot = capture_desktop_screenshot()
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

        # Get next action code from the agent
        info, code = agent.predict(instruction=instruction, observation=obs)
        exec_code = code[0] if code else ""
        trace_execution(f"STEP {step + 1} CODE:\n{exec_code}\n---")
        normalized_code = exec_code.strip().lower()

        if normalized_code in {"done", "agent.done()", "fail", "agent.fail()"}:
            if platform.system() == "Darwin":
                os.system(
                    f'osascript -e \'display dialog "Task Completed" with title "OpenACI Agent" buttons "OK" default button "OK"\''
                )
            elif platform.system() == "Linux":
                os.system(
                    f'zenity --info --title="OpenACI Agent" --text="Task Completed" --width=200 --height=100'
                )

            break

        if normalized_code in {"next", "agent.next()"}:
            continue

        if normalized_code == "wait" or normalized_code.startswith("agent.wait("):
            print("⏳ Agent requested wait...")
            time.sleep(5)
            continue

        else:
            time.sleep(1.0)
            print("EXECUTING CODE:", exec_code, flush=True)

            # Check for pause state before execution
            while paused:
                time.sleep(0.1)

            # Ask for permission before executing
            try:
                exec(exec_code)
            except Exception as exc:
                tb = traceback.format_exc()
                print("EXEC_CODE_ERROR:", repr(exc), flush=True)
                trace_execution(f"EXEC_CODE_ERROR: {exc!r}\n{tb}")
                logger.exception("Error executing generated code")
                continue
            time.sleep(1.0)

            # Update task and subtask trajectories
            if "reflection" in info and "executor_plan" in info:
                traj += (
                    "\n\nReflection:\n"
                    + str(info["reflection"])
                    + "\n\n----------------------\n\nPlan:\n"
                    + info["executor_plan"]
                )


def main():
    configure_windows_dpi_awareness()

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
        "--budget",
        type=int,
        default=25,
        help="Maximum number of steps (default: 25)",
    )

    args = parser.parse_args()

    # Re-scales screenshot size to ensure it fits in UI-TARS context limit.
    # Use the actual captured image size because Windows multi-monitor setups
    # can place the target app outside pyautogui.size()'s primary-screen area.
    initial_screenshot = capture_desktop_screenshot()
    screen_width, screen_height = initial_screenshot.size
    max_dim = max(args.grounding_width, args.grounding_height)
    scaled_width, scaled_height = scale_screen_dimensions(
        screen_width, screen_height, max_dim_size=max_dim
    )
    trace_execution(
        "SCREEN_INIT: "
        + repr(
            {
                "captured_size": (screen_width, screen_height),
                "scaled_size": (scaled_width, scaled_height),
                "arg_grounding_size": (args.grounding_width, args.grounding_height),
                "platform": platform.system(),
            }
        )
    )
    print(
        "SCREEN_INIT:",
        {
            "captured_size": (screen_width, screen_height),
            "scaled_size": (scaled_width, scaled_height),
            "arg_grounding_size": (args.grounding_width, args.grounding_height),
            "platform": platform.system(),
        },
        flush=True,
    )

    # Load the general engine params
    engine_params = {
        "engine_type": args.provider,
        "model": args.model,
        "base_url": args.model_url,
        "api_key": args.model_api_key,
        "temperature": getattr(args, "model_temperature", None),
    }

    # Load the grounding engine from a custom endpoint
    engine_params_for_grounding = {
        "engine_type": args.ground_provider,
        "model": args.ground_model,
        "base_url": args.ground_url,
        "api_key": args.ground_api_key,
        "grounding_width": scaled_width,
        "grounding_height": scaled_height,
    }
    trace_execution(
        "MODEL_INTERFACE_INIT: "
        + repr(
            {
                "main_provider": args.provider,
                "main_model": args.model,
                "main_url": summarize_endpoint(args.model_url),
                "ground_provider": args.ground_provider,
                "ground_model": args.ground_model,
                "ground_url": summarize_endpoint(args.ground_url),
                "same_model": args.model == args.ground_model,
                "same_url": args.model_url.rstrip("/") == args.ground_url.rstrip("/"),
                "requested_grounding_size": (
                    args.grounding_width,
                    args.grounding_height,
                ),
                "actual_grounding_size": (scaled_width, scaled_height),
                "captured_screen_size": (screen_width, screen_height),
            }
        )
    )

    grounding_agent = OSWorldACI(
        platform=current_platform,
        engine_params_for_generation=engine_params,
        engine_params_for_grounding=engine_params_for_grounding,
        width=screen_width,
        height=screen_height,
        code_agent_budget=args.budget,
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
        repaired_query = repair_text_mojibake(query)
        if repaired_query != query:
            trace_execution(f"QUERY_REPAIRED: {query!r} => {repaired_query!r}")
            query = repaired_query

        agent.reset()

        # Run the agent on your own device
        run_agent(agent, query, scaled_width, scaled_height, args.budget)

        response = input("Would you like to provide another query? (y/n): ")
        if response.lower() != "y":
            break


if __name__ == "__main__":
    main()
