import unittest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ui.colors import strip_ansi, visible_len, Colors, colorize
from ui.ascii_art import center_line, get_terminal_width, get_divider

class TestAsciiArt(unittest.TestCase):
    def test_strip_ansi_and_visible_len(self):
        styled = f"{Colors.RED}{Colors.BOLD}DEVIL CHAT{Colors.RESET}"
        self.assertEqual(strip_ansi(styled), "DEVIL CHAT")
        self.assertEqual(visible_len(styled), 10)

    def test_center_line_calculation(self):
        raw = "DEVIL CHAT"
        # In a 20-column terminal, (20 - 10) // 2 = 5 spaces padding
        centered = center_line(raw, cols=20)
        self.assertEqual(centered, "     DEVIL CHAT")

        # With ANSI escape codes, padding must STILL be exactly 5 spaces!
        styled = f"{Colors.RED}{Colors.BOLD}DEVIL CHAT{Colors.RESET}"
        centered_styled = center_line(styled, cols=20)
        self.assertTrue(centered_styled.startswith("     "))
        self.assertEqual(visible_len(centered_styled), 15)

    def test_get_divider(self):
        divider = get_divider("=", Colors.RED)
        self.assertIn("=", divider)
        self.assertTrue(visible_len(divider) >= 40)

if __name__ == "__main__":
    unittest.main()
