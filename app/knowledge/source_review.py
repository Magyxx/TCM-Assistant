from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from app.knowledge.source_registry import (
    DEFAULT_SOURCE_REGISTRY_PATH,
    load_source_registry,
    resolve_source_content_path,
    source_file_hash,
    source_registry_metrics,
    utc_now,
    validate_source_registry,
)


REVIEW_CHECKS = [
    "rights_review",
    "safety_review",
    "provenance_review",
    "runtime_permission_review",
    "training_permission_review",
    "public_demo_permission_review",
    "prescription_content_review",
    "diagnosis_content_review",
    "pii_review",
    "staleness_review",
    "hash_integrity_review",
]


@dataclass(frozen=True)
class SourceReviewResult:
    source_id: str
    status: str
    approved_for_runtime: bool
    approved_for_eval: bool
    approved_for_training: bool
    approved_for_public_demo: bool
    checks: dict[str, bool]
    failures: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.failures


def _is_smoke_only(source: dict[str, Any]) -> bool:
    return str(source.get("ingestion_status") or "") == "planned_smoke_only" or "smoke" in str(
        source.get("source_id") or ""
    ).lower()


def review_source(source: dict[str, Any], *, registry_path: Path | str) -> SourceReviewResult:
    source_id = str(source.get("source_id") or "missing_source_id")
    rights_status = str(source.get("rights_status") or "")
    safety_status = str(source.get("safety_status") or "")
    provenance_status = str(source.get("provenance_status") or "")
    approved_for_runtime = source.get("approved_for_runtime") is True
    approved_for_eval = source.get("approved_for_eval") is True
    approved_for_training = source.get("approved_for_training") is True
    approved_for_public_demo = source.get("approved_for_public_demo") is True
    contains_pii = source.get("contains_pii") is True
    contains_prescription_content = source.get("contains_prescription_content") is True
    contains_diagnosis_content = source.get("contains_diagnosis_content") is True
    source_use_category = str(source.get("source_use_category") or "")

    actual_hash = source_file_hash(source, registry_path)
    declared_hash = str(source.get("hash") or "")
    hash_ok = bool(actual_hash and declared_hash == actual_hash)
    if not source.get("content_path"):
        hash_ok = bool(declared_hash.startswith("sha256:"))

    checks = {
        "rights_review": rights_status == "approved",
        "safety_review": safety_status == "approved",
        "provenance_review": provenance_status == "approved",
        "runtime_permission_review": (
            not approved_for_runtime
            or (
                rights_status == "approved"
                and safety_status == "approved"
                and provenance_status == "approved"
                and not contains_pii
                and not _is_smoke_only(source)
                and (
                    not contains_prescription_content
                    or source_use_category == "safety_negative_sample"
                )
            )
        ),
        "training_permission_review": (
            not approved_for_training
            or bool(source.get("training_rights_basis"))
        ),
        "public_demo_permission_review": (
            not approved_for_public_demo
            or (
                rights_status == "approved"
                and safety_status == "approved"
                and provenance_status == "approved"
                and not contains_pii
            )
        ),
        "prescription_content_review": (
            not approved_for_runtime
            or not contains_prescription_content
            or source_use_category == "safety_negative_sample"
        ),
        "diagnosis_content_review": not (approved_for_runtime and contains_diagnosis_content),
        "pii_review": not (approved_for_runtime and contains_pii),
        "staleness_review": str(source.get("staleness_status") or "current") in {"current", "fixture_static"},
        "hash_integrity_review": hash_ok,
    }
    failures = [name for name, ok in checks.items() if not ok and approved_for_runtime]
    warnings: list[str] = []
    if rights_status == "unknown":
        warnings.append("unknown rights source is fail-closed for runtime")
    if provenance_status == "unknown":
        warnings.append("unknown provenance source is fail-closed for runtime")
    if safety_status != "approved":
        warnings.append("source is not safety-approved for runtime")
    if _is_smoke_only(source):
        warnings.append("P5 smoke-only source is excluded from runtime index")
    if source.get("content_path") and resolve_source_content_path(source, registry_path) is None:
        failures.append("content_path_scope_review")

    if approved_for_runtime and failures:
        status = "failed"
    elif approved_for_runtime:
        status = "approved"
    elif warnings:
        status = "skipped"
    else:
        status = "skipped"

    return SourceReviewResult(
        source_id=source_id,
        status=status,
        approved_for_runtime=approved_for_runtime and not failures,
        approved_for_eval=approved_for_eval,
        approved_for_training=approved_for_training,
        approved_for_public_demo=approved_for_public_demo,
        checks=checks,
        failures=tuple(failures),
        warnings=tuple(warnings),
    )


def review_source_registry(
    *,
    registry_path: Path | str = DEFAULT_SOURCE_REGISTRY_PATH,
) -> dict[str, Any]:
    registry_path = Path(registry_path)
    registry = load_source_registry(registry_path)
    registry_validation = validate_source_registry(registry, registry_path=registry_path)
    raw_sources = registry.get("sources") if isinstance(registry.get("sources"), list) else []
    sources = [source for source in raw_sources if isinstance(source, dict)]
    reviews = [review_source(source, registry_path=registry_path) for source in sources]
    metrics = source_registry_metrics(sources)

    review_failures = [
        {"source_id": review.source_id, "failures": list(review.failures)}
        for review in reviews
        if review.failures
    ]
    warnings = [
        {"source_id": review.source_id, "warnings": list(review.warnings)}
        for review in reviews
        if review.warnings
    ]
    approved_for_runtime_count = len([review for review in reviews if review.approved_for_runtime])
    status = "ok"
    if registry_validation.get("status") != "ok" or review_failures:
        status = "failed"
    elif warnings:
        status = "caution"
    return {
        "phase": "P6C",
        "generated_at": utc_now(),
        "status": status,
        "source_count": len(sources),
        **metrics,
        "approved_for_runtime_count": approved_for_runtime_count,
        "review_checks": REVIEW_CHECKS,
        "registry_validation_status": registry_validation.get("status"),
        "review_failures": review_failures,
        "warnings": warnings,
        "reviews": [
            {
                "source_id": review.source_id,
                "status": review.status,
                "approved_for_runtime": review.approved_for_runtime,
                "approved_for_eval": review.approved_for_eval,
                "approved_for_training": review.approved_for_training,
                "approved_for_public_demo": review.approved_for_public_demo,
                "checks": review.checks,
                "failures": list(review.failures),
                "warnings": list(review.warnings),
            }
            for review in reviews
        ],
    }


def source_review_hard_pass(payload: dict[str, Any]) -> bool:
    return (
        payload.get("status") in {"ok", "caution"}
        and int(payload.get("approved_for_runtime_count") or 0) >= 1
        and not payload.get("review_failures")
    )
