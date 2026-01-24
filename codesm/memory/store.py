"""Storage-backed persistence for memory items"""

from datetime import datetime

from ..storage.storage import Storage
from .models import MemoryItem


class MemoryStore:
    @staticmethod
    def _get_storage_key(project_id: str | None) -> list[str]:
        if project_id is None:
            return ["memory", "global", "items"]
        return ["memory", "project", project_id, "items"]

    def list(self, project_id: str | None = None) -> list[MemoryItem]:
        key = self._get_storage_key(project_id)
        data = Storage.read(key)
        if data is None:
            return []
        return [MemoryItem.from_dict(item) for item in data]

    def get(self, item_id: str, project_id: str | None = None) -> MemoryItem | None:
        items = self.list(project_id)
        for item in items:
            if item.id == item_id:
                return item
        return None

    def upsert(self, item: MemoryItem) -> None:
        items = self.list(item.project_id)

        existing_idx = None
        for idx, existing in enumerate(items):
            if (
                existing.text == item.text
                and existing.type == item.type
                and existing.project_id == item.project_id
            ):
                existing_idx = idx
                break

        if existing_idx is not None:
            item.id = items[existing_idx].id
            item.created_at = items[existing_idx].created_at
            item.updated_at = datetime.now().isoformat()
            items[existing_idx] = item
        else:
            items.append(item)

        key = self._get_storage_key(item.project_id)
        Storage.write(key, [i.to_dict() for i in items])

    def delete(self, item_id: str, project_id: str | None = None) -> None:
        items = self.list(project_id)
        items = [item for item in items if item.id != item_id]
        key = self._get_storage_key(project_id)
        Storage.write(key, [i.to_dict() for i in items])

    def prune(self, project_id: str | None = None, max_items: int = 500) -> None:
        items = self.list(project_id)
        if len(items) <= max_items:
            return

        items.sort(key=lambda x: x.usefulness, reverse=True)
        items = items[:max_items]

        key = self._get_storage_key(project_id)
        Storage.write(key, [i.to_dict() for i in items])
