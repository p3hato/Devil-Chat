import sys
import os
import time
from typing import Optional, List, Dict, Any

# Ensure project root is in sys.path
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from ui import (
    Colors,
    CHOOSABLE_COLORS,
    colorize,
    enable_windows_ansi,
    print_devil_header,
    center_line,
    get_divider,
    get_terminal_width,
    clear_screen,
    render_screen_header,
    ChatUI
)
from core import (
    UserSession,
    validate_username,
    get_local_ip,
    parse_address,
    RoomHost,
    PeerClient,
    load_config,
    save_config,
    create_room_code,
    parse_room_code,
    is_room_code,
    get_public_ip,
    UPnPManager
)
from i18n import (
    t,
    set_language,
    get_language,
    get_language_name,
    SUPPORTED_LANGUAGES
)

def prompt_color_selection(current_color: str = "Red") -> str:
    """Renders color selection menu and returns chosen color name."""
    cols = get_terminal_width()
    print(center_line(f"{Colors.BOLD}{t('choose_color')}{Colors.RESET}"))
    print()
    for idx, cname in enumerate(CHOOSABLE_COLORS, 1):
        sample = colorize(f"  {idx}. {cname}", cname, bold=True)
        print(center_line(sample))
    print()

    while True:
        try:
            choice_str = input(center_line(t("color_prompt", max=len(CHOOSABLE_COLORS)))).strip()
            if not choice_str:
                return current_color
            idx = int(choice_str)
            if 1 <= idx <= len(CHOOSABLE_COLORS):
                return CHOOSABLE_COLORS[idx - 1]
        except (ValueError, EOFError):
            pass
        print(center_line(f"{Colors.RED}{t('invalid_option')}{Colors.RESET}"))

def prompt_username(default_name: str = "") -> str:
    """Prompts and validates a temporary username."""
    while True:
        prompt_text = t("enter_username")
        if default_name:
            prompt_text += f"[{default_name}]: "
        try:
            name = input(center_line(prompt_text)).strip()
            if not name and default_name:
                name = default_name
            valid, err_key = validate_username(name)
            if valid:
                return name
            print(center_line(f"{Colors.RED}{t(err_key)}{Colors.RESET}"))
        except (EOFError, KeyboardInterrupt):
            return "User"

