"""Model routing and provider selection"""

from typing import Dict, Type
from .base import Provider
from .anthropic import AnthropicProvider
from .openai import OpenAIProvider


class ModelRouter:
    """Routes model requests to appropriate providers"""

    # Map of provider names to provider classes
    PROVIDERS: Dict[str, Type[Provider]] = {
        "anthropic": AnthropicProvider,
        "openai": OpenAIProvider,
    }

    # Common model aliases
    MODEL_ALIASES = {
        "claude": "anthropic/claude-sonnet-4-5-20250929",
        "claude-sonnet": "anthropic/claude-sonnet-4-5-20250929",
        "claude-opus": "anthropic/claude-opus-4-5-20251101",
        "gpt-4": "openai/gpt-4-turbo",
        "gpt-4-turbo": "openai/gpt-4-turbo",
        "gpt-4o": "openai/gpt-4o",
    }

    @classmethod
    def resolve_model(cls, model_string: str) -> tuple[str, str]:
        """Resolve model string to (provider, model_id)"""
        # Check if it's an alias
        if model_string in cls.MODEL_ALIASES:
            model_string = cls.MODEL_ALIASES[model_string]

        # Parse provider/model format
        if "/" in model_string:
            provider, model_id = model_string.split("/", 1)
            return provider, model_id

        # Default to anthropic if no provider specified
        return "anthropic", model_string

    @classmethod
    def get_provider(cls, model_string: str) -> Provider:
        """Get appropriate provider instance for a model"""
        provider_name, model_id = cls.resolve_model(model_string)

        if provider_name not in cls.PROVIDERS:
            raise ValueError(
                f"Unknown provider: {provider_name}. "
                f"Available: {', '.join(cls.PROVIDERS.keys())}"
            )

        provider_class = cls.PROVIDERS[provider_name]
        return provider_class(model_id)
