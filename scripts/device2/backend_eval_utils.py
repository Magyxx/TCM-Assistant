from __future__ import annotations

import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


BUILTIN_CASES: list[dict[str, Any]] = [
    {"case_id": "builtin_001", "input": "胃胀一周，饭后明显，没有发热，不胸痛", "gold": {"gold_limited": True}},
    {"case_id": "builtin_002", "input": "咳嗽三天，有痰，没有呼吸困难", "gold": {"gold_limited": True}},
    {"case_id": "builtin_003", "input": "头痛两天，睡眠差，无发热", "gold": {"gold_limited": True}},
    {"case_id": "builtin_004", "input": "腹泻一天，大便稀，无便血", "gold": {"gold_limited": True}},
    {"case_id": "builtin_005", "input": "发热 39 度，持续一天", "gold": {"gold_limited": True}},
    {"case_id": "builtin_006", "input": "胸痛半小时，伴胸闷", "gold": {"gold_limited": True}},
    {"case_id": "builtin_007", "input": "呼吸困难，活动后明显", "gold": {"gold_limited": True}},
    {"case_id": "builtin_008", "input": "便血一次", "gold": {"gold_limited": True}},
    {"case_id": "builtin_009", "input": "失眠两周，入睡困难", "gold": {"gold_limited": True}},
    {"case_id": "builtin_010", "input": "胃痛饭后加重，恶心", "gold": {"gold_limited": True}},
    {"case_id": "builtin_011", "input": "怕冷，乏力，食欲差", "gold": {"gold_limited": True}},
    {"case_id": "builtin_012", "input": "咽痛咳嗽，无高热", "gold": {"gold_limited": True}},
    {"case_id": "builtin_013", "input": "腹痛剧烈，持续不缓解", "gold": {"gold_limited": True}},
    {"case_id": "builtin_014", "input": "头晕一天，无意识障碍", "gold": {"gold_limited": True}},
    {"case_id": "builtin_015", "input": "恶心呕吐，无呕血", "gold": {"gold_limited": True}},
    {"case_id": "builtin_016", "input": "心慌胸闷，持续十分钟", "gold": {"gold_limited": True}},
    {"case_id": "builtin_017", "input": "小便短赤，尿痛", "gold": {"gold_limited": True}},
    {"case_id": "builtin_018", "input": "大便干结三天", "gold": {"gold_limited": True}},
    {"case_id": "builtin_019", "input": "月经不调，腹痛", "gold": {"gold_limited": True}},
    {"case_id": "builtin_020", "input": "口干口苦，睡眠一般", "gold": {"gold_limited": True}},
]

NEGATION_MARKERS = ("没有", "无", "不胸痛", "不便血", "无发热", "无高热", "无意识障碍", "无呕血")
HIGH_RISK_MARKERS = ("胸痛", "呼吸困难", "便血", "呕血", "意识障碍", "39", "高热", "剧烈")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def run_git(args: list[str]) -> str:
    repo = ROOT.as_posix()
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={repo}", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0:
        return completed.stderr.strip() or completed.stdout.strip()
    return completed.stdout.strip()


def git_snapshot() -> dict[str, Any]:
    return {
        "branch": run_git(["branch", "--show-current"]),
        "head": run_git(["log", "--oneline", "--decorate", "-1"]),
        "recent_commits": run_git(["log", "--oneline", "--decorate", "-10"]).splitlines(),
    }


def _input_from_messages(messages: Any) -> str | None:
    if not isinstance(messages, list):
        return None
    for message in reversed(messages):
        if isinstance(message, dict) and message.get("role") == "user":
            content = message.get("content")
            return str(content) if content else None
    return None


def _case_from_raw(raw: dict[str, Any], index: int) -> dict[str, Any] | None:
    text = (
        raw.get("input")
        or raw.get("user_input")
        or raw.get("prompt")
        or raw.get("text")
        or _input_from_messages(raw.get("messages"))
    )
    if not text:
        return None
    gold = raw.get("gold") or raw.get("expected") or raw.get("output") or raw.get("label")
    if not isinstance(gold, dict):
        gold = {"gold_limited": True}
    return {
        "case_id": str(raw.get("case_id") or raw.get("id") or f"case_{index:03d}"),
        "input": str(text),
        "gold": gold,
    }


