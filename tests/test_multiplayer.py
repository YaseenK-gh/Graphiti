from tests import support

import random
import time
import unittest

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from core.constants import RACE_COLORING, RACE_PLANAR
from core.game_state import GameScreen
from net.client import LobbyClient
from net.discovery import LobbyAnnouncer, LobbyBrowser
from net.host import LobbyHost
from net.protocol import (CODE_ALPHABET, CODE_LENGTH, COUNTDOWN, LOBBY, PLAYING, LineReader,
                          encode, make_code)
from ui.dialogs import HowToPlayDialog
from ui.screens.multiplayer_screen import parse_address
from ui.widgets.pixel import PixelButton
from tests.test_race import solution
from tests.test_ui_flow import UITestCase, pump

HOST_OPTIONS = {"port": 0, "announce": False, "countdown_seconds": 0.05, "search_seconds": 0.01}


def wait_until(condition, timeout_ms=3000):
    end = time.perf_counter() + timeout_ms / 1000
    while not condition() and time.perf_counter() < end:
        pump(5)
    return condition()


class TestProtocol(unittest.TestCase):
    def test_messages_survive_being_split_and_joined(self):
        reader = LineReader()
        raw = encode({"t": "join", "name": "ANN"}) + encode({"t": "skip", "index": 2})
        self.assertEqual(reader.feed(raw[:9]), [])
        self.assertEqual(reader.feed(raw[9:]), [{"t": "join", "name": "ANN"},
                                                {"t": "skip", "index": 2}])
        self.assertEqual(reader.feed(b"not json\n[1, 2]\n" + encode({"t": "leave"})),
                         [{"t": "leave"}])

    def test_lobby_codes(self):
        code = make_code(random.Random(1))
        self.assertEqual(len(code), CODE_LENGTH)
        self.assertTrue(all(ch in CODE_ALPHABET for ch in code))

    def test_addresses(self):
        self.assertEqual(parse_address(" 192.168.0.12 "), ("192.168.0.12", 47801))
        self.assertEqual(parse_address("192.168.0.12:5000"), ("192.168.0.12", 5000))
        for bad in ("", "host:port", "a b", "1.2.3.4:0", "1.2.3.4:99999"):
            self.assertIsNone(parse_address(bad))


class NetCase(unittest.TestCase):
    def setUp(self):
        support.qapp()
        self.clients = []
        self.host = None

    def tearDown(self):
        for client in self.clients:
            client.leave()
        if self.host is not None:
            self.host.close()
        pump(20)

    def open_host(self, mode=RACE_COLORING, duration=30.0):
        self.host = LobbyHost("YASEEN", mode, rng=random.Random(7), duration=duration,
                              **HOST_OPTIONS)
        self.assertTrue(self.host.listen())
        return self.host

    def join(self, name, code=None, host_key="", wait=True):
        client = LobbyClient()
        client.events = []
        client.rejected.connect(lambda reason: client.events.append(("rejected", reason)))
        client.closed.connect(lambda reason: client.events.append(("closed", reason)))
        client.ended.connect(lambda: client.events.append(("ended", None)))
        self.clients.append(client)
        client.connect_to("127.0.0.1", self.host.port, name,
                          self.host.code if code is None else code, host_key)
        if wait:
            wait_until(lambda: client.connected or client.events)
        return client

    def start_match(self, mode=RACE_COLORING, duration=30.0):
        host = self.open_host(mode, duration)
        me = self.join("yaseen", code="", host_key=host.host_key)
        ann = self.join("ann")
        me.start()
        self.assertTrue(wait_until(lambda: me.puzzle is not None and ann.puzzle is not None))
        return host, me, ann


