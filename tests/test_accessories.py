from tests import support

import os
import tempfile
import unittest

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

from core.accessories import CATALOG, CURSOR, DEFAULT, VERTEX, Wallet, find, items_of
from core.achievements import AchievementSystem
from core.constants import DEFAULT_NODE_STROKE
from core.game_state import GameScreen, GameState
from core.graph_manager import GraphManager
from core.leaderboard import LeaderboardSystem
from ui import accessories
from ui.dialogs import HowToPlayDialog
from ui.shop import AccessoriesDialog
from ui.widgets.pixel import PixelButton
from tests.test_ui_flow import UITestCase, pump

PRICES = {
    (VERTEX, "heart"): 45000, (VERTEX, "bow"): 60000, (VERTEX, "star"): 90000,
    (VERTEX, "block"): 120000, (VERTEX, "ghost"): 150000, (VERTEX, "pokeball"): 200000,
    (CURSOR, "hand"): 45000, (CURSOR, "sparkle"): 60000, (CURSOR, "pin"): 90000,
    (CURSOR, "lollipop"): 120000, (CURSOR, "pizza"): 150000, (CURSOR, "sword"): 200000,
}


def temp_wallet() -> Wallet:
    return Wallet(os.path.join(tempfile.mkdtemp(dir=support.TEST_DATA_DIR), "wallet.json"))


class TestCatalog(unittest.TestCase):
    def test_items_and_prices(self):
        priced = {(item.kind, item.id): item.price for item in CATALOG if item.id != DEFAULT}
        self.assertEqual(priced, PRICES)
        for kind in (CURSOR, VERTEX):
            self.assertEqual(items_of(kind)[0].id, DEFAULT)
            self.assertEqual(items_of(kind)[0].price, 0)

    def test_every_item_has_its_image_and_cursors_have_click_points(self):
        support.qapp()
        spots = accessories.cursor_hotspots()
        for item in CATALOG:
            if item.id == DEFAULT:
                continue
            with self.subTest(item=item.id):
                image = QImage(item.path)
                self.assertFalse(image.isNull())
                if item.kind == CURSOR:
                    x, y = spots[item.id]
                    self.assertTrue(0 <= x < image.width() and 0 <= y < image.height())
        self.assertEqual(spots["lollipop"][1], 0)

    def test_vertex_icon_takes_the_vertex_color(self):
        support.qapp()
        image = accessories.vertex_pixmap("pokeball", "#ff0000", 1).toImage()
        self.assertEqual(image.pixelColor(5, 3).name(), "#ff0000")
        self.assertEqual(image.pixelColor(5, 9).name(), "#ffffff")
        self.assertEqual(image.pixelColor(5, 0).name(), QColor(DEFAULT_NODE_STROKE).name())
        self.assertEqual(image.pixelColor(0, 0).alpha(), 0)


class TestWallet(unittest.TestCase):
    def test_starts_empty_with_defaults(self):
        wallet = temp_wallet()
        self.assertEqual(wallet.balance, 0)
        self.assertEqual(wallet.equipped, {CURSOR: DEFAULT, VERTEX: DEFAULT})
        self.assertTrue(wallet.owns(find(CURSOR, DEFAULT)))
        self.assertFalse(wallet.owns(find(VERTEX, "star")))

    def test_buying_needs_enough_points_and_equips(self):
        wallet = temp_wallet()
        star = find(VERTEX, "star")
        wallet.add(89999)
        self.assertIn("1 more", wallet.buy(star))
        self.assertFalse(wallet.equip(star))
        wallet.add(10001)
        self.assertIsNone(wallet.buy(star))
        self.assertEqual(wallet.balance, 10000)
        self.assertTrue(wallet.owns(star) and wallet.is_equipped(star))
        self.assertIsNotNone(wallet.buy(star))
        self.assertEqual(wallet.balance, 10000)

    def test_balance_and_items_survive_a_restart(self):
        wallet = temp_wallet()
        wallet.add(300000)
        wallet.buy(find(CURSOR, "sword"))
        wallet.buy(find(VERTEX, "heart"))
        wallet.equip(find(VERTEX, DEFAULT))
        again = Wallet(wallet.path)
        self.assertEqual(again.balance, 55000)
        self.assertEqual(again.owned[CURSOR], {DEFAULT, "sword"})
        self.assertEqual(again.owned[VERTEX], {DEFAULT, "heart"})
        self.assertEqual(again.equipped, {CURSOR: "sword", VERTEX: DEFAULT})

    def test_damaged_file_falls_back_to_defaults(self):
        wallet = temp_wallet()
        with open(wallet.path, "w", encoding="utf-8") as f:
            f.write('{"balance": "lots", "owned": {"vertex": ["dragon", "star"]}, '
                    '"equipped": {"vertex": "ghost", "cursor": 7}}')
        again = Wallet(wallet.path)
        self.assertEqual(again.balance, 0)
        self.assertEqual(again.owned[VERTEX], {DEFAULT, "star"})
        self.assertEqual(again.equipped, {CURSOR: DEFAULT, VERTEX: DEFAULT})

    def test_only_a_finished_standard_difficulty_earns_points(self):
        folder = tempfile.mkdtemp(dir=support.TEST_DATA_DIR)
        state = GameState(
            achievement_system=AchievementSystem.load(os.path.join(folder, "achievements.json")),
            leaderboard_system=LeaderboardSystem(os.path.join(folder, "leaderboard.json")),
            wallet=Wallet(os.path.join(folder, "wallet.json")))
        state.start_difficulty('EASY', ['PATH'])
        state.provisional_score = 4100
        result = state.finalize_difficulty()
        self.assertEqual(state.wallet.balance, result.banked_score)
        self.assertEqual(Wallet(state.wallet.path).balance, 4100)
        state.start_free_mode()
        state.start_planar_run()
        self.assertEqual(state.wallet.balance, 4100)


