import unittest
import base64
import os
import sys

# Ensure parent directory is in path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.crypto import RoomCrypto, DecryptionError, derive_key

class TestCrypto(unittest.TestCase):
    def test_encrypt_decrypt_default_key(self):
        crypto = RoomCrypto()
        plaintext = "Hello, Devil Chat!"
        encrypted = crypto.encrypt(plaintext)

        self.assertIn("iv", encrypted)
        self.assertIn("data", encrypted)
        self.assertNotEqual(encrypted["data"], plaintext)

        decrypted = crypto.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)

    def test_encrypt_decrypt_with_passphrase(self):
        crypto1 = RoomCrypto.from_passphrase("SecretPassphrase123")
        crypto2 = RoomCrypto.from_passphrase("SecretPassphrase123")
        plaintext = "Confidential message between peers"

        encrypted = crypto1.encrypt(plaintext)
        decrypted = crypto2.decrypt(encrypted)
        self.assertEqual(decrypted, plaintext)

    def test_wrong_passphrase_rejection(self):
        crypto1 = RoomCrypto.from_passphrase("CorrectPassword")
        crypto2 = RoomCrypto.from_passphrase("WrongPassword")

        encrypted = crypto1.encrypt("Secret message")
        with self.assertRaises(DecryptionError):
            crypto2.decrypt(encrypted)

    def test_tampering_detection(self):
        crypto = RoomCrypto()
        encrypted = crypto.encrypt("Tamper-proof payload")

        # Corrupt one byte of the ciphertext data
        raw_data = bytearray(base64.b64decode(encrypted["data"]))
        raw_data[0] ^= 0xFF
        tampered_encrypted = {
            "iv": encrypted["iv"],
            "data": base64.b64encode(raw_data).decode("ascii")
        }

        with self.assertRaises(DecryptionError):
            crypto.decrypt(tampered_encrypted)

if __name__ == "__main__":
    unittest.main()