def run_chat_session(
    session: UserSession,
    host: Optional[RoomHost] = None,
    peer: Optional[PeerClient] = None,
    initial_admin: str = "",
    max_members: int = 10
):
    """
    Main interactive chat screen controller.
    Used seamlessly by both Host and Peer participants.
    """
    admin_name = [initial_admin]
    members_count = [1]
    is_session_alive = [True]
    is_voting_active = [False]
    pending_confirm_leave = [False]

    def get_members():
        if host:
            with host._lock:
                return [m.to_dict() for m in host.members.values()]
        elif peer:
            return peer.members
        return []

    ui = ChatUI(session.username, session.color, get_members)

    # Handlers for events
    def handle_message(sender: str, color: str, text: str):
        formatted = ui.format_chat_message(sender, color, text)
        ui.queue_message(formatted)

    def handle_system(key: str, **kwargs):
        # Translate system notification
        text = t(key, **kwargs)
        formatted = ui.format_system_message(text)
        ui.queue_message(formatted)

    def handle_members_update(members_list: List[Dict[str, Any]], max_m: int, admin: str):
        members_count[0] = len(members_list)
        admin_name[0] = admin
        if session.username == admin:
            session.is_admin = True

    def handle_vote_start(initiator: str):
        is_voting_active[0] = True
        ui.queue_message(ui.format_system_message(t("system_vote_started", username=initiator)))
        ui.queue_message(f"{Colors.BOLD}{Colors.YELLOW}{t('vote_question')}{Colors.RESET}")

    def handle_vote_result(approved: bool):
        is_voting_active[0] = False
        if approved:
            ui.queue_message(ui.format_system_message(t("system_chat_closed_vote")))
            time.sleep(1.0)
            is_session_alive[0] = False
            ui.stop()
        else:
            ui.queue_message(ui.format_system_message(t("system_vote_failed")))

    def handle_room_close():
        ui.queue_message(ui.format_system_message(t("system_room_closed")))
        time.sleep(1.0)
        is_session_alive[0] = False
        ui.stop()

    def handle_disconnect():
        ui.queue_message(ui.format_system_message(t("connection_failed")))
        time.sleep(1.0)
        is_session_alive[0] = False
        ui.stop()

    # Hook callbacks
    if host:
        host.on_message_cb = handle_message
        host.on_system_cb = handle_system
        host.on_members_update_cb = handle_members_update
        host.on_vote_start_cb = handle_vote_start
        host.on_vote_result_cb = handle_vote_result
        host.on_room_close_cb = handle_room_close
        members_count[0] = len(host.members)
    elif peer:
        peer.on_message_cb = handle_message
        peer.on_system_cb = handle_system
        peer.on_members_update_cb = handle_members_update
        peer.on_vote_start_cb = handle_vote_start
        peer.on_vote_result_cb = handle_vote_result
        peer.on_room_close_cb = handle_room_close
        peer.on_disconnect_cb = handle_disconnect
        members_count[0] = len(peer.members)

    # Draw initial header
    ui.draw_chat_header(members_count[0], max_members, admin_name[0])

    def on_input_submitted(raw_input: str):
        cmd = raw_input.strip()
        if not cmd:
            return

        # Handle leave confirmation
        if pending_confirm_leave[0]:
            choice = cmd.upper()
            if choice == "Y" or choice == "S" or choice == "O":  # Y / Sim / Oui
                ui.queue_message(ui.format_system_message(t("leaving_chat")))
                is_session_alive[0] = False
                if host:
                    host.close()
                elif peer:
                    peer.leave()
                ui.stop()
            else:
                pending_confirm_leave[0] = False
                ui.queue_message(f"{Colors.DIM}* Resumed chat.{Colors.RESET}")
            return

        # Check for commands
        lower_cmd = cmd.lower()
        if lower_cmd in ("/sair", "/leave", "/exit"):
            pending_confirm_leave[0] = True
            ui.queue_message(f"{Colors.BOLD}{Colors.YELLOW}{t('leave_confirm_prompt')}{Colors.RESET}")
            return

        elif lower_cmd in ("/encerrar", "/close"):
            if not session.is_admin:
                ui.queue_message(ui.format_system_message(t("only_admin_can_close")))
                return
            if host:
                host.start_close_vote(session.username)
            elif peer:
                peer.start_close_vote()
            return

        elif lower_cmd == "/clear":
            ui.draw_chat_header(members_count[0], max_members, admin_name[0])
            return

        elif lower_cmd == "/help":
            ui.queue_message(f"{Colors.BOLD}{Colors.RED}{t('cmd_help_title')}{Colors.RESET}")
            ui.queue_message(f"{Colors.WHITE}{t('cmd_help_desc')}{Colors.RESET}")
            ui.queue_message(f"{Colors.WHITE}{t('cmd_members_desc')}{Colors.RESET}")
            ui.queue_message(f"{Colors.WHITE}{t('cmd_clear_desc')}{Colors.RESET}")
            ui.queue_message(f"{Colors.WHITE}{t('cmd_sair_desc')}{Colors.RESET}")
            ui.queue_message(f"{Colors.WHITE}{t('cmd_encerrar_desc')}{Colors.RESET}")
            ui.queue_message(f"{Colors.WHITE}{t('cmd_vote_desc')}{Colors.RESET}")
            ui.queue_message(get_divider())
            return

        elif lower_cmd == "/members":
            members_list = get_members()
            ui.queue_message(f"{Colors.BOLD}{Colors.YELLOW}{t('cmd_members_list', count=len(members_list), max=max_members)}{Colors.RESET}")
            for m in members_list:
                uname = m.get("username", "")
                uid = m.get("id", "")
                is_adm = m.get("is_admin", False)
                adm_tag = t("cmd_admin_tag") if is_adm else ""
                colored_m = colorize(uname, m.get("color", "White"), bold=True)
                item = t("cmd_member_item", username=colored_m, id=uid, admin_tag=f"{Colors.RED}{adm_tag}{Colors.RESET}")
                ui.queue_message(item)
            ui.queue_message(get_divider())
            return

        elif lower_cmd.startswith("/vote ") or (is_voting_active[0] and lower_cmd in ("y", "n", "s")):
            choice = "Y" if (" y" in lower_cmd or lower_cmd in ("y", "s")) else "N"
            if host:
                success = host.record_vote(session.username, choice)
            elif peer:
                success = peer.cast_vote(choice)
            if success:
                ui.queue_message(ui.format_system_message(t("vote_cast", choice=choice)))
            else:
                ui.queue_message(ui.format_system_message(t("already_voted")))
            return

        # Normal chat message
        if host:
            host.send_local_message(cmd)
        elif peer:
            peer.send_message(cmd)
            # Display locally for peer
            ui.queue_message(ui.format_chat_message(session.username, session.color, cmd))

    # Run the interactive non-blocking loop
    ui.run_input_loop(on_input_submitted)

    # Session ended: wipe memory
    if host:
        host.close()
    if peer:
        peer.leave()

