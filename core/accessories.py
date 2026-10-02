import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Set

from core import constants
from core.storage import load_json, save_json

CURSOR, VERTEX = "cursor", "vertex"
KINDS = (CURSOR, VERTEX)
DEFAULT = "default"
ASSET_DIR = os.path.join(constants.PROJECT_ROOT, "assets", "accessories")


@dataclass(frozen=True)
class Accessory:
    id: str
    kind: str
    name: str
    price: int

    @property
    def path(self) -> Optional[str]:
        if self.id == DEFAULT:
            return None
        return os.path.join(ASSET_DIR, self.kind, f"{self.id}.png")


CATALOG: List[Accessory] = [
    Accessory(DEFAULT, CURSOR, "DEFAULT", 0),
    Accessory("hand", CURSOR, "HAND", 45000),
    Accessory("sparkle", CURSOR, "SPARKLE", 60000),
    Accessory("pin", CURSOR, "PIN", 90000),
    Accessory("lollipop", CURSOR, "LOLLIPOP", 120000),
    Accessory("pizza", CURSOR, "PIZZA", 150000),
    Accessory("sword", CURSOR, "SWORD", 200000),
    Accessory(DEFAULT, VERTEX, "DEFAULT", 0),
    Accessory("heart", VERTEX, "HEART", 45000),
    Accessory("bow", VERTEX, "BOW", 60000),
    Accessory("star", VERTEX, "STAR", 90000),
    Accessory("block", VERTEX, "BLOCK", 120000),
    Accessory("ghost", VERTEX, "GHOST", 150000),
    Accessory("pokeball", VERTEX, "POKEBALL", 200000),
]


def items_of(kind: str) -> List[Accessory]:
    return [item for item in CATALOG if item.kind == kind]


def find(kind: str, item_id: str) -> Optional[Accessory]:
    return next((item for item in CATALOG if item.kind == kind and item.id == item_id), None)


class Wallet:
    FILE_NAME = "wallet.json"

    def __init__(self, path: Optional[str] = None):
        self.path = path or os.path.join(constants.DATA_DIR, self.FILE_NAME)
        self.balance = 0
        self.owned: Dict[str, Set[str]] = {kind: {DEFAULT} for kind in KINDS}
        self.equipped: Dict[str, str] = {kind: DEFAULT for kind in KINDS}
        self.load()

    def load(self):
        data = load_json(self.path, {})
        if not isinstance(data, dict):
            return
        try:
            self.balance = max(0, int(data.get("balance", 0)))
        except (TypeError, ValueError):
            self.balance = 0
        owned = data.get("owned") if isinstance(data.get("owned"), dict) else {}
        equipped = data.get("equipped") if isinstance(data.get("equipped"), dict) else {}
        for kind in KINDS:
            names = owned.get(kind) if isinstance(owned.get(kind), list) else []
            self.owned[kind] = {DEFAULT} | {n for n in names if find(kind, str(n)) is not None}
            choice = equipped.get(kind)
            self.equipped[kind] = choice if choice in self.owned[kind] else DEFAULT

    def save(self) -> bool:
        return save_json(self.path, {
            "balance": self.balance,
            "owned": {kind: sorted(self.owned[kind] - {DEFAULT}) for kind in KINDS},
            "equipped": dict(self.equipped),
        })

    def add(self, points: int):
        if points > 0:
            self.balance += int(points)
            self.save()

    def owns(self, item: Accessory) -> bool:
        return item.id in self.owned[item.kind]

    def is_equipped(self, item: Accessory) -> bool:
        return self.equipped[item.kind] == item.id

    def missing_for(self, item: Accessory) -> int:
        return max(0, item.price - self.balance)

    def buy(self, item: Accessory) -> Optional[str]:
        if self.owns(item):
            return "You already own this."
        if self.missing_for(item):
            return f"Not enough points (need {self.missing_for(item):,} more)."
        self.balance -= item.price
        self.owned[item.kind].add(item.id)
        self.equipped[item.kind] = item.id
        self.save()
        return None

    def equip(self, item: Accessory) -> bool:
        if not self.owns(item):
            return False
        self.equipped[item.kind] = item.id
        self.save()
        return True
