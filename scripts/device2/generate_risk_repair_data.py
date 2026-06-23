from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.prompts.sft_prompt import build_sft_user_message
from app.schemas.sft_schemas import SFTMessagesSample, SFTSample


SYSTEM_PROMPT = (
    "你是中医问诊辅助系统中的结构化抽取模块。"
    "请结合历史状态和当前用户输入，输出本轮结构化 JSON。"
    "该系统不是诊断模型，不输出确定性诊断。"
    "请优先抽取 chief_complaint、duration、symptoms、risk_flags 及其状态。"
    "严格输出 JSON。"
)

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
    "risk_reasons": [],
    "triggered_rule_ids": [],
    "next_question": None,
    "summary": "",
    "final_report": None,
}


def state(**updates: Any) -> dict[str, Any]:
    item = dict(DEFAULT_STATE)
    item.update(updates)
    return item


def output(
    *,
    chief_complaint: str | None = None,
    duration: str | None = None,
    symptoms: list[str] | None = None,
    symptoms_status: str = "unknown",
    risk_flags: list[str] | None = None,
    risk_flags_status: str = "unknown",
    next_question: str | None = None,
    summary: str = "",
) -> dict[str, Any]:
    return {
        "chief_complaint": chief_complaint,
        "duration": duration,
        "symptoms": symptoms or [],
        "symptoms_status": symptoms_status,
        "sleep": None,
        "appetite": None,
        "stool_urine": None,
        "risk_flags": risk_flags or [],
        "risk_flags_status": risk_flags_status,
        "next_question": next_question,
        "summary": summary,
    }


def sample(
    sample_id: str,
    user_input: str,
    expected: dict[str, Any],
    *,
    state_json: dict[str, Any] | None = None,
    tags: list[str] | None = None,
    difficulty: str = "medium",
    description: str = "",
) -> dict[str, Any]:
    return {
        "task": "report_turn_extraction",
        "id": sample_id,
        "system_prompt": SYSTEM_PROMPT,
        "input": {
            "state_json": state_json or state(),
            "user_input": user_input,
        },
        "output": expected,
        "meta": {
            "source": "augmented",
            "difficulty": difficulty,
            "tags": tags or [],
            "notes": description,
        },
    }


def to_messages(row: dict[str, Any]) -> dict[str, Any]:
    validated = SFTSample.model_validate(row)
    message_sample = SFTMessagesSample(
        id=validated.id,
        task=validated.task,
        messages=[
            {"role": "system", "content": validated.system_prompt},
            {
                "role": "user",
                "content": build_sft_user_message(
                    state_json=validated.input.state_json,
                    user_input=validated.input.user_input,
                ),
            },
            {"role": "assistant", "content": json.dumps(validated.output.model_dump(mode="json"), ensure_ascii=False)},
        ],
        meta=validated.meta,
    )
    return message_sample.model_dump(mode="json")


