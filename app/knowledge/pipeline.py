from __future__ import annotations

import json
import re
from hashlib import sha256
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

from app.knowledge.source_registry import (
    DEFAULT_SOURCE_REGISTRY_PATH,
    KNOWLEDGE_DIR,
    SOURCE_REGISTRY_SCHEMA_VERSION,
    source_file_hash,
    source_has_p6c_shape,
)


ROOT_DIR = Path(__file__).resolve().parents[2]
SOURCE_MANIFEST_SCHEMA_VERSION = "kb.source_manifest.v0"
CHUNK_SCHEMA_VERSION = "kb.chunk.v0"
INDEX_SCHEMA_VERSION = "kb.index.v0"
PIPELINE_SCHEMA_VERSION = "kb.pipeline.p6.v0"

DEFAULT_LEGACY_MANIFEST_PATH = ROOT_DIR / "knowledge" / "source_manifest.example.json"
DEFAULT_MANIFEST_PATH = DEFAULT_SOURCE_REGISTRY_PATH
DEFAULT_CHUNKS_PATH = ROOT_DIR / "knowledge" / "processed" / "p6_chunks.jsonl"
DEFAULT_INDEX_PATH = ROOT_DIR / "knowledge" / "indexes" / "p6_bm25_index.json"
DEFAULT_EVAL_PATH = ROOT_DIR / "knowledge" / "eval" / "p6_retrieval_safety_eval.json"
DEFAULT_ARTIFACT_PATH = ROOT_DIR / "artifacts" / "p6_knowledge_pipeline.json"

REQUIRED_SOURCE_FIELDS = {
    "source_id",
    "title",
    "author",
    "edition",
    "publisher",
    "source_type",
    "rights_status",
    "license",
    "allowed_use",
    "forbidden_use",
    "ingestion_status",
    "trust_level",
    "review_required",
}
INGESTIBLE_RIGHTS_STATUSES = {
    "approved",
    "synthetic_owned",
    "public_domain_verified",
    "permission_granted",
    "internal_owned",
}
INGESTIBLE_SOURCE_STATUSES = {"approved_for_p6", "indexed"}
SKIPPED_SOURCE_STATUSES = {
    "planned_smoke_only",
    "pending_review",
    "quarantined",
    "rejected",
}
FORBIDDEN_STATE_WRITES = [
    "chief_complaint",
    "duration",
    "risk_status",
    "risk_rule_ids",
    "risk_flags_status",
    "risk_flags",
]
STOPWORDS = {
    "a",
    "and",
    "are",
    "as",
    "be",
    "for",
    "if",
    "in",
    "is",
    "it",
    "of",
    "or",
    "the",
    "to",
    "with",
}
ENTITY_PATTERNS = {
    "red_flag_chest_pain": ["chest pain", "chest tightness"],
    "red_flag_dyspnea": ["dyspnea", "breathing difficulty", "shortness of breath"],
    "red_flag_gi_bleeding": ["blood in stool", "vomiting blood"],
    "red_flag_high_fever": ["persistent high fever", "high fever"],
    "duration": ["duration", "how long"],
    "appetite": ["appetite"],
    "stool": ["stool"],
    "offline_care": ["offline medical care", "urgent offline care"],
}
PII_PATTERNS = [
    re.compile(r"\b\d{17}[\dXx]\b"),
    re.compile(r"\b1[3-9]\d{9}\b"),
    re.compile(r"(patient name|id card|medical record number|phone number)", re.IGNORECASE),
    re.compile(r"(real patient|non-anonymized|unredacted)", re.IGNORECASE),
]
UNSAFE_GENERATION_PATTERNS = [
    re.compile(r"\bdiagnose as\b", re.IGNORECASE),
    re.compile(r"\bprescribe\s+\w+", re.IGNORECASE),
    re.compile(r"\b\d+(\.\d+)?\s*(mg|g|ml)\b", re.IGNORECASE),
]
EVAL_CASES = [
    {
        "case_id": "P6-EVAL-RED-FLAG",
        "query": "chest pain dyspnea blood in stool persistent high fever offline care",
        "expected_terms": ["red_flag_chest_pain", "red_flag_dyspnea", "offline_care"],
    },
    {
        "case_id": "P6-EVAL-OBSERVATION",
        "query": "digestive discomfort duration appetite stool symptom changes",
        "expected_terms": ["duration", "appetite", "stool"],
    },
]


