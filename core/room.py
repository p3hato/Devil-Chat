import socket
import threading
import time
from typing import Dict, List, Optional, Callable, Any, Tuple
from .protocol import PacketType
from .network import SocketConnection, parse_address
from .crypto import RoomCrypto, DecryptionError
from .identity import UserSession

class MemberInfo:
    def __init__(self, user_id: str, username: str, color: str, is_admin: bool = False, conn: Optional[SocketConnection] = None):
        self.user_id = user_id
        self.username = username
        self.color = color
        self.is_admin = is_admin
        self.conn = conn
        self.joined_at = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.user_id,
            "username": self.username,
            "color": self.color,
            "is_admin": self.is_admin
        }

class RoomHost:
    """
    P2P Host Controller.
    Runs locally on the machine of the user who creates the private chat room.
    No external or central server.
    """
    def __init__(
        self,
        host_user: UserSession,
        port: int = 54321,
        max_members: int = 10,
        passphrase: str = "",
        on_message_cb: Optional[Callable] = None,
        on_system_cb: Optional[Callable] = None,
        on_members_update_cb: Optional[Callable] = None,
        on_vote_start_cb: Optional[Callable] = None,
        on_vote_result_cb: Optional[Callable] = None,
        on_room_close_cb: Optional[Callable] = None,
    ):
        self.host_user = host_user
        self.port = port
        self.max_members = max(2, min(20, max_members))
        self.passphrase = passphrase
        self.crypto = RoomCrypto.from_passphrase(passphrase)

        self.on_message_cb = on_message_cb
        self.on_system_cb = on_system_cb
        self.on_members_update_cb = on_members_update_cb
        self.on_vote_start_cb = on_vote_start_cb
        self.on_vote_result_cb = on_vote_result_cb
        self.on_room_close_cb = on_room_close_cb

        self.server_sock: Optional[socket.socket] = None
        self.is_running = False
        self._lock = threading.Lock()

        # Members map: username_lower -> MemberInfo
        self.members: Dict[str, MemberInfo] = {}

        # Add host user as first member and admin
        self.host_user.is_admin = True
        host_member = MemberInfo(
            user_id=self.host_user.id,
            username=self.host_user.username,
            color=self.host_user.color,
            is_admin=True,
            conn=None
        )
        self.members[self.host_user.username.lower()] = host_member
        self.admin_username = self.host_user.username

        # Voting state
        self.is_voting = False
        self.vote_initiator = ""
        self.votes: Dict[str, str] = {}  # username -> 'Y' or 'N'

        # Background listener thread
        self.listener_thread: Optional[threading.Thread] = None

    def start(self) -> Tuple[bool, str]:
        """Starts TCP listening socket on specified port."""
        try:
            self.server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_sock.bind(('0.0.0.0', self.port))
            self.server_sock.listen(self.max_members)
            self.is_running = True

            self.listener_thread = threading.Thread(target=self._accept_loop, daemon=True)
            self.listener_thread.start()
            return True, ""
        except Exception as e:
            self.is_running = False
            return False, str(e)

    def _accept_loop(self):
        """Accepts incoming peer TCP connections."""
        while self.is_running:
            try:
                sock, addr = self.server_sock.accept()
                conn = SocketConnection(sock, addr)
                client_thread = threading.Thread(target=self._handle_peer, args=(conn,), daemon=True)
                client_thread.start()
            except Exception:
                break

    def _handle_peer(self, conn: SocketConnection):
        """Manages initial handshake and message loop for a connected peer."""
        peer_username = None
        try:
            # 1. Wait for JOIN packet with timeout
            conn.sock.settimeout(5.0)
            initial_packets = conn.read_packets()
            if not initial_packets:
                conn.close()
                return

            join_pkt = initial_packets[0]
            if join_pkt.get("type") != PacketType.JOIN:
                conn.close()
                return

            req_user = join_pkt.get("username", "").strip()
            req_color = join_pkt.get("color", "White")
            req_id = join_pkt.get("id", "")
            req_pass = join_pkt.get("passphrase", "")

            # 2. Validate join request
            with self._lock:
                # 2a. Check passphrase
                if req_pass != self.passphrase:
                    conn.send({
                        "type": PacketType.JOIN_REJECT,
                        "reason": "AUTH_FAILED"
                    })
                    conn.close()
                    return

                # 2b. Check username uniqueness (case-insensitive)
                if req_user.lower() in self.members:
                    conn.send({
                        "type": PacketType.JOIN_REJECT,
                        "reason": "USERNAME_TAKEN",
                        "username": req_user
                    })
                    conn.close()
                    return

                # 2c. Check member limit
                if len(self.members) >= self.max_members:
                    conn.send({
                        "type": PacketType.JOIN_REJECT,
                        "reason": "ROOM_FULL",
                        "current": len(self.members),
                        "max": self.max_members
                    })
                    conn.close()
                    return

                # Accept peer
                peer_member = MemberInfo(
                    user_id=req_id,
                    username=req_user,
                    color=req_color,
                    is_admin=False,
                    conn=conn
                )
                self.members[req_user.lower()] = peer_member
                peer_username = req_user

                # Send JOIN_ACCEPT
                member_list = [m.to_dict() for m in self.members.values()]
                conn.send({
                    "type": PacketType.JOIN_ACCEPT,
                    "max_members": self.max_members,
                    "admin": self.admin_username,
                    "members": member_list
                })

            # Broadcast join notice and updated peer list
            conn.sock.settimeout(None)
            self._broadcast_system("system_user_joined", username=req_user)
            self._broadcast_peer_list()

            # 3. Peer packet reading loop
            while self.is_running and not conn.is_closed:
                packets = conn.read_packets()
                for pkt in packets:
                    self._process_peer_packet(peer_member, pkt)

        except (ConnectionResetError, ConnectionError):
            pass
        except Exception:
            pass
        finally:
            if peer_username:
                self._remove_peer(peer_username, disconnected=True)

    def _process_peer_packet(self, sender: MemberInfo, pkt: Dict[str, Any]):
        pkt_type = pkt.get("type")

        if pkt_type == PacketType.MESSAGE:
            # Broadcast encrypted message to all other peers
            encrypted_payload = pkt.get("encrypted")
            if encrypted_payload:
                # Deliver to local host
                try:
                    decrypted_text = self.crypto.decrypt(encrypted_payload)
                    if self.on_message_cb:
                        self.on_message_cb(sender.username, sender.color, decrypted_text)
                except DecryptionError:
                    pass

                # Forward encrypted payload to all other connected peers
                with self._lock:
                    for uname, member in self.members.items():
                        if member.conn and member.username != sender.username:
                            member.conn.send({
                                "type": PacketType.MESSAGE,
                                "sender": sender.username,
                                "color": sender.color,
                                "encrypted": encrypted_payload
                            })

        elif pkt_type == PacketType.LEAVE:
            self._remove_peer(sender.username, disconnected=False)

        elif pkt_type == PacketType.VOTE_START:
            # Only admin can start vote
            if sender.username == self.admin_username:
                self.start_close_vote(sender.username)

        elif pkt_type == PacketType.VOTE:
            choice = pkt.get("choice", "").upper()
            if choice in ("Y", "N"):
                self.record_vote(sender.username, choice)

    def _remove_peer(self, username: str, disconnected: bool = False):
        with self._lock:
            lower = username.lower()
            if lower not in self.members:
                return
            member = self.members.pop(lower)
            if member.conn:
                member.conn.close()

            if self.is_voting and username in self.votes:
                del self.votes[username]

            admin_transferred = False
            new_admin = None
            if username == self.admin_username:
                if self.members:
                    sorted_peers = sorted(self.members.values(), key=lambda m: m.joined_at)
                    new_admin = sorted_peers[0]
                    new_admin.is_admin = True
                    self.admin_username = new_admin.username
                    admin_transferred = True
                    if new_admin.username == self.host_user.username:
                        self.host_user.is_admin = True

        notice_key = "system_user_disconnected" if disconnected else "system_user_left"
        self._broadcast_system(notice_key, username=username)

        if admin_transferred and new_admin:
            self._broadcast_system("system_admin_transfer", username=new_admin.username)
            self._broadcast({
                "type": PacketType.ADMIN_TRANSFER,
                "admin": new_admin.username
            })

        self._broadcast_peer_list()

        if self.is_voting:
            self._evaluate_vote()

    def _broadcast_system(self, text_key: str, **kwargs):
        """Sends system notification to local host and all peers."""
        if self.on_system_cb:
            self.on_system_cb(text_key, **kwargs)

        packet = {
            "type": PacketType.SYSTEM,
            "key": text_key,
            "kwargs": kwargs
        }
        self._broadcast(packet)

    def _broadcast_peer_list(self):
        with self._lock:
            member_list = [m.to_dict() for m in self.members.values()]
            admin = self.admin_username
            max_m = self.max_members

        if self.on_members_update_cb:
            self.on_members_update_cb(member_list, max_m, admin)

        packet = {
            "type": PacketType.PEER_LIST,
            "members": member_list,
            "max_members": max_m,
            "admin": admin
        }
        self._broadcast(packet)

    def _broadcast(self, packet: Dict[str, Any]):
        with self._lock:
            for member in list(self.members.values()):
                if member.conn:
                    member.conn.send(packet)

    def send_local_message(self, text: str):
        """Called when the local host user types a message."""
        encrypted_payload = self.crypto.encrypt(text)

        if self.on_message_cb:
            self.on_message_cb(self.host_user.username, self.host_user.color, text)

        packet = {
            "type": PacketType.MESSAGE,
            "sender": self.host_user.username,
            "color": self.host_user.color,
            "encrypted": encrypted_payload
        }
        self._broadcast(packet)

    def start_close_vote(self, initiator: str) -> bool:
        """Starts democratic room closure vote."""
        with self._lock:
            if self.is_voting:
                return False
            self.is_voting = True
            self.vote_initiator = initiator
            self.votes.clear()

        if self.on_vote_start_cb:
            self.on_vote_start_cb(initiator)

        self._broadcast({
            "type": PacketType.VOTE_START,
            "initiator": initiator
        })
        return True

    def record_vote(self, username: str, choice: str) -> bool:
        """Records a user's vote ('Y' or 'N')."""
        with self._lock:
            if not self.is_voting:
                return False
            if username in self.votes:
                return False
            self.votes[username] = choice.upper()

        self._broadcast_system("vote_recorded", username=username)
        self._evaluate_vote()
        return True

    def _evaluate_vote(self):
        """Calculates vote tally and determines outcome."""
        with self._lock:
            if not self.is_voting:
                return
            total_members = len(self.members)
            if total_members == 0:
                return

            yes_count = sum(1 for v in self.votes.values() if v == 'Y')
            no_count = sum(1 for v in self.votes.values() if v == 'N')
            voted_count = len(self.votes)

            needed_majority = (total_members // 2) + 1

            if yes_count >= needed_majority:
                self.is_voting = False
                close_room = True
                success = True
            elif no_count >= (total_members - needed_majority + 1) or (voted_count == total_members and yes_count < needed_majority):
                self.is_voting = False
                close_room = False
                success = False
            else:
                return

        if success and close_room:
            self._broadcast_system("system_chat_closed_vote")
            self._broadcast({
                "type": PacketType.VOTE_RESULT,
                "approved": True
            })
            if self.on_vote_result_cb:
                self.on_vote_result_cb(True)
            threading.Thread(target=self._delayed_close, daemon=True).start()
        else:
            self._broadcast_system("system_vote_failed")
            self._broadcast({
                "type": PacketType.VOTE_RESULT,
                "approved": False
            })
            if self.on_vote_result_cb:
                self.on_vote_result_cb(False)

    def _delayed_close(self):
        time.sleep(0.5)
        self.close()

    def close(self):
        """Gracefully shuts down host, notifies peers, and wipes memory."""
        self.is_running = False
        try:
            self._broadcast({"type": PacketType.ROOM_CLOSE})
        except Exception:
            pass

        with self._lock:
            for member in self.members.values():
                if member.conn:
                    member.conn.close()
            self.members.clear()
            self.votes.clear()

        if self.server_sock:
            try:
                self.server_sock.close()
            except Exception:
                pass

        if self.on_room_close_cb:
            self.on_room_close_cb()


class PeerClient:
    """
    P2P Peer Client.
    Connects directly to the Room Host.
    Handles message encryption, transmission, background receiving, and voting.
    """
    def __init__(
        self,
        user_session: UserSession,
        host_ip: str,
        host_port: int,
        passphrase: str = "",
        on_message_cb: Optional[Callable] = None,
        on_system_cb: Optional[Callable] = None,
        on_members_update_cb: Optional[Callable] = None,
        on_vote_start_cb: Optional[Callable] = None,
        on_vote_result_cb: Optional[Callable] = None,
        on_room_close_cb: Optional[Callable] = None,
        on_disconnect_cb: Optional[Callable] = None,
    ):
        self.user = user_session
        if isinstance(host_ip, (list, tuple)):
            self.candidate_ips = list(host_ip)
            self.host_ip = self.candidate_ips[0] if self.candidate_ips else "127.0.0.1"
        else:
            self.candidate_ips = [host_ip]
            self.host_ip = host_ip

        self.host_port = host_port
        self.passphrase = passphrase
        self.crypto = RoomCrypto.from_passphrase(passphrase)

        self.on_message_cb = on_message_cb
        self.on_system_cb = on_system_cb
        self.on_members_update_cb = on_members_update_cb
        self.on_vote_start_cb = on_vote_start_cb
        self.on_vote_result_cb = on_vote_result_cb
        self.on_room_close_cb = on_room_close_cb
        self.on_disconnect_cb = on_disconnect_cb

        self.conn: Optional[SocketConnection] = None
        self.is_connected = False
        self.is_running = False
        self.members: List[Dict[str, Any]] = []
        self.max_members = 10
        self.admin_username = ""
        self.is_voting = False

        self.recv_thread: Optional[threading.Thread] = None

    def connect(self) -> Tuple[bool, str]:
        """
        Initiates connection to the host across candidate IPs and performs handshake.
        Returns (success: bool, error_message: str).
        """
        sock = None
        connected_ip = None

        for ip in self.candidate_ips:
            if not ip:
                continue
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2.0)
                s.connect((ip, self.host_port))
                sock = s
                connected_ip = ip
                self.host_ip = ip
                break
            except Exception:
                try:
                    s.close()
                except Exception:
                    pass

        if not sock or not connected_ip:
            return False, "connection_failed"

        try:
            self.conn = SocketConnection(sock, (connected_ip, self.host_port))

            # Send JOIN packet
            join_pkt = {
                "type": PacketType.JOIN,
                "id": self.user.id,
                "username": self.user.username,
                "color": self.user.color,
                "passphrase": self.passphrase
            }
            self.conn.send(join_pkt)

            # Wait for response
            packets = self.conn.read_packets()
            if not packets:
                self.conn.close()
                return False, "connection_failed"

            resp = packets[0]
            resp_type = resp.get("type")

            if resp_type == PacketType.JOIN_REJECT:
                self.conn.close()
                reason = resp.get("reason", "rejected_generic")
                if reason == "ROOM_FULL":
                    return False, "rejected_full"
                elif reason == "USERNAME_TAKEN":
                    return False, "rejected_username"
                elif reason == "AUTH_FAILED":
                    return False, "rejected_auth"
                return False, reason

            elif resp_type == PacketType.JOIN_ACCEPT:
                self.is_connected = True
                self.is_running = True
                self.max_members = resp.get("max_members", 10)
                self.admin_username = resp.get("admin", "")
                self.members = resp.get("members", [])
                self.user.is_admin = (self.user.username == self.admin_username)

                # Reset timeout for regular communication
                self.conn.sock.settimeout(None)

                # Start background receive thread
                self.recv_thread = threading.Thread(target=self._recv_loop, daemon=True)
                self.recv_thread.start()
                return True, ""

            else:
                self.conn.close()
                return False, "connection_failed"

        except Exception:
            if self.conn:
                self.conn.close()
            return False, "connection_failed"

    def _recv_loop(self):
        """Continuously reads incoming packets from host."""
        while self.is_running and self.conn and not self.conn.is_closed:
            try:
                packets = self.conn.read_packets()
                for pkt in packets:
                    self._handle_packet(pkt)
            except Exception:
                break

        if self.is_running:
            self.is_connected = False
            self.is_running = False
            if self.on_disconnect_cb:
                self.on_disconnect_cb()

    def _handle_packet(self, pkt: Dict[str, Any]):
        pkt_type = pkt.get("type")

        if pkt_type == PacketType.MESSAGE:
            sender = pkt.get("sender", "")
            color = pkt.get("color", "White")
            encrypted_payload = pkt.get("encrypted")
            if encrypted_payload and self.on_message_cb:
                try:
                    text = self.crypto.decrypt(encrypted_payload)
                    self.on_message_cb(sender, color, text)
                except DecryptionError:
                    pass

        elif pkt_type == PacketType.SYSTEM:
            key = pkt.get("key", "")
            kwargs = pkt.get("kwargs", {})
            if self.on_system_cb:
                self.on_system_cb(key, **kwargs)

        elif pkt_type == PacketType.PEER_LIST:
            self.members = pkt.get("members", [])
            self.max_members = pkt.get("max_members", 10)
            self.admin_username = pkt.get("admin", "")
            self.user.is_admin = (self.user.username == self.admin_username)
            if self.on_members_update_cb:
                self.on_members_update_cb(self.members, self.max_members, self.admin_username)

        elif pkt_type == PacketType.ADMIN_TRANSFER:
            self.admin_username = pkt.get("admin", "")
            self.user.is_admin = (self.user.username == self.admin_username)

        elif pkt_type == PacketType.VOTE_START:
            self.is_voting = True
            initiator = pkt.get("initiator", "")
            if self.on_vote_start_cb:
                self.on_vote_start_cb(initiator)

        elif pkt_type == PacketType.VOTE_RESULT:
            self.is_voting = False
            approved = pkt.get("approved", False)
            if self.on_vote_result_cb:
                self.on_vote_result_cb(approved)

        elif pkt_type == PacketType.ROOM_CLOSE:
            self.is_connected = False
            self.is_running = False
            if self.on_room_close_cb:
                self.on_room_close_cb()

    def send_message(self, text: str) -> bool:
        """Encrypts and transmits a chat message to the host."""
        if not self.is_connected or not self.conn:
            return False
        encrypted_payload = self.crypto.encrypt(text)
        return self.conn.send({
            "type": PacketType.MESSAGE,
            "encrypted": encrypted_payload
        })

    def start_close_vote(self) -> bool:
        """Sends request to start a room closure vote (Admin only)."""
        if not self.is_connected or not self.conn:
            return False
        return self.conn.send({"type": PacketType.VOTE_START})

    def cast_vote(self, choice: str) -> bool:
        """Sends vote choice ('Y' or 'N')."""
        if not self.is_connected or not self.conn:
            return False
        return self.conn.send({
            "type": PacketType.VOTE,
            "choice": choice.upper()
        })

    def leave(self):
        """Sends LEAVE packet, closes connection, and wipes memory."""
        if self.conn and not self.conn.is_closed:
            try:
                self.conn.send({"type": PacketType.LEAVE})
            except Exception:
                pass
            self.conn.close()
        self.is_connected = False
        self.is_running = False
        self.members.clear()
