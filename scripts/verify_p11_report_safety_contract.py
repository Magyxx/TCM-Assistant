from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from pydantic import ValidationError

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

STAGE = "P11-M5_FINAL_REPORT_SAFETY_CONTRACT"
DEFAULT_OUTPUT = ROOT_DIR / "artifacts" / "p11" / "report_safety_contract.json"


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


def _make_report(**updates: Any):
    from app.schemas.report_schemas import FinalReport

    payload = {
        "summary": "Structured intake summary.",
        "impression": "Inquiry support only.",
        "advice": ["Track symptom changes and seek offline care for red flags."],
        "triage_level": "followup",
        "info_complete": True,
        "missing_core_fields": [],
        "followup_needed": False,
        "metadata": {"contract": "p11_m5"},
    }
    payload.update(updates)
    return FinalReport(**payload)


def _schema_probe() -> dict[str, Any]:
    from app.schemas.report_schemas import FinalReport

    payload = _make_report(
        evidence_citations=[
            {
                "citation_id": "EV001",
                "chunk_id": "chunk-1",
                "source_id": "safety_boundaries",
                "title": "Safety boundaries",
            }
        ],
        evidence_ids=["EV001"],
        citation_coverage={"status": "passed", "coverage": 1.0},
    ).model_dump()
    validated = FinalReport.model_validate(payload)
    invalid_triage_rejected = False
    invalid_payload = dict(payload)
    invalid_payload["triage_level"] = "diagnose"
    try:
        FinalReport.model_validate(invalid_payload)
    except ValidationError:
        invalid_triage_rejected = True

    required_fields = [
        "summary",
        "impression",
        "advice",
        "triage_level",
        "info_complete",
        "missing_core_fields",
        "followup_needed",
        "safety_disclaimer",
        "evidence_citations",
        "evidence_ids",
        "citation_coverage",
        "metadata",
    ]
    return {
        "passed": all(field in validated.model_dump() for field in required_fields) and invalid_triage_rejected,
        "required_fields_present": all(field in validated.model_dump() for field in required_fields),
        "invalid_triage_rejected": invalid_triage_rejected,
        "triage_level": validated.triage_level,
        "evidence_ids": validated.evidence_ids,
    }


def _text_checker_probe() -> dict[str, Any]:
    from app.report.safety import check_report_safety

    safe = check_report_safety("Structured intake summary with offline-care boundary.")
    diagnosis = check_report_safety("The patient is diagnosed with a named condition.")
    prescription = check_report_safety("Please prescribe 10mg medicine.")
    checks = {
        "safe_text_passes": safe.ok,
        "diagnosis_blocked": (not diagnosis.ok) and "diagnosis_claim" in diagnosis.violations,
        "prescription_blocked": (not prescription.ok) and "prescription_claim" in prescription.violations,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "diagnosis_violations": diagnosis.violations,
        "prescription_violations": prescription.violations,
    }


def _post_check_probe() -> dict[str, Any]:
    from app.safety.report_safety import FORBIDDEN_PHRASES, SAFETY_BOUNDARY_TEXT, safety_post_check_report

    diagnosis_phrase = FORBIDDEN_PHRASES[0]
    prescription_phrase = FORBIDDEN_PHRASES[4]
    diagnosis_result = safety_post_check_report(_make_report(impression=f"{diagnosis_phrase}: unsafe claim."))
    prescription_result = safety_post_check_report(_make_report(advice=[f"{prescription_phrase}: unsafe claim."]))
    diagnosis_text = (
        diagnosis_result.report.summary
        + diagnosis_result.report.impression
        + "".join(diagnosis_result.report.advice)
    )
    prescription_text = (
        prescription_result.report.summary
        + prescription_result.report.impression
        + "".join(prescription_result.report.advice)
    )
    checks = {
        "diagnosis_rewritten": diagnosis_result.rewritten and diagnosis_phrase not in diagnosis_text,
        "prescription_rewritten": prescription_result.rewritten and prescription_phrase not in prescription_text,
        "rewrite_metadata_present": diagnosis_result.report.metadata.get("safety_rewrite_used") is True
        and prescription_result.report.metadata.get("safety_rewrite_used") is True,
        "boundary_added": SAFETY_BOUNDARY_TEXT in diagnosis_result.report.impression
        and SAFETY_BOUNDARY_TEXT in prescription_result.report.advice,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "diagnosis_issue_count": len(diagnosis_result.issues),
        "prescription_issue_count": len(prescription_result.issues),
        "metadata_keys": sorted(diagnosis_result.report.metadata.keys()),
    }