class TestLobby(NetCase):
    def test_joining_needs_the_code_and_names_stay_unique(self):
        host = self.open_host()
        me = self.join("yaseen", code="", host_key=host.host_key)
        self.assertTrue(me.is_host)
        self.assertEqual(me.code, host.code)
        wrong = self.join("mallory", code="0000")
        self.assertEqual(wrong.events, [("rejected", "WRONG LOBBY CODE")])
        ann = self.join("ann", code=host.code.lower())
        twin = self.join("ann")
        self.assertTrue(wait_until(lambda: len(me.players) == 3))
        self.assertIsNone(ann.code)
        self.assertFalse(ann.is_host)
        self.assertEqual(sorted(p["name"] for p in me.players), ["ANN", "ANN 2", "YASEEN"])
        self.assertEqual({ann.name, twin.name}, {"ANN", "ANN 2"})
        self.assertEqual([p["name"] for p in me.players if p["host"]], ["YASEEN"])

    def test_bad_names_are_rejected(self):
        self.open_host()
        bad = self.join("<script>")
        self.assertEqual(bad.events[0][0], "rejected")

    def test_only_the_host_starts_and_only_with_two_players(self):
        host = self.open_host()
        me = self.join("yaseen", code="", host_key=host.host_key)
        errors = []
        me.error_received.connect(errors.append)
        me.start()
        self.assertTrue(wait_until(lambda: errors))
        self.assertIn("2 PLAYERS", errors[0])
        ann = self.join("ann")
        ann.start()
        pump(60)
        self.assertEqual(host.state, LOBBY)
        counts = []
        ann.countdown_started.connect(counts.append)
        me.start()
        self.assertTrue(wait_until(lambda: host.state in (COUNTDOWN, PLAYING)))
        self.assertFalse(host.describe()["open"])
        self.assertTrue(wait_until(lambda: host.state == PLAYING and counts))
        late = self.join("late")
        self.assertEqual(late.events, [("rejected", "THAT MATCH HAS ALREADY STARTED")])

    def test_host_sets_the_match_length(self):
        host = self.open_host(duration=None)
        self.assertEqual(host.minutes, 7)
        self.assertEqual(host.describe()["minutes"], 7)
        me = self.join("yaseen", code="", host_key=host.host_key)
        ann = self.join("ann")
        self.assertTrue(wait_until(lambda: ann.minutes == 7))
        ann.set_minutes(2)
        pump(60)
        self.assertEqual(host.minutes, 7)
        me.set_minutes(3)
        self.assertTrue(wait_until(lambda: ann.minutes == 3 and me.minutes == 3))
        me.set_minutes(500)
        self.assertTrue(wait_until(lambda: host.minutes == 30))
        me.set_minutes(0)
        self.assertTrue(wait_until(lambda: host.minutes == 1))
        self.assertEqual(host.describe()["minutes"], 1)
        me.start()
        self.assertTrue(wait_until(lambda: host.state == PLAYING and ann.duration))
        self.assertEqual(ann.duration, 60)
        self.assertGreater(ann.remaining(), 50)
        me.set_minutes(5)
        pump(60)
        self.assertEqual(host.minutes, 1)

    def test_planar_lobbies_default_to_ten_minutes(self):
        host = self.open_host(RACE_PLANAR, duration=None)
        self.assertEqual(host.minutes, 10)

    def test_countdown_is_cancelled_if_a_player_leaves(self):
        self.host = LobbyHost("YASEEN", RACE_COLORING, port=0, announce=False,
                              countdown_seconds=5)
        self.assertTrue(self.host.listen())
        me = self.join("yaseen", code="", host_key=self.host.host_key)
        ann = self.join("ann")
        me.start()
        self.assertTrue(wait_until(lambda: self.host.state == COUNTDOWN))
        ann.leave()
        self.assertTrue(wait_until(lambda: self.host.state == LOBBY))
        self.assertTrue(wait_until(lambda: len(me.players) == 1))


