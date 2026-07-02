from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from scripts.personal_workstation.common import (  # noqa: E402
    MANAGED_TOP_LEVELS,
    WorkstationContext,
    frontmatter,
    json_dump,
    make_context,
    markdown_files,
    now_iso,
    read_frontmatter,
    relative_to_target,
    write_text_file,
)


EXCLUDED_PARTS = {"99_System"}
INCLUDED_TYPES = {
    "daily",
    "project",
    "codex-task",
    "knowledge-card",
    "learning-note",
    "agent-research-note",
    "document-log",
    "project-log",
    "review",
    "inbox",
    "artifact-index",
    "home-dashboard",
}


def strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    return parts[2].lstrip()


def normalize_text(text: str) -> str:
    text = re.sub(r"```[\s\S]*?```", " ", text)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[\[([^|\]]+)\|?([^\]]*)\]\]", lambda m: m.group(2) or m.group(1), text)
    text = re.sub(r"#+\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def should_include(ctx: WorkstationContext, path: Path, front: dict[str, Any]) -> bool:
    rel = path.relative_to(ctx.target_root)
    if not rel.parts or rel.parts[0] not in MANAGED_TOP_LEVELS:
        return False
    rel_parts = set(rel.parts)
    if rel_parts & EXCLUDED_PARTS:
        return False
    if front.get("type") in INCLUDED_TYPES:
        return True
    return path.suffix.lower() == ".md" and not path.name.endswith("_Template.md")


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 160) -> list[str]:
    if not text:
        return []
    chunks = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return chunks


def source_record(ctx: WorkstationContext, path: Path) -> dict[str, Any] | None:
    front = read_frontmatter(path)
    if not should_include(ctx, path, front):
        return None
    text = path.read_text(encoding="utf-8", errors="ignore")
    body = strip_frontmatter(text)
    normalized = normalize_text(body)
    digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
    rel = relative_to_target(ctx, path)
    return {
        "id": front.get("id") or hashlib.sha1(rel.encode("utf-8")).hexdigest(),
        "path": rel,
        "type": front.get("type", "markdown"),
        "project": front.get("project"),
        "project_id": front.get("project_id"),
        "topic": front.get("topic"),
        "title": front.get("title"),
        "area": front.get("area"),
        "category": front.get("category"),
        "artifact_path": front.get("artifact_path"),
        "date": front.get("date"),
        "period": front.get("period"),
        "status": front.get("status"),
        "risk": front.get("risk"),
        "human_review_required": front.get("human_review_required", True),
        "human_reviewed": front.get("human_reviewed", False),
        "preview": front.get("preview", True),
        "updated": front.get("updated"),
        "sha256": digest,
        "char_count": len(normalized),
        "chunk_count": len(chunk_text(normalized)),
    }


def build_rag_data(ctx: WorkstationContext) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    sources = []
    chunks = []
    for path in markdown_files(ctx.target_root):
        record = source_record(ctx, path)
        if record is None:
            continue
        sources.append(record)
        text = path.read_text(encoding="utf-8", errors="ignore")
        normalized = normalize_text(strip_frontmatter(text))
        for index, chunk in enumerate(chunk_text(normalized)):
            chunk_id_seed = f"{record['id']}:{index}:{record['sha256']}"
            chunks.append(
                {
                    "chunk_id": hashlib.sha1(chunk_id_seed.encode("utf-8")).hexdigest(),
                    "source_id": record["id"],
                    "path": record["path"],
                    "chunk_index": index,
                    "text": chunk,
                    "type": record["type"],
                    "project": record.get("project"),
                    "topic": record.get("topic"),
                    "title": record.get("title"),
                    "date": record.get("date"),
                    "human_reviewed": record.get("human_reviewed", False),
                    "preview": record.get("preview", True),
                }
            )
    manifest = {
        "generated_at": now_iso(ctx),
        "source": "personal_workstation.build_rag_manifest",
        "preview": bool(ctx.config.get("preview_mode", True)),
        "network_used": False,
        "embedding_generated": False,
        "model_called": False,
        "source_count": len(sources),
        "chunk_count": len(chunks),
        "sources_path": "99_System/RAG/rag_sources.jsonl",
        "chunks_path": "99_System/RAG/rag_chunks.jsonl",
        "notes": [
            "This export is RAG-ready but does not generate embeddings.",
            "Use human_reviewed and preview fields to filter retrieval scope.",
            "99_System generated views/templates are excluded from source chunks.",
        ],
    }
    return manifest, sources, chunks


def jsonl(records: list[dict[str, Any]]) -> str:
    return "".join(json_dump(record).replace("\n", " ").rstrip() + "\n" for record in records)


def rag_sources_note(ctx: WorkstationContext, manifest: dict[str, Any], sources: list[dict[str, Any]]) -> str:
    rows = "\n".join(
        f"| {item['type']} | `{item['path']}` | {item['chunk_count']} | {str(item['human_reviewed']).lower()} |"
        for item in sources
    )
    if not rows:
        rows = "| none | - | 0 | false |"
    return frontmatter(
        {
            "type": "rag-index",
            "id": "rag-sources",
            "source": "personal_workstation.build_rag_manifest",
            "preview": bool(ctx.config.get("preview_mode", True)),
            "human_review_required": False,
            "human_reviewed": True,
            "created": manifest["generated_at"],
            "updated": manifest["generated_at"],
        },
        ["rag", "index", "workstation"],
    ) + f"""# RAG Sources

This is a local-first RAG export index. It prepares source metadata and text chunks, but does not call an embedding model.

- source_count: {manifest["source_count"]}
- chunk_count: {manifest["chunk_count"]}
- embedding_generated: false
- network_used: false

| Type | Path | Chunks | Reviewed |
| --- | --- | --- | --- |
{rows}
"""


def build_rag_manifest(ctx: WorkstationContext):
    rag_dir = ctx.target_root / "99_System" / "RAG"
    manifest, sources, chunks = build_rag_data(ctx)
    results = [
        write_text_file(rag_dir / "rag_manifest.json", json_dump(manifest), overwrite=True),
        write_text_file(rag_dir / "rag_sources.jsonl", jsonl(sources), overwrite=True),
        write_text_file(rag_dir / "rag_chunks.jsonl", jsonl(chunks), overwrite=True),
        write_text_file(rag_dir / "RAG_Sources.md", rag_sources_note(ctx, manifest, sources), overwrite=True),
    ]
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Build RAG-ready local manifest and chunks.")
    parser.add_argument("--config", default=None)
    args = parser.parse_args()
    ctx = make_context(args.config)
    for result in build_rag_manifest(ctx):
        print(f"{result.action}: {result.path}")


if __name__ == "__main__":
    main()