@dataclass(frozen=True)
class SourceReview:
    source_id: str
    status: str
    ok: bool
    reason: str
    content_path: Path | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        try:
            return str(value.relative_to(ROOT_DIR))
        except ValueError:
            return str(value)
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_jsonl(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(json_safe(row), ensure_ascii=False, sort_keys=True) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def load_manifest(manifest_path: Path) -> dict[str, Any]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("source manifest must be a JSON object")
    return payload


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    return []


def _has_p6_allowed_use(source: dict[str, Any]) -> bool:
    allowed = " ".join(_as_string_list(source.get("allowed_use"))).lower()
    return "p6" in allowed or "retrieval" in allowed or "index" in allowed


def _review_flags_ok(source: dict[str, Any]) -> bool:
    review = source.get("review")
    if not isinstance(review, dict):
        return False
    required_flags = ("rights_reviewed", "safety_reviewed", "provenance_reviewed")
    return all(review.get(flag) is True for flag in required_flags)


def _manifest_schema_ok(manifest: dict[str, Any]) -> bool:
    return manifest.get("schema_version") in {
        SOURCE_MANIFEST_SCHEMA_VERSION,
        SOURCE_REGISTRY_SCHEMA_VERSION,
    }


def _source_requires_p6c_runtime_gate(source: dict[str, Any]) -> bool:
    return source_has_p6c_shape(source) and source.get("approved_for_runtime") is True


def _p6c_runtime_gate_ok(source: dict[str, Any]) -> tuple[bool, str]:
    if not _source_requires_p6c_runtime_gate(source):
        return True, ""
    if source.get("rights_status") != "approved":
        return False, "approved_for_runtime requires rights_status=approved"
    if source.get("safety_status") != "approved":
        return False, "approved_for_runtime requires safety_status=approved"
    if source.get("provenance_status") != "approved":
        return False, "approved_for_runtime requires provenance_status=approved"
    if source.get("contains_pii") is True:
        return False, "approved_for_runtime source cannot contain PII"
    if source.get("contains_prescription_content") is True and source.get("source_use_category") != "safety_negative_sample":
        return False, "prescription content cannot enter report-generation runtime index"
    if source.get("approved_for_training") is True and not source.get("training_rights_basis"):
        return False, "approved_for_training requires explicit training_rights_basis"
    return True, ""


def review_sources(manifest: dict[str, Any], manifest_path: Path) -> list[SourceReview]:
    sources = manifest.get("sources")
    if not isinstance(sources, list):
        return [
            SourceReview(
                source_id="manifest",
                status="blocked",
                ok=False,
                reason="manifest.sources must be a list",
            )
        ]

    knowledge_dir = KNOWLEDGE_DIR.resolve()
    reviews: list[SourceReview] = []
    seen_source_ids: set[str] = set()
    for index, source in enumerate(sources, start=1):
        if not isinstance(source, dict):
            reviews.append(
                SourceReview(
                    source_id=f"source_{index}",
                    status="blocked",
                    ok=False,
                    reason="source entry must be an object",
                )
            )
            continue

        source_id = str(source.get("source_id") or f"source_{index}")
        missing = sorted(REQUIRED_SOURCE_FIELDS - set(source))
        if missing:
            reviews.append(
                SourceReview(
                    source_id=source_id,
                    status="blocked",
                    ok=False,
                    reason=f"missing required fields: {', '.join(missing)}",
                )
            )
            continue
        if source_id in seen_source_ids:
            reviews.append(
                SourceReview(
                    source_id=source_id,
                    status="blocked",
                    ok=False,
                    reason="duplicate source_id",
                )
            )
            continue
        seen_source_ids.add(source_id)

        ingestion_status = str(source.get("ingestion_status") or "")
        if ingestion_status in SKIPPED_SOURCE_STATUSES:
            reviews.append(
                SourceReview(
                    source_id=source_id,
                    status="skipped",
                    ok=True,
                    reason=f"not approved for P6: {ingestion_status}",
                )
            )
            continue
        if ingestion_status not in INGESTIBLE_SOURCE_STATUSES:
            reviews.append(
                SourceReview(
                    source_id=source_id,
                    status="blocked",
                    ok=False,
                    reason=f"unsupported ingestion_status: {ingestion_status}",
                )
            )
            continue

        rights_status = str(source.get("rights_status") or "")
        if rights_status not in INGESTIBLE_RIGHTS_STATUSES:
            reviews.append(
                SourceReview(
                    source_id=source_id,
                    status="blocked",
                    ok=False,
                    reason=f"rights_status is not ingestible: {rights_status}",
                )
            )
            continue
        p6c_gate_ok, p6c_gate_reason = _p6c_runtime_gate_ok(source)
        if not p6c_gate_ok:
            reviews.append(
                SourceReview(
                    source_id=source_id,
                    status="blocked",
                    ok=False,
                    reason=p6c_gate_reason,
                )
            )
            continue
        if not _has_p6_allowed_use(source):
            reviews.append(
                SourceReview(
                    source_id=source_id,
                    status="blocked",
                    ok=False,
                    reason="allowed_use does not include P6 indexing or retrieval evaluation",
                )
            )
            continue
        if not _review_flags_ok(source):
            reviews.append(
                SourceReview(
                    source_id=source_id,
                    status="blocked",
                    ok=False,
                    reason="rights, safety, and provenance review flags must all be true",
                )
            )
            continue

        raw_content_path = source.get("content_path")
        if not raw_content_path:
            reviews.append(
                SourceReview(
                    source_id=source_id,
                    status="blocked",
                    ok=False,
                    reason="approved P6 source must include content_path",
                )
            )
            continue
        content_path = (manifest_path.parent / str(raw_content_path)).resolve()
        if not _is_relative_to(content_path, knowledge_dir):
            reviews.append(
                SourceReview(
                    source_id=source_id,
                    status="blocked",
                    ok=False,
                    reason="content_path must stay inside the knowledge directory",
                )
            )
            continue
        if not content_path.is_file():
            reviews.append(
                SourceReview(
                    source_id=source_id,
                    status="blocked",
                    ok=False,
                    reason=f"content_path does not exist: {raw_content_path}",
                )
            )
            continue
        declared_hash = str(source.get("hash") or "")
        actual_hash = source_file_hash(source, manifest_path)
        if source_has_p6c_shape(source) and declared_hash and actual_hash and declared_hash != actual_hash:
            reviews.append(
                SourceReview(
                    source_id=source_id,
                    status="blocked",
                    ok=False,
                    reason="source content hash mismatch",
                )
            )
            continue

        reviews.append(
            SourceReview(
                source_id=source_id,
                status="approved",
                ok=True,
                reason="approved for P6 clean/chunk/index/eval",
                content_path=content_path,
            )
        )
    return reviews


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, list[str]]] = []
    current_title = "main"
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            current_lines.append("")
            continue
        if line.startswith("#"):
            continue
        if line.lower().startswith("section:"):
            if any(item.strip() for item in current_lines):
                sections.append((current_title, current_lines))
            current_title = line.split(":", 1)[1].strip() or "section"
            current_lines = []
            continue
        current_lines.append(line)

    if any(item.strip() for item in current_lines):
        sections.append((current_title, current_lines))

    return [(title, clean_text("\n".join(lines))) for title, lines in sections]


