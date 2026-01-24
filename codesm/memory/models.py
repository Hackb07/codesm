"""Memory item data model"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional

MemoryType = Literal["preference", "fact", "pattern", "solution"]


@dataclass
class MemoryItem:
    id: str
    type: MemoryType
    text: str
    project_id: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    source_session_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_used_at: Optional[str] = None
    usefulness: float = 0.0
    embedding: Optional[list[float]] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "text": self.text,
            "project_id": self.project_id,
            "tags": self.tags,
            "source_session_id": self.source_session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_used_at": self.last_used_at,
            "usefulness": self.usefulness,
            "embedding": self.embedding,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MemoryItem":
        return cls(
            id=data["id"],
            type=data["type"],
            text=data["text"],
            project_id=data.get("project_id"),
            tags=data.get("tags", []),
            source_session_id=data.get("source_session_id"),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            last_used_at=data.get("last_used_at"),
            usefulness=data.get("usefulness", 0.0),
            embedding=data.get("embedding"),
        )
