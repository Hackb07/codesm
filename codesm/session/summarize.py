"""LLM-based summarization for conversation context"""

import os
import logging
from datetime import datetime

import httpx

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

SUMMARY_SYSTEM_PROMPT = """You are summarizing a coding assistant conversation so it can be continued later.

Your goal: Create a concise summary that preserves everything needed to continue the conversation seamlessly.

PRESERVE:
- Decisions made and their rationale
- Technical constraints or requirements discovered
- File names and paths mentioned or modified
- Commands run and their outcomes
- Errors encountered and their solutions (or pending solutions)
- TODOs and pending tasks
- Current plan or next steps
- Key context about the codebase or problem domain

DO NOT:
- Invent information not present in the conversation
- Include generic filler or pleasantries
- Repeat the same information multiple times

FORMAT:
- Use bullet points for clarity
- Be concise but complete
- Group related items together
- Focus on what would help continue the conversation effectively"""


def format_messages_for_summary(messages: list[dict]) -> str:
    """Format messages into a compact text representation for summarization."""
    formatted_parts = []
    
    for msg in messages:
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        
        # Handle tool calls
        tool_calls = msg.get("tool_calls", [])
        if tool_calls:
            tool_names = [tc.get("function", {}).get("name", "unknown") for tc in tool_calls]
            formatted_parts.append(f"[{role}] Called tools: {', '.join(tool_names)}")
            continue
        
        # Handle tool messages
        if role == "tool":
            tool_name = msg.get("name", "unknown")
            # Truncate tool output
            content_preview = str(content)[:500] if content else ""
            if len(str(content)) > 500:
                content_preview += "..."
            formatted_parts.append(f"[tool:{tool_name}] {content_preview}")
            continue
        
        # Handle regular messages with content
        if content:
            # Content can be string or list
            if isinstance(content, list):
                text_parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_parts.append(item.get("text", ""))
                    elif isinstance(item, str):
                        text_parts.append(item)
                content = " ".join(text_parts)
            
            # Truncate very long content
            content_str = str(content)
            if len(content_str) > 500:
                content_str = content_str[:500] + "..."
            
            formatted_parts.append(f"[{role}] {content_str}")
    
    return "\n\n".join(formatted_parts)


def create_summary_message(summary_text: str) -> dict:
    """Create a properly formatted summary message dict."""
    return {
        "role": "system",
        "content": f"## Previous Conversation Summary\n\n{summary_text}",
        "_context_summary": True,
        "_summary_timestamp": datetime.now().isoformat(),
    }


async def get_summary_provider() -> tuple:
    """Try to get a cheap model for summarization.
    
    Returns:
        (provider_type, model_id) tuple where provider_type is 'openrouter', 'anthropic', or 'openai'
    """
    # Priority 1: OpenRouter with Claude Haiku
    if os.environ.get("OPENROUTER_API_KEY"):
        return ("openrouter", "anthropic/claude-3-haiku-20240307")
    
    # Priority 2: OpenRouter with Gemini Flash (if key exists but haiku not preferred)
    # This is same as priority 1, just different model
    if os.environ.get("OPENROUTER_API_KEY"):
        return ("openrouter", "google/gemini-flash-1.5")
    
    # Priority 3: Direct Anthropic
    if os.environ.get("ANTHROPIC_API_KEY"):
        return ("anthropic", "claude-3-haiku-20240307")
    
    # Priority 4: OpenAI
    if os.environ.get("OPENAI_API_KEY"):
        return ("openai", "gpt-4o-mini")
    
    return (None, None)