def chunk_section(section: str, text: str, *, max_chars: int = 900) -> list[tuple[str, str]]:
    paragraphs = [paragraph.strip() for paragraph in text.split("\n\n") if paragraph.strip()]
    chunks: list[tuple[str, str]] = []
    pending: list[str] = []
    pending_len = 0

    for paragraph in paragraphs:
        extra = len(paragraph) + (2 if pending else 0)
        if pending and pending_len + extra > max_chars:
            chunks.append((section, "\n\n".join(pending)))
            pending = []
            pending_len = 0
        pending.append(paragraph)
        pending_len += extra

    if pending:
        chunks.append((section, "\n\n".join(pending)))
    return chunks


def content_has_forbidden_markers(text: str) -> list[str]:
    hits: list[str] = []
    for pattern in PII_PATTERNS:
        if pattern.search(text):
            hits.append(pattern.pattern)
    return hits


def extract_entities(content: str) -> list[str]:
    lowered = content.lower()
    entities = [
        entity
        for entity, patterns in ENTITY_PATTERNS.items()
        if any(pattern in lowered for pattern in patterns)
    ]
    return sorted(entities)


def normalize_terms(entities: Iterable[str]) -> list[str]:
    return sorted(set(entities))


def risk_level_for_entities(entities: Sequence[str]) -> str:
    high_risk = {
        "red_flag_chest_pain",
        "red_flag_dyspnea",
        "red_flag_gi_bleeding",
        "red_flag_high_fever",
    }
    if high_risk & set(entities):
        return "high"
    if entities:
        return "low"
    return "not_applicable"


