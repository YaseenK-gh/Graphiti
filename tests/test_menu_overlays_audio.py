from tests import support

import os
import random
import tempfile
import unittest

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import QLabel

from algorithms.solvers import compute_chromatic_number
from core.constants import DIFFICULTY_CONFIG, GRAPH_CONSTRAINTS
from core.game_state import GameScreen
from core.graph_manager import GraphManager
from core.settings import Settings
from ui.audio import shuffled_order, track_name
from ui.dialogs import HowToPlayDialog, PauseDialog, VolumeDialog
from ui.overlay import Overlay, confirm
from ui.widgets.pixel import PixelButton, PixelIconButton
from tests.test_ui_flow import UITestCase, pump


class TestDifficultyGroups(unittest.TestCase):
    def test_groups_and_counts(self):
        self.assertEqual(DIFFICULTY_CONFIG['EASY']['graph_types'],
                         ['PATH', 'TREE', 'BIPARTITE', 'CYCLE', 'COMPLETE_BIPARTITE'])
        self.assertEqual(DIFFICULTY_CONFIG['MEDIUM']['graph_types'],
                         ['WHEEL', 'OUTERPLANAR', 'TRIANGLE_FREE'])
        self.assertEqual(DIFFICULTY_CONFIG['HARD']['graph_types'],
                         ['CHORDAL', 'NEAR_TRIANGULATION', 'PLANAR'])
        for difficulty, config in DIFFICULTY_CONFIG.items():
            queue = GraphManager.generate_queue_for_difficulty(difficulty, random.Random(1))
            self.assertEqual(len(queue), config['num_graphs'])
            for graph_type in config['graph_types']:
                self.assertEqual(queue.count(graph_type), config['graphs_per_type'])
        self.assertEqual(DIFFICULTY_CONFIG['EASY']['num_graphs'], 10)

    def test_easy_is_two_colorable_except_odd_cycles(self):
        for graph_type in DIFFICULTY_CONFIG['EASY']['graph_types']:
            lo, hi = GRAPH_CONSTRAINTS[graph_type]
            for n in (lo + 1, lo + 2, hi):
                graph = GraphManager.generate_graph(graph_type, n)
                expected = 3 if graph_type == 'CYCLE' and n % 2 else 2
                with self.subTest(type=graph_type, n=n):
                    self.assertEqual(compute_chromatic_number(graph_type, n, graph.edges), expected)


class TestSettingsAndMusic(unittest.TestCase):
    def test_settings_roundtrip_and_clamping(self):
        path = os.path.join(tempfile.mkdtemp(dir=support.TEST_DATA_DIR), "settings.json")
        settings = Settings.load(path)
        self.assertEqual((settings.volume, settings.muted), (60, False))
        settings.volume, settings.muted = 25, True
        settings.save()
        self.assertEqual((Settings.load(path).volume, Settings.load(path).muted), (25, True))
        with open(path, "w") as f:
            f.write('{"volume": 900, "muted": 0}')
        self.assertEqual(Settings.load(path).volume, 100)

    def test_shuffle_plays_every_track_without_back_to_back_repeats(self):
        tracks = ["a.mp3", "b.mp3", "c.mp3", "d.mp3"]
        rng = random.Random(3)
        last = None
        for _ in range(50):
            order = shuffled_order(tracks, rng, avoid_first=last)
            self.assertEqual(sorted(order), tracks)
            self.assertNotEqual(order[0], last)
            last = order[-1]
        self.assertEqual(shuffled_order(["solo.mp3"], rng, "solo.mp3"), ["solo.mp3"])

    def test_track_names(self):
        self.assertEqual(track_name("/x/kevin-macleod-pixelland.mp3"), "KEVIN MACLEOD - PIXELLAND")
        self.assertEqual(track_name("/x/new-song.mp3"), "NEW SONG")


