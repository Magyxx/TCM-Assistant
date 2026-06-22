import argparse
from datetime import datetime, timezone
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple


BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from app.schemas.report_schemas import RunState
from app.chains.turn_extractor import get_missing_api_config
from app.rag.bm25_retriever import BM25Okapi

TEST_CASES_PATH = BASE_DIR / "tests" / "report_test_cases.json"
ARTIFACTS_DIR = BASE_DIR / "artifacts"
FAILURE_ANALYSIS_PATH = ARTIFACTS_DIR / "p0_1_eval_failure_analysis.json"
P0_2_COMPARISON_PATH = ARTIFACTS_DIR / "p0_2_eval_comparison.json"
P0_3_RESULT_PATH = ARTIFACTS_DIR / "p0_3_real_llm_eval_result.json"
P0_3_FAILURE_ANALYSIS_PATH = ARTIFACTS_DIR / "p0_3_real_llm_failure_analysis.json"
NEGATION_MARKERS = ["没有", "未见", "无", "否认", "并无", "不"]
RISK_TERMS = ["胸痛", "呼吸困难", "喘不上气", "便血", "呕血", "持续高热", "高烧", "意识模糊", "意识异常"]


def load_test_cases(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def filter_cases(cases: List[Dict[str, Any]], case_ids: List[str] | None) -> List[Dict[str, Any]]:
    if not case_ids:
        return cases
    case_id_set = set(case_ids)
    return [case for case in cases if case["id"] in case_id_set]


def run_case(turns: List[str], mode: str = "legacy", extractor: str = "fallback") -> RunState:
    state = RunState()
    for user_input in turns:
        if mode == "graph":
            from app.graphs.consultation_graph import run_consultation_graph

            graph_state = run_consultation_graph(state, user_input, extractor_mode=extractor)
            state = graph_state["run_state"]
        else:
            from app.chains.report_chain import run_turn

            state = run_turn(state, user_input)
    return state


def check_condition(state: RunState, key: str, expected_value: Any) -> Tuple[bool, str]:
    final_report = state.final_report

    if key == "chief_complaint_not_null":
        ok = state.chief_complaint is not None
        return ok, f"chief_complaint={state.chief_complaint!r}"

    if key == "chief_complaint_is_null":
        ok = state.chief_complaint is None
        return ok, f"chief_complaint={state.chief_complaint!r}"

    if key == "duration_not_null":
        ok = state.duration is not None
        return ok, f"duration={state.duration!r}"

    if key == "duration_is_null":
        ok = state.duration is None
        return ok, f"duration={state.duration!r}"

    if key == "symptoms_status":
        ok = state.symptoms_status == expected_value
        return ok, f"symptoms_status={state.symptoms_status!r}, expected={expected_value!r}"

    if key == "symptoms_status_in":
        ok = state.symptoms_status in expected_value
        return ok, f"symptoms_status={state.symptoms_status!r}, expected_in={expected_value!r}"

    if key == "risk_flags_status":
        ok = state.risk_flags_status == expected_value
        return ok, f"risk_flags_status={state.risk_flags_status!r}, expected={expected_value!r}"

    if key == "next_question_is_none":
        actual = state.next_question is None
        ok = actual == expected_value
        return ok, f"next_question={state.next_question!r}"

    if key == "next_question_contains":
        actual = state.next_question or ""
        ok = any(text in actual for text in expected_value)
        return ok, f"next_question={actual!r}, expected_contains_any={expected_value!r}"

    if key == "final_report_exists":
        actual = final_report is not None
        ok = actual == expected_value
        return ok, f"final_report_exists={actual}"

    if key == "final_report_fields_not_null":
        if final_report is None:
            return False, "final_report=None"
        missing = [field for field in expected_value if getattr(final_report, field, None) is None]
        ok = len(missing) == 0
        return ok, f"missing_final_report_fields={missing!r}"

    if key == "triage_level":
        actual = final_report.triage_level if final_report else None
        ok = actual == expected_value
        return ok, f"triage_level={actual!r}, expected={expected_value!r}"

    if key == "info_complete":
        actual = final_report.info_complete if final_report else None
        ok = actual == expected_value
        return ok, f"info_complete={actual!r}, expected={expected_value!r}"

    if key == "missing_core_fields_len":
        actual = len(final_report.missing_core_fields) if final_report else None
        ok = actual == expected_value
        return ok, f"missing_core_fields_len={actual!r}, expected={expected_value!r}"

    if key == "missing_core_fields_contains":
        if final_report is None:
            return False, "final_report=None"
        actual = final_report.missing_core_fields
        missing = [field for field in expected_value if field not in actual]
        ok = len(missing) == 0
        return ok, f"missing_core_fields={actual!r}, expected_contains={expected_value!r}"

    return False, f"未知断言键: {key}"


def evaluate_case(case: Dict[str, Any], mode: str = "legacy", extractor: str = "fallback") -> Dict[str, Any]:
    case_id = case["id"]
    description = case.get("description", "")
    turns = case["turns"]
    expected = case["expected"]

    try:
        state = run_case(turns, mode=mode, extractor=extractor)
    except Exception as e:
        return {
            "id": case_id,
            "description": description,
            "passed": False,
            "error": str(e),
            "checks": [],
            "failed_fields": [],
            "final_state": None,
        }

    checks = []
    failed_fields = []
    all_passed = True

    for key, expected_value in expected.items():
        ok, detail = check_condition(state, key, expected_value)
        checks.append(
            {
                "field": key,
                "passed": ok,
                "detail": detail,
            }
        )
        if not ok:
            all_passed = False
            failed_fields.append(key)

    final_state = state.model_dump()

    return {
        "id": case_id,
        "description": description,
        "passed": all_passed,
        "error": None,
        "checks": checks,
        "failed_fields": failed_fields,
        "final_state": final_state,
    }


def print_case_result(result: Dict[str, Any], failed_only: bool = False) -> None:
    if failed_only and result["passed"]:
        return

    status = "PASS" if result["passed"] else "FAIL"
    print(f"\n[{status}] {result['id']} - {result['description']}")

    if result["error"]:
        print(f"  error: {result['error']}")
        return

    for check in result["checks"]:
        mark = "OK" if check["passed"] else "NO"
        print(f"  {mark} {check['field']}: {check['detail']}")

    if not result["passed"]:
        print(f"  failed_fields: {', '.join(result['failed_fields'])}")
        print("  final_state:")
        print(json.dumps(result["final_state"], ensure_ascii=False, indent=2))


def _find_check(result: Dict[str, Any], field: str) -> Dict[str, Any] | None:
    for check in result.get("checks", []):
        if check.get("field") == field:
            return check
    return None


def _case_has_negated_risk(case: Dict[str, Any]) -> bool:
    text = " ".join([str(turn) for turn in case.get("turns", [])])
    return any(marker in text for marker in NEGATION_MARKERS) and any(term in text for term in RISK_TERMS)


def _case_expected_redflag(case: Dict[str, Any]) -> bool:
    expected = case.get("expected", {})
    if expected.get("risk_flags_status") == "present":
        return True
    text = " ".join([str(turn) for turn in case.get("turns", [])])
    return any(term in text for term in ["胸痛", "呼吸困难", "喘不上气", "便血", "呕血", "持续高热", "持续高烧", "高烧不退", "意识模糊", "意识异常", "剧烈腹痛"]) and not _case_has_negated_risk(case)


def _extract_recall_terms(final_state: Dict[str, Any]) -> List[str]:
    terms: List[str] = []
    chief = final_state.get("chief_complaint")
    if chief:
        terms.append(str(chief))
    for item in final_state.get("symptoms") or []:
        if isinstance(item, str):
            terms.append(item)
    for item in final_state.get("risk_flags") or []:
        if isinstance(item, str):
            terms.append(item)
    return list(dict.fromkeys([term for term in terms if term]))


def _rag_recall_hit(final_state: Dict[str, Any], top_k: int = 3) -> bool | None:
    terms = _extract_recall_terms(final_state)
    if not terms:
        return None

    query = "；".join(terms + ["观察建议", "风险提示", "就医建议"])
    try:
        from app.rag.hybrid_retriever import HybridRetriever

        evidence = HybridRetriever(mode="bm25_only").retrieve(query, top_k=top_k)
    except Exception:
        return None

    joined = "\n".join(item.content for item in evidence)
    return any(term in joined for term in terms)


def build_p0_metrics(
    cases: List[Dict[str, Any]],
    results: List[Dict[str, Any]],
    mode: str = "legacy",
    extractor: str = "fallback",
    real_llm_eval_skipped: bool = False,
    real_llm_eval_skip_reason: str | None = None,
) -> Dict[str, Any]:
    total_turns = sum(len(case.get("turns", [])) for case in cases)
    successful_turns_proxy = sum(
        len(case.get("turns", []))
        for case, result in zip(cases, results)
        if result.get("error") is None
    )
    extraction_count_total = 0
    extraction_raw_llm_json_valid = 0
    extraction_final_schema_pass = 0
    extraction_fallback_used = 0

    chief_checks = []
    risk_checks = []
    redflag_checks = []
    negation_checks = []
    multi_turn_complete = []
    rag_hits = []
    graph_runtimes = []
    observed_extractors = []
    observed_strategies = []

    for case, result in zip(cases, results):
        for key in ["chief_complaint_not_null", "chief_complaint_is_null"]:
            check = _find_check(result, key)
            if check is not None:
                chief_checks.append(bool(check["passed"]))

        risk_check = _find_check(result, "risk_flags_status")
        if risk_check is not None:
            risk_checks.append(bool(risk_check["passed"]))
            if _case_expected_redflag(case):
                redflag_checks.append(bool(risk_check["passed"]))

        if _case_has_negated_risk(case):
            if risk_check is not None:
                negation_checks.append(bool(risk_check["passed"]))
            elif result.get("final_state"):
                negation_checks.append(result["final_state"].get("risk_flags_status") != "present")

        final_state = result.get("final_state") or {}
        metadata = final_state.get("metadata") or {}
        if metadata.get("graph_runtime"):
            graph_runtimes.append(metadata.get("graph_runtime"))
        if metadata.get("last_extractor_mode"):
            observed_extractors.append(metadata.get("last_extractor_mode"))
        if metadata.get("last_strategy"):
            observed_strategies.append(metadata.get("last_strategy"))
        extraction_counts = metadata.get("extraction_counts") or {}
        if extraction_counts:
            extraction_count_total += int(extraction_counts.get("total", 0))
            extraction_raw_llm_json_valid += int(
                extraction_counts.get("raw_llm_json_valid", extraction_counts.get("json_valid", 0))
            )
            extraction_final_schema_pass += int(
                extraction_counts.get("final_schema_pass", extraction_counts.get("schema_valid", 0))
            )
            extraction_fallback_used += int(extraction_counts.get("fallback_used", 0))

        if len(case.get("turns", [])) > 1 and final_state:
            final_report = final_state.get("final_report") or {}
            multi_turn_complete.append(bool(final_report.get("info_complete")))

        if final_state:
            rag_hit = _rag_recall_hit(final_state, top_k=3)
            if rag_hit is not None:
                rag_hits.append(rag_hit)

    def rate(values: List[bool]) -> float | None:
        if not values:
            return None
        return sum(1 for item in values if item) / len(values)

    if extraction_count_total:
        raw_llm_json_valid_rate = extraction_raw_llm_json_valid / extraction_count_total
        final_schema_pass_rate = extraction_final_schema_pass / extraction_count_total
        fallback_used_rate = extraction_fallback_used / extraction_count_total
    else:
        raw_llm_json_valid_rate = (successful_turns_proxy / total_turns) if total_turns else None
        final_schema_pass_rate = raw_llm_json_valid_rate
        fallback_used_rate = None

    business_assertion_pass_rate = rate([bool(result.get("passed")) for result in results])

    return {
        "mode": mode,
        "extractor_mode": extractor,
        "observed_extractor_modes": sorted(set(str(item) for item in observed_extractors)),
        "observed_strategies": sorted(set(str(item) for item in observed_strategies)),
        "graph_runtime": sorted(set(str(item) for item in graph_runtimes)),
        "real_llm_eval_skipped": real_llm_eval_skipped,
        "real_llm_eval_skip_reason": real_llm_eval_skip_reason,
        "real_bm25_available": BM25Okapi is not None,
        "total_turns": total_turns,
        "raw_llm_json_valid_rate": raw_llm_json_valid_rate,
        "final_schema_pass_rate": final_schema_pass_rate,
        "fallback_used_rate": fallback_used_rate,
        "chief_complaint_consistency": rate(chief_checks),
        "risk_recognition_consistency": rate(risk_checks),
        "risk_recall_on_redflag_cases": rate(redflag_checks),
        "negation_accuracy": rate(negation_checks),
        "multi_turn_core_completion_rate": rate(multi_turn_complete),
        "rag_recall_at_3": rate(rag_hits),
        "rag_recall_samples": len(rag_hits),
        "business_assertion_pass_rate": business_assertion_pass_rate,
    }


def classify_failure(case: Dict[str, Any], result: Dict[str, Any]) -> Tuple[str, str]:
    if result.get("error"):
        return "graph_state_bug", "修复运行时错误，确保 graph/legacy 入口可执行。"

    failed_fields = set(result.get("failed_fields") or [])
    final_state = result.get("final_state") or {}
    metadata = final_state.get("metadata") or {}
    extraction_counts = metadata.get("extraction_counts") or {}
    fallback_total = int(extraction_counts.get("fallback_used", 0))
    total = int(extraction_counts.get("total", 0))
    last_error_type = metadata.get("last_error_type")
    last_strategy = metadata.get("last_strategy")

    if last_error_type == "authentication_error":
        return "provider_incompatibility", "当前真实 LLM API 认证失败；检查 OPENAI_API_KEY 是否有效且与 base_url/model 匹配。"
    if last_error_type == "missing_api_config":
        return "provider_incompatibility", "补齐 OPENAI_API_KEY、OPENAI_BASE_URL、OPENAI_MODEL 后重新验证。"
    if last_error_type == "provider_incompatibility":
        return "provider_incompatibility", "provider 不支持当前 structured/tool/json 调用方式，需调整 P0.4 兼容策略。"
    if last_error_type == "json_invalid":
        return "json_invalid", "强化 JSON prompt、JSON 提取或 JSON repair。"
    if last_error_type == "schema_mismatch":
        return "schema_mismatch", "检查模型输出字段与 TurnOutput schema 是否一致。"

    if "risk_flags_status" in failed_fields:
        return "rule_gap", "补充或修正风险规则，不要交给 LLM 自由判断。"
    if total and fallback_total == total and failed_fields & {"chief_complaint_not_null", "duration_not_null", "symptoms_status"}:
        if last_strategy == "rule_fallback":
            return "fallback_limit", "当前 fallback 模式缺少完整语义抽取，应使用真实 LLM 或补轻量规则。"
        return "fallback_limit", "当前 fallback-only 模式缺少完整语义抽取，应使用 fake/LLM 抽取或补轻量规则。"
    if failed_fields & {"chief_complaint_not_null", "duration_not_null", "symptoms_status"}:
        return "extraction_failed", "检查 structured/json 抽取链路或 schema 标签。"
    if failed_fields & {"final_report_exists", "triage_level", "info_complete", "missing_core_fields_len"}:
        return "graph_state_bug", "检查 graph done 判定、核心字段补全和报告生成节点。"
    if failed_fields & {"rag_recall_at_3", "retrieved_evidence"}:
        return "rag_missing", "补充知识库 chunk 或 retriever query 构造。"
    return "expected_case_too_strict", "复核测试期望是否超过当前 P0 fallback 能力。"


def build_failure_analysis(cases: List[Dict[str, Any]], results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for case, result in zip(cases, results):
        if result.get("passed"):
            continue
        suspected_reason, suggested_fix = classify_failure(case, result)
        rows.append(
            {
                "case_id": case.get("id"),
                "input": case.get("turns"),
                "expected": case.get("expected"),
                "actual": result.get("final_state"),
                "failed_assertions": result.get("failed_fields"),
                "raw_llm_json_valid": ((result.get("final_state") or {}).get("metadata") or {}).get("last_raw_llm_json_valid"),
                "final_schema_pass": ((result.get("final_state") or {}).get("metadata") or {}).get("last_final_schema_pass"),
                "fallback_used": ((result.get("final_state") or {}).get("metadata") or {}).get("last_fallback_used"),
                "suspected_reason": suspected_reason,
                "suggested_fix": suggested_fix,
            }
        )
    return rows


def write_failure_analysis(cases: List[Dict[str, Any]], results: List[Dict[str, Any]]) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    rows = build_failure_analysis(cases, results)
    with FAILURE_ANALYSIS_PATH.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)
    print(f"\n失败样本分析已写入: {FAILURE_ANALYSIS_PATH}")


def _load_p0_2_comparison() -> Dict[str, Any]:
    if P0_2_COMPARISON_PATH.exists():
        try:
            with P0_2_COMPARISON_PATH.open("r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "schema_version": "p0_2_eval_comparison.v1",
        "runs": {
            "fake": None,
            "fallback": None,
            "real_llm": None,
        },
        "summary": {},
    }


def _recommend_next_stage(comparison: Dict[str, Any]) -> str:
    runs = comparison.get("runs") or {}
    fake_run = runs.get("fake")
    fallback_run = runs.get("fallback")
    real_run = runs.get("real_llm") or {}
    summary = comparison.get("summary") or {}

    if not summary.get("real_bm25_available"):
        return "P0.3：先修复依赖环境，确保真实 BM25 可用。"
    if real_run and not real_run.get("skipped"):
        return "P1：真实 LangGraph、真实 LLM 抽取和真实 BM25 已有可观测路径，可进入服务化/部署前设计。"
    if fake_run and fallback_run:
        return "P0.3：BM25/LangGraph 已可跑，真实 LLM 因配置缺失跳过，建议补齐 OPENAI_MODEL 后复测。"
    return "P0.2：继续补齐 fake/fallback/real_llm 对比运行。"


def write_p0_2_comparison(
    extractor: str,
    mode: str,
    cases: List[Dict[str, Any]],
    results: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    skipped: bool = False,
    skip_reason: str | None = None,
) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    comparison = _load_p0_2_comparison()
    comparison["updated_at"] = datetime.now(timezone.utc).isoformat()
    comparison.setdefault("runs", {"fake": None, "fallback": None, "real_llm": None})

    comparison["runs"][extractor] = {
        "mode": mode,
        "extractor": extractor,
        "skipped": skipped,
        "skip_reason": skip_reason,
        "case_count": len(cases),
        "passed_count": sum(1 for item in results if item.get("passed")),
        "failed_count": sum(1 for item in results if not item.get("passed")),
        "metrics": metrics,
        "failed_cases": build_failure_analysis(cases, results),
    }

    if extractor != "real_llm" and get_missing_api_config() and not comparison["runs"].get("real_llm"):
        comparison["runs"]["real_llm"] = {
            "mode": mode,
            "extractor": "real_llm",
            "skipped": True,
            "skip_reason": "missing_api_config",
            "missing_api_config": get_missing_api_config(),
            "case_count": 0,
            "passed_count": 0,
            "failed_count": 0,
            "metrics": {
                "mode": mode,
                "extractor_mode": "real_llm",
                "real_llm_eval_skipped": True,
                "real_llm_eval_skip_reason": "missing_api_config",
                "real_bm25_available": BM25Okapi is not None,
            },
            "failed_cases": [],
        }

    comparison["summary"] = {
        "real_bm25_available": BM25Okapi is not None,
        "missing_api_config": get_missing_api_config(),
    }
    comparison["summary"]["recommendation"] = _recommend_next_stage(comparison)

    with P0_2_COMPARISON_PATH.open("w", encoding="utf-8") as f:
        json.dump(comparison, f, ensure_ascii=False, indent=2)
    print(f"\nP0.2 对比评估已写入: {P0_2_COMPARISON_PATH}")


def _present_or_missing(value: str | None) -> str:
    return "present" if value else "missing"


def _module_status(module_name: str) -> str:
    return "present" if importlib.util.find_spec(module_name) is not None else "missing"


def _env_snapshot() -> Dict[str, Any]:
    env = {
        "langgraph": _module_status("langgraph"),
        "langchain_openai": _module_status("langchain_openai"),
        "rank_bm25": _module_status("rank_bm25"),
        "pydantic": _module_status("pydantic"),
        "python_dotenv": _module_status("dotenv"),
        "openai_api_key": _present_or_missing(os.getenv("OPENAI_API_KEY")),
        "openai_base_url": _present_or_missing(os.getenv("OPENAI_BASE_URL")),
        "openai_model": _present_or_missing(os.getenv("OPENAI_MODEL")),
    }
    real_deps = env["langgraph"] == env["langchain_openai"] == env["rank_bm25"] == "present"
    api_ready = (
        env["openai_api_key"] == "present"
        and env["openai_base_url"] == "present"
        and env["openai_model"] == "present"
    )
    env["mode"] = "real-ready" if real_deps and api_ready else ("partial-real" if real_deps or api_ready else "fallback-only")
    return env


def _load_p0_3_result() -> Dict[str, Any]:
    if P0_3_RESULT_PATH.exists():
        try:
            return json.loads(P0_3_RESULT_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "env": {},
        "smoke_cases": [],
        "eval_comparison": {},
        "decision": {},
    }


def _summarize_eval_run(
    cases: List[Dict[str, Any]],
    results: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    skipped: bool = False,
    skip_reason: str | None = None,
) -> Dict[str, Any]:
    return {
        "skipped": skipped,
        "skip_reason": skip_reason,
        "business_assertion_pass_rate": metrics.get("business_assertion_pass_rate"),
        "passed": sum(1 for item in results if item.get("passed")),
        "failed": sum(1 for item in results if not item.get("passed")),
        "total": len(cases),
        "raw_llm_json_valid_rate": metrics.get("raw_llm_json_valid_rate"),
        "final_schema_pass_rate": metrics.get("final_schema_pass_rate"),
        "fallback_used_rate": metrics.get("fallback_used_rate"),
        "risk_recall_on_redflag_cases": metrics.get("risk_recall_on_redflag_cases"),
        "negation_accuracy": metrics.get("negation_accuracy"),
        "rag_recall_at_3": metrics.get("rag_recall_at_3"),
        "graph_runtime": metrics.get("graph_runtime"),
        "observed_extractor_modes": metrics.get("observed_extractor_modes"),
        "observed_strategies": metrics.get("observed_strategies"),
        "real_bm25_available": metrics.get("real_bm25_available"),
    }


def _decide_p0_3_next_stage(result_doc: Dict[str, Any]) -> Dict[str, str]:
    comparison = result_doc.get("eval_comparison") or {}
    real = comparison.get("real_llm") or {}
    fallback = comparison.get("fallback") or {}
    smoke_cases = result_doc.get("smoke_cases") or []

    if result_doc.get("env", {}).get("mode") != "real-ready":
        return {
            "recommended_next_stage": "P0.3",
            "reason": "环境尚未达到 real-ready，需要先补齐真实 LLM 配置。",
        }

    auth_failures = [case for case in smoke_cases if case.get("error_type") == "authentication_error"]
    if auth_failures or real.get("observed_strategies") == ["rule_fallback"] and real.get("fallback_used_rate") == 1.0:
        return {
            "recommended_next_stage": "P0.3",
            "reason": "真实 LLM 配置存在认证或 provider 调用问题，尚未完成真实 structured extraction 验证。",
        }

    if real.get("skipped"):
        return {
            "recommended_next_stage": "P0.3",
            "reason": f"real_llm eval skipped: {real.get('skip_reason')}",
        }

    final_schema = real.get("final_schema_pass_rate") or 0
    business = real.get("business_assertion_pass_rate") or 0
    fallback_business = fallback.get("business_assertion_pass_rate") or 0.3
    risk_recall = real.get("risk_recall_on_redflag_cases") or 0
    negation = real.get("negation_accuracy") or 0

    if final_schema >= 0.95 and business > fallback_business and risk_recall >= 1.0 and negation >= 1.0:
        return {
            "recommended_next_stage": "P1",
            "reason": "真实 LLM smoke、graph demo、eval 均可运行，schema 稳定且业务指标高于 fallback。",
        }

    return {
        "recommended_next_stage": "P0.4",
        "reason": "真实 LLM 可调用但结构化抽取或业务断言尚不稳定，需要做 prompt/JSON/schema 兼容加固。",
    }


def write_p0_3_eval_result(
    extractor: str,
    cases: List[Dict[str, Any]],
    results: List[Dict[str, Any]],
    metrics: Dict[str, Any],
    skipped: bool = False,
    skip_reason: str | None = None,
) -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    result_doc = _load_p0_3_result()
    result_doc["env"] = _env_snapshot()
    result_doc.setdefault("smoke_cases", [])
    result_doc.setdefault("eval_comparison", {})
    result_doc["eval_comparison"][extractor] = _summarize_eval_run(
        cases=cases,
        results=results,
        metrics=metrics,
        skipped=skipped,
        skip_reason=skip_reason,
    )
    result_doc["decision"] = _decide_p0_3_next_stage(result_doc)
    result_doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    P0_3_RESULT_PATH.write_text(json.dumps(result_doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nP0.3 真实 LLM 评估结果已写入: {P0_3_RESULT_PATH}")

    if extractor == "real_llm":
        failures = build_failure_analysis(cases, results)
        P0_3_FAILURE_ANALYSIS_PATH.write_text(json.dumps(failures, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"P0.3 真实 LLM 失败分析已写入: {P0_3_FAILURE_ANALYSIS_PATH}")


def print_p0_metrics(metrics: Dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("P0 指标")
    for key, value in metrics.items():
        if isinstance(value, float):
            print(f"{key}: {value * 100:.1f}%")
        else:
            print(f"{key}: {value}")
    print("=" * 60)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="评估 report 问诊系统测试集")
    parser.add_argument(
        "--case",
        nargs="*",
        help="只运行指定 case id，例如 --case F5 E3 E8",
    )
    parser.add_argument(
        "--failed-only",
        action="store_true",
        help="只输出失败 case 的详细结果",
    )
    parser.add_argument(
        "--mode",
        choices=["legacy", "graph"],
        default="legacy",
        help="评估模式：legacy 使用原 run_turn；graph 使用 P0 graph fallback。",
    )
    parser.add_argument(
        "--extractor",
        choices=["fake", "fallback", "real_llm"],
        default="fallback",
        help="graph 模式下选择抽取器：fake、fallback 或 real_llm。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    cases = load_test_cases(TEST_CASES_PATH)
    cases = filter_cases(cases, args.case)

    results = []
    real_llm_skipped = False
    real_llm_skip_reason = None

    print(f"加载测试用例: {TEST_CASES_PATH}")
    print(f"本次运行测试样例数: {len(cases)}")
    print(f"mode: {args.mode}")
    print(f"extractor: {args.extractor}")

    if args.mode == "graph" and args.extractor == "real_llm" and get_missing_api_config():
        real_llm_skipped = True
        real_llm_skip_reason = "missing_api_config"
        print("real_llm_validation_skipped: missing_api_config")
        print(f"missing_api_config: {','.join(get_missing_api_config())}")
        metrics = build_p0_metrics(
            cases=[],
            results=[],
            mode=args.mode,
            extractor=args.extractor,
            real_llm_eval_skipped=True,
            real_llm_eval_skip_reason=real_llm_skip_reason,
        )
        print_p0_metrics(metrics)
        write_p0_2_comparison(
            extractor=args.extractor,
            mode=args.mode,
            cases=[],
            results=[],
            metrics=metrics,
            skipped=True,
            skip_reason=real_llm_skip_reason,
        )
        write_p0_3_eval_result(
            extractor=args.extractor,
            cases=[],
            results=[],
            metrics=metrics,
            skipped=True,
            skip_reason=real_llm_skip_reason,
        )
        return

    for case in cases:
        result = evaluate_case(case, mode=args.mode, extractor=args.extractor)
        results.append(result)
        print_case_result(result, failed_only=args.failed_only)

    total_count = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = total_count - passed_count
    pass_rate = (passed_count / total_count * 100) if total_count > 0 else 0.0

    print("\n" + "=" * 60)
    print("评估完成")
    print(f"通过: {passed_count}")
    print(f"失败: {failed_count}")
    print(f"总计: {total_count}")
    print(f"通过率: {pass_rate:.1f}%")
    print("=" * 60)

    if failed_count > 0:
        print("\n未通过的 case:")
        for r in results:
            if not r["passed"]:
                print(f"- {r['id']} : {r['description']} | failed_fields={r['failed_fields']}")

    write_failure_analysis(cases, results)
    metrics = build_p0_metrics(
        cases,
        results,
        mode=args.mode,
        extractor=args.extractor,
        real_llm_eval_skipped=real_llm_skipped,
        real_llm_eval_skip_reason=real_llm_skip_reason,
    )
    print_p0_metrics(metrics)
    if args.mode == "graph":
        write_p0_2_comparison(
            extractor=args.extractor,
            mode=args.mode,
            cases=cases,
            results=results,
            metrics=metrics,
            skipped=real_llm_skipped,
            skip_reason=real_llm_skip_reason,
        )
        write_p0_3_eval_result(
            extractor=args.extractor,
            cases=cases,
            results=results,
            metrics=metrics,
            skipped=real_llm_skipped,
            skip_reason=real_llm_skip_reason,
        )


if __name__ == "__main__":
    main()
