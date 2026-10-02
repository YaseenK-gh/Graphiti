import os
from dataclasses import asdict, dataclass

from core import constants
from core.storage import load_json, save_json

DEFAULT_VOLUME = 60


@dataclass
class Settings:
    volume: int = DEFAULT_VOLUME
    muted: bool = False
    player_name: str = ""
    path: str = ""

    @classmethod
    def load(cls, path: str = None) -> "Settings":
        path = path or os.path.join(constants.DATA_DIR, "settings.json")
        data = load_json(path, {})
        if not isinstance(data, dict):
            data = {}
        volume = data.get("volume", DEFAULT_VOLUME)
        volume = max(0, min(100, int(volume))) if isinstance(volume, (int, float)) else DEFAULT_VOLUME
        name = data.get("player_name", "")
        name = name[:constants.PLAYER_NAME_MAX_LEN] if isinstance(name, str) else ""
        return cls(volume=volume, muted=bool(data.get("muted", False)), player_name=name,
                   path=path)

    def save(self) -> bool:
        data = asdict(self)
        data.pop("path")
        return save_json(self.path, data)
