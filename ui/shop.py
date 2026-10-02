from PySide6.QtCore import QPointF, QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QGridLayout, QHBoxLayout,
                               QSizePolicy, QStackedWidget, QWidget)

from core.accessories import CURSOR, DEFAULT, KINDS, VERTEX, Accessory, Wallet, items_of
from core.constants import (DEFAULT_NODE_FILL, PALETTE, UI_BAD_ON_LIGHT, UI_BG, UI_BORDER,
                            UI_BUTTON, UI_CARD, UI_DANGER_TEXT, UI_GOOD_ON_LIGHT, UI_INK, UI_LIME,
                            UI_MUTED_ON_LIGHT)
from ui.accessories import apply_wallet, preview_pixmap
from ui.fonts import body_font, pixel_font
from ui.overlay import Overlay, confirm
from ui.screens import make_button, make_divider, make_label
from ui.styles import GAP, GAP_TIGHT, SIZE_BODY, SIZE_SUBTITLE
from ui.widgets.grid_paper import draw_vertex
from ui.widgets.pixel import draw_bitmap, draw_block

TAB_NAMES = {CURSOR: "CURSOR", VERTEX: "VERTEX"}
KIND_WORDS = {CURSOR: "cursor", VERTEX: "vertex icon"}
COLUMNS = 4
PREVIEW_BOX = 72
PREVIEW_COLOR = PALETTE[4]
PREVIEW_COLORS = {"heart": PALETTE[0], "bow": PALETTE[6], "pokeball": PALETTE[0],
                  "star": PALETTE[2], "block": PALETTE[2]}
ARROW = ["#.......", "##......", "###.....", "####....", "#####...", "######..", "#######.",
         "########", "#####...", "##.##...", "#..##...", "....##..", "....##.."]