def create_chat_flow(session: UserSession, config: Dict[str, Any]):
    """Flow for creating a private chat room (Host)."""
    render_screen_header(t("create_title"))

    # 1. Username
    username = prompt_username(session.username)
    session.username = username

    # 2. Color
    color = prompt_color_selection(session.color)
    session.color = color

    # 3. Member Limit
    render_screen_header(t("create_title"))
    limit = 10
    while True:
        try:
            limit_str = input(center_line(t("member_limit_prompt"))).strip()
            if not limit_str:
                limit = 10
                break
            val = int(limit_str)
            if 2 <= val <= 20:
                limit = val
                break
            print(center_line(f"{Colors.RED}{t('member_limit_invalid')}{Colors.RESET}"))
        except (ValueError, EOFError):
            print(center_line(f"{Colors.RED}{t('member_limit_invalid')}{Colors.RESET}"))

    # 4. Optional Passphrase
    try:
        passphrase = input(center_line(t("optional_key_prompt"))).strip()
    except (EOFError, KeyboardInterrupt):
        passphrase = ""

    # 5. Start Host
    port = 54321
    host = RoomHost(
        host_user=session,
        port=port,
        max_members=limit,
        passphrase=passphrase
    )
    success, err = host.start()
    if not success:
        # If port 54321 occupied, attempt fallback port
        port = 54322
        host.port = port
        success, err = host.start()
        if not success:
            print(center_line(f"{Colors.RED}Failed to bind host port: {err}{Colors.RESET}"))
            input(center_line(t("press_enter")))
            return

    local_ip = get_local_ip()

    render_screen_header(t("create_title"))
    print(center_line(f"{Colors.DIM}{t('resolving_network')}{Colors.RESET}"))

    # Discover Public IP (for peers in other countries)
    public_ip = get_public_ip(timeout=2.0)
    best_ip = public_ip if public_ip else local_ip

    # Generate Room Code (Dual-Endpoint: Public IP + Local IP for seamless home/LAN and global use)
    room_code = create_room_code(best_ip, local_ip, port, passphrase)

    # Attempt UPnP automatic router port forwarding
    upnp = UPnPManager()
    upnp_success = upnp.forward_port(local_ip, port, "DEVIL CHAT")

    render_screen_header(t("create_title"))
    print(center_line(f"{Colors.BOLD}{Colors.GREEN}{t('host_started')}{Colors.RESET}"))
    print()
    print(center_line(f"{Colors.BOLD}{Colors.YELLOW}{t('room_code_label')}{Colors.RESET}"))
    print(center_line(f"{Colors.BOLD}{Colors.BLOOD_BRIGHT}  >>> {room_code} <<<  {Colors.RESET}"))
    print()
    if public_ip:
        print(center_line(f"{Colors.DIM}Public Internet: {public_ip}:{port} | Local LAN: {local_ip}:{port}{Colors.RESET}"))
    else:
        print(center_line(f"{Colors.DIM}Local Address: {local_ip}:{port}{Colors.RESET}"))

    if upnp_success:
        print(center_line(f"{Colors.GREEN}{t('upnp_success', port=port)}{Colors.RESET}"))
    else:
        print(center_line(f"{Colors.DIM}{t('public_address_note', port=port)}{Colors.RESET}"))

    print(center_line(f"{Colors.DIM}{t('p2p_warning')}{Colors.RESET}"))
    print()
    print(center_line(f"{Colors.BOLD}{Colors.RED}{t('host_is_admin')}{Colors.RESET}"))
    print()
    input(center_line(t("press_enter_continue")))

    # Enter chat
    run_chat_session(
        session=session,
        host=host,
        initial_admin=session.username,
        max_members=limit
    )

    # Clean up UPnP on exit
    if upnp_success:
        upnp.release_port(port)

def join_chat_flow(session: UserSession, config: Dict[str, Any]):
    """Flow for joining an existing private chat room (Peer)."""
    render_screen_header(t("join_title"))

    # 1. Host Address or Room Code
    host_ip = None
    host_port = None
    embedded_passphrase = ""

    while not host_ip:
        try:
            entry_str = input(center_line(t("enter_host_or_code"))).strip()
            if not entry_str:
                return

            if is_room_code(entry_str):
                parsed = parse_room_code(entry_str)
                if parsed:
                    host_ip, host_port, embedded_passphrase = parsed
                else:
                    print(center_line(f"{Colors.RED}{t('invalid_code_or_address')}{Colors.RESET}"))
            else:
                addr_tuple = parse_address(entry_str)
                if addr_tuple:
                    host_ip, host_port = addr_tuple
                else:
                    print(center_line(f"{Colors.RED}{t('invalid_code_or_address')}{Colors.RESET}"))
        except (EOFError, KeyboardInterrupt):
            return

    # 2. Username
    username = prompt_username(session.username)
    session.username = username

    # 3. Color
    color = prompt_color_selection(session.color)
    session.color = color

    # 4. Passphrase
    if embedded_passphrase:
        passphrase = embedded_passphrase
    else:
        try:
            passphrase = input(center_line(t("enter_passphrase"))).strip()
        except (EOFError, KeyboardInterrupt):
            passphrase = ""

    render_screen_header(t("join_title"))
    display_addr = host_ip if isinstance(host_ip, str) else host_ip[0]
    print(center_line(f"{Colors.DIM}{t('connecting_to_host', ip=display_addr, port=host_port)}{Colors.RESET}"))

    peer = PeerClient(
        user_session=session,
        host_ip=host_ip,
        host_port=host_port,
        passphrase=passphrase
    )

    success, err_key = peer.connect()
    if not success:
        print()
        print(center_line(f"{Colors.RED}{t(err_key, current='?', max='?', username=session.username, reason=err_key)}{Colors.RESET}"))
        print()
        input(center_line(t("press_enter")))
        return

    # Enter chat
    run_chat_session(
        session=session,
        peer=peer,
        initial_admin=peer.admin_username,
        max_members=peer.max_members
    )

