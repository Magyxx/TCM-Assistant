from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path
from typing import Any, Sequence


ROOT_DIR = Path(__file__).resolve().parents[2]
KNOWLEDGE_DIR = ROOT_DIR / "knowledge"
SOURCE_REGISTRY_SCHEMA_VERSION = "kb.source_registry.v1"
DEFAULT_SOURCE_REGISTRY_PATH = KNOWLEDGE_DIR / "sources" / "source_registry.json"
DEFAULT_SOURCE_MANIFEST_SCHEMA_PATH = KNOWLEDGE_DIR / "sources" / "source_manifest.schema.json"

SOURCE_TYPES = {
    "policy",
    "terminology",
    "guideline",
    "internal_review",
    "fixture",
    "public_domain",
    "other",
}
RIGHTS_STATUSES = {"approved", "rejected", "unknown", "restricted"}
SAFETY_STATUSES = {"approved", "rejected", "needs_review"}
PROVENANCE_STATUSES = {"approved", "rejected", "unknown"}
REQUIRED_P6C_SOURCE_FIELDS = {
    "source_id",
    "title",
    "source_type",
    "language",
    "rights_status",
    "safety_status",
    "provenance_status",
    "approved_for_runtime",
    "approved_for_eval",
    "approved_for_training",
    "approved_for_public_demo",
    "contains_medical_claims",
    "contains_prescription_content",
    "contains_pii",
    "reviewer",
    "reviewed_at",
    "version",
    "hash",
    "notes",
}


class SourceRegistryError(ValueError):
    pass


