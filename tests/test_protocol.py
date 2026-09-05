import unittest
import struct
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.protocol import encode_packet, PacketDecoder, PacketType, MAX_PACKET_SIZE

class TestProtocol(unittest.TestCase):
    def test_encode_and_decode_single_packet(self):
        packet = {"type": PacketType.MESSAGE, "text": "Hello world", "count": 42}
        encoded = encode_packet(packet)

        # First 4 bytes must be length
        length = struct.unpack('>I', encoded[:4])[0]
        self.assertEqual(len(encoded) - 4, length)

        decoder = PacketDecoder()
        packets = decoder.feed(encoded)
        self.assertEqual(len(packets), 1)
        self.assertEqual(packets[0], packet)

    def test_tcp_fragmentation(self):
        """Simulate TCP delivery in 1-byte chunks."""
        packet = {"type": PacketType.SYSTEM, "msg": "Peer connected", "nested": {"a": 1}}
        encoded = encode_packet(packet)

        decoder = PacketDecoder()
        received = []
        for i in range(len(encoded)):
            chunk = encoded[i:i+1]
            pkts = decoder.feed(chunk)
            received.extend(pkts)

        self.assertEqual(len(received), 1)
        self.assertEqual(received[0], packet)

    def test_bundled_packets(self):
        """Simulate multiple packets delivered in a single TCP read buffer."""
        pkt1 = {"type": PacketType.JOIN, "user": "Alice"}
        pkt2 = {"type": PacketType.MESSAGE, "text": "Hi"}
        pkt3 = {"type": PacketType.LEAVE, "user": "Bob"}

        bundled = encode_packet(pkt1) + encode_packet(pkt2) + encode_packet(pkt3)

        decoder = PacketDecoder()
        packets = decoder.feed(bundled)
        self.assertEqual(len(packets), 3)
        self.assertEqual(packets[0], pkt1)
        self.assertEqual(packets[1], pkt2)
        self.assertEqual(packets[2], pkt3)

    def test_oversized_packet_rejection(self):
        oversized = {"big": "X" * (MAX_PACKET_SIZE + 10)}
        with self.assertRaises(ValueError):
            encode_packet(oversized)

if __name__ == "__main__":
    unittest.main()
