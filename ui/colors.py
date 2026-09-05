import sys
import re
import os

# ANSI escape sequence remover
ANSI_ESCAPE_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')

class Colors:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Standard / Bright palette
    RED = "\033[91m"
    GREEN = "\033[92m"
    BLUE = "\033[94m"
    YELLOW = "\033[93m"
    PURPLE = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"

    # Blood & Devil gradients (256-color with standard ANSI fallback)
    BLOOD_BRIGHT = "\033[38;5;196m"
    BLOOD_CRIMSON = "\033[38;5;160m"
    BLOOD_MAROON = "\033[38;5;124m"
    BLOOD_DARK = "\033[38;5;88m"
    BLOOD_DRIP = "\033[38;5;52m"

USER_COLOR_MAP = {
    "Red": Colors.RED,
    "Green": Colors.GREEN,
    "Blue": Colors.BLUE,
    "Yellow": Colors.YELLOW,
    "Purple": Colors.PURPLE,
    "Cyan": Colors.CYAN,
    "White": Colors.WHITE,
}

CHOOSABLE_COLORS = ["Red", "Green", "Blue", "Yellow", "Purple", "Cyan", "White"]

def enable_windows_ansi():
    """Enables ANSI Virtual Terminal Processing on Windows 10/11."""
    if sys.platform == "win32":
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # STD_OUTPUT_HANDLE = -11
            handle = kernel32.GetStdHandle(-11)
            mode = ctypes.c_ulong()
            kernel32.GetConsoleMode(handle, ctypes.byref(mode))
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
        except Exception:
            pass

        try:
            import colorama
            colorama.init()
        except Exception:
            pass

        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stdin.reconfigure(encoding='utf-8')
        except Exception:
            pass

def strip_ansi(text: str) -> str:
    """Removes all ANSI escape sequences from a string."""
    return ANSI_ESCAPE_RE.sub('', text)

def visible_len(text: str) -> int:
    """Returns the visible width of a string ignoring ANSI codes."""
    return len(strip_ansi(text))

def colorize(text: str, color_name: str, bold: bool = False) -> str:
    """Applies ANSI color and optional bolding to text."""
    code = USER_COLOR_MAP.get(color_name, Colors.WHITE)
    prefix = f"{Colors.BOLD}{code}" if bold else code
    return f"{prefix}{text}{Colors.RESET}"