@dataclass(frozen=True)
class SourceRegistryValidation:
    source_id: str
    status: str
    errors: tuple[str, ...]
    warnings: tuple[str, ...]

    @property
    def ok(self) -> bool:
        return not self.errors


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def json_safe(value: Any) -> Any:
    if isinstance(value, Path):
        try:
            return str(value.relative_to(ROOT_DIR)).replace("\\", "/")
        except ValueError:
            return str(value).replace("\\", "/")
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def write_json(path: Path | str, payload: dict[str, Any]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(json_safe(payload), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def read_json(path: Path | str) -> dict[str, Any]:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SourceRegistryError(f"missing source registry: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SourceRegistryError(f"invalid source registry JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise SourceRegistryError("source registry must be a JSON object")
    return payload


def load_source_registry(path: Path | str = DEFAULT_SOURCE_REGISTRY_PATH) -> dict[str, Any]:
    return read_json(path)


def is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def resolve_source_content_path(source: dict[str, Any], registry_path: Path | str) -> Path | None:
    raw = source.get("content_path")
    if not raw:
        return None
    registry_path = Path(registry_path)
    candidate = (registry_path.parent / str(raw)).resolve()
    if is_relative_to(candidate, KNOWLEDGE_DIR.resolve()):
        return candidate
    return None


def source_file_hash(source: dict[str, Any], registry_path: Path | str) -> str | None:
    content_path = resolve_source_content_path(source, registry_path)
    if content_path is None or not content_path.is_file():
        return None
    return "sha256:" + sha256(content_path.read_bytes()).hexdigest()


def source_has_p6c_shape(source: dict[str, Any]) -> bool:
    return bool(REQUIRED_P6C_SOURCE_FIELDS & set(source))


def validate_source_entry(
    source: dict[str, Any],
    *,
    registry_path: Path | str,
    seen_ids: set[str],
) -> SourceRegistryValidation:
    source_id = str(source.get("source_id") or "")
    errors: list[str] = []
    warnings: list[str] = []
    if not source_id:
        source_id = "missing_source_id"
        errors.append("source_id is required")
    if source_id in seen_ids:
        errors.append("duplicate source_id")
    seen_ids.add(source_id)

    missing = sorted(REQUIRED_P6C_SOURCE_FIELDS - set(source))
    if missing:
        errors.append(f"missing required P6C fields: {', '.join(missing)}")

    source_type = str(source.get("source_type") or "")
    if source_type and source_type not in SOURCE_TYPES:
        errors.append(f"unsupported source_type: {source_type}")
    rights_status = str(source.get("rights_status") or "")
    safety_status = str(source.get("safety_status") or "")
    provenance_status = str(source.get("provenance_status") or "")
    if rights_status and rights_status not in RIGHTS_STATUSES:
        errors.append(f"unsupported rights_status: {rights_status}")
    if safety_status and safety_status not in SAFETY_STATUSES:
        errors.append(f"unsupported safety_status: {safety_status}")
    if provenance_status and provenance_status not in PROVENANCE_STATUSES:
        errors.append(f"unsupported provenance_status: {provenance_status}")

    approved_for_runtime = source.get("approved_for_runtime") is True
    if approved_for_runtime:
        if rights_status != "approved":
            errors.append("approved_for_runtime requires rights_status=approved")
        if safety_status != "approved":
            errors.append("approved_for_runtime requires safety_status=approved")
        if provenance_status != "approved":
            errors.append("approved_for_runtime requires provenance_status=approved")
        if source.get("contains_pii") is True:
            errors.append("approved_for_runtime cannot be true when contains_pii=true")
        if source.get("contains_prescription_content") is True and source.get("source_use_category") != "safety_negative_sample":
            errors.append(
                "prescription content cannot enter report-generation runtime index unless it is a safety_negative_sample"
            )
        if str(source.get("ingestion_status") or "") == "planned_smoke_only":
            errors.append("P5 smoke-only sources cannot be approved for runtime")

    if source.get("approved_for_training") is True and source.get("training_rights_basis") in {None, ""}:
        errors.append("approved_for_training requires an explicit training_rights_basis")

    if rights_status == "unknown":
        warnings.append("unknown rights must fail closed")
    if provenance_status == "unknown":
        warnings.append("unknown provenance must fail closed")
    if source.get("contains_pii") is True:
        warnings.append("PII-containing source must fail closed for runtime")

    content_path = resolve_source_content_path(source, registry_path)
    if source.get("content_path"):
        if content_path is None:
            errors.append("content_path must stay inside knowledge/")
        elif not content_path.is_file():
            errors.append(f"content_path does not exist: {source.get('content_path')}")

    declared_hash = str(source.get("hash") or "")
    actual_hash = source_file_hash(source, registry_path)
    if declared_hash.startswith("sha256:") and actual_hash and declared_hash != actual_hash:
        errors.append("source content hash mismatch")
    elif approved_for_runtime and not declared_hash.startswith("sha256:"):
        errors.append("approved_for_runtime source requires sha256 hash")

    return SourceRegistryValidation(
        source_id=source_id,
        status="ok" if not errors else "failed",
        errors=tuple(errors),
        warnings=tuple(warnings),
    )


def validate_source_registry(
    registry: dict[str, Any],
    *,
    registry_path: Path | str = DEFAULT_SOURCE_REGISTRY_PATH,
) -> dict[str, Any]:
    schema_pass = registry.get("schema_version") == SOURCE_REGISTRY_SCHEMA_VERSION
    sources = registry.get("sources")
    source_errors: list[str] = []
    if not isinstance(sources, list):
        sources = []
        source_errors.append("sources must be a list")

    seen_ids: set[str] = set()
    validations: list[SourceRegistryValidation] = []
    for source in sources:
        if not isinstance(source, dict):
            validations.append(
                SourceRegistryValidation(
                    source_id="invalid_source_entry",
                    status="failed",
                    errors=("source entry must be an object",),
                    warnings=(),
                )
            )
            continue
        validations.append(validate_source_entry(source, registry_path=registry_path, seen_ids=seen_ids))

    source_count = len(sources)
    validation_errors = [
        {"source_id": item.source_id, "errors": list(item.errors)}
        for item in validations
        if item.errors
    ]
    warnings = [
        {"source_id": item.source_id, "warnings": list(item.warnings)}
        for item in validations
        if item.warnings
    ]
    metrics = source_registry_metrics(sources)
    status = "ok" if schema_pass and not source_errors and not validation_errors else "failed"
    return {
        "phase": "P6C",
        "schema_version": SOURCE_REGISTRY_SCHEMA_VERSION,
        "generated_at": utc_now(),
        "status": status,
        "source_registry_schema_pass": schema_pass,
        "source_count": source_count,
        **metrics,
        "registry_errors": source_errors,
        "source_validation_errors": validation_errors,
        "warnings": warnings,
        "validations": [
            {
                "source_id": item.source_id,
                "status": item.status,
                "ok": item.ok,
                "errors": list(item.errors),
                "warnings": list(item.warnings),
            }
            for item in validations
        ],
    }


def source_registry_metrics(sources: Sequence[dict[str, Any]]) -> dict[str, int]:
    return {
        "approved_for_runtime_count": len([s for s in sources if s.get("approved_for_runtime") is True]),
        "approved_for_eval_count": len([s for s in sources if s.get("approved_for_eval") is True]),
        "approved_for_training_count": len([s for s in sources if s.get("approved_for_training") is True]),
        "approved_for_public_demo_count": len([s for s in sources if s.get("approved_for_public_demo") is True]),
        "rejected_count": len(
            [
                s
                for s in sources
                if s.get("rights_status") == "rejected"
                or s.get("safety_status") == "rejected"
                or s.get("provenance_status") == "rejected"
                or s.get("registry_location") == "rejected"
            ]
        ),
        "quarantine_count": len([s for s in sources if s.get("registry_location") == "quarantine"]),
        "unknown_rights_count": len([s for s in sources if s.get("rights_status") == "unknown"]),
        "unknown_provenance_count": len([s for s in sources if s.get("provenance_status") == "unknown"]),
        "pii_source_count": len([s for s in sources if s.get("contains_pii") is True]),
        "prescription_content_source_count": len([s for s in sources if s.get("contains_prescription_content") is True]),
    }
