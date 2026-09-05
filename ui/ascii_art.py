import shutil
from .colors import Colors, visible_len

# Full-width single-line DEVIL CHAT block banner (70 chars wide)
WIDE_BANNER = [
    (Colors.BLOOD_BRIGHT,  "         ▲                                                               ▲"),
    (Colors.BLOOD_BRIGHT,  "       )▓▓▓(                                                           )▓▓▓("),
    (Colors.BLOOD_BRIGHT,  "      )▓▓▓▓▓(                                                         )▓▓▓▓▓("),
    (Colors.BLOOD_BRIGHT,  "██████╗ ███████╗██╗   ██╗██╗██╗         ██████╗██╗  ██╗ █████╗ ████████╗"),
    (Colors.BLOOD_CRIMSON, "██╔══██╗██╔════╝██║   ██║██║██║        ██╔════╝██║  ██║██╔══██╗╚══██╔══╝"),
    (Colors.BLOOD_CRIMSON, "██║  ██║█████╗  ██║   ██║██║██║        ██║     ███████║███████║   ██║   "),
    (Colors.BLOOD_CRIMSON, "██║  ██║██╔══╝  ╚██╗ ██╔╝██║██║        ██║     ██╔══██║██╔══██║   ██║   "),
    (Colors.BLOOD_MAROON,  "██████╔╝███████╗ ╚████╔╝ ██║███████╗   ╚██████╗██║  ██║██║  ██║   ██║   "),
    (Colors.BLOOD_MAROON,  "╚═════╝ ╚══════╝  ╚═══╝  ╚═╝╚══════╝    ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   "),
    (Colors.BLOOD_DARK,    "   :   :   v    :   :   :     :   :       :   :   v   :   :   :       v   :"),
    (Colors.BLOOD_DRIP,    "   '   .        '   .   '     .   '       '   .       '   .   '           .")
]

# Compact stacked 2-tier banner for narrower terminals (<74 columns)
STACKED_DEVIL = [
    (Colors.BLOOD_BRIGHT,  "  ▲                               ▲"),
    (Colors.BLOOD_BRIGHT,  "██████╗ ███████╗██╗   ██╗██╗██╗     "),
    (Colors.BLOOD_CRIMSON, "██╔══██╗██╔════╝██║   ██║██║██║     "),
    (Colors.BLOOD_CRIMSON, "██║  ██║█████╗  ██║   ██║██║██║     "),
    (Colors.BLOOD_CRIMSON, "██║  ██║██╔══╝  ╚██╗ ██╔╝██║██║     "),
    (Colors.BLOOD_MAROON,  "██████╔╝███████╗ ╚████╔╝ ██║███████╗"),
    (Colors.BLOOD_MAROON,  "╚═════╝ ╚══════╝  ╚═══╝  ╚═╝╚══════╝"),
    (Colors.BLOOD_DARK,    "   :   :   v    :   :   :     :   : "),
]

STACKED_CHAT = [
    (Colors.BLOOD_BRIGHT,  " ██████╗██╗  ██╗ █████╗ ████████╗"),
    (Colors.BLOOD_CRIMSON, "██╔════╝██║  ██║██╔══██╗╚══██╔══╝"),
    (Colors.BLOOD_CRIMSON, "██║     ███████║███████║   ██║   "),
    (Colors.BLOOD_CRIMSON, "██║     ██╔══██║██╔══██║   ██║   "),
    (Colors.BLOOD_MAROON,  "╚██████╗██║  ██║██║  ██║   ██║   "),
    (Colors.BLOOD_MAROON,  " ╚═════╝╚═╝  ╚═╝╚═╝  ╚═╝   ╚═╝   "),
    (Colors.BLOOD_DARK,    "   :   :   v   :   :   :       v   :"),
    (Colors.BLOOD_DRIP,    "   '   .       '   .   '           ."),
]

def get_terminal_width() -> int:
    """Returns current terminal column width, minimum 40."""
    try:
        cols = shutil.get_terminal_size((80, 24)).columns
        return max(40, cols)
    except Exception:
        return 80

def center_line(text: str, cols: int = None) -> str:
    """Centers a string (stripping ANSI length) within terminal columns."""
    if cols is None:
        cols = get_terminal_width()
    v_len = visible_len(text)
    pad = max(0, (cols - v_len) // 2)
    return (" " * pad) + text

def print_devil_header(subtitle: str = ""):
    """
    Renders the DEVIL CHAT ASCII banner dynamically centered at the top.
    Includes blood dripping accents and subtitle.
    """
    cols = get_terminal_width()

    # Determine whether to use wide or stacked layout
    if cols >= 74:
        banner = WIDE_BANNER
    else:
        banner = STACKED_DEVIL + [(Colors.RESET, "")] + STACKED_CHAT

    for color_code, line in banner:
        v_len = visible_len(line)
        pad = max(0, (cols - v_len) // 2)
        print((" " * pad) + f"{Colors.BOLD}{color_code}{line}{Colors.RESET}")

    if subtitle:
        sub_text = f"{Colors.DIM}{Colors.WHITE}{subtitle}{Colors.RESET}"
        print(center_line(sub_text, cols))
    print()

def get_divider(char: str = "─", color: str = Colors.BLOOD_DARK) -> str:
    """Returns a full-width horizontal divider line."""
    cols = get_terminal_width()
    return f"{color}{char * cols}{Colors.RESET}"
