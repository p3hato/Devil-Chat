import json
import struct
from typing import Dict, Any, List, Optional

MAX_PACKET_SIZE = 65536  # 64 KB limit

class PacketType:
    JOIN = "JOIN"
    JOIN_ACCEPT = "JOIN_ACCEPT"
    JOIN_REJECT = "JOIN_REJECT"
    MESSAGE = "MESSAGE"
    SYSTEM = "SYSTEM"
    LEAVE = "LEAVE"
    ADMIN_TRANSFER = "ADMIN_TRANSFER"
    VOTE_START = "VOTE_START"
    VOTE = "VOTE"
    VOTE_RESULT = "VOTE_RESULT"
    ROOM_CLOSE = "ROOM_CLOSE"
    PEER_LIST = "PEER_LIST"
    PING = "PING"
    PONG = "PONG"

def encode_packet(packet: Dict[str, Any]) -> bytes:
    """Encodes a dictionary packet into length-prefixed bytes (4 bytes big-endian + UTF-8 JSON)."""
    payload = json.dumps(packet, ensure_ascii=False).encode('utf-8')
    length = len(payload)
    if length > MAX_PACKET_SIZE:
        raise ValueError(f"Packet payload size ({length} bytes) exceeds maximum ({MAX_PACKET_SIZE} bytes)")
    return struct.pack('>I', length) + payload

class PacketDecoder:
    """
    Stateful buffer that decodes incoming byte streams into individual packets.
    Handles TCP fragmentation, partial packets, and multi-packet bundling.
    """
    def __init__(self):
        self._buffer = bytearray()

    def feed(self, data: bytes) -> List[Dict[str, Any]]:
        self._buffer.extend(data)
        packets: List[Dict[str, Any]] = []

        while len(self._buffer) >= 4:
            # Read 4-byte big-endian length
            payload_len = struct.unpack('>I', self._buffer[:4])[0]
            if payload_len > MAX_PACKET_SIZE:
                # Corrupted stream or malicious payload size, clear buffer
                self._buffer.clear()
                raise ValueError(f"Invalid packet size: {payload_len} bytes")

            total_len = 4 + payload_len
            if len(self._buffer) < total_len:
                # Incomplete packet, wait for more data
                break

            payload_bytes = bytes(self._buffer[4:total_len])
            del self._buffer[:total_len]

            try:
                packet = json.loads(payload_bytes.decode('utf-8'))
                if isinstance(packet, dict):
                    packets.append(packet)
            except Exception:
                # Ignore malformed individual JSON packet
                pass

        return packets
