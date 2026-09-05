import os
import base64
from typing import Optional, Dict
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

# Fixed room salt for PBKDF2 passphrase derivation
ROOM_SALT = b"DEVIL_CHAT_EPHEMERAL_SALT_2026"
DEFAULT_KEY = b"\xde\xad\xbe\xef\xca\xfe\xba\xbe\x01\x23\x45\x67\x89\xab\xcd\xef\xfe\xdc\xba\x98\x76\x54\x32\x10\x00\x11\x22\x33\x44\x55\x66\x77"

class DecryptionError(Exception):
    """Raised when decryption or cryptographic authentication fails (wrong key or tampering)."""
    pass

def derive_key(passphrase: str, salt: bytes = ROOM_SALT) -> bytes:
    """Derives a 256-bit AES key from a passphrase using PBKDF2-HMAC-SHA256 (100,000 rounds)."""
    if not passphrase:
        return DEFAULT_KEY
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=100000,
    )
    return kdf.derive(passphrase.encode('utf-8'))

class RoomCrypto:
    """
    Handles authenticated end-to-end symmetric encryption using AES-256-GCM.
    Ensures both confidentiality and tamper detection for all messages in RAM and over the wire.
    """
    def __init__(self, key: Optional[bytes] = None):
        self._key = key if key else DEFAULT_KEY
        self._aesgcm = AESGCM(self._key)

    @classmethod
    def from_passphrase(cls, passphrase: str) -> "RoomCrypto":
        key = derive_key(passphrase)
        return cls(key)

    def encrypt(self, plaintext: str) -> Dict[str, str]:
        """
        Encrypts plaintext string with AES-256-GCM using a fresh 12-byte IV.
        Returns a dictionary containing base64-encoded 'iv' and 'ciphertext' (with auth tag).
        """
        iv = os.urandom(12)  # 96-bit standard IV for AES-GCM
        ciphertext = self._aesgcm.encrypt(iv, plaintext.encode('utf-8'), None)
        return {
            "iv": base64.b64encode(iv).decode('ascii'),
            "data": base64.b64encode(ciphertext).decode('ascii')
        }

    def decrypt(self, encrypted_payload: Dict[str, str]) -> str:
        """
        Decrypts and authenticates AES-256-GCM payload.
        Raises DecryptionError if the key is incorrect or data was tampered with.
        """
        try:
            iv = base64.b64decode(encrypted_payload["iv"].encode('ascii'))
            data = base64.b64decode(encrypted_payload["data"].encode('ascii'))
            plaintext_bytes = self._aesgcm.decrypt(iv, data, None)
            return plaintext_bytes.decode('utf-8')
        except Exception as e:
            raise DecryptionError("Authentication tag mismatch or corrupted message") from e
