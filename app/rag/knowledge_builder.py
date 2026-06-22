from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from app.rag.chunk_schema import KnowledgeChunk


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_RAW_DIR = ROOT_DIR / "knowledge" / "raw"
DEFAULT_PROCESSED_DIR = ROOT_DIR / "knowledge" / "processed"
DEFAULT_CHUNKS_PATH = DEFAULT_PROCESSED_DIR / "chunks.jsonl"
DEFAULT_SYNONYMS_PATH = DEFAULT_PROCESSED_DIR / "synonyms.json"
DEFAULT_REPORT_PATH = ROOT_DIR / "artifacts" / "p10m2" / "knowledge_build_report.json"
LEGACY_KNOWLEDGE_PATHS = (
    ROOT_DIR / "knowledge" / "knowledge_base.txt",
    ROOT_DIR / "app" / "rag" / "knowledge_base.txt",
)

SOURCE_TYPE_BY_FILE = {
    "tcm_inquiry.md": "inquiry_guidance",
    "red_flags.md": "red_flag",
    "safety_boundaries.md": "safety_boundary",
    "terminology_synonyms.md": "terminology",
}

ENTITY_PATTERNS = {
    "chief_complaint": ["chief complaint", "main complaint", "主诉"],
    "duration": ["duration", "timeline", "病程", "持续"],
    "sleep": ["sleep", "睡眠"],
    "appetite": ["appetite", "食欲"],
    "stool": ["stool", "urination", "大便", "二便", "便溏", "便血"],
    "digestive_discomfort": ["digestive", "stomach", "胃胀", "腹胀", "bloating", "abdominal"],
    "red_flag_chest_pain": ["chest pain", "胸痛", "chest tightness"],
    "red_flag_dyspnea": ["breathing difficulty", "dyspnea", "呼吸困难"],
    "red_flag_bleeding": ["blood in stool", "black stool", "vomiting blood", "便血", "呕血"],
    "red_flag_high_fever": ["high fever", "persistent high fever", "高热"],
    "red_flag_confusion": ["confusion", "altered consciousness", "意识"],
    "red_flag_abdominal_pain": ["severe abdominal pain", "剧烈腹痛"],
    "no_diagnosis": ["no diagnosis", "not a diagnosis", "不诊断"],
    "no_prescription": ["no prescription", "prescribe", "不开方"],
    "rag_guard": ["overwrite", "risk status", "RAG", "LoRA", "risk rule"],
    "secret_logging": ["Authorization", "API key", ".env", "log"],
}

