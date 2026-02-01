"""Context management and compaction for long conversations"""

from __future__ import annotations

import json
from typing import Callable, Any

# Try to use tiktoken for accurate token counting
try:
    import tiktoken
    _TIKTOKEN_AVAILABLE = True
    _ENCODING = tiktoken.get_encoding("cl100k_base")
except ImportError:
    _TIKTOKEN_AVAILABLE = False
    _ENCODING = None


class TokenEstimator:
    """Estimates token counts for messages"""

    def __init__(self):
        self.use_tiktoken = _TIKTOKEN_AVAILABLE
        self._encoding = _ENCODING

    def estimate_text(self, text: str) -> int:
        """Estimate tokens for a text string"""
        if not text:
            return 0
        if self.use_tiktoken and self._encoding:
            return len(self._encoding.encode(text))
        # Heuristic fallback: words * 1.3
        return int(len(text.split()) * 1.3)

    def estimate_message(self, msg: dict) -> int:
        """Estimate tokens for a single message dict"""
        if not msg:
            return 0

        tokens = 6  # Base overhead per message (role, formatting, etc.)

        # Handle content
        content = msg.get("content")
        if content:
            if isinstance(content, str):
                tokens += self.estimate_text(content)
            elif isinstance(content, list):
                # Multi-part content (e.g., with images)
                for part in content:
                    if isinstance(part, dict):
                        if part.get("type") == "text":
                            tokens += self.estimate_text(part.get("text", ""))
                        elif part.get("type") == "image_url":
                            tokens += 85  # Base image token estimate
                    elif isinstance(part, str):
                        tokens += self.estimate_text(part)

        # Handle tool_calls
        tool_calls = msg.get("tool_calls")
        if tool_calls:
            for tc in tool_calls:
                if isinstance(tc, dict):
                    func = tc.get("function", {})
                    tokens += self.estimate_text(func.get("name", ""))
                    args = func.get("arguments", "")
                    if isinstance(args, str):
                        tokens += self.estimate_text(args)
                    else:
                        tokens += self.estimate_text(json.dumps(args))
                    tokens += 10  # Overhead for tool_call structure

        # Handle tool_call_id (tool responses)
        if msg.get("tool_call_id"):
            tokens += 10

        # Handle name field
        if msg.get("name"):
            tokens += self.estimate_text(msg.get("name", ""))

        return tokens

    def estimate_messages(self, messages: list[dict]) -> int:
        """Estimate total tokens for a list of messages"""
        if not messages:
            return 0
        return sum(self.estimate_message(msg) for msg in messages)


