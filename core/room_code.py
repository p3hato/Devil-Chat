import socket
import struct
import base64
import hashlib
from typing import Optional, Tuple, List

PREFIX = "DEVIL-"

def create_room_code(public_ip: str, local_ip: str, port: int, passphrase: str = "") -> str:
    """
    Encodes both Public IP (for global peers) and Local IP (for same Wi-Fi/same PC)
    plus Port and optional Passphrase into a clean, base32-encoded ticket.
    Format: DEVIL-XXXX-XXXX-XXXX...
    """
    header = bytes([2])  # Version 2 (dual-IP aware)

    # Encode Public IP
    try:
        pub_bytes = socket.inet_aton(public_ip)
        pub_type = bytes([4])
    except Exception:
        enc = public_ip.encode('utf-8')[:32]
        pub_type = bytes([len(enc)])
        pub_bytes = enc

    # Encode Local IP
    try:
        loc_bytes = socket.inet_aton(local_ip)
        loc_type = bytes([4])
    except Exception:
        enc = local_ip.encode('utf-8')[:32]
        loc_type = bytes([len(enc)])
        loc_bytes = enc

    port_bytes = struct.pack('>H', port)
    pass_bytes = passphrase.encode('utf-8')[:16]
    pass_len = bytes([len(pass_bytes)])

    payload = (
        header +
        pub_type + pub_bytes +
        loc_type + loc_bytes +
        port_bytes +
        pass_len + pass_bytes
    )
    checksum = hashlib.sha256(payload).digest()[:2]
    full = payload + checksum

    b32 = base64.b32encode(full).decode('ascii').rstrip('=')
    chunks = [b32[i:i+4] for i in range(0, len(b32), 4)]
    return PREFIX + '-'.join(chunks)

def is_room_code(text: str) -> bool:
    """Checks if a given string looks like a DEVIL CHAT room code."""
    cleaned = text.strip().upper()
    return cleaned.startswith("DEVIL-") or cleaned.startswith("DEVIL#")

def parse_room_code(code_str: str) -> Optional[Tuple[List[str], int, str]]:
    """
    Parses a DEVIL CHAT room code into (candidate_ips_list, port, passphrase).
    Candidate IPs are ordered intelligently for fast connection.
    """
    cleaned = code_str.strip().upper()
    if cleaned.startswith("DEVIL-") or cleaned.startswith("DEVIL#"):
        cleaned = cleaned[6:]
    cleaned = cleaned.replace("-", "").replace(" ", "").replace("#", "")

    pad_len = (8 - len(cleaned) % 8) % 8
    cleaned += "=" * pad_len

    try:
        raw = base64.b32decode(cleaned)
    except Exception:
        return None

    if len(raw) < 8:
        return None

    ver = raw[0]
    payload = raw[:-2]
    checksum = raw[-2:]
    expected_checksum = hashlib.sha256(payload).digest()[:2]
    if checksum != expected_checksum:
        return None

    # Version 2: Dual IP (Public + Local)
    if ver == 2:
        idx = 1
        # Public IP
        pub_type = payload[idx]
        idx += 1
        if pub_type == 4:
            public_ip = socket.inet_ntoa(payload[idx:idx+4])
            idx += 4
        else:
            public_ip = payload[idx:idx+pub_type].decode('utf-8', errors='replace')
            idx += pub_type

        # Local IP
        loc_type = payload[idx]
        idx += 1
        if loc_type == 4:
            local_ip = socket.inet_ntoa(payload[idx:idx+4])
            idx += 4
        else:
            local_ip = payload[idx:idx+loc_type].decode('utf-8', errors='replace')
            idx += loc_type

        port = struct.unpack('>H', payload[idx:idx+2])[0]
        idx += 2

        pass_len = payload[idx]
        idx += 1
        passphrase = payload[idx:idx+pass_len].decode('utf-8', errors='replace')

        # Candidates list: distinct IPs + local loopback
        candidates = []
        for ip in (public_ip, local_ip, "127.0.0.1"):
            if ip and ip not in candidates:
                candidates.append(ip)

        return (candidates, port, passphrase)

    # Version 1 (single IP backward compatibility)
    elif ver == 1:
        t = payload[1]
        idx = 2
        if t == 4:
            ip = socket.inet_ntoa(payload[idx:idx+4])
            idx += 4
        else:
            ip = payload[idx:idx+t].decode('utf-8', errors='replace')
            idx += t
        port = struct.unpack('>H', payload[idx:idx+2])[0]
        idx += 2
        pass_len = payload[idx]
        idx += 1
        passphrase = payload[idx:idx+pass_len].decode('utf-8', errors='replace')
        return ([ip, "127.0.0.1"], port, passphrase)

    return None
