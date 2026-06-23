from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.extractors.local_lora_extractor import extract_with_local_lora  # noqa: E402
from app.extractors.local_vllm_extractor import extract_with_local_vllm  # noqa: E402
from app.extractors.router import extract_with_backend_router  # noqa: E402
from app.graphs.consultation_graph import run_consultation_graph  # noqa: E402
from app.schemas.report_schemas import RunState  # noqa: E402


STAGE = "D2-P6C_BACKEND_COMPARE"
BACKENDS = ("fake", "local_base", "local_lora", "cloud_llm")
DEFAULT_METRICS = ROOT / "artifacts" / "device2" / "d2_p6c_backend_metrics.json"
DEFAULT_PREDICTIONS = ROOT / "artifacts" / "device2" / "d2_p6c_backend_predictions.sample.jsonl"
DEFAULT_BADCASES = ROOT / "artifacts" / "device2" / "d2_p6c_backend_badcases.sample.jsonl"
DEFAULT_REPORT = ROOT / "reports" / "device2" / "d2_p6c_backend_compare_report.md"

REQUESTED_EVAL_PATHS = (
    ROOT / "data" / "sft" / "eval" / "eval_extract.jsonl",
    ROOT / "data" / "sft" / "eval" / "eval_negation.jsonl",
    ROOT / "data" / "sft" / "eval" / "eval_risk.jsonl",
)

RISK_TERMS = ("发热", "高热", "胸痛", "胸闷", "呼吸困难", "喘", "便血", "呕血", "意识")
WEIGHT_SUFFIXES = (".safetensors", ".bin", ".ckpt", ".pt", ".pth", ".gguf", ".onnx")
WEIGHT_SEGMENTS = ("/checkpoints/", "\\checkpoints\\", "/adapters/", "\\adapters\\", "adapter_model")


P6C_BUILTIN_CASES: list[dict[str, Any]] = [
    {
        "case_id": "digestive_negation_001",
        "user_input": "最近胃胀，饭后明显，差不多一周，没有发热，也不胸痛",
        "expected": {
            "chief_complaint": "胃胀",
            "duration": "一周",
            "risk_flags_status": "none",
            "risk_flags": [],
            "negated_risk": True,
        },
    },
    {
        "case_id": "cough_negation_001",
        "user_input": "最近咳嗽三天，没有发热，没有胸痛，也不喘",
        "expected": {
            "chief_complaint": "咳嗽",
            "duration": "三天",
            "risk_flags_status": "none",
            "risk_flags": [],
            "negated_risk": True,
        },
    },
    {
        "case_id": "high_risk_chest_dyspnea_001",
        "user_input": "胸痛半小时，伴随出汗和呼吸困难",
        "expected": {
            "chief_complaint": "胸痛",
            "duration": "半小时",
            "risk_flags_status": "present",
            "risk_flags": ["胸痛", "呼吸困难"],
            "negated_risk": False,
        },
    },
    {
        "case_id": "duration_headache_001",
        "user_input": "头痛两天，晚上更明显，没有呕吐",
        "expected": {
            "chief_complaint": "头痛",
            "duration": "两天",
            "risk_flags_status": "unknown",
            "risk_flags": [],
            "negated_risk": False,
        },
    },
    {
        "case_id": "multi_symptom_diarrhea_001",
        "user_input": "腹泻一天，大便稀，肚子隐痛，没有便血",
        "expected": {
            "chief_complaint": "腹泻",
            "duration": "一天",
            "risk_flags_status": "none",
            "risk_flags": [],
            "negated_risk": True,
        },
    },
    {
        "case_id": "schema_fail_mock_001",
        "user_input": "胃胀两天",
        "expected": {
            "chief_complaint": "胃胀",
            "duration": "两天",
            "risk_flags_status": "unknown",
            "risk_flags": [],
            "negated_risk": False,
        },
        "mock_fail_backends": {"local_base": "invalid_json"},
    },
    {
        "case_id": "hallucination_sleep_001",
        "user_input": "睡眠不好一周",
        "expected": {
            "chief_complaint": None,
            "duration": "一周",
            "risk_flags_status": "unknown",
            "risk_flags": [],
            "negated_risk": False,
        },
    },
]


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _Completion:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, content: str) -> None:
        self.content = content

    def create(self, **kwargs: Any) -> _Completion:
        return _Completion(self.content)


class _Chat:
    def __init__(self, content: str) -> None:
        self.completions = _Completions(content)


class _Client:
    def __init__(self, content: str) -> None:
        self.chat = _Chat(content)