def settings_flow(session: UserSession, config: Dict[str, Any]):
    """Settings menu flow."""
    while True:
        render_screen_header(t("settings_title"))
        current_lang_name = get_language_name()
        print(center_line(t("settings_lang", current=current_lang_name)))
        print(center_line(t("settings_username", current=session.username or "None")))
        print(center_line(t("settings_color", current=session.color)))
        print(center_line(t("settings_clear")))
        print(center_line(t("settings_back")))
        print()

        try:
            choice = input(center_line(t("menu_prompt"))).strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "1":
            # Language picker
            render_screen_header(t("select_language"))
            lang_codes = list(SUPPORTED_LANGUAGES.keys())
            for idx, code in enumerate(lang_codes, 1):
                name = SUPPORTED_LANGUAGES[code]
                print(center_line(f"{idx}. {name} ({code.upper()})"))
            print()
            try:
                lchoice = input(center_line(t("color_prompt", max=len(lang_codes)))).strip()
                if lchoice:
                    lidx = int(lchoice)
                    if 1 <= lidx <= len(lang_codes):
                        new_code = lang_codes[lidx - 1]
                        set_language(new_code)
                        config["language"] = new_code
                        save_config(config)
                        print(center_line(f"{Colors.GREEN}{t('lang_changed')}{Colors.RESET}"))
                        time.sleep(0.8)
            except Exception:
                pass

        elif choice == "2":
            # Default username
            render_screen_header(t("settings_title"))
            uname = prompt_username(session.username)
            session.username = uname
            config["default_username"] = uname
            save_config(config)
            print(center_line(f"{Colors.GREEN}{t('username_saved')}{Colors.RESET}"))
            time.sleep(0.8)

        elif choice == "3":
            # Default color
            render_screen_header(t("settings_title"))
            color = prompt_color_selection(session.color)
            session.color = color
            config["default_color"] = color
            save_config(config)
            print(center_line(f"{Colors.GREEN}{t('color_saved')}{Colors.RESET}"))
            time.sleep(0.8)

        elif choice == "4":
            clear_screen()

        elif choice == "5":
            break

def main():
    """Application entry point."""
    enable_windows_ansi()

    # Load non-identifying local preferences
    config = load_config()
    # First run automatically defaults to English ('en') without prompt
    set_language(config.get("language", "en"))

    # Create temporary in-memory session (fresh random ID every run)
    session = UserSession(
        username=config.get("default_username", ""),
        color=config.get("default_color", "Red")
    )

    while True:
        render_screen_header()

        # Display menu options
        print(center_line(f"{Colors.BOLD}{Colors.WHITE}{t('menu_create')}{Colors.RESET}"))
        print(center_line(f"{Colors.BOLD}{Colors.WHITE}{t('menu_join')}{Colors.RESET}"))
        print(center_line(f"{Colors.BOLD}{Colors.WHITE}{t('menu_settings')}{Colors.RESET}"))
        print(center_line(f"{Colors.BOLD}{Colors.WHITE}{t('menu_exit')}{Colors.RESET}"))
        print()

        try:
            choice = input(center_line(t("menu_prompt"))).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break

        if choice == "1":
            create_chat_flow(session, config)
        elif choice == "2":
            join_chat_flow(session, config)
        elif choice == "3":
            settings_flow(session, config)
        elif choice == "4":
            break
        else:
            print(center_line(f"{Colors.RED}{t('invalid_option')}{Colors.RESET}"))
            time.sleep(0.8)

    # Clean exit
    clear_screen()
    print(center_line(f"{Colors.BLOOD_CRIMSON}{t('goodbye')}{Colors.RESET}"))
    print()

if __name__ == "__main__":
    main()