class TestAccessoriesShop(UITestCase):
    def setUp(self):
        super().setUp()
        self.state.wallet = temp_wallet()
        self.menu = self.window.screens[GameScreen.MENU]

    def tearDown(self):
        accessories.set_vertex_icon(DEFAULT)
        accessories.apply_cursor(DEFAULT)
        super().tearDown()

    def open_shop(self) -> AccessoriesDialog:
        dialog = AccessoriesDialog(self.state.wallet, self.menu, on_change=self.menu.update_stats)
        dialog.confirm_purchase = lambda item: True
        dialog.open()
        pump()
        return dialog

    def test_menu_opens_the_shop_below_play(self):
        texts = [b.text() for b in self.menu.findChildren(PixelButton)]
        self.assertEqual(texts.index("ACCESSORIES"), texts.index("MULTIPLAYER") + 1)
        self.assertLess(texts.index("ACCESSORIES"), texts.index("LEADERBOARD"))

    def test_cannot_buy_without_enough_points(self):
        self.state.wallet.add(1000)
        dialog = self.open_shop()
        dialog.on_item_clicked(find(CURSOR, "hand"))
        self.assertFalse(self.state.wallet.owns(find(CURSOR, "hand")))
        self.assertIn("44,000 MORE", dialog.message_label.text())
        self.assertEqual(self.state.wallet.balance, 1000)

    def test_declining_the_confirmation_buys_nothing(self):
        self.state.wallet.add(500000)
        dialog = self.open_shop()
        dialog.confirm_purchase = lambda item: False
        dialog.on_item_clicked(find(VERTEX, "ghost"))
        self.assertEqual(self.state.wallet.balance, 500000)
        self.assertEqual(accessories.vertex_icon(), DEFAULT)

    def test_buying_a_cursor_applies_it_and_default_removes_it(self):
        self.state.wallet.add(250000)
        dialog = self.open_shop()
        dialog.on_item_clicked(find(CURSOR, "sword"))
        self.assertEqual(self.state.wallet.balance, 50000)
        self.assertIn("50,000", dialog.balance_label.text())
        self.assertIn("50,000", self.menu.banked_label.text())
        self.assertEqual(accessories.current_cursor(), "sword")
        self.assertIsNotNone(QApplication.overrideCursor())
        dialog.on_item_clicked(find(CURSOR, DEFAULT))
        self.assertEqual(accessories.current_cursor(), DEFAULT)
        self.assertIsNone(QApplication.overrideCursor())
        self.assertTrue(self.state.wallet.owns(find(CURSOR, "sword")))

    def test_vertex_icon_replaces_the_circle_and_hides_letters(self):
        self.state.wallet.add(100000)
        dialog = self.open_shop()
        dialog.on_item_clicked(find(VERTEX, "star"))
        self.assertEqual(accessories.vertex_icon(), "star")

        def first_vertex():
            self.state.start_free_mode()
            self.state.begin_graph(GraphManager.generate_graph('CYCLE', 6))
            self.window.show_screen(GameScreen.PLAYING)
            pump()
            canvas = self.window.screens[GameScreen.PLAYING].canvas
            return canvas, canvas.vertex_items[0]

        canvas, vertex = first_vertex()
        self.assertIsNone(vertex.label_item)
        self.assertTrue(vertex.boundingRect().width() > 2 * vertex.radius)
        canvas.color_vertex(0, 2)
        self.assertEqual(canvas.coloring[0], 2)
        canvas.grab()

        self.window.show_screen(GameScreen.MENU)
        dialog.on_item_clicked(find(VERTEX, DEFAULT))
        canvas, vertex = first_vertex()
        self.assertIsNotNone(vertex.label_item)

    def test_guide_explains_accessories(self):
        text = HowToPlayDialog(self.menu).text.text()
        self.assertIn("ACCESSORIES", text)
        self.assertIn("balance", text)


if __name__ == "__main__":
    unittest.main()
