import os
import sys
import time
import queue
from typing import Optional, List, Dict, Any, Callable
from .colors import Colors, CHOOSABLE_COLORS, colorize, visible_len
from .ascii_art import print_devil_header, center_line, get_divider, get_terminal_width
from i18n import t

def clear_screen():
    """Clears the console screen."""
    os.system("cls" if os.name == "nt" else "clear")

def render_screen_header(subtitle: str = ""):
    """Clears screen and prints the dynamically centered DEVIL CHAT banner."""
    clear_screen()
    print_devil_header(subtitle if subtitle else t("app_subtitle"))

class ChatUI:
    """
    Terminal UI manager for the live interactive chat session.
    Provides non-blocking live output while the user is typing, preventing
    incoming messages from colliding with the prompt.
    """
    def __init__(self, username: str, color_name: str, get_members_fn: Callable):
        self.username = username
        self.color_name = color_name
        self.get_members_fn = get_members_fn
        self.msg_queue = queue.Queue()
        self.is_active = True
        self.in_confirmation = False
        self.confirmation_callback: Optional[Callable] = None

    def format_user_prompt(self) -> str:
        """Returns the colored prompt: [Username]: """
        colored_user = colorize(self.username, self.color_name, bold=True)
        return f"{Colors.DIM}[{Colors.RESET}{colored_user}{Colors.DIM}]{Colors.RESET}: "

    def format_chat_message(self, sender: str, color: str, text: str) -> str:
        """Formats incoming chat message: [Sender]: text"""
        colored_sender = colorize(sender, color, bold=True)
        return f"{Colors.DIM}[{Colors.RESET}{colored_sender}{Colors.DIM}]{Colors.RESET}: {text}"

    def format_system_message(self, text: str) -> str:
        """Formats system notification: * text"""
        return f"{Colors.BLOOD_CRIMSON}* {text}{Colors.RESET}"

    def queue_message(self, formatted_text: str):
        """Adds a message to be rendered on screen."""
        self.msg_queue.put(formatted_text)

    def draw_chat_header(self, current_count: int, max_count: int, admin_name: str):
        """Renders the top chat banner and status bar."""
        render_screen_header()
        status = t("members_header", current=current_count, max=max_count, admin=admin_name)
        status_styled = f"{Colors.BOLD}{Colors.YELLOW}{status}{Colors.RESET}"
        print(center_line(status_styled))
        hint = f"{Colors.DIM}{t('chat_help_hint')}{Colors.RESET}"
        print(center_line(hint))
        print(get_divider())

    def run_input_loop(self, on_input_submitted: Callable[[str], None]):
        """
        Windows-optimized interactive keyboard loop.
        Allows typing without getting corrupted by background incoming messages.
        """
        prompt = self.format_user_prompt()
        line_buffer: List[str] = []

        # Initial prompt render
        sys.stdout.write(prompt)
        sys.stdout.flush()

        use_msvcrt = (sys.platform == "win32" and sys.stdin.isatty())
        if use_msvcrt:
            import msvcrt

        while self.is_active:
            # 1. Flush any pending incoming messages to display
            while not self.msg_queue.empty():
                try:
                    msg = self.msg_queue.get_nowait()
                    # Clear current line
                    sys.stdout.write('\r\033[K')
                    sys.stdout.write(msg + '\n')
                    # Redraw prompt and buffer
                    sys.stdout.write(prompt + ''.join(line_buffer))
                    sys.stdout.flush()
                except queue.Empty:
                    break

            # 2. Check for keyboard input
            if use_msvcrt:
                if msvcrt.kbhit():
                    ch = msvcrt.getwch()
                    # Handle Windows extended keys (arrow keys, function keys)
                    if ch in ('\x00', '\xe0'):
                        if msvcrt.kbhit():
                            msvcrt.getwch()
                        continue

                    if ch in ('\r', '\n'):
                        text = ''.join(line_buffer).strip()
                        line_buffer.clear()
                        sys.stdout.write('\r\033[K')
                        sys.stdout.flush()
                        if text:
                            on_input_submitted(text)
                        # Re-display prompt if still active
                        if self.is_active:
                            sys.stdout.write(prompt)
                            sys.stdout.flush()
                    elif ch == '\x08':  # Backspace
                        if line_buffer:
                            line_buffer.pop()
                            sys.stdout.write('\b \b')
                            sys.stdout.flush()
                    elif ch == '\x03':  # Ctrl+C
                        line_buffer.clear()
                        sys.stdout.write('\r\033[K')
                        sys.stdout.flush()
                        on_input_submitted("/sair")
                        if self.is_active:
                            sys.stdout.write(prompt)
                            sys.stdout.flush()
                    elif ch >= ' ':
                        line_buffer.append(ch)
                        sys.stdout.write(ch)
                        sys.stdout.flush()
                else:
                    time.sleep(0.015)
            else:
                # Fallback standard line input (when stdin is piped or not a TTY)
                try:
                    line = sys.stdin.readline()
                    if not line:
                        on_input_submitted("/sair")
                        break
                    text = line.strip()
                    if text:
                        on_input_submitted(text)
                    if self.is_active:
                        sys.stdout.write(prompt)
                        sys.stdout.flush()
                except (EOFError, KeyboardInterrupt):
                    on_input_submitted("/sair")
                    break

    def stop(self):
        """Stops the UI input loop."""
        self.is_active = False
