"""
Q&A handler. Thin wrapper around the synthesizer's ask() method.

Exists as a separate module for clarity and future extension
(e.g., caching frequent questions, answer quality tracking).
"""

from llm.provider import LLMProvider
from models import QAResult
from storage.db import Storage
from synthesizer.engine import Synthesizer


class QAHandler:
    def __init__(self, llm: LLMProvider, storage: Storage):
        self._synthesizer = Synthesizer(llm, storage)

    def ask(self, question: str, days: int = 7) -> QAResult | None:
        """
        Answer a question using recent collected data.

        Args:
            question: Natural language question.
            days: How far back to look (default 7 days).

        Returns:
            QAResult or None on failure.
        """
        return self._synthesizer.ask(question, days=days)
