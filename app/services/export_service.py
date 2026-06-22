from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.api.redaction import redact_secrets
from app.schemas.report_schemas import SAFETY_DISCLAIMER
from app.services.consultation_service import ConsultationService


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_EXPORT_DIR = ROOT_DIR / "artifacts" / "p10m2" / "exports"
SECRETISH = re.compile(r"(Authorization:\s*Bearer\s+\S+|OPENAI_API_KEY=\S+|sk-[A-Za-z0-9_-]+)", re.IGNORECASE)


def _export_dir() -> Path:
    raw = os.getenv("REPORT_EXPORT_DIR")
    path = Path(raw) if raw else DEFAULT_EXPORT_DIR
    return path if path.is_absolute() else ROOT_DIR / path


def _safe(value: Any) -> Any:
    return redact_secrets(value)


def _safe_text(value: str) -> str:
    return SECRETISH.sub("[redacted-secret]", str(redact_secrets(value)))


def _rel(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT_DIR)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


class ExportService:
    def __init__(self, consultation_service: ConsultationService | None = None, export_dir: Path | None = None) -> None:
        self.consultation_service = consultation_service or ConsultationService()
        self.export_dir = export_dir or _export_dir()

    def _payload(self, session_id: str, *, include_debug_raw_input: bool = False) -> dict[str, Any]:
        report = self.consultation_service.get_report(session_id)
        if not include_debug_raw_input:
            report.pop("debug_raw_input", None)
        return _safe(report)

    def export_report(
        self,
        session_id: str,
        *,
        format: str = "json",
        include_debug_raw_input: bool = False,
    ) -> dict[str, Any]:
        payload = self._payload(session_id, include_debug_raw_input=include_debug_raw_input)
        report_available = bool(payload.get("report_available"))
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        safe_session = re.sub(r"[^A-Za-z0-9_.-]+", "-", session_id)
        suffix = "md" if format in {"markdown", "summary_markdown"} else "json"
        output_path = self.export_dir / f"{safe_session}-{timestamp}.{suffix}"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        if suffix == "json":
            output_path.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
        else:
            output_path.write_text(self._markdown(payload, summary_only=format == "summary_markdown"), encoding="utf-8")
        return {
            "status": "ok",
            "session_id": session_id,
            "format": format,
            "path": _rel(output_path),
            "report_available": report_available,
        }

    def _markdown(self, payload: dict[str, Any], *, summary_only: bool = False) -> str:
        report = payload.get("final_report") or {}
        lines = [
            "# TCM-Assistant Session Report",
            "",
            f"Session: `{_safe_text(str(payload.get('session_id', '')) )}`",
            "",
            "## Safety Disclaimer",
            "",
            _safe_text(str(payload.get("safety_disclaimer") or report.get("safety_disclaimer") or SAFETY_DISCLAIMER)),
            "",
            "## Risk",
            "",
            f"- Risk status: `{_safe_text(str(payload.get('risk_status') or 'unknown'))}`",
        ]
        for reason in payload.get("risk_reasons") or []:
            lines.append(f"- {_safe_text(str(reason))}")
        if summary_only:
            lines.extend(["", "## Summary", "", _safe_text(str(report.get("summary") or "Report is not available yet."))])
        else:
            lines.extend(
                [
                    "",
                    "## Summary",
                    "",
                    _safe_text(str(report.get("summary") or "Report is not available yet.")),
                    "",
                    "## Impression",
                    "",
                    _safe_text(str(report.get("impression") or "")),
                    "",
                    "## Advice",
                    "",
                ]
            )
            for item in report.get("advice") or []:
                lines.append(f"- {_safe_text(str(item))}")
        citations = report.get("evidence_citations") or payload.get("evidence") or []
        lines.extend(["", "## Evidence Citations", ""])
        if citations:
            for citation in citations:
                if not isinstance(citation, dict):
                    continue
                label = citation.get("citation_id") or citation.get("chunk_id") or "evidence"
                title = citation.get("title") or citation.get("source_id") or ""
                excerpt = citation.get("content_excerpt") or citation.get("content") or ""
                lines.append(f"- `{_safe_text(str(label))}` {_safe_text(str(title))}: {_safe_text(str(excerpt))}")
        else:
            lines.append("- not_applicable")
        return "\n".join(lines).rstrip() + "\n"

