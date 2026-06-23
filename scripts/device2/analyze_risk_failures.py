from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.rules.risk_rules import RISK_RULES, evaluate_risk_rules


DEFAULT_GOLD = ROOT / "data" / "sft" / "processed" / "sft_report_turn_extract_val.jsonl"
DEFAULT_METRICS = ROOT / "artifacts" / "device2" / "d2t1_metrics.json"
DEFAULT_REPO_PRED = ROOT / "artifacts" / "device2" / "predictions" / "local_lora_sample.jsonl"
DEFAULT_AUDIT_JSON = ROOT / "artifacts" / "device2" / "metrics" / "d2t1r_risk_failure_audit.json"
DEFAULT_METRIC_JSON = ROOT / "artifacts" / "device2" / "metrics" / "d2t1r_metric_audit.json"
DEFAULT_AUDIT_REPORT = ROOT / "reports" / "device2" / "d2t1r_risk_failure_audit.md"
DEFAULT_METRIC_REPORT = ROOT / "reports" / "device2" / "d2t1r_metric_audit.md"
TRI_STATES = {"unknown", "none", "present"}
NEGATION_TAGS = {"negation_detection", "parallel_negation", "risk_none", "fever_not_high_risk"}
RISK_TYPES = {
    "high fever": ["持续高热", "高烧不退", "高热", "39度", "39℃", "39°C", "体温39"],
    "chest pain": ["胸痛", "胸口痛", "胸口压着疼", "心口痛"],
    "dyspnea": ["呼吸困难", "喘不上气", "喘不过气", "气喘明显"],
    "hematochezia": ["便血", "黑便", "柏油样便"],
    "hematemesis": ["呕血"],
    "altered consciousness": ["意识模糊", "意识异常", "意识不清", "反应迟钝", "迷糊"],
    "severe abdominal pain": ["突发剧烈腹痛", "剧烈腹痛", "腹痛明显加重", "疼得很厉害"],
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def path_from_metrics(metrics_path: Path, backend: str) -> Path | None:
    if not metrics_path.exists():
        return None
    metrics = read_json(metrics_path)
    pred_dir = ((metrics.get("predictions") or {}).get("external_full") or "").strip()
    if not pred_dir:
        return None
    raw_candidate = f"{pred_dir.rstrip('/')}/{backend}_predictions.jsonl"
    candidate = Path(raw_candidate)
    if candidate.exists():
        return candidate
    if raw_candidate.startswith("/mnt/e/"):
        windows_candidate = Path("E:/") / raw_candidate[len("/mnt/e/") :]
        if windows_candidate.exists():
            return windows_candidate
    return None


def normalize(value: Any) -> Any:
    if isinstance(value, list):
        return sorted(str(item).strip() for item in value)
    if isinstance(value, str):
        return value.strip()
    return value


def tags(row: dict[str, Any]) -> set[str]:
    return set((row.get("meta") or {}).get("tags") or [])


def user_text(row: dict[str, Any]) -> str:
    return str(((row.get("input") or {}).get("user_input")) or "")


def state_json(row: dict[str, Any]) -> dict[str, Any]:
    state = (row.get("input") or {}).get("state_json") or {}
    return state if isinstance(state, dict) else {}


def expected_status(row: dict[str, Any]) -> str:
    return str((row.get("output") or {}).get("risk_flags_status") or "unknown")


def predicted_status(pred: dict[str, Any] | None) -> str:
    if not pred:
        return "<missing>"
    return str((pred.get("output") or {}).get("risk_flags_status") or "<missing>")


def predicted_flags(pred: dict[str, Any] | None) -> list[str]:
    if not pred:
        return []
    flags = (pred.get("output") or {}).get("risk_flags") or []
    return [str(item) for item in flags] if isinstance(flags, list) else []


def has_risk_tag(row: dict[str, Any]) -> bool:
    return any("risk" in tag for tag in tags(row))


def is_legacy_risk_case(row: dict[str, Any]) -> bool:
    return has_risk_tag(row) or expected_status(row) != "unknown"


def is_negation_case(row: dict[str, Any]) -> bool:
    return bool(tags(row) & NEGATION_TAGS) or any("negation" in tag for tag in tags(row))


def risk_text_blob(row: dict[str, Any]) -> str:
    state = state_json(row)
    output = row.get("output") or {}
    parts = [
        user_text(row),
        str(state.get("summary") or ""),
        " ".join(str(item) for item in state.get("risk_flags") or []),
        " ".join(str(item) for item in output.get("risk_flags") or []),
        str((row.get("meta") or {}).get("description") or ""),
    ]
    return " ".join(parts)


def detected_risk_types(row: dict[str, Any]) -> list[str]:
    blob = risk_text_blob(row)
    found: list[str] = []
    for risk_type, keywords in RISK_TYPES.items():
        if any(keyword in blob for keyword in keywords):
            found.append(risk_type)
    return found or ["unknown"]


def has_present_evidence(row: dict[str, Any]) -> bool:
    state = state_json(row)
    if state.get("risk_flags_status") == "present" or state.get("risk_flags"):
        return True
    if (row.get("output") or {}).get("risk_flags"):
        return True
    evaluation = evaluate_risk_rules(user_text(row), previous_status=state.get("risk_flags_status", "unknown"))
    return evaluation.risk_status == "present"


def has_none_evidence(row: dict[str, Any]) -> bool:
    state = state_json(row)
    if state.get("risk_flags_status") == "none":
        return True
    evaluation = evaluate_risk_rules(user_text(row), previous_status=state.get("risk_flags_status", "unknown"))
    if evaluation.risk_status == "none":
        return True
    text = user_text(row)
    return any(marker in text for marker in ["没有", "未见", "无", "否认", "不"])


def tag_gold_conflict(row: dict[str, Any]) -> bool:
    row_tags = tags(row)
    status = expected_status(row)
    return ("risk_present" in row_tags and status != "present") or ("risk_none" in row_tags and status == "present")


def label_context_mismatch(row: dict[str, Any]) -> bool:
    status = expected_status(row)
    if status == "present":
        return not has_present_evidence(row)
    if status == "none":
        return not has_none_evidence(row)
    return False


def coherent_risk_case(row: dict[str, Any]) -> bool:
    if not is_legacy_risk_case(row):
        return False
    if tag_gold_conflict(row):
        return False
    if label_context_mismatch(row):
        return False
    return True


def classify_failure(row: dict[str, Any], pred: dict[str, Any] | None) -> tuple[str, str]:
    expected = expected_status(row)
    predicted = predicted_status(pred)
    if pred is None:
        return "missing_prediction", "prediction row is missing"
    if predicted not in TRI_STATES:
        return "invalid_or_empty_risk_field", "prediction risk_flags_status is missing or outside the tri-state schema"
    if tag_gold_conflict(row):
        return "tag_gold_conflict", "risk tag conflicts with gold risk_flags_status"
    if label_context_mismatch(row):
        return "label_context_mismatch", "gold status cannot be derived from state_json or current user text"
    if expected == "present" and predicted != "present":
        if has_present_evidence(row):
            return "false_negative", "risk evidence exists but predicted status is not present"
        return "false_negative_without_context", "gold is present but input context has no recoverable risk evidence"
    if expected != "present" and predicted == "present":
        return "false_positive", "prediction raised present risk when gold did not"
    if expected == "none" and predicted == "unknown":
        return "negative_case_left_unknown", "gold says risk was resolved as none but prediction stayed unknown"
    if expected == "unknown" and predicted != "unknown":
        return "unknown_case_overcommitted", "gold expects recheck/unknown but prediction committed a status"
    if expected != predicted:
        return "status_mismatch", "risk_flags_status differs from gold"
    return "passed", "status matches gold"


def summarize(gold_rows: list[dict[str, Any]], pred_rows: list[dict[str, Any]]) -> dict[str, Any]:
    pred_by_id = {row["id"]: row for row in pred_rows}
    legacy_cases = [row for row in gold_rows if is_legacy_risk_case(row)]
    coherent_cases = [row for row in legacy_cases if coherent_risk_case(row)]
    failed_examples: list[dict[str, Any]] = []
    per_type: dict[str, dict[str, int]] = {
        risk_type: {"total": 0, "passed": 0, "failed": 0} for risk_type in list(RISK_TYPES) + ["unknown"]
    }
    counts = {
        "passed_cases": 0,
        "failed_cases": 0,
        "false_negative_count": 0,
        "false_positive_count": 0,
        "negation_false_positive_count": 0,
        "negation_false_negative_count": 0,
        "risk_keyword_extracted_but_status_wrong_count": 0,
        "status_correct_but_evidence_missing_count": 0,
        "invalid_or_empty_risk_field_count": 0,
        "tag_gold_conflict_count": 0,
        "label_context_mismatch_count": 0,
    }

    for row in legacy_cases:
        pred = pred_by_id.get(row["id"])
        expected = expected_status(row)
        predicted = predicted_status(pred)
        status_ok = normalize(expected) == normalize(predicted)
        error_type, root_cause = classify_failure(row, pred)
        if status_ok:
            counts["passed_cases"] += 1
        else:
            counts["failed_cases"] += 1

        if error_type in {"false_negative", "false_negative_without_context"}:
            counts["false_negative_count"] += 1
        if error_type == "false_positive":
            counts["false_positive_count"] += 1
        if is_negation_case(row) and predicted == "present":
            counts["negation_false_positive_count"] += 1
        if is_negation_case(row) and expected == "none" and predicted != "none":
            counts["negation_false_negative_count"] += 1
        if predicted_flags(pred) and not status_ok:
            counts["risk_keyword_extracted_but_status_wrong_count"] += 1
        if status_ok and expected == "present" and not predicted_flags(pred):
            counts["status_correct_but_evidence_missing_count"] += 1
        if predicted not in TRI_STATES:
            counts["invalid_or_empty_risk_field_count"] += 1
        if tag_gold_conflict(row):
            counts["tag_gold_conflict_count"] += 1
        if label_context_mismatch(row):
            counts["label_context_mismatch_count"] += 1

        for risk_type in detected_risk_types(row):
            item = per_type[risk_type]
            item["total"] += 1
            if status_ok:
                item["passed"] += 1
            else:
                item["failed"] += 1

        if not status_ok:
            failed_examples.append(
                {
                    "id": row["id"],
                    "input": {
                        "state_json": state_json(row),
                        "user_input": user_text(row),
                    },
                    "gold": row.get("output") or {},
                    "prediction": (pred or {}).get("output") or None,
                    "tags": sorted(tags(row)),
                    "error_type": error_type,
                    "suspected_root_cause": root_cause,
                }
            )

    for item in per_type.values():
        item["accuracy"] = round(item["passed"] / item["total"], 4) if item["total"] else None

    coherent_pass = 0
    for row in coherent_cases:
        pred = pred_by_id.get(row["id"])
        if pred and normalize(expected_status(row)) == normalize(predicted_status(pred)):
            coherent_pass += 1

    return {
        "generated_at": utc_now(),
        "gold_file": str(DEFAULT_GOLD.relative_to(ROOT)),
        "total_risk_eval_cases": len(legacy_cases),
        "coherent_risk_eval_cases": len(coherent_cases),
        **counts,
        "legacy_metric": {
            "definition": "tag contains risk OR gold risk_flags_status is not unknown; exact tri-state string match",
            "risk_total": len(legacy_cases),
            "risk_status_pass": counts["passed_cases"],
            "risk_status_rate": round(counts["passed_cases"] / len(legacy_cases), 4) if legacy_cases else 0.0,
        },
        "new_metric": {
            "definition": "legacy risk case excluding tag/gold conflicts and label-context mismatches; exact tri-state string match",
            "risk_total": len(coherent_cases),
            "risk_status_pass": coherent_pass,
            "risk_status_rate": round(coherent_pass / len(coherent_cases), 4) if coherent_cases else 0.0,
            "excluded_as_tag_gold_conflict": counts["tag_gold_conflict_count"],
            "excluded_as_label_context_mismatch": counts["label_context_mismatch_count"],
        },
        "per_risk_type_accuracy": per_type,
        "top_failed_examples": failed_examples[:20],
        "metric_audit_conclusion": (
            "The D2-T1 risk_status_rate uses risk_flags_status, not risk_flags. It is an exact tri-state "
            "string match over a tag-derived risk subset. In this dataset the subset includes cases whose "
            "tags and gold labels or state context are inconsistent, so the legacy rate mixes model behavior "
            "with fixture quality."
        ),
    }


def write_reports(payload: dict[str, Any], audit_report: Path, metric_report: Path) -> None:
    lines = [
        "# D2-T1R Risk Failure Audit",
        "",
        f"Generated at: `{payload['generated_at']}`",
        "",
        "## Summary",
        "",
        f"* total risk eval cases: `{payload['total_risk_eval_cases']}`",
        f"* passed cases: `{payload['passed_cases']}`",
        f"* failed cases: `{payload['failed_cases']}`",
        f"* false negative count: `{payload['false_negative_count']}`",
        f"* false positive count: `{payload['false_positive_count']}`",
        f"* negation false positive count: `{payload['negation_false_positive_count']}`",
        f"* negation false negative count: `{payload['negation_false_negative_count']}`",
        f"* risk keyword extracted but status wrong count: `{payload['risk_keyword_extracted_but_status_wrong_count']}`",
        f"* status correct but evidence missing count: `{payload['status_correct_but_evidence_missing_count']}`",
        f"* invalid or empty risk field count: `{payload['invalid_or_empty_risk_field_count']}`",
        f"* tag/gold conflict count: `{payload['tag_gold_conflict_count']}`",
        f"* label/context mismatch count: `{payload['label_context_mismatch_count']}`",
        "",
        "## Per Risk Type Accuracy",
        "",
        "| Risk type | Total | Passed | Failed | Accuracy |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for risk_type, item in payload["per_risk_type_accuracy"].items():
        accuracy = "n/a" if item["accuracy"] is None else str(item["accuracy"])
        lines.append(f"| {risk_type} | {item['total']} | {item['passed']} | {item['failed']} | {accuracy} |")
    lines.extend(["", "## Top Failed Examples", ""])
    if payload["top_failed_examples"]:
        for item in payload["top_failed_examples"]:
            lines.extend(
                [
                    f"### {item['id']}",
                    "",
                    f"* error_type: `{item['error_type']}`",
                    f"* suspected_root_cause: {item['suspected_root_cause']}",
                    f"* input: `{item['input']['user_input']}`",
                    f"* gold risk_flags_status: `{item['gold'].get('risk_flags_status')}`",
                    f"* prediction risk_flags_status: `{(item['prediction'] or {}).get('risk_flags_status')}`",
                    "",
                ]
            )
    else:
        lines.append("* none")
    write_text(audit_report, "\n".join(lines) + "\n")

    metric = [
        "# D2-T1R Metric Audit",
        "",
        f"Generated at: `{payload['generated_at']}`",
        "",
        "## Legacy Metric",
        "",
        f"* definition: {payload['legacy_metric']['definition']}",
        f"* risk_total: `{payload['legacy_metric']['risk_total']}`",
        f"* risk_status_pass: `{payload['legacy_metric']['risk_status_pass']}`",
        f"* risk_status_rate: `{payload['legacy_metric']['risk_status_rate']}`",
        "",
        "## New Metric",
        "",
        f"* definition: {payload['new_metric']['definition']}",
        f"* risk_total: `{payload['new_metric']['risk_total']}`",
        f"* risk_status_pass: `{payload['new_metric']['risk_status_pass']}`",
        f"* risk_status_rate: `{payload['new_metric']['risk_status_rate']}`",
        f"* excluded_as_tag_gold_conflict: `{payload['new_metric']['excluded_as_tag_gold_conflict']}`",
        f"* excluded_as_label_context_mismatch: `{payload['new_metric']['excluded_as_label_context_mismatch']}`",
        "",
        "## Required Confirmations",
        "",
        "* Compared field: `risk_flags_status`.",
        "* Match rule: exact normalized tri-state string equality.",
        "* `unknown`, `none`, and `present` are distinct; the legacy subset selection can mix recheck/unknown cases with resolved risk cases.",
        "* `risk_flags_status` is the current TurnOutput field; there is no separate `risk_status` field in SFT TurnOutput.",
        "* Final risk judgement remains the responsibility of the deterministic RiskRuleEngine; the LoRA extractor should provide candidates, flags, and evidence.",
        "",
        "## Conclusion",
        "",
        payload["metric_audit_conclusion"],
        "",
    ]
    write_text(metric_report, "\n".join(metric))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze D2-T1 risk status failures and metric definition.")
    parser.add_argument("--gold-file", type=Path, default=DEFAULT_GOLD)
    parser.add_argument("--pred-file", type=Path, default=None)
    parser.add_argument("--metrics-file", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--backend", default="local_lora")
    parser.add_argument("--audit-json", type=Path, default=DEFAULT_AUDIT_JSON)
    parser.add_argument("--metric-json", type=Path, default=DEFAULT_METRIC_JSON)
    parser.add_argument("--audit-report", type=Path, default=DEFAULT_AUDIT_REPORT)
    parser.add_argument("--metric-report", type=Path, default=DEFAULT_METRIC_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    pred_file = args.pred_file or path_from_metrics(args.metrics_file, args.backend) or DEFAULT_REPO_PRED
    gold_rows = read_jsonl(args.gold_file)
    pred_rows = read_jsonl(pred_file)
    payload = summarize(gold_rows, pred_rows)
    payload["gold_file"] = str(args.gold_file)
    payload["pred_file"] = str(pred_file)
    write_json(args.audit_json, payload)
    write_json(args.metric_json, {
        "generated_at": payload["generated_at"],
        "gold_file": payload["gold_file"],
        "pred_file": payload["pred_file"],
        "legacy_metric": payload["legacy_metric"],
        "new_metric": payload["new_metric"],
        "required_confirmations": {
            "compared_field": "risk_flags_status",
            "exact_string_match": True,
            "tri_states_distinct": True,
            "turn_output_has_direct_risk_flags_status": True,
            "final_risk_judgement_should_be_rule_engine_backed": True,
        },
        "conclusion": payload["metric_audit_conclusion"],
    })
    write_reports(payload, args.audit_report, args.metric_report)
    print(json.dumps({"audit": str(args.audit_json), "metric_audit": str(args.metric_json)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
