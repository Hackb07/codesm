"""Provider abstraction for LLM APIs"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Literal


@dataclass
class StreamChunk:
    """A chunk of streamed response from an LLM"""
    type: Literal["text", "tool_call", "tool_call_delta", "tool_result"]
    content: str = ""
    name: str = ""
    args: dict = field(default_factory=dict)
    id: str = ""


class Provider(ABC):
    """Base class for LLM providers"""
    
    @abstractmethod
    async def stream(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict] | None = None,
    ) -> AsyncIterator[StreamChunk]:
        """Stream a response from the model"""
        pass


def get_provider(model: str) -> Provider:
    """Get a provider instance from a model string like 'anthropic/claude-sonnet-4'"""
    if "/" not in model:
        # Default to anthropic
        provider_id = "anthropic"
        model_id = model
    else:
        provider_id, model_id = model.split("/", 1)
    
    if provider_id == "anthropic":
        from .anthropic import AnthropicProvider
        return AnthropicProvider(model_id)
    elif provider_id == "openai":
        from .openai import OpenAIProvider
        return OpenAIProvider(model_id)
    else:
        raise ValueError(f"Unknown provider: {provider_id}. Supported: anthropic, openai")