def _high_risk_probe() -> dict[str, Any]:
    from app.safety.report_safety import SAFETY_BOUNDARY_TEXT, safety_post_check_report

    report = _make_report(
        impression="High risk signal reported; offline medical evaluation is recommended.",
        advice=["Seek urgent offline medical evaluation."],
        triage_level="urgent_visit",
        metadata={"risk_status": "present"},
    )
    result = safety_post_check_report(report)
    checks = {
        "urgent_triage_preserved": result.report.triage_level == "urgent_visit",
        "offline_care_advice_preserved": "Seek urgent offline medical evaluation." in result.report.advice,
        "boundary_added": SAFETY_BOUNDARY_TEXT in result.report.impression
        and SAFETY_BOUNDARY_TEXT in result.report.advice,
        "safe_content_not_rewritten": result.rewritten is False
        and result.report.metadata.get("safety_rewrite_used") is False,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "triage_level": result.report.triage_level,
        "advice_count": len(result.report.advice),
    }


def _citation_probe() -> dict[str, Any]:
    from app.rag.chunk_schema import RetrievalResult
    from app.rag.citation import attach_citations_to_report, citation_coverage, citations_from_results
    from app.safety.report_safety import safety_post_check_report

    retrieval_result = RetrievalResult(
        chunk_id="chunk-1",
        source_id="safety_boundaries",
        title="Safety boundaries",
        content="Evidence can support explanation but cannot diagnose or prescribe.",
        score=1.0,
        fusion_score=1.0,
        citation_id="EV001",
        source_type="safety_boundary",
        trust_level="project_curated",
    )
    citations = citations_from_results([retrieval_result])
    cited_report = attach_citations_to_report(_make_report(), citations)
    checked = safety_post_check_report(cited_report).report
    coverage = citation_coverage(checked.model_dump(), citations)
    checks = {
        "evidence_ids_preserved": checked.evidence_ids == ["EV001"],
        "citations_preserved": bool(checked.evidence_citations)
        and checked.evidence_citations[0].get("chunk_id") == "chunk-1",
        "citation_coverage_passed": checked.citation_coverage
        and checked.citation_coverage.get("status") == "passed"
        and coverage.status == "passed",
        "safety_metadata_added": "safety_boundary" in checked.metadata,
    }
    return {
        "passed": all(checks.values()),
        "checks": checks,
        "evidence_ids": checked.evidence_ids,
        "citation_coverage": checked.citation_coverage,
    }


def verify() -> dict[str, Any]:
    schema = _schema_probe()
    text_checker = _text_checker_probe()
    post_check = _post_check_probe()
    high_risk = _high_risk_probe()
    citation = _citation_probe()
    checks = {
        "final_report_schema_guard": bool(schema["passed"]),
        "text_safety_checker_blocks_claims": bool(text_checker["passed"]),
        "post_check_rewrites_forbidden_terms": bool(post_check["passed"]),
        "high_risk_triage_preserved": bool(high_risk["passed"]),
        "evidence_citations_preserved": bool(citation["passed"]),
    }
    return {
        "stage": STAGE,
        "status": "ok" if all(checks.values()) else "failed",
        "branch": _git(["branch", "--show-current"]),
        "commit": _git(["rev-parse", "HEAD"]),
        "origin_main": _git(["rev-parse", "origin/main"]),
        "checks": checks,
        "schema": schema,
        "text_safety_checker": text_checker,
        "post_check": post_check,
        "high_risk_triage": high_risk,
        "evidence_citation": citation,
        "contract": {
            "forbidden_claims": [
                "diagnosis_claim",
                "prescription_claim",
                "treatment_plan_claim",
                "replaces_clinician",
                "discourages_care",
                "drug_dose_like",
            ],
            "high_risk_action": "urgent_visit with offline medical evaluation guidance",
            "citation_policy": "preserve evidence_ids, evidence_citations, and citation_coverage through post-check",
            "rewrite_metadata": ["safety_post_check_issues", "safety_rewrite_used", "safety_violation_type"],
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify P11-M5 final report safety contract.")
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
