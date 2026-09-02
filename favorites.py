from __future__ import annotations

import json
import threading
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
FAVORITES_FILE = BASE_DIR / ".favorites.json"
FAVORITES_LOCK = threading.Lock()
Favorite = tuple[int, str]


def load_favorites() -> set[Favorite]:
    with FAVORITES_LOCK:
        return _load_favorites()


def toggle_favorite(root_index: int, relative: str) -> bool:
    favorite = (root_index, relative)
    with FAVORITES_LOCK:
        favorites = _load_favorites()
        if favorite in favorites:
            favorites.remove(favorite)
            enabled = False
        else:
            favorites.add(favorite)
            enabled = True
        _save_favorites(favorites)
    return enabled


def _load_favorites() -> set[Favorite]:
    try:
        payload = json.loads(FAVORITES_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return set()

    if not isinstance(payload, list):
        return set()

    favorites: set[Favorite] = set()
    for item in payload:
        if not isinstance(item, dict):
            continue
        root_index = item.get("root")
        relative = item.get("path")
        if isinstance(root_index, int) and isinstance(relative, str) and relative:
            favorites.add((root_index, relative))
    return favorites


def _save_favorites(favorites: set[Favorite]) -> None:
    payload = [
        {"root": root_index, "path": relative}
        for root_index, relative in sorted(favorites)
    ]
    temporary = FAVORITES_FILE.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary.replace(FAVORITES_FILE)
