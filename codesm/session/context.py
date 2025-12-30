"""Context management and compaction for long conversations"""

from typing import List
from .message import Message


class ContextManager:
    """Manages conversation context and handles context window limits"""

    def __init__(self, max_tokens: int = 100000):
        self.max_tokens = max_tokens

    def should_compact(self, messages: List[Message]) -> bool:
        """Check if messages should be compacted"""
        # Rough estimate: ~4 chars per token
        total_chars = sum(len(m.content) for m in messages)
        estimated_tokens = total_chars // 4
        return estimated_tokens > self.max_tokens * 0.8

    def compact_messages(self, messages: List[Message]) -> List[Message]:
        """Compact messages to fit within context window"""
        if not self.should_compact(messages):
            return messages

        # Keep system message, recent messages, and summarize the middle
        system_messages = [m for m in messages if m.role == "system"]
        recent_messages = messages[-20:]  # Keep last 20 messages

        # For now, just return system + recent
        # TODO: Implement proper summarization using LLM
        result = system_messages + recent_messages

        # Remove duplicates while preserving order
        seen = set()
        compacted = []
        for m in result:
            msg_id = id(m)
            if msg_id not in seen:
                seen.add(msg_id)
                compacted.append(m)

        return compacted

    def estimate_tokens(self, messages: List[Message]) -> int:
        """Estimate token count for messages"""
        total_chars = sum(len(m.content) for m in messages)
        return total_chars // 4
