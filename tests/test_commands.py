from tests import support

import io
import os
import tempfile
import unittest

from core.accessories import Wallet
from core.commands import GIVE_LIMIT, run_command
from core.game_state import GameScreen
from ui.console import TerminalCommands
from tests.test_ui_flow import UITestCase, pump


def temp_wallet() -> Wallet:
    return Wallet(os.path.join(tempfile.mkdtemp(dir=support.TEST_DATA_DIR), "wallet.json"))


class FakeTerminal(io.StringIO):
    def isatty(self):
        return True


class TestGiveCommand(unittest.TestCase):
    def test_give_adds_points_and_saves_them(self):
        wallet = temp_wallet()
        self.assertEqual(run_command("/give @s points 10000", wallet),
                         "Gave 10,000 points. Balance: 10,000")
        self.assertEqual(run_command("  GIVE   @s Points 2,500 \n", wallet),
                         "Gave 2,500 points. Balance: 12,500")
        self.assertEqual(Wallet(wallet.path).balance, 12500)

    def test_bad_commands_change_nothing(self):
        wallet = temp_wallet()
        for line in ("/give @s points -5", "/give @s points 0", "/give @s points abc",
                     "/give @s points 1.5", "/give @p points 10", "/give @s coins 10",
                     "/give @s points", "/kill @s"):
            with self.subTest(line=line):
                self.assertTrue(run_command(line, wallet))
        self.assertIn("at most", run_command(f"/give @s points {GIVE_LIMIT + 1}", wallet))
        self.assertEqual(run_command("", wallet), "")
        self.assertEqual(wallet.balance, 0)


class TestTerminalCommands(UITestCase):
    def test_lines_typed_in_the_terminal_reach_the_game(self):
        self.state.wallet = temp_wallet()
        self.window.show_screen(GameScreen.MENU)
        commands = TerminalCommands(self.window, FakeTerminal("/give @s points 10000\nhello\n"))
        self.assertTrue(commands.start())
        end = 0
        while self.state.wallet.balance == 0 and end < 200:
            pump(10)
            end += 1
        self.assertEqual(self.state.wallet.balance, 10000)
        self.assertIn("BANKED: 10,000", self.window.screens[GameScreen.MENU].banked_label.text())

    def test_nothing_listens_without_a_terminal(self):
        self.assertFalse(TerminalCommands(self.window, io.StringIO("/give @s points 5\n")).start())


if __name__ == "__main__":
    unittest.main()