def write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def build_rows() -> list[dict[str, Any]]:
    present = [
        sample(
            "risk_repair_present_high_fever_001",
            "高热三天不退，体温一直在39度左右。",
            output(risk_flags=["持续高热"], risk_flags_status="present", summary="用户提到持续高热不退。"),
            tags=["risk_repair", "risk_present", "high_fever"],
            description="明确 present: 高热三天不退",
        ),
        sample(
            "risk_repair_present_chest_pain_001",
            "胸痛伴出汗，胸口压着疼。",
            output(risk_flags=["胸痛"], risk_flags_status="present", summary="用户提到胸痛伴出汗。"),
            tags=["risk_repair", "risk_present", "chest_pain", "colloquial"],
            description="明确 present: 胸痛伴出汗",
        ),
        sample(
            "risk_repair_present_dyspnea_001",
            "我现在呼吸困难，喘不过气。",
            output(risk_flags=["呼吸困难"], risk_flags_status="present", summary="用户提到呼吸困难。"),
            tags=["risk_repair", "risk_present", "dyspnea", "colloquial"],
            description="明确 present: 呼吸困难",
        ),
        sample(
            "risk_repair_present_hematochezia_001",
            "今天腹痛，还出现了便血。",
            output(risk_flags=["便血/呕血"], risk_flags_status="present", summary="用户提到便血。"),
            tags=["risk_repair", "risk_present", "hematochezia"],
            description="明确 present: 便血",
        ),
        sample(
            "risk_repair_present_hematemesis_001",
            "刚才突然呕血了。",
            output(risk_flags=["便血/呕血"], risk_flags_status="present", summary="用户提到呕血。"),
            tags=["risk_repair", "risk_present", "hematemesis"],
            description="明确 present: 呕血",
        ),
        sample(
            "risk_repair_present_consciousness_001",
            "人有点迷糊，反应也慢。",
            output(risk_flags=["意识异常"], risk_flags_status="present", summary="用户提到意识状态异常。"),
            tags=["risk_repair", "risk_present", "altered_consciousness", "colloquial"],
            description="明确 present: 意识模糊",
        ),
        sample(
            "risk_repair_present_severe_abdominal_pain_001",
            "腹痛疼得很厉害，像突然加重了一样。",
            output(risk_flags=["突发剧烈腹痛"], risk_flags_status="present", summary="用户提到腹痛明显加重。"),
            tags=["risk_repair", "risk_present", "severe_abdominal_pain", "colloquial"],
            description="明确 present: 剧烈腹痛",
        ),
        sample(
            "risk_repair_present_black_stool_001",
            "这两天拉黑便。",
            output(risk_flags=["便血/呕血"], risk_flags_status="present", summary="用户提到黑便。"),
            tags=["risk_repair", "risk_present", "hematochezia", "colloquial"],
            description="口语表达: 拉黑便",
        ),
    ]

    negated = [
        sample(
            "risk_repair_negated_fever_001",
            "没有发热。",
            output(risk_flags=[], risk_flags_status="none", summary="用户否认发热相关风险。"),
            tags=["risk_repair", "risk_none", "negation_detection", "high_fever"],
            description="明确 negated: 没有发热",
        ),
        sample(
            "risk_repair_negated_chest_pain_001",
            "不胸痛，也没有胸口压着疼。",
            output(risk_flags=[], risk_flags_status="none", summary="用户否认胸痛。"),
            tags=["risk_repair", "risk_none", "negation_detection", "chest_pain"],
            description="明确 negated: 不胸痛",
        ),
        sample(
            "risk_repair_negated_dyspnea_001",
            "没有呼吸困难，也没有喘不过气。",
            output(risk_flags=[], risk_flags_status="none", summary="用户否认呼吸困难。"),
            tags=["risk_repair", "risk_none", "negation_detection", "dyspnea"],
            description="明确 negated: 没有呼吸困难",
        ),
        sample(
            "risk_repair_negated_hematochezia_001",
            "未见便血。",
            output(risk_flags=[], risk_flags_status="none", summary="用户否认便血。"),
            tags=["risk_repair", "risk_none", "negation_detection", "hematochezia"],
            description="明确 negated: 未见便血",
        ),
    ]

    mixed = [
        sample(
            "risk_repair_mixed_chest_001",
            "胃胀一周，没有发热，但昨晚胸口压着疼。",
            output(
                chief_complaint="胃胀",
                duration="一周",
                risk_flags=["胸痛"],
                risk_flags_status="present",
                summary="用户主诉胃胀一周，否认发热，但提到胸口压着疼。",
            ),
            tags=["risk_repair", "risk_present", "parallel_negation", "chest_pain"],
            difficulty="hard",
            description="混合表达: 否定发热但存在胸痛类风险",
        ),
        sample(
            "risk_repair_mixed_dyspnea_001",
            "咳嗽三天，不发烧，但有点喘不上气。",
            output(
                chief_complaint="咳嗽",
                duration="三天",
                risk_flags=["呼吸困难"],
                risk_flags_status="present",
                summary="用户主诉咳嗽三天，否认发烧，但提到喘不上气。",
            ),
            tags=["risk_repair", "risk_present", "parallel_negation", "dyspnea"],
            difficulty="hard",
            description="混合表达: 否定发烧但存在呼吸困难",
        ),
        sample(
            "risk_repair_mixed_abdominal_001",
            "腹痛，没有便血，但疼得很厉害。",
            output(
                chief_complaint="腹痛",
                risk_flags=["突发剧烈腹痛"],
                risk_flags_status="present",
                summary="用户主诉腹痛，否认便血，但描述疼痛严重。",
            ),
            tags=["risk_repair", "risk_present", "parallel_negation", "severe_abdominal_pain"],
            difficulty="hard",
            description="混合表达: 否定便血但存在严重腹痛",
        ),
    ]

    distractors = [
        sample(
            "risk_repair_distractor_chest_001",
            "胸口不疼，只是胃胀。",
            output(chief_complaint="胃胀", risk_flags=[], risk_flags_status="none", summary="用户否认胸口疼，主诉胃胀。"),
            tags=["risk_repair", "risk_none", "distractor", "chest_pain"],
            description="干扰项: 胸口不疼",
        ),
        sample(
            "risk_repair_distractor_fever_001",
            "有点热但体温正常。",
            output(risk_flags=[], risk_flags_status="none", summary="用户未提示持续高热，体温正常。"),
            tags=["risk_repair", "risk_none", "distractor", "high_fever"],
            description="干扰项: 有点热但体温正常",
        ),
        sample(
            "risk_repair_distractor_stool_001",
            "大便颜色深但不是黑便。",
            output(risk_flags=[], risk_flags_status="none", summary="用户说明大便颜色深但不是黑便。"),
            tags=["risk_repair", "risk_none", "distractor", "hematochezia"],
            description="干扰项: 深色便不等于黑便",
        ),
        sample(
            "risk_repair_distractor_palpitation_001",
            "紧张时心慌但无胸痛。",
            output(risk_flags=[], risk_flags_status="none", summary="用户提到紧张时心慌，但否认胸痛。"),
            tags=["risk_repair", "risk_none", "distractor", "chest_pain"],
            description="干扰项: 心慌但无胸痛",
        ),
    ]

    persistence = [
        sample(
            "risk_repair_persist_present_001",
            "现在感觉好一点了，也没有别的不舒服。",
            output(risk_flags=["胸痛"], risk_flags_status="present", summary="历史已出现胸痛风险，本轮否认其他不适不应降级。"),
            state_json=state(
                risk_flags=["胸痛"],
                risk_flags_status="present",
                triggered_rule_ids=["P0_RISK_CHEST_PAIN"],
                summary="上一轮用户提到胸痛，已记录高危风险。",
            ),
            tags=["risk_repair", "risk_present", "risk_persistence", "chest_pain"],
            difficulty="hard",
            description="历史 present 不能被后续否认降级",
        ),
        sample(
            "risk_repair_persist_none_001",
            "后来还有点乏力。",
            output(symptoms=["乏力"], symptoms_status="present", risk_flags=[], risk_flags_status="none", summary="历史已确认无高危，本轮补充普通症状。"),
            state_json=state(
                symptoms_status="none",
                risk_flags=[],
                risk_flags_status="none",
                summary="此前已确认没有高危表现。",
            ),
            tags=["risk_repair", "risk_none", "risk_persistence"],
            difficulty="hard",
            description="历史 none 后补充普通症状不应回到 unknown",
        ),
    ]

    return present + negated + mixed + distractors + persistence


