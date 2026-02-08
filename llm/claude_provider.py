"""
Claude (Anthropic) LLM provider implementation.
"""

from llm.provider import LLMProvider, LLMResponse, LLMError


class ClaudeProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        if not api_key:
            raise LLMError("ANTHROPIC_API_KEY not set")
        try:
            import anthropic
        except ImportError:
            raise LLMError("anthropic package not installed: pip install anthropic")
        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return LLMResponse(
                text=response.content[0].text,
                input_tokens=response.usage.input_tokens,
                output_tokens=response.usage.output_tokens,
                model=self._model,
            )
        except Exception as e:
            raise LLMError(f"Claude API error: {e}") from e

    def name(self) -> str:
        return f"claude/{self._model}"
