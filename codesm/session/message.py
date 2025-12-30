"""Message models for session management"""

from dataclasses import dataclass, field
from typing import Any, Literal
from datetime import datetime


@dataclass
class Message:
    """Represents a single message in the conversation"""
    role: Literal["user", "assistant", "system", "tool"]
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: dict[str, Any] = field(default_factory=dict)
    tool_call_id: str | None = None
    tool_calls: list[dict] | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for LLM API"""
        result = {
            "role": self.role,
            "content": self.content,
        }
        if self.tool_call_id:
            result["tool_call_id"] = self.tool_call_id
        if self.tool_calls:
            result["tool_calls"] = self.tool_calls
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        """Create from dictionary"""
        return cls(
            role=data["role"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data.get("timestamp", datetime.now().isoformat())),
            metadata=data.get("metadata", {}),
            tool_call_id=data.get("tool_call_id"),
            tool_calls=data.get("tool_calls"),
        )


@dataclass
class ToolCall:
    """Represents a tool call request from the LLM"""
    id: str
    name: str
    arguments: dict[str, Any]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "arguments": self.arguments,
        }


@dataclass
class ToolResult:
    """Represents the result of a tool execution"""
    tool_call_id: str
    content: str
    error: str | None = None

    def to_dict(self) -> dict:
        result = {
            "tool_call_id": self.tool_call_id,
            "content": self.content,
        }
        if self.error:
            result["error"] = self.error
        return result
