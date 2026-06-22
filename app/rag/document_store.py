from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_KNOWLEDGE_FILE = BASE_DIR / "knowledge_base.txt"


@dataclass(frozen=True)
class DocumentChunk:
    chunk_id: str
    content: str
    source: str


class LocalTextDocumentStore:
    def __init__(self, knowledge_file: Path = DEFAULT_KNOWLEDGE_FILE) -> None:
        self.knowledge_file = knowledge_file

    def load_chunks(self) -> List[DocumentChunk]:
        with self.knowledge_file.open("r", encoding="utf-8") as f:
            text = f.read()

        chunks: List[DocumentChunk] = []
        for idx, content in enumerate([chunk.strip() for chunk in text.split("\n\n") if chunk.strip()], start=1):
            digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]
            chunks.append(
                DocumentChunk(
                    chunk_id=f"kb-{idx}-{digest}",
                    content=content,
                    source=str(self.knowledge_file),
                )
            )
        return chunks