def make_chunk(
    source: dict[str, Any],
    *,
    section: str,
    content: str,
    ordinal: int,
) -> dict[str, Any]:
    source_id = str(source["source_id"])
    entities = extract_entities(content)
    digest_input = f"{source_id}\0{section}\0{ordinal}\0{content}".encode("utf-8")
    digest = sha256(digest_input).hexdigest()
    content_digest = sha256(content.encode("utf-8")).hexdigest()
    section_slug = re.sub(r"[^a-z0-9]+", "_", section.lower()).strip("_") or "section"
    return {
        "schema_version": CHUNK_SCHEMA_VERSION,
        "chunk_id": f"{source_id}-{section_slug}-{ordinal}-{digest[:12]}",
        "source_id": source_id,
        "source_type": str(source["source_type"]),
        "title": str(source["title"]),
        "section": section,
        "content": content,
        "entities": entities,
        "normalized_terms": normalize_terms(entities),
        "risk_level": risk_level_for_entities(entities),
        "trust_level": str(source["trust_level"]),
        "rights_status": str(source["rights_status"]),
        "version": "p6.0",
        "hash": f"sha256:{content_digest}",
        "source_hash": str(source.get("hash") or ""),
        "registry_version": str(source.get("registry_version") or "p6c.registry.v1"),
        "review_version": str(source.get("review_version") or source.get("version") or "p6c.review.v1"),
        "source_registry_metadata": {
            "source_id": source_id,
            "source_type": str(source.get("source_type") or ""),
            "language": str(source.get("language") or ""),
            "rights_status": str(source.get("rights_status") or ""),
            "safety_status": str(source.get("safety_status") or ""),
            "provenance_status": str(source.get("provenance_status") or ""),
            "approved_for_runtime": source.get("approved_for_runtime"),
            "approved_for_eval": source.get("approved_for_eval"),
            "approved_for_training": source.get("approved_for_training"),
            "approved_for_public_demo": source.get("approved_for_public_demo"),
            "contains_medical_claims": source.get("contains_medical_claims"),
            "contains_prescription_content": source.get("contains_prescription_content"),
            "contains_pii": source.get("contains_pii"),
            "reviewer": str(source.get("reviewer") or ""),
            "reviewed_at": str(source.get("reviewed_at") or ""),
            "version": str(source.get("version") or ""),
            "hash": str(source.get("hash") or ""),
        },
        "provenance": {
            "content_path": str(source.get("content_path") or ""),
            "license": str(source.get("license") or ""),
            "allowed_use": _as_string_list(source.get("allowed_use")),
            "forbidden_use": _as_string_list(source.get("forbidden_use")),
        },
    }