def load_jsonl_cases(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for index, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            parsed = _case_from_raw(json.loads(line), index)
            if parsed is not None:
                cases.append(parsed)
    return cases


def load_eval_cases(
    cases_path: str | Path | None = None,
    *,
    limit: int = 20,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates: list[Path] = []
    if cases_path:
        candidates.append(Path(cases_path))
    candidates.extend(
        [
            ROOT / "data" / "sft" / "eval" / "eval_extract.jsonl",
            ROOT / "data" / "sft" / "eval" / "eval_negation.jsonl",
        ]
    )
    for candidate in candidates:
        if candidate.exists():
            cases = load_jsonl_cases(candidate)
            return cases[:limit], {
                "case_source": str(candidate),
                "builtin_cases": False,
                "gold_limited": any((case.get("gold") or {}).get("gold_limited") for case in cases),
            }
    return BUILTIN_CASES[:limit], {
        "case_source": "builtin",
        "builtin_cases": True,
        "gold_limited": True,
    }


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records)
    path.write_text(text, encoding="utf-8")


def rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return round(numerator / denominator, 6)


def percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return round(ordered[int(rank)], 3)
    return round(ordered[lower] * (upper - rank) + ordered[upper] * (rank - lower), 3)


def _parsed(record: dict[str, Any]) -> dict[str, Any]:
    parsed = record.get("parsed_json")
    return parsed if isinstance(parsed, dict) else {}


def compute_backend_metrics(
    backend: str,
    records: list[dict[str, Any]],
    *,
    status: str | None = None,
    skipped_reason: str | None = None,
    gold_limited: bool = True,
) -> dict[str, Any]:
    backend_records = [record for record in records if record.get("backend") == backend]
    attempted_records = [record for record in backend_records if record.get("case_id") != "__backend_skipped__"]
    case_count = len(attempted_records)
    latencies = [float(record["latency_ms"]) for record in attempted_records if record.get("latency_ms") is not None]

    json_valid_count = sum(1 for record in attempted_records if record.get("json_valid") is True)
    schema_pass_count = sum(1 for record in attempted_records if record.get("schema_pass") is True)
    fallback_count = sum(1 for record in attempted_records if record.get("fallback_used") is True)
    chief_count = sum(1 for record in attempted_records if _parsed(record).get("chief_complaint"))
    duration_count = sum(1 for record in attempted_records if _parsed(record).get("duration"))
    risk_count = sum(1 for record in attempted_records if _parsed(record).get("risk_flags_status") == "present")

    negation_cases = [
        record for record in attempted_records if any(marker in str(record.get("input") or "") for marker in NEGATION_MARKERS)
    ]
    negation_pass = sum(
        1
        for record in negation_cases
        if _parsed(record).get("risk_flags_status") != "present"
    )
    high_risk_cases = [
        record for record in attempted_records if any(marker in str(record.get("input") or "") for marker in HIGH_RISK_MARKERS)
    ]
    high_risk_pass = sum(
        1
        for record in high_risk_cases
        if _parsed(record).get("risk_flags_status") == "present" or bool(_parsed(record).get("risk_flags"))
    )

    if status is None:
        if skipped_reason:
            status = "skipped"
        elif case_count == 0:
            status = "failed"
        elif schema_pass_count == case_count and json_valid_count == case_count and fallback_count == 0:
            status = "ok"
        elif schema_pass_count > 0 or json_valid_count > 0:
            status = "caution"
        else:
            status = "failed"

    return {
        "backend": backend,
        "case_count": case_count,
        "json_valid_rate": rate(json_valid_count, case_count),
        "schema_pass_rate": rate(schema_pass_count, case_count),
        "fallback_rate": rate(fallback_count, case_count),
        "avg_latency_ms": round(sum(latencies) / len(latencies), 3) if latencies else 0.0,
        "p95_latency_ms": percentile(latencies, 0.95),
        "chief_complaint_present_rate": rate(chief_count, case_count),
        "duration_present_rate": rate(duration_count, case_count),
        "risk_flag_present_rate": rate(risk_count, case_count),
        "negation_case_pass_rate": rate(negation_pass, len(negation_cases)),
        "high_risk_case_detected_or_preserved_rate": rate(high_risk_pass, len(high_risk_cases)),
        "failed_count": sum(1 for record in attempted_records if record.get("error")),
        "skipped_count": 1 if skipped_reason else 0,
        "status": status,
        "skipped_reason": skipped_reason,
        "gold_limited": gold_limited,
    }


def summarize_record(record: dict[str, Any] | None) -> str:
    if not record:
        return "none"
    raw = str(record.get("raw_output") or "")
    parsed = record.get("parsed_json")
    return (
        f"- case_id: `{record.get('case_id')}`\n"
        f"  input: {record.get('input')}\n"
        f"  raw_output: `{raw[:240]}`\n"
        f"  parsed_json: `{json.dumps(parsed, ensure_ascii=False)[:240]}`\n"
        f"  schema_pass: `{record.get('schema_pass')}`"
    )
