"""
Provider factory. Reads config, returns the right LLMProvider.
"""

from config.settings import Config
from llm.provider import LLMProvider, LLMError


def create_provider(config: Config) -> LLMProvider:
    """Create LLM provider based on config. Provider selected at runtime."""
    provider = config.llm_provider.lower()

    if provider == "claude":
        from llm.claude_provider import ClaudeProvider
        return ClaudeProvider(
            api_key=config.anthropic_api_key,
            model=config.anthropic_model,
        )
    elif provider == "openai":
        from llm.openai_provider import OpenAIProvider
        return OpenAIProvider(
            api_key=config.openai_api_key,
            model=config.openai_model,
        )
    elif provider == "openrouter":
        from llm.openrouter_provider import OpenRouterProvider
        return OpenRouterProvider(
            api_key=config.openrouter_api_key,
            model=config.openrouter_model,
        )
    else:
        raise LLMError(
            f"Unknown LLM provider: '{provider}'. "
            f"Set SIGNAL_LLM_PROVIDER to 'claude', 'openai', or 'openrouter'."
        )