class TestMenuAndOverlays(UITestCase):
    def test_menu_layout(self):
        menu = self.screen(GameScreen.MENU)
        texts = [b.text() for b in menu.findChildren(PixelButton)]
        self.assertEqual(texts, ["PLAY", "LEADERBOARD", "QUIT"])
        self.assertEqual([b.icon_name for b in menu.findChildren(PixelButton)], ["play", "star", "close"])
        icons = {b.icon_name for b in menu.findChildren(PixelIconButton)}
        self.assertEqual(icons, {"guide", "trophy", "sound"})
        guide, achievements, volume = menu.guide_btn, menu.achievements_btn, menu.volume_btn
        self.assertLess(guide.x(), menu.width() / 2)
        self.assertLess(achievements.x(), menu.width() / 2)
        self.assertGreater(volume.x(), menu.width() / 2)
        self.assertEqual(self.window.windowTitle(), "Graphiti")

    def test_overlays_live_inside_the_window(self):
        overlay = PauseDialog(self.screen(GameScreen.PLAYING))
        self.assertIs(overlay.parentWidget(), self.window.overlay_host)
        self.assertFalse(overlay.isWindow())
        overlay.open()
        pump(250)
        self.assertEqual(overlay.geometry(), self.window.overlay_host.rect())
        overlay.reject()

    def test_confirm_returns_the_choice(self):
        menu = self.screen(GameScreen.MENU)
        QTimer.singleShot(50, lambda: self._click_overlay("yes_btn"))
        self.assertTrue(confirm(menu, "Sure?", "Really?"))
        QTimer.singleShot(50, lambda: self._click_overlay("no_btn"))
        self.assertFalse(confirm(menu, "Sure?", "Really?"))

    def _click_overlay(self, name):
        for overlay in self.window.overlay_host.findChildren(Overlay):
            if overlay.isVisible():
                getattr(overlay, name).click()

    def test_volume_dialog_updates_and_saves_settings(self):
        settings = Settings.load(os.path.join(tempfile.mkdtemp(dir=support.TEST_DATA_DIR), "s.json"))
        self.window.settings = settings
        menu = self.screen(GameScreen.MENU)
        dialog = VolumeDialog(settings, None, menu, on_change=menu.update_volume_icon)
        dialog.slider.setValue(35)
        self.assertEqual(dialog.value_label.text(), "35%")
        dialog.toggle_mute()
        self.assertEqual(dialog.value_label.text(), "OFF")
        self.assertEqual(menu.volume_btn.icon_name, "muted")
        dialog.accept()
        reloaded = Settings.load(settings.path)
        self.assertEqual((reloaded.volume, reloaded.muted), (35, True))

    def test_guide_explains_palette_keys_without_bold(self):
        dialog = HowToPlayDialog(self.window)
        from ui.dialogs import guide_html
        html = guide_html()
        self.assertIn("keys 1 to 5", html)
        self.assertNotIn("KEY 0", html)
        self.assertNotIn("<b>", html)
        self.assertEqual(dialog.text.textFormat(), Qt.TextFormat.RichText)
        self.assertNotIn("&lt;", QLabel.text(dialog.text))
        dialog.reject()

    def test_palette_swatches_have_no_numbers(self):
        playing = self.screen(GameScreen.PLAYING)
        self.assertTrue(all(swatch.text() == "" for swatch in playing.color_buttons))

    def test_panels_follow_window_width(self):
        menu = self.screen(GameScreen.MENU)
        panel = menu._fitted[0][0]
        self.window.resize(1200, 760)
        pump(50)
        small = panel.width()
        self.window.resize(1700, 900)
        pump(50)
        self.assertGreater(panel.width(), small)


if __name__ == '__main__':
    unittest.main()


class TestPlainText(unittest.TestCase):

    def test_game_code_is_ascii_only(self):
        import glob
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        for path in [os.path.join(root, "main.py")] + glob.glob(os.path.join(root, "*", "**", "*.py"),
                                                                recursive=True):
            if os.sep + "tests" + os.sep in path:
                continue
            with self.subTest(path=path):
                open(path, encoding="utf-8").read().encode("ascii")