class ContextManager:
    """Manages conversation context and handles context window limits"""

    def __init__(
        self,
        max_tokens: int = 128000,
        compact_trigger_ratio: float = 0.75,
        recent_budget_ratio: float = 0.4,
        summary_budget_tokens: int = 1500,
        min_messages_to_summarize: int = 5,
    ):
        self.max_tokens = max_tokens
        self.compact_trigger_ratio = compact_trigger_ratio
        self.recent_budget_ratio = recent_budget_ratio
        self.summary_budget_tokens = summary_budget_tokens
        self.min_messages_to_summarize = min_messages_to_summarize
        self.estimator = TokenEstimator()

    def should_compact(self, messages: list[dict]) -> bool:
        """Check if messages should be compacted based on token estimation"""
        if not messages:
            return False
        estimated_tokens = self.estimator.estimate_messages(messages)
        return estimated_tokens > self.max_tokens * self.compact_trigger_ratio

    def prune_tool_outputs(
        self,
        messages: list[dict],
        keep_recent: int = 4,
        max_output_chars: int = 4000,
    ) -> list[dict]:
        """
        Prune large tool outputs from older messages.
        
        - Keep the most recent `keep_recent` tool/tool_display messages unmodified
        - For older ones, if content > max_output_chars, replace with "[OUTPUT PRUNED: N chars]"
        - Keep message structure intact (tool_call_id, role, etc.)
        """
        if not messages:
            return []

        result = []
        
        # Find indices of tool response messages (role == "tool")
        tool_indices = [
            i for i, msg in enumerate(messages)
            if msg.get("role") == "tool"
        ]
        
        # Determine which tool messages to keep unmodified
        recent_tool_indices = set(tool_indices[-keep_recent:]) if tool_indices else set()

        for i, msg in enumerate(messages):
            if msg.get("role") != "tool":
                result.append(msg)
                continue

            # Tool message - check if it should be pruned
            if i in recent_tool_indices:
                result.append(msg)
                continue

            # Older tool message - check content size
            content = msg.get("content", "")
            if isinstance(content, str) and len(content) > max_output_chars:
                pruned_msg = msg.copy()
                pruned_msg["content"] = f"[OUTPUT PRUNED: {len(content)} chars]"
                result.append(pruned_msg)
            else:
                result.append(msg)

        return result

    def _extract_sections(
        self, messages: list[dict]
    ) -> tuple[list[dict], dict | None, list[dict]]:
        """
        Extract system messages, existing summary, and conversation messages.
        
        Returns:
            (system_messages, existing_summary, conversation_messages)
        """
        system_messages = []
        existing_summary = None
        conversation = []

        for msg in messages:
            if msg.get("role") == "system":
                if msg.get("_context_summary"):
                    existing_summary = msg
                else:
                    system_messages.append(msg)
            else:
                conversation.append(msg)

        return system_messages, existing_summary, conversation

    def _select_recent_messages(
        self, messages: list[dict], budget_tokens: int
    ) -> tuple[list[dict], list[dict]]:
        """
        Walk backward through messages to select recent ones within budget.
        
        Returns:
            (middle_messages, recent_messages)
        """
        if not messages:
            return [], []

        recent = []
        tokens_used = 0

        # Walk backward
        for msg in reversed(messages):
            msg_tokens = self.estimator.estimate_message(msg)
            if tokens_used + msg_tokens <= budget_tokens:
                recent.insert(0, msg)
                tokens_used += msg_tokens
            else:
                break

        # Middle is everything not in recent
        middle_count = len(messages) - len(recent)
        middle = messages[:middle_count]

        return middle, recent

    def _create_summary_message(self, summary_text: str) -> dict:
        """Create a summary message in the standard format"""
        return {
            "role": "system",
            "content": f"## Previous Conversation Summary\n\n{summary_text}",
            "_context_summary": True,
        }

    async def compact_messages_async(
        self,
        messages: list[dict],
        summarizer: Callable[[list[dict]], Any] | None = None,
    ) -> list[dict]:
        """
        Compact messages asynchronously, optionally using an LLM summarizer.
        
        If summarizer is provided, it will be called with the middle section
        and should return a summary string.
        """
        if not messages:
            return []

        if not self.should_compact(messages):
            return messages

        # Prune tool outputs first
        messages = self.prune_tool_outputs(messages)

        # Extract sections
        system_messages, existing_summary, conversation = self._extract_sections(messages)

        # Calculate recent budget
        recent_budget = int(self.max_tokens * self.recent_budget_ratio)

        # Select recent messages
        middle, recent = self._select_recent_messages(conversation, recent_budget)

        # Check if we have enough middle content to summarize
        if len(middle) < self.min_messages_to_summarize:
            # Not enough to summarize, just return pruned messages
            result = system_messages[:]
            if existing_summary:
                result.append(existing_summary)
            result.extend(conversation)
            return result

        # Build result
        result = system_messages[:]

        # Handle summarization
        if summarizer is not None:
            # If we have an existing summary, include it in context for the new summary
            summary_context = []
            if existing_summary:
                summary_context.append(existing_summary)
            summary_context.extend(middle)

            # Call the summarizer
            try:
                summary_result = summarizer(summary_context)
                # Handle both sync and async summarizers
                if hasattr(summary_result, "__await__"):
                    summary_text = await summary_result
                else:
                    summary_text = summary_result

                if summary_text:
                    result.append(self._create_summary_message(summary_text))
            except Exception:
                # If summarization fails, keep existing summary if available
                if existing_summary:
                    result.append(existing_summary)
        else:
            # No summarizer - keep existing summary if available
            if existing_summary:
                result.append(existing_summary)

        # Add recent messages
        result.extend(recent)

        return result

    def compact_messages(self, messages: list[dict]) -> list[dict]:
        """
        Compact messages synchronously (no LLM summary, just prune + select).
        """
        if not messages:
            return []

        if not self.should_compact(messages):
            return messages

        # Prune tool outputs
        messages = self.prune_tool_outputs(messages)

        # Extract sections
        system_messages, existing_summary, conversation = self._extract_sections(messages)

        # Calculate recent budget
        recent_budget = int(self.max_tokens * self.recent_budget_ratio)

        # Select recent messages
        middle, recent = self._select_recent_messages(conversation, recent_budget)

        # Build result
        result = system_messages[:]

        # Keep existing summary
        if existing_summary:
            result.append(existing_summary)

        # Add recent messages
        result.extend(recent)

        return result

    def estimate_tokens(self, messages: list[dict]) -> int:
        """Estimate token count for messages"""
        return self.estimator.estimate_messages(messages)