def split_train_valid(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    valid_ids = {
        "risk_repair_present_chest_pain_001",
        "risk_repair_present_dyspnea_001",
        "risk_repair_negated_chest_pain_001",
        "risk_repair_mixed_abdominal_001",
        "risk_repair_distractor_stool_001",
        "risk_repair_persist_present_001",
    }
    train = [row for row in rows if row["id"] not in valid_ids]
    valid = [row for row in rows if row["id"] in valid_ids]
    return train, valid


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate D2-T1R risk repair SFT and eval data.")
    parser.add_argument("--processed-dir", type=Path, default=ROOT / "data" / "sft" / "processed")
    parser.add_argument("--eval-dir", type=Path, default=ROOT / "data" / "sft" / "eval")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    rows = build_rows()
    for row in rows:
        SFTSample.model_validate(row)
    train, valid = split_train_valid(rows)
    risk_eval = [row for row in rows if "risk_present" in (row.get("meta") or {}).get("tags", [])]
    negation_eval = [row for row in rows if "negation_detection" in (row.get("meta") or {}).get("tags", []) or "distractor" in (row.get("meta") or {}).get("tags", [])]

    write_jsonl(args.processed_dir / "train_sft_risk_repair.jsonl", train)
    write_jsonl(args.processed_dir / "valid_sft_risk_repair.jsonl", valid)
    write_jsonl(args.processed_dir / "train_sft_risk_repair_messages.jsonl", [to_messages(row) for row in train])
    write_jsonl(args.processed_dir / "valid_sft_risk_repair_messages.jsonl", [to_messages(row) for row in valid])
    write_jsonl(args.eval_dir / "eval_risk_repair.jsonl", risk_eval)
    write_jsonl(args.eval_dir / "eval_negation_repair.jsonl", negation_eval)

    print(
        json.dumps(
            {
                "train": len(train),
                "valid": len(valid),
                "eval_risk_repair": len(risk_eval),
                "eval_negation_repair": len(negation_eval),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

