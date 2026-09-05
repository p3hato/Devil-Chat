import unittest
import time
import os
import sys
import glob
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import UserSession, RoomHost, PeerClient

TEST_PORT = 54388

class TestRoomIntegration(unittest.TestCase):
    def setUp(self):
        self.host_session = UserSession(username="DevilAdmin", color="Red")
        self.received_host_msgs = []
        self.received_p1_msgs = []
        self.received_p2_msgs = []
        self.host = None
        self.p1 = None
        self.p2 = None

    def tearDown(self):
        if self.p1:
            self.p1.leave()
        if self.p2:
            self.p2.leave()
        if self.host:
            self.host.close()
        time.sleep(0.2)

    def test_full_room_lifecycle(self):
        # 1. Create Room (Host, Limit = 3)
        self.host = RoomHost(
            host_user=self.host_session,
            port=TEST_PORT,
            max_members=3,
            on_message_cb=lambda u, c, m: self.received_host_msgs.append((u, m))
        )
        started, err = self.host.start()
        self.assertTrue(started, f"Failed to start host: {err}")
        self.assertEqual(len(self.host.members), 1)
        self.assertEqual(self.host.admin_username, "DevilAdmin")

        # 2. Connect Peer 1 (Shadow)
        p1_session = UserSession(username="Shadow", color="Cyan")
        self.p1 = PeerClient(
            user_session=p1_session,
            host_ip="127.0.0.1",
            host_port=TEST_PORT,
            on_message_cb=lambda u, c, m: self.received_p1_msgs.append((u, m))
        )
        connected, err = self.p1.connect()
        self.assertTrue(connected, f"P1 failed to connect: {err}")
        time.sleep(0.2)
        self.assertEqual(len(self.host.members), 2)

        # 3. Connect Peer 2 (Raven)
        p2_session = UserSession(username="Raven", color="Purple")
        self.p2 = PeerClient(
            user_session=p2_session,
            host_ip="127.0.0.1",
            host_port=TEST_PORT,
            on_message_cb=lambda u, c, m: self.received_p2_msgs.append((u, m))
        )
        connected, err = self.p2.connect()
        self.assertTrue(connected, f"P2 failed to connect: {err}")
        time.sleep(0.2)
        self.assertEqual(len(self.host.members), 3)

        # 4. Attempt Duplicate Username (shadow - case insensitive)
        dup_session = UserSession(username="shadow", color="Yellow")
        p_dup = PeerClient(dup_session, "127.0.0.1", TEST_PORT)
        connected, err = p_dup.connect()
        self.assertFalse(connected)
        self.assertEqual(err, "rejected_username")

        # 5. Attempt Connecting 4th Member (Limit = 3)
        extra_session = UserSession(username="ExtraPeer", color="Green")
        p_extra = PeerClient(extra_session, "127.0.0.1", TEST_PORT)
        connected, err = p_extra.connect()
        self.assertFalse(connected)
        self.assertEqual(err, "rejected_full")

        # 6. Messaging Between Peers
        # P1 sends a message
        self.p1.send_message("Hello from Shadow!")
        time.sleep(0.3)
        self.assertIn(("Shadow", "Hello from Shadow!"), self.received_host_msgs)
        self.assertIn(("Shadow", "Hello from Shadow!"), self.received_p2_msgs)

        # Host sends a message
        self.host.send_local_message("Host announcement")
        time.sleep(0.3)
        self.assertIn(("DevilAdmin", "Host announcement"), self.received_p1_msgs)
        self.assertIn(("DevilAdmin", "Host announcement"), self.received_p2_msgs)

        # 7. Unexpected Disconnect
        self.p2.conn.sock.close()
        time.sleep(0.3)
        self.assertEqual(len(self.host.members), 2)
        self.assertNotIn("raven", self.host.members)

        # 8. Re-connecting after disconnect with same username
        p2_reconnect = PeerClient(p2_session, "127.0.0.1", TEST_PORT)
        connected, err = p2_reconnect.connect()
        self.assertTrue(connected)
        time.sleep(0.2)
        self.assertEqual(len(self.host.members), 3)
        p2_reconnect.leave()
        time.sleep(0.2)
        self.assertEqual(len(self.host.members), 2)

    def test_voting_and_admin_transfer(self):
        # Start Host with 2 members
        self.host = RoomHost(
            host_user=self.host_session,
            port=TEST_PORT + 1,
            max_members=5
        )
        self.host.start()

        p1_session = UserSession(username="Ghost", color="Blue")
        self.p1 = PeerClient(p1_session, "127.0.0.1", TEST_PORT + 1)
        self.p1.connect()
        time.sleep(0.2)

        # Non-admin cannot start vote
        self.assertFalse(p1_session.is_admin)

        # Admin starts vote to close chat
        vote_started = self.host.start_close_vote(self.host_session.username)
        self.assertTrue(vote_started)
        self.assertTrue(self.host.is_voting)

        # Vote NO scenario
        self.p1.cast_vote("N")
        time.sleep(0.2)
        self.host.record_vote(self.host_session.username, "N")
        time.sleep(0.2)
        # Majority voted NO -> vote fails, room remains open
        self.assertFalse(self.host.is_voting)
        self.assertTrue(self.host.is_running)

        # Start vote again for YES scenario
        self.host.start_close_vote(self.host_session.username)
        self.p1.cast_vote("Y")
        time.sleep(0.2)
        self.host.record_vote(self.host_session.username, "Y")
        time.sleep(0.8)
        # Majority voted YES -> room closes
        self.assertFalse(self.host.is_running)

    def test_concurrent_messages(self):
        """Tests sending multiple simultaneous messages from multiple peers."""
        self.host = RoomHost(
            host_user=self.host_session,
            port=TEST_PORT + 2,
            max_members=5,
            on_message_cb=lambda u, c, m: self.received_host_msgs.append((u, m))
        )
        self.host.start()

        p1_session = UserSession(username="ClientA", color="Green")
        self.p1 = PeerClient(p1_session, "127.0.0.1", TEST_PORT + 2)
        self.p1.connect()

        p2_session = UserSession(username="ClientB", color="Yellow")
        self.p2 = PeerClient(p2_session, "127.0.0.1", TEST_PORT + 2)
        self.p2.connect()
        time.sleep(0.2)

        def send_p1():
            for i in range(5):
                self.p1.send_message(f"Msg from A {i}")
                time.sleep(0.01)

        def send_p2():
            for i in range(5):
                self.p2.send_message(f"Msg from B {i}")
                time.sleep(0.01)

        t1 = threading.Thread(target=send_p1)
        t2 = threading.Thread(target=send_p2)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        time.sleep(0.5)
        # Host should have received all 10 messages without crash or corruption
        self.assertEqual(len(self.received_host_msgs), 10)

    def test_zero_disk_persistence(self):
        """Verify that no chat logs, database, or message history files were written to disk."""
        project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Search for any .log, .db, .sqlite, or chat files
        forbidden_extensions = ["*.log", "*.db", "*.sqlite", "*.sqlite3", "*history*", "*messages*"]
        found_files = []
        for ext in forbidden_extensions:
            found_files.extend(glob.glob(os.path.join(project_dir, "**", ext), recursive=True))

        self.assertEqual(
            len(found_files),
            0,
            f"Found forbidden persistent message or database files on disk: {found_files}"
        )

if __name__ == "__main__":
    unittest.main()
