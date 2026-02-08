"""
LLMProvider interface. This is the only abstraction that matters.

Every LLM call in the system goes through this interface.
Implementations live in separate modules. No provider-specific
logic exists outside of llm/*.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """What comes back from any LLM call."""
    text: str
    input_tokens: int
    output_tokens: int
    model: str


class LLMProvider(ABC):
    """
    Single interface for all LLM providers.

    Design notes:
    - One method: `complete`. That's it.
    - System prompt + user prompt. No chat history management.
      This is a batch tool, not a chatbot.
    - Temperature exposed because synthesis wants low (0.2)
      and Q&A wants medium (0.5).
    - Max tokens to bound cost.
    """

    @abstractmethod
    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        """
        Send a prompt to the LLM and get a response.

        Args:
            system_prompt: Sets the LLM's behavior/role.
            user_prompt: The actual content to process.
            temperature: 0.0-1.0, lower = more deterministic.
            max_tokens: Upper bound on response length.

        Returns:
            LLMResponse with text and usage stats.

        Raises:
            LLMError: On any provider-specific failure.
        """
        ...

    @abstractmethod
    def name(self) -> str:
        """Return provider name for logging."""
        ...


class LLMError(Exception):
    """Raised when an LLM call fails."""
    pass