class TestMatch(NetCase):
    def test_same_graph_for_everyone_then_each_at_their_own_pace(self):
        host, me, ann = self.start_match()
        self.assertEqual(me.puzzle, ann.puzzle)
        self.assertGreater(me.remaining(), 25)
        first = me.puzzle
        me.submit(first["index"], solution(first))
        self.assertTrue(wait_until(lambda: me.puzzle["index"] == 1))
        self.assertEqual(ann.puzzle["index"], 0)
        self.assertTrue(wait_until(lambda: ann.my_row() is not None and ann.rows[0]["score"] == 1))
        self.assertEqual(ann.rows[0]["name"], "YASEEN")
        ann.submit(0, solution(first))
        self.assertTrue(wait_until(lambda: ann.puzzle["index"] == 1))
        self.assertEqual(ann.puzzle, me.puzzle)

    def test_wrong_colorings_are_refused(self):
        host, me, ann = self.start_match()
        replies = []
        ann.result_received.connect(replies.append)
        ann.submit(0, [0] * ann.puzzle["n"])
        self.assertTrue(wait_until(lambda: replies))
        self.assertFalse(replies[0]["ok"])
        self.assertEqual(ann.puzzle["index"], 0)

    def test_skips_move_on_and_too_many_disqualify(self):
        host, me, ann = self.start_match()
        replies = []
        ann.result_received.connect(replies.append)
        for count in range(1, 6):
            ann.skip(ann.puzzle["index"])
            self.assertTrue(wait_until(lambda: len(replies) == count))
        self.assertEqual([reply["dq"] for reply in replies], [False] * 4 + [True])
        self.assertEqual(ann.puzzle["index"], 4)
        self.assertTrue(wait_until(lambda: ann.my_row() and ann.my_row()["dq"]))
        self.assertEqual(ann.my_row()["score"], -15)

    def test_time_up_sends_results_and_reopens_the_lobby(self):
        host, me, ann = self.start_match(duration=0.4)
        me.submit(0, solution(me.puzzle))
        self.assertTrue(wait_until(lambda: me.results is not None and ann.results is not None))
        self.assertEqual(me.results["reason"], "time")
        rows = ann.results["rows"]
        self.assertEqual([(row["name"], row["rank"], row["dq"]) for row in rows],
                         [("YASEEN", 1, False), ("ANN", None, True)])
        self.assertTrue(wait_until(lambda: host.state == LOBBY and me.state == LOBBY))
        self.assertEqual(len(me.players), 2)
        self.assertTrue(host.describe()["open"])
        me.start()
        self.assertTrue(wait_until(lambda: host.state == PLAYING and ann.results is None))

    def test_a_guest_leaving_is_marked_and_the_match_goes_on(self):
        host, me, ann = self.start_match()
        ann.leave()
        self.assertTrue(wait_until(lambda: any(row["left"] for row in me.rows)))
        self.assertEqual(host.state, PLAYING)
        me.submit(0, solution(me.puzzle))
        self.assertTrue(wait_until(lambda: me.puzzle["index"] == 1))

    def test_the_host_leaving_ends_the_match_with_standings(self):
        host, me, ann = self.start_match()
        me.submit(0, solution(me.puzzle))
        self.assertTrue(wait_until(lambda: me.puzzle["index"] == 1))
        host.close()
        self.assertTrue(wait_until(lambda: ("closed", "THE HOST CLOSED THE LOBBY") in ann.events))
        self.assertEqual(ann.results["reason"], "host_left")
        self.assertEqual(ann.results["rows"][0]["name"], "YASEEN")
        self.assertFalse(ann.connected)

    def test_planar_match_has_no_skips_and_reports_layouts(self):
        host, me, ann = self.start_match(RACE_PLANAR, duration=0.6)
        replies = []
        ann.result_received.connect(replies.append)
        ann.skip(0)
        pump(80)
        self.assertEqual(ann.puzzle["index"], 0)
        me.submit(0, [list(p) for p in host.race.planar[0].solution])
        self.assertTrue(wait_until(lambda: me.puzzle["index"] == 1))
        self.assertTrue(wait_until(lambda: me.results is not None))
        entry = me.results["planar"][0]
        self.assertEqual(entry["best_name"], "YASEEN")
        self.assertEqual(len(entry["program_pos"]), entry["n"])
        self.assertEqual(me.results["rows"][0]["solved"], 1)


