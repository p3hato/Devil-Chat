import secrets
from typing import Tuple

def generate_ephemeral_id() -> str:
    """Generates a random, temporary 6-character hex ID (e.g., '7F2A91')."""
    return secrets.token_hex(3).upper()

def validate_username(username: str) -> Tuple[bool, str]:
    """
    Validates a chosen username.
    Must be 1-16 characters, no whitespace or control characters.
    """
    if not username:
        return False, 'username_empty'
    username = username.strip()
    if not username:
        return False, 'username_empty'
    if len(username) > 16:
        return False, 'username_too_long'
    if any(c in '\r\n\t ' or ord(c) < 32 for c in username):
        return False, 'username_empty'
    return True, ''

class UserSession:
    """
    Represents an in-memory ephemeral user session.
    All data is temporary and lives only in memory.
    """
    def __init__(self, username: str = '', color: str = 'Red'):
        self.id = generate_ephemeral_id()
        self.username = username
        self.color = color
        self.is_admin = False

    def reset_id(self):
        self.id = generate_ephemeral_id()