SYNONYMS = {
    "digestive_bloating": ["胃胀", "腹胀", "脘腹胀满", "bloating", "abdominal distension", "stomach fullness"],
    "loose_stool": ["大便稀", "便溏", "loose stool", "diarrhea-like stool"],
    "cold_sensation": ["怕冷", "畏寒", "chills"],
    "dry_mouth": ["口干", "口渴", "dry mouth", "thirst"],
    "high_risk_care": ["高热", "胸痛", "呼吸困难", "便血", "呕血", "剧烈腹痛", "意识异常"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _slug(value: str) -> str:
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", value.lower()).strip("-")
    return normalized or "section"


def _digest(value: str, length: int = 12) -> str:
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:length]


def _display_path(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _infer_risk_level(source_type: str, content: str) -> str:
    lowered = content.lower()
    high_terms = [
        "high-risk",
        "red flag",
        "urgent",
        "offline medical",
        "chest pain",
        "breathing difficulty",
        "blood in stool",
        "vomiting blood",
        "persistent high fever",
        "severe abdominal pain",
        "confusion",
        "高热",
        "胸痛",
        "呼吸困难",
        "便血",
        "呕血",
        "剧烈腹痛",
        "意识",
    ]
    if source_type == "red_flag" or any(term.lower() in lowered for term in high_terms):
        return "high"
    if source_type == "safety_boundary":
        return "medium"
    return "low"


def _entities_for(content: str, source_type: str) -> list[str]:
    haystack = content.lower()
    entities: list[str] = [source_type]
    for entity, patterns in ENTITY_PATTERNS.items():
        if any(pattern.lower() in haystack for pattern in patterns):
            entities.append(entity)
    return sorted(set(entities))


def _read_sections(path: Path) -> Iterable[tuple[str, str]]:
    text = path.read_text(encoding="utf-8")
    title = path.stem.replace("_", " ").title()
    current_title = title
    current_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if line.startswith("#"):
            if current_lines:
                yield current_title, "\n".join(current_lines).strip()
                current_lines = []
            current_title = line.lstrip("#").strip() or title
            continue
        if line:
            current_lines.append(line)
    if current_lines:
        yield current_title, "\n".join(current_lines).strip()


def build_knowledge_chunks(
    *,
    raw_dir: Path = DEFAULT_RAW_DIR,
    chunks_path: Path = DEFAULT_CHUNKS_PATH,
    include_legacy: bool = True,
) -> list[KnowledgeChunk]:
    chunks: list[KnowledgeChunk] = []
    raw_files = sorted(raw_dir.glob("*.md")) if raw_dir.exists() else []

    for path in raw_files:
        source_type = SOURCE_TYPE_BY_FILE.get(path.name, "inquiry_guidance")
        source_id = path.stem
        for index, (title, content) in enumerate(_read_sections(path), start=1):
            if not content:
                continue
            chunk_id = f"{source_id}-{_slug(title)}-{index}-{_digest(content)}"
            chunks.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    source_id=source_id,
                    source_type=source_type,
                    title=title,
                    content=content,
                    entities=_entities_for(content, source_type),
                    risk_level=_infer_risk_level(source_type, content),
                    trust_level="project_curated",
                    version="p10m2.chunk.v1",
                    section=title,
                    metadata={"source_path": _display_path(path)},
                )
            )

    if include_legacy:
        for legacy_path in LEGACY_KNOWLEDGE_PATHS:
            if not legacy_path.exists():
                continue
            paragraphs = [item.strip() for item in legacy_path.read_text(encoding="utf-8", errors="ignore").split("\n\n") if item.strip()]
            for index, content in enumerate(paragraphs, start=1):
                chunk_id = f"legacy-knowledge-{index}-{_digest(content)}"
                chunks.append(
                    KnowledgeChunk(
                        chunk_id=chunk_id,
                        source_id="legacy_knowledge_base",
                        source_type="legacy_knowledge",
                        title=f"Legacy Knowledge {index}",
                        content=content,
                        entities=_entities_for(content, "legacy_knowledge"),
                        risk_level=_infer_risk_level("legacy_knowledge", content),
                        trust_level="legacy_project_curated",
                        version="p10m2.chunk.v1",
                        section=f"legacy-{index}",
                        metadata={"source_path": _display_path(legacy_path)},
                    )
                )
            break

    chunks_path.parent.mkdir(parents=True, exist_ok=True)
    with chunks_path.open("w", encoding="utf-8") as handle:
        for chunk in chunks:
            handle.write(json.dumps(chunk.model_dump(), ensure_ascii=False, sort_keys=True) + "\n")
    return chunks


def load_knowledge_chunks(chunks_path: Path = DEFAULT_CHUNKS_PATH) -> list[KnowledgeChunk]:
    if not chunks_path.exists():
        return []
    chunks: list[KnowledgeChunk] = []
    for line in chunks_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.strip():
            chunks.append(KnowledgeChunk.model_validate(json.loads(line)))
    return chunks


def write_synonyms(path: Path = DEFAULT_SYNONYMS_PATH) -> dict[str, list[str]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(SYNONYMS, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return SYNONYMS


def write_build_report(
    chunks: list[KnowledgeChunk],
    *,
    chunks_path: Path = DEFAULT_CHUNKS_PATH,
    report_path: Path = DEFAULT_REPORT_PATH,
) -> dict[str, object]:
    by_source_type: dict[str, int] = {}
    for chunk in chunks:
        by_source_type[str(chunk.source_type)] = by_source_type.get(str(chunk.source_type), 0) + 1
    report = {
        "status": "ok" if chunks else "failed",
        "generated_at": utc_now(),
        "chunks_count": len(chunks),
        "chunks_path": str(chunks_path.relative_to(ROOT_DIR)).replace("\\", "/"),
        "source_type_counts": by_source_type,
        "required_fields_present": all(
            bool(chunk.chunk_id and chunk.source_id and chunk.source_type and chunk.title and chunk.content)
            for chunk in chunks
        ),
        "diagnosis_content_allowed": False,
        "prescription_content_allowed": False,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def build_p10m2_knowledge() -> dict[str, object]:
    chunks = build_knowledge_chunks()
    write_synonyms()
    for subdir in ("bm25", "dense", "hybrid"):
        (ROOT_DIR / "knowledge" / "indexes" / subdir).mkdir(parents=True, exist_ok=True)
    return write_build_report(chunks)