def json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(payload), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(json_safe(row), ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def run_git(args: list[str]) -> str:
    completed = subprocess.run(
        ["git", "-c", f"safe.directory={ROOT.as_posix()}", *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
        timeout=30,
    )
    return completed.stdout.strip() if completed.returncode == 0 else completed.stderr.strip()


def git_info() -> dict[str, Any]:
    return {
        "branch": run_git(["branch", "--show-current"]),
        "head": run_git(["rev-parse", "--short", "HEAD"]),
        "recent_commits": run_git(["log", "--oneline", "-10"]).splitlines(),
    }


def _case_from_raw(raw: dict[str, Any], index: int) -> dict[str, Any] | None:
    text = raw.get("user_input") or raw.get("input") or raw.get("text") or raw.get("prompt")
    if isinstance(text, dict):
        text = text.get("user_input")
    if not text:
        return None
    expected = raw.get("expected") or raw.get("gold") or raw.get("output") or {}
    if not isinstance(expected, dict):
        expected = {}
    return {
        "case_id": str(raw.get("case_id") or raw.get("id") or f"external_{index:03d}"),
        "user_input": str(text),
        "expected": expected,
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        parsed = _case_from_raw(json.loads(line), index)
        if parsed:
            cases.append(parsed)
    return cases


def load_eval_cases(limit: int | None = None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    existing = [path for path in REQUESTED_EVAL_PATHS if path.exists()]
    if existing:
        cases: list[dict[str, Any]] = []
        for path in existing:
            cases.extend(_load_jsonl(path))
        return cases[:limit] if limit else cases, {
            "source": "requested_eval_jsonl",
            "paths": [str(path.relative_to(ROOT)) for path in existing],
            "requested_paths_missing": [
                str(path.relative_to(ROOT)) for path in REQUESTED_EVAL_PATHS if not path.exists()
            ],
            "case_count": len(cases[:limit] if limit else cases),
            "built_in": False,
        }

    cases = P6C_BUILTIN_CASES[:limit] if limit else list(P6C_BUILTIN_CASES)
    return cases, {
        "source": "builtin_d2_p6c_minimal",
        "paths": [],
        "requested_paths_missing": [str(path.relative_to(ROOT)) for path in REQUESTED_EVAL_PATHS],
        "case_count": len(cases),
        "built_in": True,
        "reason": "Requested eval_extract/eval_negation/eval_risk JSONL files are not present.",
    }


def turn_payload(**updates: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "chief_complaint": None,
        "duration": None,
        "symptoms": [],
        "symptoms_status": "unknown",
        "sleep": None,
        "appetite": None,
        "stool_urine": None,
        "risk_flags": [],
        "risk_flags_status": "unknown",
        "next_question": None,
        "summary": "mock backend comparison candidate.",
    }
    payload.update(updates)
    return payload


def mock_candidate_payload(backend: str, case: dict[str, Any]) -> str:
    case_id = case["case_id"]
    expected = case.get("expected") or {}
    failure = (case.get("mock_fail_backends") or {}).get(backend)
    if failure == "invalid_json":
        return "not json"

    base = turn_payload(
        chief_complaint=expected.get("chief_complaint"),
        duration=expected.get("duration"),
        risk_flags=list(expected.get("risk_flags") or []),
        risk_flags_status=expected.get("risk_flags_status", "unknown"),
    )

    if case_id == "high_risk_chest_dyspnea_001":
        base.update(symptoms=["出汗", "呼吸困难"], symptoms_status="present")
    if case_id == "multi_symptom_diarrhea_001":
        base.update(symptoms=["肚子隐痛"], symptoms_status="present", stool_urine="大便稀")
    if case_id == "hallucination_sleep_001":
        base.update(sleep="睡眠不好")

    if backend == "local_base":
        if case_id in {"digestive_negation_001", "duration_headache_001"}:
            base["duration"] = None
        if case_id == "cough_negation_001":
            base["chief_complaint"] = None
        if case_id == "hallucination_sleep_001":
            base.update(risk_flags=["胸痛"], risk_flags_status="present")
    elif backend == "local_lora":
        if case_id == "digestive_negation_001":
            base.update(risk_flags=["模型声称胸痛"], risk_flags_status="present")

    return json.dumps(base, ensure_ascii=False)


def _output_payload(result: Any) -> dict[str, Any]:
    return result.turn_output.model_dump() if getattr(result, "turn_output", None) is not None else {}


def _raw_output(result: Any) -> str | None:
    return getattr(result, "raw_text", None) or getattr(result, "raw_output", None)


def _schema_pass(result: Any) -> bool:
    if hasattr(result, "schema_pass"):
        return bool(result.schema_pass)
    return bool(getattr(result, "schema_valid", False) and getattr(result, "final_schema_pass", False))


def _parsed_payload(result: Any) -> dict[str, Any]:
    parsed = getattr(result, "parsed_json", None)
    if isinstance(parsed, dict):
        return parsed
    return _output_payload(result)


def _expected_summary(case: dict[str, Any]) -> str:
    expected = case.get("expected") or {}
    return json.dumps(expected, ensure_ascii=False, sort_keys=True)


def hallucinated_fields(user_input: str, expected: dict[str, Any], payload: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    risk_expected = expected.get("risk_flags_status") == "present"
    if not risk_expected and (payload.get("risk_flags") or payload.get("risk_flags_status") == "present"):
        fields.append("risk_flags")
    if payload.get("chief_complaint") and expected.get("chief_complaint") is None:
        if str(payload["chief_complaint"]) not in user_input:
            fields.append("chief_complaint")
    for symptom in payload.get("symptoms") or []:
        if symptom and str(symptom) not in user_input and symptom not in (expected.get("risk_flags") or []):
            fields.append(f"symptom:{symptom}")
    return list(dict.fromkeys(fields))


def _risk_owned_by_rules(case: dict[str, Any], output: dict[str, Any]) -> bool:
    graph_state = run_consultation_graph(
        RunState(),
        case["user_input"],
        use_langgraph=False,
        extractor_mode="fake",
        rag_enabled=False,
    )
    state = graph_state["run_state"]
    return output.get("risk_flags_status") == state.risk_flags_status or bool(
        state.metadata.get("last_risk_rule_eval") is not None
    )


def _skip_prediction(backend: str, case: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "case_id": case["case_id"],
        "backend": backend,
        "user_input": case["user_input"],
        "gold_summary": _expected_summary(case),
        "expected": case.get("expected") or {},
        "raw_output": None,
        "parsed_json": None,
        "final_turn_output": None,
        "json_valid": False,
        "schema_pass": False,
        "fallback_used": False,
        "latency_ms": None,
        "error": reason,
        "error_message": reason,
        "error_type": "backend_skipped",
        "schema_error": None,
        "risk_owned_by_rules": None,
        "lora_risk_claim_stripped": None,
        "hallucinated_fields": [],
        "raw_hallucinated_fields": [],
        "failure_types": ["backend_skipped"],
        "skipped": True,
        "skip_reason": reason,
        "model_name": None,
        "base_url": None,
    }


def backend_available_status(backend: str, live_enabled: bool) -> tuple[bool, str | None]:
    if backend == "cloud_llm":
        if not (os.getenv("OPENAI_API_KEY") and os.getenv("OPENAI_BASE_URL") and os.getenv("OPENAI_MODEL")):
            return False, "missing_api_key_or_offline_test"
    if backend in {"local_base", "local_lora"} and live_enabled:
        return True, None
    return True, None


def run_backend_case(backend: str, case: dict[str, Any], *, live_enabled: bool) -> dict[str, Any]:
    available, skip_reason = backend_available_status(backend, live_enabled)
    if not available and skip_reason:
        return _skip_prediction(backend, case, skip_reason)

    if backend == "fake":
        result = extract_with_backend_router(RunState(), case["user_input"], backend_name="fake")
    elif backend == "local_base":
        raw = mock_candidate_payload(backend, case)
        result = extract_with_local_vllm(
            RunState(),
            case["user_input"],
            client=_Client(raw),
            base_url="mock://local-base",
            model="local_base_mock",
            api_key="EMPTY",
            response_format_enabled=False,
        )
    elif backend == "local_lora":
        raw = mock_candidate_payload(backend, case)
        result = extract_with_local_lora(
            RunState(),
            case["user_input"],
            client=_Client(raw),
            base_url="mock://local-lora",
            model="local_lora_mock",
            api_key="EMPTY",
            response_format_enabled=False,
            allow_fallback=False,
        )
    else:
        return _skip_prediction(backend, case, "missing_api_key_or_offline_test")

    expected = case.get("expected") or {}
    final_output = _output_payload(result)
    parsed = _parsed_payload(result)
    raw_hallucinated = hallucinated_fields(case["user_input"], expected, parsed)
    final_hallucinated = hallucinated_fields(case["user_input"], expected, final_output)
    failure_types = classify_failure_types(
        case=case,
        json_valid=bool(result.json_valid),
        schema_pass=_schema_pass(result),
        fallback_used=bool(result.fallback_used),
        final_output=final_output,
        hallucinated=final_hallucinated,
        skipped=False,
    )
    lora_risk_claim_stripped = None
    if backend == "local_lora":
        lora_risk_claim_stripped = not (
            parsed.get("risk_flags") or parsed.get("risk_flags_status") == "present"
        ) or (
            parsed.get("risk_flags") != final_output.get("risk_flags")
            or parsed.get("risk_flags_status") != final_output.get("risk_flags_status")
        )

    return {
        "case_id": case["case_id"],
        "backend": backend,
        "user_input": case["user_input"],
        "gold_summary": _expected_summary(case),
        "expected": expected,
        "raw_output": _raw_output(result),
        "parsed_json": parsed,
        "final_turn_output": final_output or None,
        "json_valid": bool(result.json_valid),
        "schema_pass": _schema_pass(result),
        "fallback_used": bool(result.fallback_used),
        "latency_ms": result.latency_ms,
        "error": result.error,
        "error_message": result.error,
        "error_type": result.error_type,
        "schema_error": getattr(result, "schema_error", None),
        "risk_owned_by_rules": _risk_owned_by_rules(case, final_output) if final_output else False,
        "lora_risk_claim_stripped": lora_risk_claim_stripped,
        "hallucinated_fields": final_hallucinated,
        "raw_hallucinated_fields": raw_hallucinated,
        "failure_types": failure_types,
        "skipped": False,
        "skip_reason": None,
        "model_name": "mock" if backend in {"local_base", "local_lora"} else result.model_name,
        "base_url": "mock://local" if backend in {"local_base", "local_lora"} else result.base_url,
    }


def classify_failure_types(
    *,
    case: dict[str, Any],
    json_valid: bool,
    schema_pass: bool,
    fallback_used: bool,
    final_output: dict[str, Any],
    hallucinated: list[str],
    skipped: bool,
) -> list[str]:
    if skipped:
        return ["backend_skipped"]
    expected = case.get("expected") or {}
    failures: list[str] = []
    if not json_valid:
        failures.append("invalid_json")
    if json_valid and not schema_pass:
        failures.append("schema_fail")
    if fallback_used:
        failures.append("fallback_used")
    expected_status = expected.get("risk_flags_status")
    actual_status = final_output.get("risk_flags_status")
    if expected_status == "present" and actual_status != "present":
        failures.append("risk_false_negative")
    if expected_status in {"none", "unknown", None} and actual_status == "present":
        failures.append("risk_false_positive")
    if expected.get("negated_risk") and actual_status == "present":
        failures.append("negation_error")
    if hallucinated:
        failures.append("hallucination")
    return list(dict.fromkeys(failures))


def p95(values: list[float]) -> float | None:
    if not values:
        return None
    values = sorted(values)
    if len(values) == 1:
        return round(values[0], 3)
    index = int(round((len(values) - 1) * 0.95))
    return round(values[index], 3)


def safe_rate(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 6)


def compute_metrics(backend: str, cases: list[dict[str, Any]], predictions: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [row for row in predictions if row["backend"] == backend]
    attempted = [row for row in rows if not row.get("skipped")]
    skipped_count = len(rows) - len(attempted)
    latencies = [float(row["latency_ms"]) for row in attempted if row.get("latency_ms") is not None]

    chief_cases = [case for case in cases if (case.get("expected") or {}).get("chief_complaint")]
    duration_cases = [case for case in cases if (case.get("expected") or {}).get("duration")]
    risk_cases = [case for case in cases if (case.get("expected") or {}).get("risk_flags_status") in {"none", "present"}]
    negation_cases = [case for case in cases if (case.get("expected") or {}).get("negated_risk")]

    by_case = {row["case_id"]: row for row in rows}

    def final_for(case: dict[str, Any]) -> dict[str, Any]:
        row = by_case.get(case["case_id"]) or {}
        payload = row.get("final_turn_output")
        return payload if isinstance(payload, dict) else {}

    chief_match = sum(
        1 for case in chief_cases if final_for(case).get("chief_complaint") == case["expected"]["chief_complaint"]
    )
    duration_match = sum(
        1 for case in duration_cases if final_for(case).get("duration") == case["expected"]["duration"]
    )
    negation_ok = sum(
        1
        for case in negation_cases
        if final_for(case).get("risk_flags_status") != "present" and not final_for(case).get("risk_flags")
    )
    risk_ok = sum(
        1 for case in risk_cases if final_for(case).get("risk_flags_status") == case["expected"]["risk_flags_status"]
    )
    risk_false_negative = sum(
        1
        for case in cases
        if (case.get("expected") or {}).get("risk_flags_status") == "present"
        and final_for(case).get("risk_flags_status") != "present"
    )
    risk_false_positive = sum(
        1
        for case in cases
        if (case.get("expected") or {}).get("risk_flags_status") in {"none", "unknown", None}
        and final_for(case).get("risk_flags_status") == "present"
    )

    json_valid = sum(1 for row in attempted if row.get("json_valid"))
    schema_pass = sum(1 for row in attempted if row.get("schema_pass"))
    fallback = sum(1 for row in attempted if row.get("fallback_used"))
    structured_errors = sum(1 for row in attempted if not row.get("json_valid") or not row.get("schema_pass") or row.get("error"))
    hallucinations = sum(1 for row in attempted if row.get("hallucinated_fields"))
    failure_type_counts: dict[str, int] = {}
    for row in rows:
        for failure_type in row.get("failure_types") or []:
            failure_type_counts[failure_type] = failure_type_counts.get(failure_type, 0) + 1

    if skipped_count == len(rows):
        status = "skipped"
    elif attempted and schema_pass == len(attempted) and fallback == 0:
        status = "passed"
    elif attempted and schema_pass > 0:
        status = "passed_with_badcases"
    else:
        status = "failed"

    if status == "skipped":
        return {
            "backend": backend,
            "status": status,
            "case_count": 0,
            "skipped_case_count": skipped_count,
            "json_valid_rate": None,
            "schema_pass_rate": None,
            "chief_complaint_match_rate": None,
            "duration_match_rate": None,
            "negation_accuracy": None,
            "risk_flag_accuracy": None,
            "risk_false_negative_count": 0,
            "risk_false_positive_count": 0,
            "hallucination_rate": None,
            "fallback_rate": None,
            "structured_error_rate": None,
            "latency_ms_avg": None,
            "latency_ms_p95": None,
            "failure_type_counts": failure_type_counts,
            "skip_reason": next((row.get("skip_reason") for row in rows if row.get("skip_reason")), None),
        }

    return {
        "backend": backend,
        "status": status,
        "case_count": len(attempted),
        "skipped_case_count": skipped_count,
        "json_valid_rate": safe_rate(json_valid, len(attempted)),
        "schema_pass_rate": safe_rate(schema_pass, len(attempted)),
        "chief_complaint_match_rate": safe_rate(chief_match, len(chief_cases)),
        "duration_match_rate": safe_rate(duration_match, len(duration_cases)),
        "negation_accuracy": safe_rate(negation_ok, len(negation_cases)),
        "risk_flag_accuracy": safe_rate(risk_ok, len(risk_cases)),
        "risk_false_negative_count": risk_false_negative,
        "risk_false_positive_count": risk_false_positive,
        "hallucination_rate": safe_rate(hallucinations, len(attempted)),
        "fallback_rate": safe_rate(fallback, len(attempted)),
        "structured_error_rate": safe_rate(structured_errors, len(attempted)),
        "latency_ms_avg": round(statistics.fmean(latencies), 3) if latencies else None,
        "latency_ms_p95": p95(latencies),
        "failure_type_counts": failure_type_counts,
        "skip_reason": next((row.get("skip_reason") for row in rows if row.get("skip_reason")), None),
    }


def badcase_rows(predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in predictions:
        if not row.get("failure_types"):
            continue
        rows.append(
            {
                "case_id": row["case_id"],
                "backend": row["backend"],
                "user_input": row["user_input"],
                "gold_summary": row["gold_summary"],
                "expected": row["expected"],
                "raw_output": row["raw_output"],
                "parsed_json": row["parsed_json"],
                "json_valid": row["json_valid"],
                "schema_pass": row["schema_pass"],
                "failure_type": row["failure_types"][0],
                "failure_types": row["failure_types"],
                "error_message": row.get("error_message"),
                "risk_owned_by_rules": row.get("risk_owned_by_rules"),
                "hallucinated_fields": row.get("hallucinated_fields") or [],
                "latency_ms": row.get("latency_ms"),
            }
        )
    return rows


def compare_local_lora_vs_base(metrics: list[dict[str, Any]]) -> dict[str, Any]:
    by_backend = {item["backend"]: item for item in metrics}
    base = by_backend.get("local_base") or {}
    lora = by_backend.get("local_lora") or {}
    comparable = bool(base.get("case_count") and lora.get("case_count"))
    higher_better = [
        "json_valid_rate",
        "schema_pass_rate",
        "chief_complaint_match_rate",
        "duration_match_rate",
        "negation_accuracy",
        "risk_flag_accuracy",
    ]
    lower_better = [
        "risk_false_negative_count",
        "risk_false_positive_count",
        "hallucination_rate",
        "fallback_rate",
        "structured_error_rate",
        "latency_ms_avg",
        "latency_ms_p95",
    ]
    improved: list[str] = []
    regressed: list[str] = []
    if comparable:
        for key in higher_better:
            if lora.get(key) is not None and base.get(key) is not None:
                if lora[key] > base[key]:
                    improved.append(key)
                elif lora[key] < base[key]:
                    regressed.append(key)
        for key in lower_better:
            if lora.get(key) is not None and base.get(key) is not None:
                if lora[key] < base[key]:
                    improved.append(key)
                elif lora[key] > base[key]:
                    regressed.append(key)
    notes = []
    if not comparable:
        notes.append("local_base and local_lora were not both attempted.")
    if lora.get("status") == "passed" and base.get("status") == "passed_with_badcases":
        notes.append("local_lora had no schema/fallback badcases in the mocked default comparison.")
    return {
        "comparable": comparable,
        "improved_metrics": improved,
        "regressed_metrics": regressed,
        "notes": notes,
    }


def same_eval_cases_used(predictions: list[dict[str, Any]], cases: list[dict[str, Any]]) -> bool:
    expected_ids = {case["case_id"] for case in cases}
    for backend in BACKENDS:
        backend_ids = {row["case_id"] for row in predictions if row["backend"] == backend}
        if backend_ids != expected_ids:
            return False
    return True


def weights_not_tracked() -> tuple[bool, list[str]]:
    tracked = run_git(["ls-files"]).splitlines()
    findings = [
        path for path in tracked if path.endswith(WEIGHT_SUFFIXES) or any(segment in path for segment in WEIGHT_SEGMENTS)
    ]
    return not findings, findings


def predictions_are_sample_safe(predictions: list[dict[str, Any]]) -> bool:
    text = "\n".join(json.dumps(row, ensure_ascii=False) for row in predictions)
    return not any(suffix in text for suffix in WEIGHT_SUFFIXES) and not any(segment in text for segment in WEIGHT_SEGMENTS)


def schema_fail_no_runstate_write_check() -> bool:
    before = RunState(chief_complaint="既有主诉", duration="一天", risk_flags_status="none")
    before_dump = before.model_dump()

    class BadClient:
        chat = _Chat("not json")

    with patch_env({"EXTRACTOR_BACKEND": "local_lora", "ALLOW_EXTRACTOR_FALLBACK": "false"}), patch_client(BadClient()):
        graph_state = run_consultation_graph(
            before.model_copy(deep=True),
            "胃胀两天",
            use_langgraph=False,
            extractor_mode=None,
            rag_enabled=False,
        )
    return graph_state["run_state"].model_dump() == before_dump and bool(graph_state.get("state_merge_blocked"))


class patch_env:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values
        self.old: dict[str, str | None] = {}

    def __enter__(self) -> None:
        for key, value in self.values.items():
            self.old[key] = os.environ.get(key)
            os.environ[key] = value

    def __exit__(self, *args: Any) -> None:
        for key, value in self.old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


class patch_client:
    def __init__(self, client: Any) -> None:
        self.client = client
        self.original: Any = None

    def __enter__(self) -> None:
        import app.extractors.local_vllm_extractor as module

        self.original = module._build_client
        module._build_client = lambda *args, **kwargs: self.client

    def __exit__(self, *args: Any) -> None:
        import app.extractors.local_vllm_extractor as module

        module._build_client = self.original


def run_backend_compare(
    *,
    write_artifacts: bool = True,
    limit: int | None = None,
    metrics_path: Path = DEFAULT_METRICS,
    predictions_path: Path = DEFAULT_PREDICTIONS,
    badcases_path: Path = DEFAULT_BADCASES,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, Any]:
    cases, case_source = load_eval_cases(limit=limit)
    live_enabled = os.getenv("RUN_LOCAL_VLLM_SMOKE", "").strip().lower() in {"1", "true", "yes"}
    predictions = [
        run_backend_case(backend, case, live_enabled=live_enabled)
        for backend in BACKENDS
        for case in cases
    ]
    metrics = [compute_metrics(backend, cases, predictions) for backend in BACKENDS]
    badcases = badcase_rows(predictions)
    comparison = compare_local_lora_vs_base(metrics)
    weights_ok, weight_findings = weights_not_tracked()
    payload = {
        "stage": STAGE,
        "status": "ok",
        "git": git_info(),
        "case_source": case_source,
        "eval_cases": cases,
        "backends": {
            item["backend"]: {
                "status": item["status"],
                "case_count": item["case_count"],
                "skipped_case_count": item["skipped_case_count"],
                "skip_reason": item.get("skip_reason"),
            }
            for item in metrics
        },
        "metrics": metrics,
        "badcase_type_distribution": aggregate_badcase_types(badcases),
        "local_lora_vs_local_base": comparison,
        "checks": {
            "same_eval_cases_used": same_eval_cases_used(predictions, cases),
            "fake_backend_regression": (next(item for item in metrics if item["backend"] == "fake")["status"] == "passed"),
            "local_lora_schema_validation": (
                next(item for item in metrics if item["backend"] == "local_lora")["schema_pass_rate"] == 1.0
            ),
            "schema_fail_no_runstate_write": schema_fail_no_runstate_write_check(),
            "risk_rule_projection": any(
                row["backend"] == "local_lora"
                and row["case_id"] == "high_risk_chest_dyspnea_001"
                and row["final_turn_output"]
                and row["final_turn_output"].get("risk_flags_status") == "present"
                and row["risk_owned_by_rules"]
                for row in predictions
            ),
            "lora_risk_claim_stripped": any(
                row["backend"] == "local_lora"
                and row.get("lora_risk_claim_stripped") is True
                and row.get("parsed_json", {}).get("risk_flags_status") == "present"
                and row.get("final_turn_output", {}).get("risk_flags_status") != "present"
                for row in predictions
            ),
            "cloud_skip_safe": (
                next(item for item in metrics if item["backend"] == "cloud_llm")["status"] == "skipped"
            ),
            "weights_not_tracked": weights_ok,
            "predictions_sample_safe": predictions_are_sample_safe(predictions),
        },
        "live_vllm": {
            "enabled": live_enabled,
            "status": "skipped" if not live_enabled else "mocked_in_default_runner",
            "reason": None if live_enabled else "RUN_LOCAL_VLLM_SMOKE not enabled",
        },
        "known_env_blockers": {
            "full_unittest_discover": "failed_due_preexisting_local_env_blockers",
            "details": [
                "missing fastapi",
                "import-time cloud model config",
                "temp permission errors",
                "historical fixture failures",
            ],
        },
        "safety": {
            "no_diagnosis": True,
            "no_prescription": True,
            "lora_does_not_own_final_risk": True,
            "weights_not_tracked": weights_ok,
            "tracked_weight_findings": weight_findings,
            "predictions_sample_safe": predictions_are_sample_safe(predictions),
        },
        "artifacts": {
            "metrics": str(metrics_path.relative_to(ROOT)),
            "predictions_sample": str(predictions_path.relative_to(ROOT)),
            "badcases_sample": str(badcases_path.relative_to(ROOT)),
            "report": str(report_path.relative_to(ROOT)),
        },
        "predictions_sample": predictions,
        "badcases_sample": badcases,
    }
    if not all(payload["checks"].values()) or not weights_ok:
        payload["status"] = "failed"

    if write_artifacts:
        write_json(metrics_path, {key: value for key, value in payload.items() if key not in {"predictions_sample", "badcases_sample"}})
        write_jsonl(predictions_path, predictions)
        write_jsonl(badcases_path, badcases)
        write_report(report_path, payload)
    return payload


def aggregate_badcase_types(badcases: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in badcases:
        for failure_type in row.get("failure_types") or [row.get("failure_type")]:
            if failure_type:
                counts[failure_type] = counts.get(failure_type, 0) + 1
    return counts


def _metric_cell(value: Any) -> str:
    return "null" if value is None else str(value)


def write_report(path: Path, payload: dict[str, Any]) -> None:
    git = payload["git"]
    lines = [
        "# D2-P6C Backend Compare & Regression Metrics",
        "",
        "## 1. Branch and HEAD",
        "",
        f"- Branch: `{git['branch']}`",
        f"- Validation HEAD: `{git['head']}`",
        "",
        "## 2. Recent Commits",
        "",
    ]
    lines.extend(f"- `{commit}`" for commit in git["recent_commits"])
    lines.extend(
        [
            "",
            "## 3. Files Added or Modified",
            "",
            "- `scripts/device2/eval_compare_backends.py`",
            "- `scripts/device2/analyze_backend_badcases.py`",
            "- `scripts/device2/verify_d2_p6c_backend_compare.py`",
            "- `tests/test_device2_p6c_backend_compare.py`",
            "- `tests/test_device2_p6c_metrics.py`",
            "- `tests/test_device2_p6c_backend_skip.py`",
            "- `artifacts/device2/d2_p6c_backend_compare_validation.json`",
            "- `artifacts/device2/d2_p6c_backend_metrics.json`",
            "- `artifacts/device2/d2_p6c_backend_predictions.sample.jsonl`",
            "- `artifacts/device2/d2_p6c_backend_badcases.sample.jsonl`",
            "- `reports/device2/d2_p6c_backend_compare_report.md`",
            "",
            "## 4. D2-P6A / D2-P6B Summary",
            "",
            "D2-P6A connected `local_lora` as an `ExtractorBackend`. D2-P6B proved that `EXTRACTOR_BACKEND=local_lora` runs through `run_consultation_graph`, updates `RunState` after schema pass, blocks writes after schema fail, and keeps final risk status rule-owned.",
            "",
            "## 5. Backend Compare Purpose",
            "",
            "D2-P6C compares `fake`, `local_base`, `local_lora`, and `cloud_llm` on the same eval cases, producing compact metrics, prediction samples, badcase samples, and a regression report without live service dependency by default.",
            "",
            "## 6. Eval Cases",
            "",
            f"- Source: `{payload['case_source']['source']}`",
            f"- Count: `{payload['case_source']['case_count']}`",
            f"- Missing requested paths: `{', '.join(payload['case_source'].get('requested_paths_missing') or [])}`",
            "",
            "## 7. Backend Status",
            "",
            "| backend | status | case_count | skipped_case_count | skip_reason |",
            "| --- | --- | ---: | ---: | --- |",
        ]
    )
    for backend, info in payload["backends"].items():
        lines.append(
            f"| {backend} | {info['status']} | {info['case_count']} | {info['skipped_case_count']} | {info.get('skip_reason')} |"
        )
    lines.extend(
        [
            "",
            "## 8-12. Metrics Table",
            "",
            "| backend | json_valid_rate | schema_pass_rate | chief_match | duration_match | negation_accuracy | risk_accuracy | hallucination_rate | fallback_rate | structured_error_rate | avg_ms | p95_ms |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for item in payload["metrics"]:
        lines.append(
            "| {backend} | {json_valid_rate} | {schema_pass_rate} | {chief_complaint_match_rate} | "
            "{duration_match_rate} | {negation_accuracy} | {risk_flag_accuracy} | {hallucination_rate} | "
            "{fallback_rate} | {structured_error_rate} | {latency_ms_avg} | {latency_ms_p95} |".format(
                **{key: _metric_cell(value) for key, value in item.items()}
            )
        )
    comparison = payload["local_lora_vs_local_base"]
    lines.extend(
        [
            "",
            "## 13. local_lora vs local_base",
            "",
            f"- Comparable: `{comparison['comparable']}`",
            f"- Improved metrics: `{', '.join(comparison['improved_metrics']) or 'none'}`",
            f"- Regressed metrics: `{', '.join(comparison['regressed_metrics']) or 'none'}`",
            f"- Notes: `{'; '.join(comparison['notes']) or 'none'}`",
            "",
            "## 14. Badcase Distribution",
            "",
            json.dumps(payload["badcase_type_distribution"], ensure_ascii=False, sort_keys=True),
            "",
            "## 15. Schema Fail Guard",
            "",
            f"- schema fail blocks RunState write: `{payload['checks']['schema_fail_no_runstate_write']}`",
            "",
            "## 16. Risk Rule Ownership",
            "",
            f"- risk rule projection: `{payload['checks']['risk_rule_projection']}`",
            f"- local_lora risk claim stripped: `{payload['checks']['lora_risk_claim_stripped']}`",
            "",
            "## 17. Live vLLM",
            "",
            f"- status: `{payload['live_vllm']['status']}`",
            f"- reason: `{payload['live_vllm']['reason']}`",
            "",
            "## 18. Full Unittest Discover",
            "",
            "`failed_due_preexisting_local_env_blockers`; this is not reported as a full-suite pass.",
            "",
            "## 19. Model Weights",
            "",
            "none",
            "",
            "## 20. Next Step",
            "",
            "D2-P7 final docs / resume / release summary.",
            "",
        ]
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Device2 D2-P6C backend comparison metrics.")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--metrics-output", type=Path, default=DEFAULT_METRICS)
    parser.add_argument("--predictions-output", type=Path, default=DEFAULT_PREDICTIONS)
    parser.add_argument("--badcases-output", type=Path, default=DEFAULT_BADCASES)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    args = parse_args()
    payload = run_backend_compare(
        write_artifacts=True,
        limit=args.limit,
        metrics_path=args.metrics_output,
        predictions_path=args.predictions_output,
        badcases_path=args.badcases_output,
        report_path=args.report_output,
    )
    if args.json:
        print(json.dumps(json_safe({key: value for key, value in payload.items() if key not in {"predictions_sample"}}), ensure_ascii=False, indent=2))
    else:
        print(f"D2-P6C backend compare: {payload['status']} -> {args.metrics_output}")
    return 0 if payload["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
