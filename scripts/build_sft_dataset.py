import json
from pathlib import Path
from typing import Any, Dict, List


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_CASES_PATH = PROJECT_ROOT / "tests" / "report_test_cases.json"
OUTPUT_PATH = PROJECT_ROOT / "data" / "sft" / "raw" / "sft_report_turn_extract_raw.jsonl"


DEFAULT_STATE = {
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
    "summary": "",
    "final_report": None,
}


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def load_test_cases(path: Path) -> List[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError("tests/report_test_cases.json 必须是 list")
    return data


def extract_last_user_turn(case: Dict[str, Any]) -> str | None:
    turns = case.get("turns")
    if isinstance(turns, list) and turns:
        for t in reversed(turns):
            if isinstance(t, str) and t.strip():
                return t.strip()
            if isinstance(t, dict):
                content = t.get("content") or t.get("text") or t.get("utterance")
                if isinstance(content, str) and content.strip():
                    return content.strip()
    return None


def build_output_stub(case: Dict[str, Any]) -> Dict[str, Any]:
    expected = case.get("expected", {}) or {}

    # 这里只能根据 expected 生成“弱标签骨架”，不是完整 gold
    output = {
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
        "summary": "",
    }

    if expected.get("risk_flags_status") in {"unknown", "none", "present"}:
        output["risk_flags_status"] = expected["risk_flags_status"]

    if "symptoms_status_in" in expected:
        values = expected["symptoms_status_in"]
        if isinstance(values, list) and len(values) == 1:
            output["symptoms_status"] = values[0]

    if expected.get("next_question_is_none") is True:
        output["next_question"] = None

    return output


def build_tags(case: Dict[str, Any]) -> List[str]:
    tags: List[str] = []
    desc = str(case.get("description", ""))

    if len(case.get("turns", [])) <= 1:
        tags.append("single_turn")
    else:
        tags.append("multi_turn_context")

    if "低风险" in desc:
        tags.append("low_risk")
    if "高危" in desc:
        tags.append("risk_present")
    if "否定" in desc:
        tags.append("negation_detection")
    if "泛化主诉" in desc:
        tags.append("generic_complaint_invalid")
    if "发热" in desc:
        tags.append("fever_related")

    return tags


def build_sample(case: Dict[str, Any]) -> Dict[str, Any] | None:
    user_input = extract_last_user_turn(case)
    if not user_input:
        return None

    case_id = str(case.get("id", "")).strip() or "unknown_case"

    sample = {
        "task": "report_turn_extraction",
        "id": f"sft_{case_id}",
        "system_prompt": (
            "你是中医问诊辅助系统中的结构化抽取模块。"
            "请结合历史状态和当前用户输入，输出本轮结构化 JSON。"
            "该系统不是诊断模型，不输出确定性诊断。"
            "请优先抽取 chief_complaint、duration、symptoms、risk_flags 及其状态。"
            "严格输出 JSON。"
        ),
        "input": {
            "state_json": DEFAULT_STATE,
            "user_input": user_input,
        },
        "output": build_output_stub(case),
        "meta": {
            "source": "test_case",
            "difficulty": "medium",
            "tags": build_tags(case),
            "description": case.get("description", ""),
            "expected_assertions": case.get("expected", {}),
            "needs_manual_label": True,
        },
    }
    return sample


def write_jsonl(path: Path, rows: List[Dict[str, Any]]) -> None:
    ensure_parent(path)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    cases = load_test_cases(TEST_CASES_PATH)
    samples: List[Dict[str, Any]] = []
    skipped: List[str] = []

    for idx, case in enumerate(cases, start=1):
        sample = build_sample(case)
        if sample is None:
            skipped.append(f"#{idx}: 缺少可用 turns/user_input")
            continue
        samples.append(sample)

    if skipped:
        print("[build_sft_dataset] 以下测试项未自动转换：")
        for item in skipped:
            print(f"  - {item}")

    write_jsonl(OUTPUT_PATH, samples)
    print(f"[build_sft_dataset] 写入 {len(samples)} 条样本 -> {OUTPUT_PATH}")
    print("[build_sft_dataset] 注意：当前输出为待人工补标的 SFT 骨架，不是完整 gold 标签。")


if __name__ == "__main__":
    main()
