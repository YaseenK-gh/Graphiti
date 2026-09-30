"""QMainWindow with a stacked widget of screens."""

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMainWindow, QStackedWidget, QVBoxLayout

from core.game_state import GameScreen, GameState
from ui.fonts import load_fonts
from ui.screens.difficulty_select_screen import DifficultySelectScreen
from ui.screens.free_complete_screen import FreeCompleteScreen
from ui.screens.free_graph_select_screen import FreeGraphSelectScreen
from ui.screens.menu_screen import MenuScreen
from ui.screens.mode_select_screen import ModeSelectScreen
from ui.screens.playing_screen import PlayingScreen
from ui.screens.post_difficulty_screen import PostDifficultyScreen
from ui.screens.post_level_screen import PostLevelScreen
from ui.screens.pre_game_screen import PreGameScreen
from ui.styles import get_stylesheet
from ui.widgets.pixel import PixelBackground


class MainWindow(QMainWindow):
    """Main application window with screen stack management."""

    def __init__(self, game_state: GameState = None):
        super().__init__()
        self.setWindowTitle("Graph Coloring — Color Theorem")
        self.setGeometry(100, 100, 1400, 820)
        self.setMinimumSize(1200, 760)

        load_fonts()
        # Game state (shared across all screens)
        self.game_state = game_state or GameState()

        background = PixelBackground()
        page = QVBoxLayout(background)
        page.setContentsMargins(16, 16, 16, 16)
        self.stacked_widget = QStackedWidget()
        page.addWidget(self.stacked_widget)
        self.setCentralWidget(background)

        self.screens = {
            GameScreen.MENU: MenuScreen(self),
            GameScreen.MODE_SELECT: ModeSelectScreen(self),
            GameScreen.DIFFICULTY_SELECT: DifficultySelectScreen(self),
            GameScreen.FREE_GRAPH_SELECT: FreeGraphSelectScreen(self),
            GameScreen.PRE_GAME: PreGameScreen(self),
            GameScreen.PLAYING: PlayingScreen(self),
            GameScreen.POST_LEVEL: PostLevelScreen(self),
            GameScreen.POST_DIFFICULTY: PostDifficultyScreen(self),
            GameScreen.FREE_COMPLETE: FreeCompleteScreen(self),
        }
        for screen in self.screens.values():
            self.stacked_widget.addWidget(screen)

        # 100ms tick for the live timer display.
        self.update_timer = QTimer(self)
        self.update_timer.timeout.connect(self.update_game)
        self.update_timer.start(100)

        self.setStyleSheet(get_stylesheet())
        self.show_screen(GameScreen.MENU)

    def show_screen(self, screen: GameScreen):
        """Transition to a new screen."""
        previous = self.game_state.current_screen
        if previous != screen and previous in self.screens:
            self.screens[previous].on_hide()
        self.game_state.current_screen = screen
        self.stacked_widget.setCurrentWidget(self.screens[screen])
        self.screens[screen].on_show()

    def update_game(self):
        if self.game_state.current_screen == GameScreen.PLAYING:
            self.screens[GameScreen.PLAYING].update_timer_display()
