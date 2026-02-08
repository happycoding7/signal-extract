"""
Base collector interface. All collectors must implement this.
"""

from abc import ABC, abstractmethod

from models import Item
from storage.db import Storage


class Collector(ABC):
    """
    A collector pulls data from one source type.

    Contract:
    - collect() is idempotent. Calling it twice yields no duplicates.
    - Collectors manage their own cursors via Storage.
    - Collectors never call LLMs. All logic is deterministic.
    - Collectors yield raw Items with score=0 (filters score later).
    """

    def __init__(self, storage: Storage):
        self.storage = storage

    @abstractmethod
    def collect(self) -> list[Item]:
        """
        Fetch new items since last collection.
        Returns only new items (not previously seen).
        """
        ...

    @abstractmethod
    def name(self) -> str:
        """Collector name, used as key for state persistence."""
        ...
