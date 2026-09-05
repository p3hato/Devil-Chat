import unittest
import re
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.identity import generate_ephemeral_id, validate_username, UserSession

class TestIdentity(unittest.TestCase):
    def test_ephemeral_id_format(self):
        eid = generate_ephemeral_id()
        self.assertEqual(len(eid), 6)
        # Must be valid uppercase hex characters
        self.assertTrue(re.match(r'^[0-9A-F]{6}$', eid))

    def test_ephemeral_id_randomness(self):
        ids = {generate_ephemeral_id() for _ in range(50)}
        # 50 random 6-hex IDs should virtually all be distinct
        self.assertEqual(len(ids), 50)

    def test_username_validation(self):
        # Valid usernames
        valid, _ = validate_username("Shadow")
        self.assertTrue(valid)
        valid, _ = validate_username("Ghost_01")
        self.assertTrue(valid)
        valid, _ = validate_username("Devil")
        self.assertTrue(valid)

        # Empty / whitespace
        valid, err = validate_username("")
        self.assertFalse(valid)
        self.assertEqual(err, "username_empty")

        valid, err = validate_username("   ")
        self.assertFalse(valid)
        self.assertEqual(err, "username_empty")

        # Contains spaces
        valid, err = validate_username("User Name")
        self.assertFalse(valid)
        self.assertEqual(err, "username_empty")

        # Too long (> 16 chars)
        valid, err = validate_username("SuperLongUsernameExceedingLimit")
        self.assertFalse(valid)
        self.assertEqual(err, "username_too_long")

    def test_user_session(self):
        session = UserSession("Ghost", "Cyan")
        self.assertEqual(session.username, "Ghost")
        self.assertEqual(session.color, "Cyan")
        self.assertFalse(session.is_admin)
        old_id = session.id
        session.reset_id()
        self.assertNotEqual(session.id, old_id)

if __name__ == "__main__":
    unittest.main()