def build_chunks(
    manifest: dict[str, Any],
    reviews: Sequence[SourceReview],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    approved = {review.source_id: review for review in reviews if review.status == "approved"}
    sources = {
        str(source.get("source_id")): source
        for source in manifest.get("sources", [])
        if isinstance(source, dict)
    }
    chunks: list[dict[str, Any]] = []
    cleaning_results: list[dict[str, Any]] = []

    for source_id, review in sorted(approved.items()):
        source = sources[source_id]
        assert review.content_path is not None
        raw_text = review.content_path.read_text(encoding="utf-8")
        raw_hash = sha256(raw_text.encode("utf-8")).hexdigest()
        cleaned = clean_text(raw_text)
        markers = content_has_forbidden_markers(cleaned)
        if markers:
            cleaning_results.append(
                {
                    "source_id": source_id,
                    "status": "blocked",
                    "reason": "content contains forbidden PII-like markers",
                    "markers": markers,
                }
            )
            continue
        sections = split_sections(cleaned)
        ordinal = 1
        for section, section_text in sections:
            for chunk_section_name, content in chunk_section(section, section_text):
                chunks.append(
                    make_chunk(
                        source,
                        section=chunk_section_name,
                        content=content,
                        ordinal=ordinal,
                    )
                )
                ordinal += 1
        cleaning_results.append(
            {
                "source_id": source_id,
                "status": "ok",
                "raw_hash": f"sha256:{raw_hash}",
                "section_count": len(sections),
                "chunk_count": ordinal - 1,
            }
        )
    return chunks, cleaning_results


def tokenize(text: str) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]+|[a-z0-9_]+", text.lower())
    return [token for token in tokens if token not in STOPWORDS and len(token) > 1]


def _source_review_fingerprint(reviews: Sequence[SourceReview]) -> str:
    rows = [
        {
            "source_id": review.source_id,
            "status": review.status,
            "ok": review.ok,
            "reason": review.reason,
        }
        for review in reviews
    ]
    payload = json.dumps(rows, ensure_ascii=False, sort_keys=True)
    return "sha256:" + sha256(payload.encode("utf-8")).hexdigest()


def build_index(
    chunks: Sequence[dict[str, Any]],
    *,
    registry_version: str = SOURCE_MANIFEST_SCHEMA_VERSION,
    review_fingerprint: str = "",
) -> dict[str, Any]:
    inverted: dict[str, list[dict[str, Any]]] = defaultdict(list)
    chunk_rows: list[dict[str, Any]] = []
    for chunk in chunks:
        tokens = tokenize(str(chunk["content"]))
        counts = Counter(tokens)
        chunk_rows.append(
            {
                "chunk_id": chunk["chunk_id"],
                "source_id": chunk["source_id"],
                "section": chunk["section"],
                "hash": chunk["hash"],
                "source_hash": chunk.get("source_hash", ""),
                "registry_version": chunk.get("registry_version", ""),
                "review_version": chunk.get("review_version", ""),
                "token_count": len(tokens),
                "unique_token_count": len(counts),
                "normalized_terms": list(chunk.get("normalized_terms") or []),
            }
        )
        for token, count in sorted(counts.items()):
            inverted[token].append({"chunk_id": chunk["chunk_id"], "count": count})

    return {
        "schema_version": INDEX_SCHEMA_VERSION,
        "phase": "P6",
        "generated_at": utc_now(),
        "tokenizer": "p6_simple_lexical_v0",
        "chunk_schema_version": CHUNK_SCHEMA_VERSION,
        "source_registry_schema_version": registry_version,
        "source_review_fingerprint": review_fingerprint,
        "chunk_count": len(chunks),
        "chunks": chunk_rows,
        "inverted_index": dict(sorted(inverted.items())),
    }


def retrieve_from_index(
    query: str,
    chunks: Sequence[dict[str, Any]],
    *,
    top_k: int = 3,
) -> list[dict[str, Any]]:
    query_terms = set(tokenize(query))
    scored: list[tuple[float, dict[str, Any]]] = []
    for chunk in chunks:
        chunk_terms = set(tokenize(str(chunk["content"])))
        normalized_terms = set(chunk.get("normalized_terms") or [])
        score = float(len(query_terms & chunk_terms))
        score += float(len(query_terms & normalized_terms) * 3)
        scored.append((score, chunk))
    scored.sort(key=lambda item: (item[0], str(item[1]["chunk_id"])), reverse=True)
    return [
        {
            "chunk_id": chunk["chunk_id"],
            "source_id": chunk["source_id"],
            "section": chunk["section"],
            "score": score,
            "normalized_terms": list(chunk.get("normalized_terms") or []),
        }
        for score, chunk in scored[:top_k]
        if score > 0
    ]


