import socket
import threading
from typing import Optional, List, Dict, Any, Tuple
from .protocol import encode_packet, PacketDecoder

def get_local_ip() -> str:
    """Discovers the active local network IPv4 address."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(('8.8.8.8', 80))
        ip = s.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            ip = '127.0.0.1'
    finally:
        s.close()
    return ip

def parse_address(addr_str: str, default_port: int = 54321) -> Optional[Tuple[str, int]]:
    """Parses 'IP:PORT' or 'IP' string into (ip, port) tuple."""
    addr_str = addr_str.strip()
    if not addr_str:
        return None
    try:
        if ':' in addr_str:
            parts = addr_str.rsplit(':', 1)
            ip = parts[0].strip()
            port = int(parts[1].strip())
        else:
            ip = addr_str
            port = default_port
        if not (1 <= port <= 65535):
            return None
        return (ip, port)
    except Exception:
        return None

class SocketConnection:
    """
    Thread-safe wrapper around a connected TCP socket.
    Handles framing, decoding, buffer management, and clean teardown.
    """
    def __init__(self, sock: socket.socket, addr: Tuple[str, int]):
        self.sock = sock
        self.addr = addr
        self.decoder = PacketDecoder()
        self._send_lock = threading.Lock()
        self.is_closed = False

    def send(self, packet: Dict[str, Any]) -> bool:
        """Encodes and sends a packet over TCP. Thread-safe."""
        if self.is_closed:
            return False
        try:
            raw_data = encode_packet(packet)
            with self._send_lock:
                self.sock.sendall(raw_data)
            return True
        except Exception:
            self.close()
            return False

    def read_packets(self, chunk_size: int = 4096) -> List[Dict[str, Any]]:
        """
        Reads available data from socket and returns any decoded complete packets.
        Raises ConnectionError or ConnectionResetError on socket disconnect.
        """
        if self.is_closed:
            return []
        try:
            data = self.sock.recv(chunk_size)
            if not data:
                # EOF received - peer closed connection
                self.close()
                raise ConnectionResetError("Connection closed by peer.")
            return self.decoder.feed(data)
        except (socket.timeout, BlockingIOError):
            return []
        except Exception as e:
            self.close()
            raise e

    def close(self):
        """Closes the underlying socket cleanly."""
        if not self.is_closed:
            self.is_closed = True
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            try:
                self.sock.close()
            except Exception:
                pass