class TestDiscovery(unittest.TestCase):
    def test_announced_lobbies_are_listed_and_expire(self):
        support.qapp()
        port = random.randint(48000, 56000)
        info = {"id": "abc", "name": "YASEEN", "mode": RACE_COLORING, "players": 1, "max": 20,
                "port": 47801, "open": True}
        browser = LobbyBrowser(port=port)
        announcer = LobbyAnnouncer(lambda: dict(info), port=port)
        self.assertTrue(browser.start())
        announcer.start()
        self.assertTrue(wait_until(lambda: browser.lobbies()))
        found = browser.lobbies()[0]
        self.assertEqual((found["name"], found["mode"], found["port"]), ("YASEEN", "coloring", 47801))
        self.assertEqual(found["minutes"], 0)
        info["minutes"] = 12
        announcer.announce()
        self.assertTrue(wait_until(lambda: browser.lobbies()[0]["minutes"] == 12))
        self.assertTrue(found["address"])
        info["open"] = False
        announcer.announce()
        self.assertTrue(wait_until(lambda: not browser.lobbies()))
        info["open"] = True
        announcer.announce()
        self.assertTrue(wait_until(lambda: browser.lobbies()))
        announcer.stop()
        for entry in browser.found.values():
            entry["seen"] -= 60
        browser._prune()
        self.assertEqual(browser.lobbies(), [])
        browser.stop()


