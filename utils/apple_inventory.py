from __future__ import annotations

import json
import os
import threading
from pathlib import Path


DEFAULT_STORE_PATH = Path(__file__).resolve().parents[1] / "data" / "apple_inventory.json"
STORE_PATH = Path(os.getenv("APPLE_INVENTORY_FILE") or DEFAULT_STORE_PATH).expanduser()
VALID_ITEMS = {"common", "ripe", "golden", "rotten", "arthur", "sock", "watermelon", "air"}
_lock = threading.Lock()


class InventoryStoreError(Exception):
    """Raised when the inventory cannot be read or persisted safely."""


class AppleInventoryStore:
    def __init__(self, path: Path = STORE_PATH):
        self.path = path

    def _load(self) -> dict[str, dict[str, int]]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return {}
        except (OSError, json.JSONDecodeError) as exc:
            raise InventoryStoreError("Could not read inventory") from exc

        if not isinstance(raw, dict):
            raise InventoryStoreError("Inventory data must be a JSON object")

        inventory: dict[str, dict[str, int]] = {}
        for user_id, items in raw.items():
            if not isinstance(user_id, str) or not isinstance(items, dict):
                continue
            valid_counts = {
                item: count
                for item, count in items.items()
                if item in VALID_ITEMS and isinstance(count, int) and not isinstance(count, bool) and count > 0
            }
            if valid_counts:
                inventory[user_id] = valid_counts
        return inventory

    def _save(self, inventory: dict[str, dict[str, int]]) -> None:
        temporary_path = self.path.with_suffix(self.path.suffix + ".tmp")
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path.write_text(
                json.dumps(inventory, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            temporary_path.replace(self.path)
        except OSError as exc:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
            raise InventoryStoreError("Could not save inventory") from exc

    def add(self, user_id: int, item: str) -> None:
        if item not in VALID_ITEMS:
            raise ValueError(f"Unknown inventory item: {item}")
        with _lock:
            inventory = self._load()
            user_items = inventory.setdefault(str(user_id), {})
            user_items[item] = user_items.get(item, 0) + 1
            self._save(inventory)

    def get(self, user_id: int) -> dict[str, int]:
        with _lock:
            return self._load().get(str(user_id), {}).copy()