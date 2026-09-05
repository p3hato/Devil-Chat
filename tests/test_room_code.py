import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.room_code import create_room_code, parse_room_code, is_room_code

class TestRoomCode(unittest.TestCase):
    def test_create_and_parse_dual_ip(self):
        code = create_room_code("45.70.144.188", "192.168.0.102", 54321, "secret123")
        self.assertTrue(code.startswith("DEVIL-"))
        self.assertTrue(is_room_code(code))

        parsed = parse_room_code(code)
        self.assertIsNotNone(parsed)
        candidates, port, passphrase = parsed

        self.assertIn("45.70.144.188", candidates)
        self.assertIn("192.168.0.102", candidates)
        self.assertIn("127.0.0.1", candidates)
        self.assertEqual(port, 54321)
        self.assertEqual(passphrase, "secret123")

    def test_create_and_parse_dual_ip_no_pass(self):
        code = create_room_code("189.45.210.55", "192.168.1.100", 54322)
        parsed = parse_room_code(code)
        self.assertIsNotNone(parsed)
        candidates, port, passphrase = parsed
        self.assertIn("189.45.210.55", candidates)
        self.assertIn("192.168.1.100", candidates)
        self.assertEqual(port, 54322)
        self.assertEqual(passphrase, "")

    def test_corrupted_code_detection(self):
        code = create_room_code("189.45.210.55", "192.168.1.100", 54321)
        chars = list(code)
        chars[10] = "A" if chars[10] != "A" else "B"
        corrupted = "".join(chars)
        self.assertIsNone(parse_room_code(corrupted))

    def test_invalid_formats(self):
        self.assertIsNone(parse_room_code("random_junk"))
        self.assertIsNone(parse_room_code("DEVIL-SHORT"))
        self.assertFalse(is_room_code("192.168.1.10:54321"))

if __name__ == "__main__":
    unittest.main()
