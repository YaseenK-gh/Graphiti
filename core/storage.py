import json
import logging
import os
from typing import Any

logger = logging.getLogger(__name__)


def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as e:
        backup = path + ".corrupt"
        logger.warning("Could not read %s (%s); moving it to %s and starting fresh", path, e, backup)
        try:
            os.replace(path, backup)
        except OSError:
            pass
        return default


def save_json(path: str, data: Any) -> bool:
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
        return True
    except OSError as e:
        logger.error("Could not save %s: %s", path, e)
        return False
