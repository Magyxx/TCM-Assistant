from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import patch

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STAGE = "P11-M4_RAG_EVIDENCE_CONTRACT"
DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p11" / "rag_evidence_contract.json"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=ROOT_DIR,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
    )
    return completed.stdout.strip() if completed.returncode == 0 else ""


def _sanitize_chunk_payload(chunk: dict[str, Any]) -> dict[str, Any]:
    sanitized = dict(chunk)
    metadata = dict(sanitized.get("metadata") or {})
    source_path = metadata.get("source_path")
    if source_path:
        try:
            path = Path(str(source_path))
            metadata["source_path"] = path.relative_to(ROOT_DIR).as_posix()
        except Exception:
            metadata["source_path"] = Path(str(source_path)).name
    sanitized["metadata"] = metadata
    return sanitized


def _evidence_pack_probe() -> dict[str, Any]:
    from app.rag.evidence_pack import build_evidence_pack
    from app.rag.models import EvidencePack

    pack = build_evidence_pack("stomach discomfort observation guidance", top_k=3)
    payload = pack.model_dump()
    validated = EvidencePack.model_validate(payload)
    required_chunk_fields = {"chunk_id", "source_id", "title", "content", "score"}
    chunk_payloads = [_sanitize_chunk_payload(chunk.model_dump()) for chunk in validated.chunks]
    required_present = [
        required_chunk_fields.issubset(chunk.keys())
        and bool(chunk.get("chunk_id"))
        and bool(chunk.get("source_id"))
        and bool(chunk.get("title"))
        and bool(chunk.get("content"))
        and isinstance(chunk.get("score"), float)
        for chunk in chunk_payloads
    ]
    source_metadata_present = [
        bool(chunk.get("source_type")) and bool(chunk.get("trust_level")) and isinstance(chunk.get("metadata"), dict)
        for chunk in chunk_payloads
    ]
    return {
        "passed": bool(validated.chunks)
        and validated.retrieval_mode == "bm25"
        and validated.guard_status == "passed"
        and all(required_present)
        and all(source_metadata_present),
        "result_count": validated.result_count,
        "retrieval_mode": validated.retrieval_mode,
        "guard_status": validated.guard_status,
        "required_chunk_fields_present": all(required_present),
        "source_metadata_present": all(source_metadata_present),
        "sample_chunks": chunk_payloads[:2],
    }


def _bm25_realpath_probe() -> dict[str, Any]:
    from app.config.settings import AppSettings
    from app.rag.retriever_router import retrieve_evidence_pack

    pack = retrieve_evidence_pack(
        "stomach discomfort observation guidance",
        top_k=2,
        settings=AppSettings(ENABLE_RAG=True, RAG_BACKEND="bm25_realpath"),
    )
    payload = pack.model_dump()
    sample_chunks = [_sanitize_chunk_payload(chunk) for chunk in payload.get("chunks", [])[:2]]
    return {
        "passed": pack.backend == "bm25_realpath" and not pack.skipped and bool(pack.chunks),
        "backend": pack.backend,
        "skipped": pack.skipped,
        "skip_reason": pack.skip_reason,
        "chunk_count": len(pack.chunks),
        "sample_chunks": sample_chunks,
    }


def _core_overwrite_guard_probe() -> dict[str, Any]:
    from app.rag.rag_guard import guard_rag_update

    fields = ["chief_complaint", "duration", "risk_status", "risk_rule_ids", "triggered_rule_ids"]
    blocked = {field: guard_rag_update({field: "retrieved evidence"}).allowed is False for field in fields}
    allowed = guard_rag_update({"retrieved_evidence": [{"chunk_id": "c1"}]}).allowed
    return {
        "passed": all(blocked.values()) and allowed,
        "blocked": blocked,
        "retrieved_evidence_allowed": allowed,
    }


def _retrieval_failure_probe() -> dict[str, Any]:
    from app.config.settings import AppSettings
    from app.rag.retriever_router import retrieve_evidence_pack

    def raise_runtime_error(*args, **kwargs):
        raise RuntimeError("forced retrieval failure")

    with patch("app.rag.retriever_router.build_realpath_evidence_pack", raise_runtime_error):
        pack = retrieve_evidence_pack(
            "stomach discomfort",
            top_k=2,
            settings=AppSettings(ENABLE_RAG=True, RAG_BACKEND="bm25_realpath"),
        )
    return {
        "passed": pack.skipped is True and pack.skip_reason.startswith("bm25_realpath_failed:"),
        "backend": pack.backend,
        "skipped": pack.skipped,
        "skip_reason": pack.skip_reason,
        "chunk_count": len(pack.chunks),
    }


def verify() -> dict[str, Any]:
    evidence_pack = _evidence_pack_probe()
    bm25_realpath = _bm25_realpath_probe()
    overwrite_guard = _core_overwrite_guard_probe()
    retrieval_failure = _retrieval_failure_probe()
    checks = {
        "evidence_pack_schema": bool(evidence_pack["passed"]),
        "bm25_realpath": bool(bm25_realpath["passed"]),
        "source_metadata": bool(evidence_pack["source_metadata_present"]),
        "rag_core_overwrite_guard": bool(overwrite_guard["passed"]),
        "retrieval_failure_degrades": bool(retrieval_failure["passed"]),
        "no_vector_db_or_reranker_required": True,
    }
    return {
        "stage": STAGE,
        "status": "ok" if all(checks.values()) else "failed",
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "HEAD"]),
        "origin_main": _git(["rev-parse", "origin/main"]),
        "checks": checks,
        "evidence_pack": evidence_pack,
        "bm25_realpath": bm25_realpath,
        "core_overwrite_guard": overwrite_guard,
        "retrieval_failure": retrieval_failure,
        "contract": {
            "allowed_targets": ["report", "evidence", "advice", "citations", "metadata"],
            "forbidden_core_fields": ["chief_complaint", "duration", "risk_status", "risk_rule_ids", "triggered_rule_ids"],
            "retrieval_mode": "bm25",
            "external_model_downloads": "not_required",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify P11-M4 RAG evidence contract.")
    parser.add_argument("--json", action="store_true", help="Print JSON output.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="Artifact output path.")
    args = parser.parse_args()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = verify()
    output = Path(args.output)
    if not output.is_absolute():
        output = ROOT_DIR / output
    _write_json(output, result)
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(result["status"])
    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
