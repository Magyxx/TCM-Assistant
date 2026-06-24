from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.schemas.evidence import EvidenceChunk


ROOT_KNOWLEDGE_FILE = Path("knowledge/knowledge_base.txt")
PROCESSED_CHUNKS_FILE = Path("knowledge/processed/chunks.jsonl")
P6_CHUNKS_FILE = Path("knowledge/processed/p6_chunks.jsonl")


def _chunk_id(content: str, index: int) -> str:
    digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]
    return f"p9-kb-{index}-{digest}"


def load_knowledge_chunks(path: str | Path | None = None) -> list[EvidenceChunk]:
    selected = Path(path) if path else None
    candidates = [selected] if selected else [ROOT_KNOWLEDGE_FILE, PROCESSED_CHUNKS_FILE, P6_CHUNKS_FILE]
    for candidate in candidates:
        if candidate is None or not candidate.exists():
            continue
        if candidate.suffix == ".jsonl":
            chunks: list[EvidenceChunk] = []
            with candidate.open("r", encoding="utf-8") as f:
                for index, line in enumerate(f, start=1):
                    if not line.strip():
                        continue
                    payload = json.loads(line)
                    content = str(payload.get("content") or payload.get("text") or "")
                    if not content:
                        continue
                    chunks.append(
                        EvidenceChunk(
                            chunk_id=str(payload.get("chunk_id") or _chunk_id(content, index)),
                            title=str(payload.get("title") or "TCM Assistant knowledge chunk"),
                            source=str(payload.get("source") or candidate),
                            content=content,
                            score=0.0,
                        )
                    )
            return chunks

        text = candidate.read_text(encoding="utf-8")
        parts = [part.strip() for part in text.split("\n\n") if part.strip()]
        return [
            EvidenceChunk(
                chunk_id=_chunk_id(content, index),
                title=content.splitlines()[0].strip("# ").strip()[:80] or "TCM Assistant knowledge chunk",
                source=str(candidate),
                content=content,
                score=0.0,
            )
            for index, content in enumerate(parts, start=1)
        ]
    return []


__all__ = ["ROOT_KNOWLEDGE_FILE", "load_knowledge_chunks"]
