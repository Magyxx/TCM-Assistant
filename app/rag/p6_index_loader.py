from __future__ import annotations

import json
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Any

from app.knowledge.pipeline import (
    CHUNK_SCHEMA_VERSION,
    DEFAULT_CHUNKS_PATH,
    DEFAULT_INDEX_PATH,
    DEFAULT_MANIFEST_PATH,
    INDEX_SCHEMA_VERSION,
    INGESTIBLE_RIGHTS_STATUSES,
    SOURCE_MANIFEST_SCHEMA_VERSION,
    review_sources,
)
from app.knowledge.source_registry import SOURCE_REGISTRY_SCHEMA_VERSION


class P6IndexLoadError(RuntimeError):
    pass


@dataclass(frozen=True)
class P6SourceGate:
    source_id: str
    rights_status: str
    safety_status: str
    provenance_status: str
    trust_level: str
    source_hash: str = ""
    registry_version: str = ""
    review_version: str = ""
    approved_for_runtime: bool = True


@dataclass(frozen=True)
class LoadedP6RuntimeIndex:
    index_path: Path
    chunks_path: Path
    source_manifest_path: Path
    index_payload: dict[str, Any]
    chunks: list[dict[str, Any]]
    source_gates: dict[str, P6SourceGate]
    index_version: str
    chunk_schema_version: str
    source_manifest_version: str

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    @property
    def loaded_source_ids(self) -> list[str]:
        return sorted({str(chunk["source_id"]) for chunk in self.chunks})


