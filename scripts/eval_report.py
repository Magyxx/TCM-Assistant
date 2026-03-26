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

    if key == "final_report_exists":
        actual = final_report is not None
        ok = actual == expected_value
        return ok, f"final_report_exists={actual}"

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
            "final_state": None,
        }

    checks = []
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

    final_state = state.model_dump()

    return {
        "id": case_id,
        "description": description,
        "passed": all_passed,
        "error": None,
        "checks": checks,
        "final_state": final_state,
    }


def print_case_result(result: Dict[str, Any]) -> None:
    status = "PASS" if result["passed"] else "FAIL"
    print(f"\n[{status}] {result['id']} - {result['description']}")

    if result["error"]:
        print(f"  error: {result['error']}")
        return

    for check in result["checks"]:
        mark = "✓" if check["passed"] else "✗"
        print(f"  {mark} {check['field']}: {check['detail']}")

    if not result["passed"]:
        print("  final_state:")
        print(json.dumps(result["final_state"], ensure_ascii=False, indent=2))


def main():
    cases = load_test_cases(TEST_CASES_PATH)
    results = []

    print(f"加载测试用例: {TEST_CASES_PATH}")
    print(f"共 {len(cases)} 条测试样例")

    for case in cases:
        result = evaluate_case(case)
        results.append(result)
        print_case_result(result)

    passed_count = sum(1 for r in results if r["passed"])
    failed_count = len(results) - passed_count

    print("\n" + "=" * 60)
    print("评估完成")
    print(f"通过: {passed_count}")
    print(f"失败: {failed_count}")
    print(f"总计: {len(results)}")
    print("=" * 60)

    if failed_count > 0:
        print("\n未通过的 case:")
        for r in results:
            if not r["passed"]:
                print(f"- {r['id']} : {r['description']}")


if __name__ == "__main__":
    main()