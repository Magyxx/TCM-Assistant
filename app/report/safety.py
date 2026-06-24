from __future__ import annotations

import re

from app.report.schemas import ReportSafetyCheck


FORBIDDEN_PATTERNS = {
    "你得了": "diagnosis_claim",
    "诊断为": "diagnosis_claim",
    "确诊": "diagnosis_claim",
    "患有": "diagnosis_claim",
    "处方": "prescription_claim",
    "开方": "prescription_claim",
    "服用某药": "prescription_claim",
    "治疗方案": "treatment_plan_claim",
    "无需就医": "discourages_care",
    "不用就医": "discourages_care",
    "不必就医": "discourages_care",
    "可以代替医生": "replaces_clinician",
    "能够代替医生": "replaces_clinician",
    "可以替代医生": "replaces_clinician",
    "能够替代医生": "replaces_clinician",
    "prescribe": "prescription_claim",
    "diagnosed with": "diagnosis_claim",
    "no need to see a doctor": "discourages_care",
    "can replace a doctor": "replaces_clinician",
    "can replace clinician": "replaces_clinician",
}

DRUG_DOSE_PATTERN = re.compile(
    r"\d+(?:\.\d+)?\s*(?:mg|g|ml|毫克|克|毫升|片|粒|丸|袋|滴|bid|tid|qid|次/日)",
    re.IGNORECASE,
)


def check_report_safety(text: str) -> ReportSafetyCheck:
    lowered = text.lower()
    violations = [
        code
        for phrase, code in FORBIDDEN_PATTERNS.items()
        if phrase.lower() in lowered
    ]
    if DRUG_DOSE_PATTERN.search(text):
        violations.append("drug_dose_like")
    unique = list(dict.fromkeys(violations))
    return ReportSafetyCheck(ok=not unique, violations=unique)