REQUIRED_CHUNK_FIELDS = {
    "schema_version",
    "chunk_id",
    "source_id",
    "source_type",
    "title",
    "section",
    "content",
    "entities",
    "normalized_terms",
    "risk_level",
    "trust_level",
    "rights_status",
    "version",
    "hash",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise P6IndexLoadError(f"missing required P6 artifact: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise P6IndexLoadError(f"invalid JSON artifact: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise P6IndexLoadError(f"JSON artifact must be an object: {path}")
    return payload


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise P6IndexLoadError(f"missing required P6 chunk artifact: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise P6IndexLoadError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
        if not isinstance(row, dict):
            raise P6IndexLoadError(f"chunk row must be an object at {path}:{line_number}")
        rows.append(row)
    if not rows:
        raise P6IndexLoadError(f"P6 chunk artifact is empty: {path}")
    return rows


def _source_gate_map(manifest: dict[str, Any], manifest_path: Path) -> dict[str, P6SourceGate]:
    if manifest.get("schema_version") not in {
        SOURCE_MANIFEST_SCHEMA_VERSION,
        SOURCE_REGISTRY_SCHEMA_VERSION,
    }:
        raise P6IndexLoadError(
            "source manifest schema mismatch: "
            f"{manifest.get('schema_version')!r} not in "
            f"{sorted([SOURCE_MANIFEST_SCHEMA_VERSION, SOURCE_REGISTRY_SCHEMA_VERSION])}"
        )

    reviews = review_sources(manifest, manifest_path)
    blocked = [review for review in reviews if review.status == "blocked"]
    if blocked:
        details = "; ".join(f"{review.source_id}:{review.reason}" for review in blocked)
        raise P6IndexLoadError(f"source manifest review failed: {details}")

    sources = {
        str(source.get("source_id")): source
        for source in manifest.get("sources", [])
        if isinstance(source, dict)
    }
    gates: dict[str, P6SourceGate] = {}
    for review in reviews:
        if review.status != "approved":
            continue
        source = sources.get(review.source_id) or {}
        rights_status = str(source.get("rights_status") or "")
        if rights_status not in INGESTIBLE_RIGHTS_STATUSES:
            raise P6IndexLoadError(f"source rights status is not ingestible: {review.source_id}")
        if source.get("approved_for_runtime") is False:
            raise P6IndexLoadError(f"source is not approved for P6 runtime: {review.source_id}")
        gates[review.source_id] = P6SourceGate(
            source_id=review.source_id,
            rights_status=rights_status,
            safety_status=str(source.get("safety_status") or "reviewed"),
            provenance_status=str(source.get("provenance_status") or "reviewed"),
            trust_level=str(source.get("trust_level") or ""),
            source_hash=str(source.get("hash") or ""),
            registry_version=str(source.get("registry_version") or "p6c.registry.v1"),
            review_version=str(source.get("review_version") or source.get("version") or "p6c.review.v1"),
            approved_for_runtime=True,
        )
    if not gates:
        raise P6IndexLoadError("no approved P6 sources found in source manifest")
    return gates


def _validate_chunks(
    chunks: list[dict[str, Any]],
    index_payload: dict[str, Any],
    source_gates: dict[str, P6SourceGate],
) -> None:
    if index_payload.get("schema_version") != INDEX_SCHEMA_VERSION:
        raise P6IndexLoadError(
            f"index schema mismatch: {index_payload.get('schema_version')!r} != {INDEX_SCHEMA_VERSION}"
        )
    if int(index_payload.get("chunk_count") or 0) <= 0:
        raise P6IndexLoadError("P6 index is empty")

    index_rows = index_payload.get("chunks")
    if not isinstance(index_rows, list) or not index_rows:
        raise P6IndexLoadError("P6 index has no chunk manifest rows")
    index_hash_by_id = {
        str(row.get("chunk_id")): str(row.get("hash"))
        for row in index_rows
        if isinstance(row, dict)
    }

    chunk_ids: set[str] = set()
    for chunk in chunks:
        missing = REQUIRED_CHUNK_FIELDS - set(chunk)
        if missing:
            raise P6IndexLoadError(
                f"chunk {chunk.get('chunk_id')!r} missing required fields: {sorted(missing)}"
            )
        if chunk.get("schema_version") != CHUNK_SCHEMA_VERSION:
            raise P6IndexLoadError(
                f"chunk schema mismatch for {chunk.get('chunk_id')}: "
                f"{chunk.get('schema_version')!r} != {CHUNK_SCHEMA_VERSION}"
            )
        chunk_id = str(chunk["chunk_id"])
        if chunk_id in chunk_ids:
            raise P6IndexLoadError(f"duplicate chunk_id in P6 chunks: {chunk_id}")
        chunk_ids.add(chunk_id)

        source_id = str(chunk["source_id"])
        if source_id not in source_gates:
            raise P6IndexLoadError(f"chunk source is not approved for P6 runtime: {source_id}")
        if str(chunk.get("rights_status")) != source_gates[source_id].rights_status:
            raise P6IndexLoadError(f"chunk rights status mismatch for {chunk_id}")
        if chunk.get("source_hash") and source_gates[source_id].source_hash:
            if str(chunk.get("source_hash")) != source_gates[source_id].source_hash:
                raise P6IndexLoadError(f"source hash mismatch for {chunk_id}")

        expected_hash = "sha256:" + sha256(str(chunk["content"]).encode("utf-8")).hexdigest()
        if chunk.get("hash") != expected_hash:
            raise P6IndexLoadError(f"chunk content hash mismatch for {chunk_id}")
        if index_hash_by_id.get(chunk_id) != chunk.get("hash"):
            raise P6IndexLoadError(f"index hash mismatch for {chunk_id}")

    missing_from_index = sorted(chunk_ids - set(index_hash_by_id))
    if missing_from_index:
        raise P6IndexLoadError(f"chunks missing from P6 index manifest: {missing_from_index}")
    if len(chunks) != int(index_payload.get("chunk_count") or 0):
        raise P6IndexLoadError(
            f"index chunk_count mismatch: {index_payload.get('chunk_count')} != {len(chunks)}"
        )


def load_p6_runtime_index(
    *,
    index_path: Path | str = DEFAULT_INDEX_PATH,
    chunks_path: Path | str = DEFAULT_CHUNKS_PATH,
    source_manifest_path: Path | str = DEFAULT_MANIFEST_PATH,
) -> LoadedP6RuntimeIndex:
    index_path = Path(index_path)
    chunks_path = Path(chunks_path)
    source_manifest_path = Path(source_manifest_path)
    index_payload = _read_json(index_path)
    chunks = _read_jsonl(chunks_path)
    manifest = _read_json(source_manifest_path)
    source_gates = _source_gate_map(manifest, source_manifest_path)
    _validate_chunks(chunks, index_payload, source_gates)
    return LoadedP6RuntimeIndex(
        index_path=index_path,
        chunks_path=chunks_path,
        source_manifest_path=source_manifest_path,
        index_payload=index_payload,
        chunks=chunks,
        source_gates=source_gates,
        index_version=str(index_payload.get("schema_version")),
        chunk_schema_version=CHUNK_SCHEMA_VERSION,
        source_manifest_version=str(manifest.get("schema_version")),
    )
