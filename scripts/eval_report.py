import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

from app.schemas.report_schemas import RunState
from app.chains.report_chain import run_turn


BASE_DIR = Path(__file__).resolve().parent.parent
TEST_CASES_PATH = BASE_DIR / "tests" / "report_test_cases.json"


def load_test_cases(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def filter_cases(cases: List[Dict[str, Any]], case_ids: List[str] | None) -> List[Dict[str, Any]]:
    if not case_ids:
        return cases
    case_id_set = set(case_ids)
    return [case for case in cases if case["id"] in case_id_set]


def run_case(turns: List[str]) -> RunState:
    state = RunState()
    for user_input in turns:
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


def evaluate_case(case: Dict[str, Any]) -> Dict[str, Any]:
    case_id = case["id"]
    description = case.get("description", "")
    turns = case["turns"]
    expected = case["expected"]

    try:
        state = run_case(turns)
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
        mark = "✓" if check["passed"] else "✗"
        print(f"  {mark} {check['field']}: {check['detail']}")

    if not result["passed"]:
        print(f"  failed_fields: {', '.join(result['failed_fields'])}")
        print("  final_state:")
        print(json.dumps(result["final_state"], ensure_ascii=False, indent=2))


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
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    cases = load_test_cases(TEST_CASES_PATH)
    cases = filter_cases(cases, args.case)

    results = []

    print(f"加载测试用例: {TEST_CASES_PATH}")
    print(f"本次运行测试样例数: {len(cases)}")

    for case in cases:
        result = evaluate_case(case)
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


if __name__ == "__main__":
    main()