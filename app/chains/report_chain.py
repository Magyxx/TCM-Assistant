import os
import json

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from app.chains.rag_enhancer import enhance_final_report_with_rag
from app.rules.risk_rules import evaluate_risk_rules
from app.schemas.report_schemas import (
    RunState,
    TurnOutput,
    FinalReport,
)
USE_RAG = os.getenv("USE_RAG", "true").lower() == "true"
try:
    from app.chains.sft_infer_chain import run_sft_turn
except Exception as exc:  # pragma: no cover - optional LoRA/SFT dependency path
    run_sft_turn = None
    SFT_IMPORT_ERROR = exc
else:
    SFT_IMPORT_ERROR = None
from app.prompts.report_prompt import STATEFUL_SYSTEM_PROMPT
import re
from typing import Dict, Any, List, Optional

SAFETY_BOUNDARY_TEXT = (
    "本系统仅用于问诊信息整理和风险提示，不构成诊断或治疗建议，不能替代医生判断。"
    "如出现持续高热、胸痛、呼吸困难、便血、意识异常、剧烈腹痛等高风险信号，应及时线下就医。"
)

def extract_json_object_text(raw_text: str) -> str:
    """
    从模型原始输出中尽量提取 JSON 对象文本。
    处理几种常见情况：
    1. 纯 JSON
    2. ```json ... ``` 代码块
    3. 前后带解释文字，但中间包含一个 JSON 对象
    """
    if not raw_text:
        raise ValueError("模型返回为空，无法解析 JSON。")

    text = raw_text.strip()

    # 情况1：去掉 markdown 代码块包裹
    text = re.sub(r"^```json\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"^```\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    text = text.strip()

    # 情况2：如果本身就是完整 JSON，直接返回
    if text.startswith("{") and text.endswith("}"):
        return text

    # 情况3：提取第一个完整的 JSON 对象
    start = text.find("{")
    if start == -1:
        raise ValueError(f"未找到 JSON 起始符 '{{'。原始输出：{raw_text}")

    brace_count = 0
    end = -1
    for i in range(start, len(text)):
        ch = text[i]
        if ch == "{":
            brace_count += 1
        elif ch == "}":
            brace_count -= 1
            if brace_count == 0:
                end = i
                break

    if end == -1:
        raise ValueError(f"未找到完整 JSON 结束符 '}}'。原始输出：{raw_text}")

    json_text = text[start:end + 1].strip()
    return json_text


def parse_turn_output(raw_content: str) -> TurnOutput:
    """
    将模型原始输出解析为 TurnOutput。
    流程：
    1. 提取 JSON 主体
    2. json.loads
    3. TurnOutput.model_validate
    """
    try:
        json_text = extract_json_object_text(raw_content)
    except Exception as e:
        print("\n===== JSON EXTRACTION ERROR =====")
        print(raw_content)
        print("===== END JSON EXTRACTION ERROR =====\n")
        raise ValueError(f"提取 JSON 失败：{e}") from e

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as e:
        print("\n===== JSON DECODE ERROR =====")
        print(json_text)
        print("===== END JSON DECODE ERROR =====\n")
        raise ValueError(f"JSON 解析失败：{e}") from e

    try:
        return TurnOutput.model_validate(data)
    except Exception as e:
        print("\n===== TURN OUTPUT VALIDATION ERROR =====")
        print(json.dumps(data, ensure_ascii=False, indent=2))
        print("===== END TURN OUTPUT VALIDATION ERROR =====\n")
        raise ValueError(f"TurnOutput 校验失败：{e}") from e


INVALID_CHIEF_COMPLAINTS = {
    "不舒服",
    "不太舒服",
    "有点不舒服",
    "有些不舒服",
    "不大舒服",
    "有点难受",
    "难受",
    "不太对劲",
    "不对劲",
    "状态不好",
    "不太好",
    "不适",
    "身体不舒服",
    "身体不太舒服",
    "人不舒服",
}


BODY_PART_HINTS = [
    "胃", "肚子", "腹", "胸", "头", "喉咙", "咽喉", "腰", "背", "腿", "脚", "手", "心口"
]


SYMPTOM_HINTS = [
    "痛", "胀", "咳嗽", "发热", "发烧", "头晕", "恶心", "反酸", "腹泻", "便秘", "胸闷", "乏力", "呕吐"
]


def normalize_text(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    text = text.strip()
    if not text:
        return None
    return text


def is_vague_only_expression(text: str) -> bool:
    """
    只包含泛化不适，不带明确部位或症状
    """
    text = text.strip()

    if text in INVALID_CHIEF_COMPLAINTS:
        return True

    vague_keywords = ["不舒服", "难受", "不对劲", "状态不好", "不适"]

    has_vague = any(k in text for k in vague_keywords)
    has_body_part = any(k in text for k in BODY_PART_HINTS)
    has_symptom = any(k in text for k in SYMPTOM_HINTS)

    # 例如“胃不舒服”“胸口不舒服”这种，虽然带“不舒服”，但仍然算弱有效主诉
    if has_vague and (has_body_part or has_symptom):
        return False

    if has_vague and len(text) <= 10:
        return True

    return False


def is_valid_chief_complaint(text: Optional[str]) -> bool:
    text = normalize_text(text)
    if text is None:
        return False

    if is_vague_only_expression(text):
        return False

    return True


def clean_chief_complaint(text: Optional[str]) -> Optional[str]:
    text = normalize_text(text)
    if not is_valid_chief_complaint(text):
        return None
    return text


WEAK_CHIEF_BODY_PARTS = [
    "胃", "肚子", "腹", "胸口", "胸", "头", "喉咙", "咽喉", "腰", "背", "心口"
]

WEAK_CHIEF_HINTS = ["不舒服", "难受", "不适", "疼", "痛", "胀"]
WEAK_CHIEF_NEGATION_MARKERS = ["没有", "无", "未见", "否认", "不"]


def is_weak_chief_body_part_negated(text: str, idx: int, window: int = 6) -> bool:
    prefix = text[max(0, idx - window):idx]
    return any(marker in prefix for marker in WEAK_CHIEF_NEGATION_MARKERS)


def infer_weak_chief_complaint(user_input: str) -> Optional[str]:
    text = normalize_text(user_input)
    if text is None:
        return None

    for body_part in WEAK_CHIEF_BODY_PARTS:
        idx = text.find(body_part)
        if idx < 0:
            continue
        if is_weak_chief_body_part_negated(text, idx):
            continue
        window = text[idx: idx + 12]
        if any(hint in window for hint in WEAK_CHIEF_HINTS):
            candidate = re.split(r"[，,。；;、\s]", window)[0]
            return clean_chief_complaint(candidate)
    return None


def confirms_no_accompanying_symptoms(user_input: str) -> bool:
    text = normalize_text(user_input)
    if text is None:
        return False

    explicit_none_phrases = [
        "没有其他症状",
        "没有其它症状",
        "没有别的症状",
        "没有其他不舒服",
        "没有其它不舒服",
        "没有别的不舒服",
        "无其他症状",
        "无其它症状",
        "无明显伴随症状",
    ]
    if any(phrase in text for phrase in explicit_none_phrases):
        return True

    negation_markers = ["没有", "无", "否认", "不伴"]
    summary_markers = ["这些情况", "这些症状", "这类情况", "这类症状"]
    if any(marker in text for marker in negation_markers) and any(marker in text for marker in summary_markers):
        return True

    negated_symptom_terms = [
        "腹痛",
        "呕吐",
        "恶心",
        "反酸",
        "头晕",
        "乏力",
        "发热",
        "发烧",
        "咳嗽",
        "胸痛",
        "呼吸困难",
        "便血",
        "呕血",
    ]
    return any(marker in text for marker in negation_markers) and any(
        term in text for term in negated_symptom_terms
    )


RISK_RECHECK_SYMPTOM_HINTS = [
    "发热",
    "发烧",
    "高热",
    "高烧",
    "头晕",
    "胸闷",
    "腹痛",
    "呕吐",
    "便血",
    "呕血",
    "明显加重",
]


def symptom_upgrade_requires_risk_recheck(user_input: str, symptoms: List[str]) -> bool:
    text = normalize_text(user_input) or ""
    candidates = [text] + [normalize_text(symptom) or "" for symptom in symptoms]
    return any(
        hint in candidate
        for candidate in candidates
        for hint in RISK_RECHECK_SYMPTOM_HINTS
    )

load_dotenv()


def build_model():
    llm = ChatOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        model=os.getenv("OPENAI_MODEL") or os.getenv("MODEL_NAME"),
        temperature=0.2,
    )
    # DeepSeek 兼容：使用 json_object，而不是 with_structured_output
    return llm.bind(response_format={"type": "json_object"})


prompt = ChatPromptTemplate.from_messages(
    [
        ("system", STATEFUL_SYSTEM_PROMPT),
        (
            "human",
            """
历史累计状态如下（json）：
{state_json}

本轮用户输入如下：
{user_input}

请结合历史状态与本轮输入，输出本轮结构化 json。
""".strip(),
        ),
    ]
)

structured_llm = None
report_chain = None


def get_report_chain():
    global structured_llm, report_chain
    if report_chain is None:
        structured_llm = build_model()
        report_chain = prompt | structured_llm
    return report_chain


def state_to_json_dict(state: RunState) -> Dict[str, Any]:
    return state.model_dump()



def filter_false_high_fever(user_input: str, turn_output: TurnOutput) -> TurnOutput:
    """
    过滤模型把普通“发热”误抽成“持续高热”的情况。
    只有当用户明确提到高热/持续高热/高烧不退/39度等，才保留该风险信号。
    """
    text = normalize_text(user_input)

    has_general_fever = "发热" in text
    has_true_high_fever_signal = any(
        kw in text for kw in [
            "高热", "持续高热", "高烧", "高烧不退",
            "反复高热", "一直高热", "持续发高烧",
            "39度", "39℃", "39°C", "体温39"
        ]
    )

    predicts_high_fever = "持续高热" in (turn_output.risk_flags or [])

    if has_general_fever and not has_true_high_fever_signal and predicts_high_fever:
        turn_output.risk_flags = [x for x in (turn_output.risk_flags or []) if x != "持续高热"]

        # 如果删掉后风险列表空了，且本轮 only 因为这个误判才被标成 present，
        # 就把状态降回 unknown，让后续流程继续确认风险
        if not turn_output.risk_flags and turn_output.risk_flags_status == "present":
            turn_output.risk_flags_status = "unknown"

    return turn_output

   
def merge_turn_fields(old_state: RunState, turn_output: TurnOutput, user_input: str) -> RunState:
    """
    将本轮输出合并到累计状态中
    关键原则：
    1. 新值非空时覆盖旧值
    2. 三态字段允许从 none -> present 升级
    3. 不要因为本轮没提到就把旧值清掉
    4. 对风险识别加规则兜底，增强否定句稳定性
    """
    new_state = old_state.model_copy(deep=True)
    turn_output = filter_false_high_fever(user_input, turn_output)
    # -------------------------
    # 1. chief_complaint
    # -------------------------
    cleaned_cc = clean_chief_complaint(turn_output.chief_complaint)
    if cleaned_cc is None:
        cleaned_cc = infer_weak_chief_complaint(user_input)
    if cleaned_cc:
        new_state.chief_complaint = cleaned_cc

    active_chief_complaint = cleaned_cc or new_state.chief_complaint
    symptoms_to_merge = [
        symptom
        for symptom in (turn_output.symptoms or [])
        if normalize_text(symptom) and normalize_text(symptom) != normalize_text(active_chief_complaint)
    ]

    # -------------------------
    # 2. duration
    # -------------------------
    if turn_output.duration:
        new_state.duration = turn_output.duration

    # -------------------------
    # 3. symptoms / symptoms_status
    # -------------------------
    old_symptoms_status = old_state.symptoms_status

    if turn_output.symptoms_status == "present":
        if symptoms_to_merge:
            new_state.symptoms_status = "present"
            merged = list(dict.fromkeys(new_state.symptoms + symptoms_to_merge))
            new_state.symptoms = merged

    elif turn_output.symptoms_status == "none":
        if (
            new_state.symptoms_status != "present"
            and (
                old_state.symptoms_status == "none"
                or confirms_no_accompanying_symptoms(user_input)
            )
        ):
            new_state.symptoms_status = "none"
            if not new_state.symptoms:
                new_state.symptoms = []

    elif turn_output.symptoms_status == "unknown":
        pass

    # 兜底：如果模型没把状态改成 present，但这轮明确抽出了 symptoms，也升级
    if symptoms_to_merge:
        merged = list(dict.fromkeys(new_state.symptoms + symptoms_to_merge))
        new_state.symptoms = merged
        new_state.symptoms_status = "present"

    if (
        new_state.symptoms_status == "unknown"
        and not new_state.symptoms
        and confirms_no_accompanying_symptoms(user_input)
    ):
        new_state.symptoms_status = "none"

    symptoms_upgraded_none_to_present = (
        old_symptoms_status == "none" and new_state.symptoms_status == "present"
    )
    # -------------------------
    # 4. risk_flags / risk_flags_status
    # 允许 none -> present 升级
    # -------------------------
    
    risk_evaluation = evaluate_risk_rules(user_input, previous_status=old_state.risk_flags_status)
    rule_risk_status = risk_evaluation.risk_status

    if risk_evaluation.triggered_rule_ids:
        new_state.triggered_rule_ids = list(dict.fromkeys(new_state.triggered_rule_ids + risk_evaluation.triggered_rule_ids))
    if risk_evaluation.risk_reasons:
        new_state.risk_reasons = list(dict.fromkeys(new_state.risk_reasons + risk_evaluation.risk_reasons))
    if risk_evaluation.risk_flags:
        turn_output.risk_flags = list(dict.fromkeys((turn_output.risk_flags or []) + risk_evaluation.risk_flags))

    should_reset_risk = (
        symptoms_upgraded_none_to_present
        and symptom_upgrade_requires_risk_recheck(user_input, symptoms_to_merge)
        and rule_risk_status != "present"
        and turn_output.risk_flags_status != "present"
        and not turn_output.risk_flags
    )

    if should_reset_risk and old_state.risk_flags_status != "present":
        new_state.risk_flags_status = "unknown"
        new_state.risk_flags = []

    

    final_risk_status = turn_output.risk_flags_status
    if rule_risk_status is not None:
        final_risk_status = rule_risk_status

    if final_risk_status == "present":
        new_state.risk_flags_status = "present"
        if turn_output.risk_flags:
            merged = list(dict.fromkeys(new_state.risk_flags + turn_output.risk_flags))
            new_state.risk_flags = merged

    elif final_risk_status == "none":
        if should_reset_risk:
            # 本轮症状刚从 none 升级到 present，风险需要重新确认，
            # 即使模型/规则给了 none，也先保持 unknown，等待下一轮明确确认
            pass
        else:
            if (
                new_state.risk_flags_status != "present"
                and (
                    old_state.risk_flags_status == "none"
                    or rule_risk_status == "none"
                )
            ):
                new_state.risk_flags_status = "none"
                if not new_state.risk_flags:
                    new_state.risk_flags = []

    elif final_risk_status == "unknown":
        pass

    # 如果模型已经抽到 risk_flags，也强制升级
    if turn_output.risk_flags:
        merged = list(dict.fromkeys(new_state.risk_flags + turn_output.risk_flags))
        new_state.risk_flags = merged
        new_state.risk_flags_status = "present"

    # -------------------------
    # 5. 非核心字段
    # -------------------------
    if turn_output.sleep:
        new_state.sleep = turn_output.sleep

    if turn_output.appetite:
        new_state.appetite = turn_output.appetite

    if turn_output.stool_urine:
        new_state.stool_urine = turn_output.stool_urine

    if turn_output.summary:
        new_state.summary = turn_output.summary

    new_state.metadata = {
        **new_state.metadata,
        "last_risk_rule_eval": {
            "risk_status": risk_evaluation.risk_status,
            "triggered_rule_ids": risk_evaluation.triggered_rule_ids,
            "negated_rule_ids": risk_evaluation.negated_rule_ids,
            "risk_reasons": risk_evaluation.risk_reasons,
        },
    }

    return new_state


def merge_state(old_state: RunState, turn_output: TurnOutput, user_input: str) -> RunState:
    """
    兼容旧入口：合并字段后继续由程序决定下一问和最终报告。
    """
    new_state = merge_turn_fields(old_state, turn_output, user_input)

    # -------------------------
    # 6. 统一由程序决定下一问
    # -------------------------
    new_state.next_question = decide_next_question(new_state)

    if new_state.next_question is None:
        base_report = generate_final_report(new_state)

        print("\n===== BASE FINAL REPORT =====")
        print(base_report.model_dump_json(indent=2, ensure_ascii=False))
        print("===== END BASE FINAL REPORT =====\n")

        if USE_RAG:
            rag_report = enhance_final_report_with_rag(new_state, base_report)

            print("\n===== RAG FINAL REPORT =====")
            print(rag_report.model_dump_json(indent=2, ensure_ascii=False))
            print("===== END RAG FINAL REPORT =====\n")

            new_state.final_report = rag_report
        else:
            new_state.final_report = base_report
    else:
        new_state.final_report = None

    new_state.turn_count += 1
    return new_state


def decide_next_question(state: RunState) -> str | None:
    """
    只根据核心字段决定是否继续追问
    一旦核心字段齐了，就停止追问，避免循环
    """
    # 高风险优先：停止常规追问
    if state.risk_flags_status == "present":
        return None

    if state.chief_complaint is None:
        return "请具体说一下你最主要的不舒服是什么，比如哪里不舒服，或者是胃痛、咳嗽、头晕、腹泻、胸闷这类具体表现？"
    if state.duration is None:
        return "这种情况持续多久了，或者是从什么时候开始的？"

    if state.symptoms_status == "unknown":
        return "除了这个主要不适外，还有没有其他伴随症状，比如腹痛、反酸、恶心、乏力、头晕等？如果没有也可以直接说没有。"

    if state.risk_flags_status == "unknown":
        return "最近有没有出现胸痛、呼吸困难、持续高热、便血、呕血、意识模糊，或突然明显加重的情况？如果没有可以直接说没有。"

    return None


def get_missing_core_fields(state: RunState) -> List[str]:
    """
    返回尚未完成确认的核心字段
    """
    missing = []

    if not state.chief_complaint:
        missing.append("chief_complaint")

    if not state.duration:
        missing.append("duration")

    if state.symptoms_status == "unknown":
        missing.append("symptoms_status")

    if state.risk_flags_status == "unknown":
        missing.append("risk_flags_status")

    return missing


def is_info_complete(state: RunState) -> bool:
    """
    核心字段是否全部完成确认
    """
    return len(get_missing_core_fields(state)) == 0


def compute_triage_level(state: RunState) -> str:
    """
    先纯规则分级，不交给模型
    """
    if state.risk_flags_status == "present":
        return "urgent_visit"

    if is_info_complete(state):
        return "observe"

    return "followup"


def generate_summary_text(state: RunState) -> str:
    parts = []

    if state.chief_complaint:
        parts.append(f"主诉：{state.chief_complaint}")
    else:
        parts.append("主诉：暂未明确")

    if state.duration:
        parts.append(f"持续时间：{state.duration}")
    else:
        parts.append("持续时间：暂未明确")

    if state.symptoms_status == "present":
        parts.append(f"伴随症状：{'、'.join(state.symptoms)}")
    elif state.symptoms_status == "none":
        parts.append("伴随症状：已确认无明显伴随症状")
    else:
        parts.append("伴随症状：尚未确认")

    if state.risk_flags_status == "present":
        if state.risk_flags:
            parts.append(f"风险信号：{'、'.join(state.risk_flags)}")
        else:
            parts.append("风险信号：已发现高风险表现")
    elif state.risk_flags_status == "none":
        parts.append("风险判断：目前未发现明显高风险信号")
    else:
        parts.append("风险判断：尚未完成确认")

    return "\n".join(parts)


def generate_impression_text(state: RunState, triage_level: str, info_complete: bool) -> str:
    """
    保守表达，不做诊断
    """
    if triage_level == "urgent_visit":
        return f"根据当前问诊信息，已出现需要警惕的风险信号，建议尽快线下就医进一步评估。{SAFETY_BOUNDARY_TEXT}"

    if not info_complete:
        return f"当前问诊信息仍不完整，暂不适合给出进一步方向判断，建议继续补充核心症状信息。{SAFETY_BOUNDARY_TEXT}"

    if state.symptoms_status == "present" and state.symptoms:
        return f"根据当前问诊信息，主要表现为“{state.chief_complaint}”，病程为“{state.duration}”，并伴有“{'、'.join(state.symptoms)}”等表现。目前暂未见明确高危信号，建议结合后续观察或线下中医问诊进一步整理。{SAFETY_BOUNDARY_TEXT}"

    return f"根据当前问诊信息，主要表现为“{state.chief_complaint}”，病程为“{state.duration}”。目前暂未见明确高危信号，可先进行一般观察；若症状持续、加重或出现新情况，建议线下进一步评估。{SAFETY_BOUNDARY_TEXT}"


def generate_advice_list(state: RunState, triage_level: str, info_complete: bool) -> List[str]:
    advice: List[str] = []

    if triage_level == "urgent_visit":
        advice.append("当前已出现高风险信号，建议尽快前往线下医疗机构就诊。")
        advice.append("若症状正在明显加重，或出现胸痛、呼吸困难、意识异常等情况，应立即就医。")
        advice.append("在就医前可整理主诉、起病时间、伴随症状及变化过程，便于医生快速评估。")
        advice.append(SAFETY_BOUNDARY_TEXT)
        return advice

    if not info_complete:
        advice.append("当前核心问诊信息仍未补全，建议继续补充主诉、持续时间、伴随症状和风险情况。")
        advice.append("在信息未完整前，不建议仅凭当前内容作进一步判断。")
        advice.append("若后续出现明显加重或高危表现，应及时线下就医。")
        advice.append(SAFETY_BOUNDARY_TEXT)
        return advice

    advice.append("目前暂未见明确高危信号，可先继续观察症状变化。")
    advice.append("建议留意症状是否加重、持续时间是否延长，或是否出现新的不适。")
    advice.append("若症状持续不缓解、反复出现，或新增胸痛、呼吸困难、持续高热、便血、呕血等情况，应及时线下就医。")

    if state.sleep:
        advice.append(f"已记录睡眠情况：{state.sleep}，后续可结合整体状态继续观察。")
    if state.appetite:
        advice.append(f"已记录食欲情况：{state.appetite}，建议继续关注饮食后的变化。")
    if state.stool_urine:
        advice.append(f"已记录二便情况：{state.stool_urine}，若出现明显异常建议线下咨询医生。")

    advice.append(SAFETY_BOUNDARY_TEXT)
    return advice


def generate_final_report(state: RunState) -> FinalReport:
    """
    问诊结束后生成结构化最终报告
    第一版采用 规则 + 模板，不依赖模型，便于调试和评估
    """
    missing_core_fields = get_missing_core_fields(state)
    info_complete = len(missing_core_fields) == 0
    triage_level = compute_triage_level(state)

    summary = generate_summary_text(state)
    impression = generate_impression_text(state, triage_level, info_complete)
    advice = generate_advice_list(state, triage_level, info_complete)

    return FinalReport(
        summary=summary,
        impression=impression,
        advice=advice,
        triage_level=triage_level,
        info_complete=info_complete,
        missing_core_fields=missing_core_fields,
        followup_needed=not info_complete,
        metadata={
            "triggered_rule_ids": state.triggered_rule_ids,
            "risk_reasons": state.risk_reasons,
            "safety_boundary": SAFETY_BOUNDARY_TEXT,
        },
    )


def generate_final_summary(state: RunState) -> str:
    """
    保留兼容旧接口；如果已经有 final_report，则优先使用它
    """
    if state.final_report is not None:
        parts = [
            state.final_report.summary,
            f"观察结论：{state.final_report.impression}",
            f"分级：{state.final_report.triage_level}",
            f"信息是否完整：{'是' if state.final_report.info_complete else '否'}",
        ]

        if state.final_report.missing_core_fields:
            parts.append(f"缺失核心字段：{'、'.join(state.final_report.missing_core_fields)}")

        if state.final_report.advice:
            parts.append("建议：")
            for idx, item in enumerate(state.final_report.advice, start=1):
                parts.append(f"{idx}. {item}")

        return "\n".join(parts)

    # 兼容未结束时的老逻辑
    return generate_summary_text(state)



def run_turn(state, user_input: str, mode: str = "api") -> RunState:
    if mode == "sft":
        if run_sft_turn is None:
            raise RuntimeError(f"SFT extractor is unavailable: {SFT_IMPORT_ERROR}")
        state_json = state_to_json_dict(state)
        sft_result = run_sft_turn(
            state_json=state_json,
            user_input=user_input,
        )

        debug_info = sft_result.pop("_debug", None)
        turn_output = TurnOutput.model_validate(sft_result)

        new_state = merge_state(state, turn_output, user_input)

        # 如果你想保留调试信息，可以打印
        if debug_info is not None:
            print("[SFT RAW OUTPUT]")
            print(debug_info.get("raw_text"))
            print("[SFT PARSED OUTPUT]")
            print(debug_info.get("parsed"))

        return new_state

    # 原来的 API 路径保留
    raw_content = get_report_chain().invoke(
        {
            "state_json": json.dumps(state_to_json_dict(state), ensure_ascii=False, indent=2),
            "user_input": user_input,
        }
    )

    turn_output = parse_turn_output(raw_content.content if hasattr(raw_content, "content") else raw_content)
    new_state = merge_state(state, turn_output, user_input)
    return new_state


RISK_KEYWORDS = ["胸痛", "呼吸困难", "意识模糊", "意识异常", "持续高热", "高热", "便血", "呕血", "突发剧烈腹痛", "明显加重", "突然加重"]
NEG_WORDS = ["没有", "无", "未见", "并无", "未出现"]

def infer_risk_status_from_user_input(user_input: str):
    return evaluate_risk_rules(user_input).risk_status