class AccessoryCard(QAbstractButton):
    SHADOW = 3
    BORDER = 3

    def __init__(self, item: Accessory, wallet: Wallet, parent=None):
        super().__init__(parent)
        self.item = item
        self.wallet = wallet
        self.setText(item.name)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

    def sizeHint(self) -> QSize:
        return QSize(190, 172)

    def minimumSizeHint(self) -> QSize:
        return QSize(150, 172)

    def status(self):
        if self.wallet.is_equipped(self.item):
            return "EQUIPPED", UI_GOOD_ON_LIGHT
        if self.wallet.owns(self.item):
            return "OWNED", UI_MUTED_ON_LIGHT
        affordable = not self.wallet.missing_for(self.item)
        return f"{self.item.price:,}", UI_INK if affordable else UI_BAD_ON_LIGHT

    def paintEvent(self, event):
        p = QPainter(self)
        equipped = self.wallet.is_equipped(self.item)
        fill = UI_LIME if equipped else UI_BUTTON if self.underMouse() else UI_CARD
        body = self.rect().adjusted(0, 0, -self.SHADOW, -self.SHADOW)
        if self.isDown():
            body.translate(self.SHADOW, self.SHADOW)
            draw_block(p, body, fill, UI_BORDER, self.BORDER)
        else:
            draw_block(p, body, fill, UI_BORDER, self.BORDER, self.SHADOW)

        centre_x = body.center().x()
        top = body.top() + 14
        pixmap = preview_pixmap(self.item.kind, self.item.id, PREVIEW_BOX,
                                PREVIEW_COLORS.get(self.item.id, PREVIEW_COLOR))
        if pixmap is not None:
            p.drawPixmap(centre_x - pixmap.width() // 2,
                         top + (PREVIEW_BOX - pixmap.height()) // 2, pixmap)
        elif self.item.kind == VERTEX:
            p.setRenderHint(QPainter.RenderHint.Antialiasing)
            draw_vertex(p, QPointF(centre_x, top + PREVIEW_BOX / 2), 22, DEFAULT_NODE_FILL,
                        plain=True)
            p.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        else:
            cell = 4
            draw_bitmap(p, ARROW, centre_x - len(ARROW[0]) * cell // 2,
                        top + (PREVIEW_BOX - len(ARROW) * cell) // 2, cell, UI_INK)

        name_top = top + PREVIEW_BOX + 10
        p.setFont(pixel_font(SIZE_SUBTITLE))
        p.setPen(QColor(UI_INK))
        p.drawText(QRect(body.left(), name_top, body.width(), SIZE_SUBTITLE + 4),
                   Qt.AlignmentFlag.AlignCenter, self.item.name)
        text, color = self.status()
        p.setFont(body_font(SIZE_BODY))
        p.setPen(QColor(color))
        p.drawText(QRect(body.left(), name_top + SIZE_SUBTITLE + 8, body.width(), SIZE_BODY + 6),
                   Qt.AlignmentFlag.AlignCenter, text)


class AccessoriesDialog(Overlay):
    def __init__(self, wallet: Wallet, parent=None, on_change=None):
        super().__init__(parent, width_fraction=0.74, min_width=940, max_width=1060)
        self.wallet = wallet
        self.on_change = on_change
        layout = self.layout_
        layout.addWidget(make_label("ACCESSORIES", role="title"))
        self.balance_label = make_label(role="badge")
        layout.addWidget(self.balance_label, alignment=Qt.AlignmentFlag.AlignCenter)

        tabs = QHBoxLayout()
        tabs.setSpacing(GAP)
        self.tab_group = QButtonGroup(self)
        self.tab_group.setExclusive(True)
        self.stack = QStackedWidget()
        self.cards = {}
        for index, kind in enumerate(KINDS):
            tab = make_button(TAB_NAMES[kind], variant="tab", small=True)
            tab.setCheckable(True)
            tab.clicked.connect(lambda _=False, i=index: self.stack.setCurrentIndex(i))
            self.tab_group.addButton(tab, index)
            tabs.addWidget(tab)
            self.stack.addWidget(self._build_page(kind))
        layout.addLayout(tabs)
        layout.addWidget(self.stack)
        self.tab_group.button(0).setChecked(True)

        self.message_label = make_label(role="body", wrap=True)
        layout.addWidget(self.message_label)
        layout.addWidget(make_divider(dark=True))
        layout.addWidget(make_button("CLOSE", self.accept, variant="dark", small=True, icon="close"))
        self.refresh()
        self.show_message("CLICK AN ITEM TO BUY IT. CLICK ONE YOU OWN TO EQUIP IT.")

    def _build_page(self, kind: str) -> QWidget:
        page = QWidget()
        grid = QGridLayout(page)
        grid.setContentsMargins(0, GAP_TIGHT, 0, 0)
        grid.setSpacing(GAP)
        for index, item in enumerate(items_of(kind)):
            card = AccessoryCard(item, self.wallet)
            card.clicked.connect(lambda _=False, chosen=item: self.on_item_clicked(chosen))
            self.cards[(kind, item.id)] = card
            grid.addWidget(card, index // COLUMNS, index % COLUMNS)
        for column in range(COLUMNS):
            grid.setColumnStretch(column, 1)
        return page

    def refresh(self):
        self.balance_label.setText(f"BALANCE: {self.wallet.balance:,}")
        for card in self.cards.values():
            card.update()

    def show_message(self, text: str, color: str = UI_BG):
        self.message_label.setText(text)
        self.message_label.setStyleSheet(f"color: {color};")

    def confirm_purchase(self, item: Accessory) -> bool:
        return confirm(self, f"Buy {item.name}?",
                       f"Spend {item.price:,} of your {self.wallet.balance:,} points on the "
                       f"{item.name} {KIND_WORDS[item.kind]}?", yes="BUY", no="CANCEL")

    def on_item_clicked(self, item: Accessory):
        wallet = self.wallet
        if wallet.is_equipped(item):
            self.show_message(f"{item.name} IS ALREADY EQUIPPED")
            return
        if wallet.owns(item):
            wallet.equip(item)
            self.applied(f"{item.name} EQUIPPED" if item.id != DEFAULT
                         else f"BACK TO THE DEFAULT {TAB_NAMES[item.kind]}")
            return
        missing = wallet.missing_for(item)
        if missing:
            self.show_message(f"NOT ENOUGH POINTS - YOU NEED {missing:,} MORE", UI_DANGER_TEXT)
            return
        if not self.confirm_purchase(item):
            return
        error = wallet.buy(item)
        if error:
            self.show_message(error.upper(), UI_DANGER_TEXT)
            return
        self.applied(f"{item.name} BOUGHT AND EQUIPPED")

    def applied(self, message: str):
        apply_wallet(self.wallet)
        self.refresh()
        self.show_message(message, UI_LIME)
        if self.on_change:
            self.on_change()