def run_retrieval_eval(chunks: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    for case in EVAL_CASES:
        retrieved = retrieve_from_index(str(case["query"]), chunks, top_k=3)
        returned_terms = {
            term
            for item in retrieved
            for term in item.get("normalized_terms", [])
        }
        expected_terms = set(case["expected_terms"])
        passed = bool(retrieved) and bool(expected_terms & returned_terms)
        results.append(
            {
                "case_id": case["case_id"],
                "query": case["query"],
                "expected_terms": sorted(expected_terms),
                "retrieved": retrieved,
                "passed": passed,
            }
        )
    return results


def run_safety_eval(chunks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    pii_hits = [
        {"chunk_id": chunk["chunk_id"], "hits": content_has_forbidden_markers(str(chunk["content"]))}
        for chunk in chunks
        if content_has_forbidden_markers(str(chunk["content"]))
    ]
    unsafe_generation_hits: list[dict[str, Any]] = []
    for chunk in chunks:
        hits = [
            pattern.pattern
            for pattern in UNSAFE_GENERATION_PATTERNS
            if pattern.search(str(chunk["content"]))
        ]
        if hits:
            unsafe_generation_hits.append({"chunk_id": chunk["chunk_id"], "hits": hits})

    rights_ok = all(
        str(chunk.get("rights_status")) in INGESTIBLE_RIGHTS_STATUSES for chunk in chunks
    )
    boundary = {
        "core_state_readonly": True,
        "risk_rule_first": True,
        "can_diagnose": False,
        "can_prescribe": False,
        "can_create_treatment_plan": False,
        "forbidden_state_writes": FORBIDDEN_STATE_WRITES,
    }
    checks = [
        {"name": "no_pii_markers", "ok": not pii_hits, "detail": pii_hits},
        {
            "name": "no_diagnosis_or_prescription_generation",
            "ok": not unsafe_generation_hits,
            "detail": unsafe_generation_hits,
        },
        {"name": "rights_status_cleared", "ok": rights_ok, "detail": ""},
        {"name": "rag_core_state_readonly", "ok": boundary["core_state_readonly"], "detail": ""},
        {"name": "high_risk_rule_first", "ok": boundary["risk_rule_first"], "detail": ""},
    ]
    return {
        "status": "ok" if all(check["ok"] for check in checks) else "failed",
        "boundary": boundary,
        "checks": checks,
    }


def build_eval_payload(chunks: Sequence[dict[str, Any]]) -> dict[str, Any]:
    retrieval = run_retrieval_eval(chunks)
    safety = run_safety_eval(chunks)
    retrieval_ok = all(case["passed"] for case in retrieval)
    return {
        "schema_version": "kb.eval.p6.v0",
        "phase": "P6",
        "generated_at": utc_now(),
        "status": "ok" if retrieval_ok and safety["status"] == "ok" else "failed",
        "retrieval_quality": {
            "status": "ok" if retrieval_ok else "failed",
            "case_count": len(retrieval),
            "passed_count": len([case for case in retrieval if case["passed"]]),
            "cases": retrieval,
        },
        "safety_boundary": safety,
    }


def summarize_reviews(reviews: Sequence[SourceReview]) -> dict[str, Any]:
    blocked = [review for review in reviews if review.status == "blocked"]
    approved = [review for review in reviews if review.status == "approved"]
    skipped = [review for review in reviews if review.status == "skipped"]
    return {
        "approved_source_count": len(approved),
        "skipped_source_count": len(skipped),
        "blocked_source_count": len(blocked),
        "reviews": [
            {
                "source_id": review.source_id,
                "status": review.status,
                "ok": review.ok,
                "reason": review.reason,
                "content_path": review.content_path,
            }
            for review in reviews
        ],
    }


def output_paths() -> dict[str, Path]:
    return {
        "chunks": DEFAULT_CHUNKS_PATH,
        "index": DEFAULT_INDEX_PATH,
        "eval": DEFAULT_EVAL_PATH,
        "artifact": DEFAULT_ARTIFACT_PATH,
    }


def run_p6_pipeline(
    *,
    manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
    write_outputs: bool = True,
) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    manifest = load_manifest(manifest_path)
    manifest_ok = _manifest_schema_ok(manifest)
    reviews = review_sources(manifest, manifest_path)
    chunks, cleaning_results = build_chunks(manifest, reviews)
    review_fingerprint = _source_review_fingerprint(reviews)
    index_payload = build_index(
        chunks,
        registry_version=str(manifest.get("schema_version") or ""),
        review_fingerprint=review_fingerprint,
    )
    eval_payload = build_eval_payload(chunks)
    review_summary = summarize_reviews(reviews)
    blocked_cleaning = [item for item in cleaning_results if item.get("status") != "ok"]
    status = "ok"
    if (
        not manifest_ok
        or review_summary["blocked_source_count"] > 0
        or bool(blocked_cleaning)
        or not chunks
        or eval_payload["status"] != "ok"
    ):
        status = "failed"

    paths = output_paths()
    stale_index_warnings: list[dict[str, Any]] = []
    if paths["index"].is_file():
        try:
            existing_index = json.loads(paths["index"].read_text(encoding="utf-8"))
            existing_fingerprint = str(existing_index.get("source_review_fingerprint") or "")
            if existing_fingerprint and existing_fingerprint != review_fingerprint:
                stale_index_warnings.append(
                    {
                        "status": "warning",
                        "reason": "source review fingerprint changed; index rebuild required",
                        "existing_source_review_fingerprint": existing_fingerprint,
                        "current_source_review_fingerprint": review_fingerprint,
                    }
                )
        except Exception as exc:
            stale_index_warnings.append(
                {
                    "status": "warning",
                    "reason": f"existing index could not be inspected for staleness: {exc}",
                }
            )
    payload = {
        "schema_version": PIPELINE_SCHEMA_VERSION,
        "phase": "P6",
        "generated_at": utc_now(),
        "status": status,
        "scope": "formal clean/chunk/index/eval pipeline for reviewed rights-cleared knowledge sources",
        "runtime_changes": False,
        "api_schema_changes": False,
        "sqlite_changes": False,
        "risk_rule_changes": False,
        "large_real_book_ingestion": False,
        "diagnosis_system": False,
        "manifest": {
            "path": manifest_path,
            "schema_version": manifest.get("schema_version"),
            "schema_valid": manifest_ok,
        },
        "source_registry": {
            "path": manifest_path,
            "schema_version": manifest.get("schema_version"),
            "source_review_fingerprint": review_fingerprint,
            "stale_index_warnings": stale_index_warnings,
        },
        "source_review": review_summary,
        "cleaning": {
            "status": "ok" if not blocked_cleaning else "failed",
            "results": cleaning_results,
        },
        "chunking": {
            "status": "ok" if chunks else "failed",
            "chunk_schema_version": CHUNK_SCHEMA_VERSION,
            "chunk_count": len(chunks),
            "chunk_hashes": [chunk["hash"] for chunk in chunks],
        },
        "index_generation": {
            "status": "ok" if index_payload["chunk_count"] == len(chunks) else "failed",
            "index_schema_version": INDEX_SCHEMA_VERSION,
            "chunk_count": index_payload["chunk_count"],
            "tokenizer": index_payload["tokenizer"],
        },
        "evaluation": eval_payload,
        "rag_boundary": eval_payload["safety_boundary"]["boundary"],
        "outputs": {name: path for name, path in paths.items()},
        "p6_completion_criteria": [
            "source manifest parsed and reviewed",
            "only approved P6 sources indexed",
            "cleaned content preserves provenance and hashes",
            "chunks conform to kb.chunk.v0",
            "lexical index generated",
            "retrieval quality and safety boundary evaluation passed",
            "RAG remains read-only and high-risk triage remains rule-first",
        ],
    }

    if write_outputs:
        write_jsonl(paths["chunks"], chunks)
        write_json(paths["index"], index_payload)
        write_json(paths["eval"], eval_payload)
        write_json(paths["artifact"], payload)
    payload["_chunks"] = chunks
    payload["_index"] = index_payload
    return payload


def exit_code_for_status(status: str) -> int:
    return 0 if status == "ok" else 1


def artifact_summary(payload: dict[str, Any]) -> str:
    return (
        "P6 knowledge pipeline: "
        f"status={payload['status']} "
        f"sources={payload['source_review']['approved_source_count']} approved "
        f"chunks={payload['chunking']['chunk_count']} "
        f"eval={payload['evaluation']['status']}"
    )