class TestMultiplayerScreens(UITestCase):
    def setUp(self):
        super().setUp()
        self.window.multiplayer.host_options = dict(HOST_OPTIONS, duration=30.0,
                                                    rng=random.Random(9))
        self.guests = []

    def tearDown(self):
        for guest in self.guests:
            guest.leave()
        self.window.multiplayer.leave()
        pump(20)
        super().tearDown()

    def screen(self, which):
        return self.window.screens[which]

    def create(self, mode=RACE_COLORING, name="yaseen"):
        self.window.show_screen(GameScreen.MULTIPLAYER)
        browse = self.screen(GameScreen.MULTIPLAYER)
        browse.name_input.setText(name)
        browse.mode_cards[mode].click()
        browse.on_create_clicked()
        self.assertTrue(wait_until(lambda: self.state.current_screen == GameScreen.LOBBY))
        return self.window.multiplayer

    def guest(self, name="ann"):
        controller = self.window.multiplayer
        client = LobbyClient()
        self.guests.append(client)
        client.connect_to("127.0.0.1", controller.host.port, name, controller.host.code)
        self.assertTrue(wait_until(lambda: client.connected))
        return client

    def race(self, mode=RACE_COLORING):
        controller = self.create(mode)
        ann = self.guest()
        self.assertTrue(wait_until(lambda: self.screen(GameScreen.LOBBY).start_btn.isEnabled()))
        self.screen(GameScreen.LOBBY).start_btn.click()
        self.assertTrue(wait_until(lambda: self.state.current_screen == GameScreen.RACE))
        screen = self.screen(GameScreen.RACE)
        self.assertTrue(wait_until(lambda: screen.puzzle is not None and ann.puzzle is not None))
        return controller, screen, ann

    def test_menu_has_multiplayer_below_play(self):
        menu = self.screen(GameScreen.MENU)
        texts = [b.text() for b in menu.findChildren(PixelButton)]
        self.assertEqual(texts[:3], ["PLAY", "MULTIPLAYER", "ACCESSORIES"])
        menu.multiplayer_btn.click()
        self.assertEqual(self.state.current_screen, GameScreen.MULTIPLAYER)

    def test_a_name_is_needed_and_remembered(self):
        self.window.show_screen(GameScreen.MULTIPLAYER)
        browse = self.screen(GameScreen.MULTIPLAYER)
        browse.name_input.setText("")
        browse.on_create_clicked()
        self.assertEqual(self.state.current_screen, GameScreen.MULTIPLAYER)
        self.assertIn("NAME", browse.notice_label.text())
        self.create(name="yaseen")
        self.assertEqual(self.window.settings.player_name, "YASEEN")

    def test_joining_needs_a_lobby_and_a_full_code(self):
        self.window.show_screen(GameScreen.MULTIPLAYER)
        browse = self.screen(GameScreen.MULTIPLAYER)
        browse.name_input.setText("ann")
        browse.on_join_clicked()
        self.assertIn("PICK A LOBBY", browse.notice_label.text())
        browse.manual_target = ("127.0.0.1", 1)
        browse.code_input.setText("ab")
        browse.on_join_clicked()
        self.assertIn("4 CHARACTERS", browse.notice_label.text())
        browse.code_input.setText("abcd")
        browse.on_join_clicked()
        self.assertTrue(wait_until(lambda: "COULD NOT REACH" in browse.notice_label.text(), 8000))
        self.assertEqual(self.state.current_screen, GameScreen.MULTIPLAYER)

    def test_host_lobby_shows_the_code_and_enables_start_with_two(self):
        controller = self.create()
        lobby = self.screen(GameScreen.LOBBY)
        self.assertIn(controller.host.code, lobby.code_label.text())
        self.assertIn("YASEEN'S LOBBY", lobby.title_label.text())
        self.assertFalse(lobby.start_btn.isEnabled())
        self.assertIn("AT LEAST 2", lobby.status_label.text())
        self.guest()
        self.assertTrue(wait_until(lambda: lobby.start_btn.isEnabled()))
        self.assertEqual(lobby.count_label.text(), "PLAYERS 2/20")
        self.assertEqual([label.text() for label in lobby.player_labels],
                         ["1. YASEEN  (HOST, YOU)", "2. ANN"])

    def test_host_changes_the_length_from_the_lobby(self):
        self.window.multiplayer.host_options.pop("duration")
        controller = self.create(RACE_PLANAR)
        lobby = self.screen(GameScreen.LOBBY)
        self.assertEqual(lobby.length_label.text(), "10 MIN")
        self.assertIn("10 MIN", lobby.mode_label.text())
        lobby.longer_btn.click()
        self.assertTrue(wait_until(lambda: lobby.length_label.text() == "11 MIN"))
        for _ in range(3):
            lobby.shorter_btn.click()
            pump(30)
        self.assertTrue(wait_until(lambda: controller.host.minutes == 8))
        guest = self.guest()
        self.assertTrue(wait_until(lambda: guest.minutes == 8))
        lobby.start_btn.click()
        self.assertTrue(wait_until(lambda: self.state.current_screen == GameScreen.RACE))
        self.assertEqual(controller.session.duration, 480)

    def test_guests_see_the_length_but_cannot_change_it(self):
        controller = self.create()
        other = self.MainWindow(self.state.__class__(
            achievement_system=self.state.achievement_system,
            leaderboard_system=self.state.leaderboard_system))
        other.show()
        try:
            other.multiplayer.join_lobby("127.0.0.1", controller.host.port, "ann",
                                         controller.host.code)
            self.assertTrue(wait_until(lambda: other.game_state.current_screen == GameScreen.LOBBY))
            lobby = other.screens[GameScreen.LOBBY]
            self.assertTrue(lobby.longer_btn.isHidden() and lobby.shorter_btn.isHidden())
            self.assertEqual(lobby.length_label.text(), "7 MIN")
            controller.session.set_minutes(4)
            self.assertTrue(wait_until(lambda: lobby.length_label.text() == "4 MIN"))
        finally:
            other.multiplayer.leave()
            other.close()
            other.deleteLater()
            pump(20)

    def test_s_selects_a_vertex_in_a_planar_race_instead_of_skipping(self):
        controller, screen, ann = self.race(RACE_PLANAR)
        self.assertFalse(screen.skip_shortcut.isEnabled())
        screen.paper.setFocus()
        screen.paper.selected = None
        QTest.keyClick(screen.paper, Qt.Key.Key_S)
        self.assertIsNotNone(screen.paper.selected)
        self.assertEqual(screen.my_row()["skips"], 0)

    def test_coloring_race_solving_loads_the_next_graph(self):
        controller, screen, ann = self.race()
        self.assertTrue(screen.is_coloring())
        self.assertFalse(screen.palette_box.isHidden())
        self.assertIn("SKIP", screen.action_btn.text())
        first = screen.puzzle
        for vertex, color in enumerate(solution(first)):
            screen.canvas.color_vertex(vertex, color)
        self.assertTrue(wait_until(lambda: screen.puzzle["index"] == 1))
        self.assertTrue(wait_until(lambda: "SOLVED: 1" in screen.mine_label.text()))
        self.assertTrue(screen.canvas.interactive)
        self.assertEqual(screen.scoreboard.cells[0][1].text(), "YASEEN")
        self.assertEqual(screen.scoreboard.cells[0][2].text(), "1")
        self.assertTrue(screen.scoreboard.cells[2][0].isHidden())

    def test_skip_shows_its_cost_and_warns_before_disqualifying(self):
        controller, screen, ann = self.race()
        asked = []
        screen.confirm_fatal_skip = lambda: asked.append(True) or False
        for expected in (1, 2, 3, 4):
            self.assertIn(f"-{expected}", screen.action_btn.text())
            before = screen.puzzle["index"]
            screen.on_skip()
            self.assertTrue(wait_until(lambda: screen.puzzle["index"] == before + 1))
            self.assertTrue(wait_until(lambda: screen.my_row()["skips"] == expected))
        self.assertEqual(asked, [])
        self.assertEqual(screen.my_row()["score"], -10)
        screen.on_skip()
        self.assertEqual(asked, [True])
        self.assertFalse(screen.out)
        screen.confirm_fatal_skip = lambda: True
        screen.on_skip()
        self.assertTrue(wait_until(lambda: screen.out))
        self.assertFalse(screen.canvas.interactive)
        self.assertFalse(screen.action_btn.isEnabled())
        self.assertIn("DISQUALIFIED", screen.message_label.text())

    def test_planar_race_submits_layouts_and_shows_them_in_results(self):
        self.window.multiplayer.host_options["duration"] = 1.2
        controller, screen, ann = self.race(RACE_PLANAR)
        self.assertFalse(screen.is_coloring())
        self.assertTrue(screen.palette_box.isHidden())
        self.assertEqual(screen.action_btn.text(), "SUBMIT (ENTER)")
        self.assertFalse(screen.action_btn.isEnabled())
        answer = controller.host.race.planar[0].solution
        screen.paper.set_positions(answer)
        self.assertTrue(screen.action_btn.isEnabled())
        screen.on_submit_planar()
        self.assertTrue(wait_until(lambda: screen.puzzle["index"] == 1))
        self.assertEqual(screen.my_layouts[0]["pos"], list(answer))
        self.assertTrue(wait_until(lambda: self.state.current_screen == GameScreen.RACE_RESULTS))
        results = self.screen(GameScreen.RACE_RESULTS)
        self.assertEqual(results.title_label.text(), "YOU WIN!")
        self.assertFalse(results.layouts_tab.isHidden())
        self.assertEqual(results.table.item(0, 1).text(), "YASEEN")
        self.assertEqual(results.table.item(1, 5).text(), "DISQUALIFIED")
        self.assertEqual(len(results.cards), 2)

    def test_results_lead_back_to_the_lobby_for_a_rematch(self):
        self.window.multiplayer.host_options["duration"] = 0.5
        controller, screen, ann = self.race()
        self.assertTrue(wait_until(lambda: self.state.current_screen == GameScreen.RACE_RESULTS))
        results = self.screen(GameScreen.RACE_RESULTS)
        self.assertEqual(results.title_label.text(), "NO WINNER")
        self.assertTrue(results.layouts_tab.isHidden())
        self.assertTrue(wait_until(lambda: results.lobby_btn.isEnabled()))
        results.lobby_btn.click()
        self.assertEqual(self.state.current_screen, GameScreen.LOBBY)
        lobby = self.screen(GameScreen.LOBBY)
        self.assertTrue(wait_until(lambda: lobby.start_btn.isEnabled()))
        lobby.start_btn.click()
        self.assertTrue(wait_until(lambda: self.state.current_screen == GameScreen.RACE))

    def test_leaving_as_host_closes_the_lobby_for_guests(self):
        controller, screen, ann = self.race()
        closed = []
        ann.closed.connect(closed.append)
        screen.confirm_leave = lambda: True
        screen.on_leave_clicked()
        self.assertEqual(self.state.current_screen, GameScreen.MULTIPLAYER)
        self.assertIsNone(controller.session)
        self.assertIsNone(controller.host)
        self.assertTrue(wait_until(lambda: closed))
        self.assertEqual(ann.results["reason"], "host_left")

    def test_guide_explains_multiplayer(self):
        text = HowToPlayDialog(self.screen(GameScreen.MENU)).text.text()
        self.assertIn("MULTIPLAYER", text)
        self.assertIn("JOIN BY ADDRESS", text)


if __name__ == "__main__":
    unittest.main()
