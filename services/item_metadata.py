from __future__ import annotations

from dataclasses import dataclass
import re
from threading import Lock
from typing import Any

import httpx

DEFAULT_ITEM_SOURCE = "https://raw.githubusercontent.com/ao-data/ao-bin-dumps/master/items.json"
RENDER_BASE = "https://render.albiononline.com/v1/item"


@dataclass(frozen=True)
class ItemMetadata:
    item_id: str
    item_name: str | None
    tier: int | None
    enchantment: int
    category: str | None
    subcategory: str | None
    source: str
    icon_url: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "item_name": self.item_name,
            "tier": self.tier,
            "enchantment": self.enchantment,
            "category": self.category,
            "subcategory": self.subcategory,
            "source": self.source,
            "icon": self.icon_url,
        }


class ItemMetadataService:
    """Loads the public ao-bin-dumps item dictionary on demand.

    The source is intentionally fetched lazily so an unavailable metadata host
    never prevents the FastAPI application from starting. Loaded metadata is
    kept in memory for the lifetime of the process.
    """

    def __init__(self, source_url: str = DEFAULT_ITEM_SOURCE, timeout: float = 30.0):
        self.source_url = source_url
        self.timeout = timeout
        self._items: dict[str, ItemMetadata] | None = None
        self._lock = Lock()
        self.last_error: str | None = None

    @staticmethod
    def _tier(item_id: str) -> int | None:
        match = re.match(r"^T(\d+)(?:_|$)", item_id)
        return int(match.group(1)) if match else None

    @staticmethod
    def _enchantment(item_id: str) -> int:
        try:
            return int(item_id.rsplit("@", 1)[1]) if "@" in item_id else 0
        except ValueError:
            return 0

    @staticmethod
    def _first(mapping: dict[str, Any], *keys: str) -> Any:
        for key in keys:
            if mapping.get(key) not in (None, ""):
                return mapping[key]
        return None

    @classmethod
    def _localized_name(cls, raw: Any) -> str | None:
        if not isinstance(raw, dict):
            return raw if isinstance(raw, str) else None
        for key in ("KO-KR", "ko-KR", "EN-US", "en-US"):
            value = raw.get(key)
            if value:
                return str(value)
        for value in raw.values():
            if value:
                return str(value)
        return None

    @classmethod
    def _iter_records(cls, payload: Any):
        if isinstance(payload, list):
            yield from (x for x in payload if isinstance(x, dict))
            return
        if not isinstance(payload, dict):
            return
        root = payload.get("items", payload)
        if isinstance(root, list):
            yield from (x for x in root if isinstance(x, dict))
            return
        if isinstance(root, dict):
            for value in root.values():
                if isinstance(value, dict):
                    yield value
                elif isinstance(value, list):
                    yield from (x for x in value if isinstance(x, dict))

    @classmethod
    def _parse(cls, payload: Any) -> dict[str, ItemMetadata]:
        result: dict[str, ItemMetadata] = {}
        for raw in cls._iter_records(payload):
            item_id = cls._first(raw, "UniqueName", "uniqueName", "@uniquename", "Type", "type")
            if not item_id:
                continue
            item_id = str(item_id)
            localized = cls._first(raw, "LocalizedNames", "localizedNames", "localized_names")
            category = cls._first(raw, "ShopCategory", "shopCategory", "@shopcategory")
            subcategory = cls._first(raw, "ShopSubcategory1", "shopSubcategory1", "@shopsubcategory1")
            metadata = ItemMetadata(
                item_id=item_id,
                item_name=cls._localized_name(localized),
                tier=cls._tier(item_id),
                enchantment=cls._enchantment(item_id),
                category=str(category) if category else None,
                subcategory=str(subcategory) if subcategory else None,
                source="ao-bin-dumps",
                icon_url=cls.icon_url(item_id),
            )
            result[item_id] = metadata
        return result

    @staticmethod
    def icon_url(item_id: str, quality: int = 1, size: int = 96) -> str:
        safe_id = str(item_id).strip()
        return f"{RENDER_BASE}/{safe_id}.png?quality={int(quality)}&size={int(size)}"

    def _load(self) -> dict[str, ItemMetadata]:
        with httpx.Client(timeout=self.timeout, follow_redirects=True) as client:
            response = client.get(self.source_url)
            response.raise_for_status()
            payload = response.json()
        parsed = self._parse(payload)
        if not parsed:
            raise ValueError("item metadata source contained no usable items")
        self.last_error = None
        return parsed

    def ensure_loaded(self) -> bool:
        if self._items is not None:
            return True
        with self._lock:
            if self._items is not None:
                return True
            try:
                self._items = self._load()
                return True
            except Exception as exc:
                self.last_error = str(exc)
                return False

    def search(self, query: str | None = None, *, tier: int | None = None,
               category: str | None = None, enchantment: int | None = None,
               limit: int = 30) -> list[ItemMetadata]:
        if not self.ensure_loaded():
            return []
        needle = query.strip().casefold() if query else ""
        items = self._items.values()
        matches = []
        for item in items:
            if needle and needle not in item.item_id.casefold() and needle not in (item.item_name or "").casefold():
                continue
            if tier is not None and item.tier != tier:
                continue
            if category and (item.category or "").casefold() != category.casefold():
                continue
            if enchantment is not None and item.enchantment != enchantment:
                continue
            matches.append(item)
        matches.sort(key=lambda x: ((x.item_name or x.item_id).casefold(), x.item_id))
        return matches[: max(1, min(limit, 100))]

    def get(self, item_id: str) -> ItemMetadata | None:
        if not self.ensure_loaded():
            return None
        return self._items.get(item_id)
