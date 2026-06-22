from __future__ import annotations

from abc import ABC, abstractmethod
from typing import List

from pydantic import BaseModel


class EvidenceChunk(BaseModel):
    chunk_id: str
    content: str
    source: str
    score: float
    retriever_type: str


class BaseRetriever(ABC):
    @abstractmethod
    def retrieve(self, query: str, top_k: int = 3) -> List[EvidenceChunk]:
        raise NotImplementedError