async def _summarize_with_openrouter(formatted_text: str, model: str, max_tokens: int) -> str:
    """Summarize using OpenRouter API."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            OPENROUTER_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/Aditya-PS-05",
                "X-Title": "codesm",
            },
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": f"Summarize this conversation:\n\n{formatted_text}"},
                ],
                "temperature": 0.3,
                "max_tokens": max_tokens,
            },
        )
        
        if response.status_code != 200:
            raise Exception(f"OpenRouter API error: {response.status_code}")
        
        data = response.json()
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")


async def _summarize_with_anthropic(formatted_text: str, model: str, max_tokens: int) -> str:
    """Summarize using Anthropic API directly."""
    from ..provider.anthropic import AnthropicProvider
    
    provider = AnthropicProvider(model)
    result = ""
    
    async for chunk in provider.stream(
        system=SUMMARY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Summarize this conversation:\n\n{formatted_text}"}],
        tools=None,
    ):
        if chunk.type == "text":
            result += chunk.content
    
    return result


async def _summarize_with_openai(formatted_text: str, model: str, max_tokens: int) -> str:
    """Summarize using OpenAI API directly."""
    from ..provider.openai import OpenAIProvider
    
    provider = OpenAIProvider(model)
    result = ""
    
    async for chunk in provider.stream(
        system=SUMMARY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Summarize this conversation:\n\n{formatted_text}"}],
        tools=None,
    ):
        if chunk.type == "text":
            result += chunk.content
    
    return result


def _create_fallback_summary(messages: list[dict]) -> str:
    """Create a basic fallback summary when LLM summarization fails."""
    parts = ["Summary generation failed. Message overview:"]
    
    for i, msg in enumerate(messages):
        role = msg.get("role", "unknown")
        content = msg.get("content", "")
        tool_calls = msg.get("tool_calls", [])
        
        if tool_calls:
            tool_names = [tc.get("function", {}).get("name", "?") for tc in tool_calls]
            parts.append(f"- [{role}] Called: {', '.join(tool_names)}")
        elif role == "tool":
            tool_name = msg.get("name", "unknown")
            parts.append(f"- [tool:{tool_name}] (result)")
        else:
            # Get first 100 chars of content
            if isinstance(content, list):
                content = str(content)
            preview = str(content)[:100].replace("\n", " ")
            if len(str(content)) > 100:
                preview += "..."
            parts.append(f"- [{role}] {preview}")
        
        if i >= 20:
            parts.append(f"- ... and {len(messages) - 20} more messages")
            break
    
    return "\n".join(parts)


async def summarize_messages(
    messages: list[dict],
    provider=None,
    model: str | None = None,
    max_summary_tokens: int = 1500,
) -> str:
    """Summarize a list of messages for context compression.
    
    Args:
        messages: List of message dicts to summarize
        provider: Optional provider instance to use
        model: Optional model override
        max_summary_tokens: Maximum tokens for the summary output
    
    Returns:
        Summary text string
    """
    if not messages:
        return ""
    
    # Format messages for summarization
    formatted_text = format_messages_for_summary(messages)
    
    if not formatted_text.strip():
        return ""
    
    try:
        # If provider is passed, use it directly
        if provider:
            result = ""
            async for chunk in provider.stream(
                system=SUMMARY_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": f"Summarize this conversation:\n\n{formatted_text}"}],
                tools=None,
            ):
                if chunk.type == "text":
                    result += chunk.content
            return result.strip()
        
        # Otherwise, find a cheap provider
        provider_type, model_id = await get_summary_provider()
        
        if model:
            # Override model if specified
            model_id = model
        
        if provider_type == "openrouter":
            result = await _summarize_with_openrouter(formatted_text, model_id, max_summary_tokens)
        elif provider_type == "anthropic":
            result = await _summarize_with_anthropic(formatted_text, model_id, max_summary_tokens)
        elif provider_type == "openai":
            result = await _summarize_with_openai(formatted_text, model_id, max_summary_tokens)
        else:
            # No provider available, return fallback
            return _create_fallback_summary(messages)
        
        return result.strip() if result else _create_fallback_summary(messages)
        
    except Exception as e:
        logger.warning(f"Summarization failed: {e}")
        return _create_fallback_summary(messages)
