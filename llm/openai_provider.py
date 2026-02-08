"""
OpenAI LLM provider implementation.
"""

from llm.provider import LLMProvider, LLMResponse, LLMError


class OpenAIProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "gpt-4o"):
        if not api_key:
            raise LLMError("OPENAI_API_KEY not set")
        try:
            import openai
        except ImportError:
            raise LLMError("openai package not installed: pip install openai")
        self._client = openai.OpenAI(api_key=api_key)
        self._model = model

    def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.3,
        max_tokens: int = 2000,
    ) -> LLMResponse:
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=max_tokens,
                temperature=temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            choice = response.choices[0]
            usage = response.usage
            return LLMResponse(
                text=choice.message.content or "",
                input_tokens=usage.prompt_tokens if usage else 0,
                output_tokens=usage.completion_tokens if usage else 0,
                model=self._model,
            )
        except Exception as e:
            raise LLMError(f"OpenAI API error: {e}") from e

    def name(self) -> str:
        return f"openai/{self._model}"
