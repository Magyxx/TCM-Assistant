import re
from copy import deepcopy
from typing import Any, Dict, List, Optional


VALID_TRI_STATES = {"unknown", "none", "present"}

DURATION_PATTERNS = [
    r"一天",
    r"两天",
    r"三天",
    r"四天",
    r"五天",
    r"六天",
    r"七天",
    r"一周",
    r"两周",
    r"三周",
    r"一个月",
    r"两个月",
    r"三个月",
    r"半年",
    r"一年",
    r"\d+天",
    r"\d+周",
    r"\d+个月",
    r"\d+年",
]

GENERIC_INVALID_COMPLAINTS = {
    "不太舒服",
    "有点难受",
    "不对劲",
    "不舒服",
    "难受",
}

WEAK_VALID_COMPLAINT_KEYWORDS = [
    "胃不舒服",
    "肚子不舒服",
]

HIGH_RISK_TERMS = [
    "胸痛",
    "呼吸困难",
    "持续高热",
    "便血",
    "呕血",
    "意识模糊",
    "突然明显加重",
]

NORMALIZE_SYMPTOM_MAP = {
    "confirmed": "present",
    "new": "present",
    "yes": "present",
    "no": "none",
    "absent": "none",
    "unknown_status": "unknown",
}


def normalize_text(text: Optional[str]) -> Optional[str]:
    if text is None:
        return None
    text = str(text).strip()
    if not text:
        return None
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normalize_list_str(items: Any) -> List[str]:
    if not isinstance(items, list):
        return []

    out: List[str] = []
    seen = set()

    for item in items:
        text = None

        if isinstance(item, str):
            text = normalize_text(item)

        elif isinstance(item, dict):
            # 优先取常见字段
            for key in ["name", "value", "text", "content", "symptom"]:
                if key in item:
                    text = normalize_text(item.get(key))
                    if text:
                        break

        else:
            text = normalize_text(item)

        if not text:
            continue

        if text not in seen:
            seen.add(text)
            out.append(text)

    return out


def normalize_tri_state(value: Any, fallback: str = "unknown") -> str:
    value_text = normalize_text(value)
    if value_text is None:
        return fallback

    value_text = value_text.lower()
    value_text = NORMALIZE_SYMPTOM_MAP.get(value_text, value_text)

    if value_text in VALID_TRI_STATES:
        return value_text
    return fallback


def extract_duration_from_text(text: Optional[str]) -> Optional[str]:
    text = normalize_text(text)
    if not text:
        return None

    for pattern in DURATION_PATTERNS:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def remove_duration_from_complaint(text: Optional[str]) -> Optional[str]:
    text = normalize_text(text)
    if not text:
        return None

    original = text
    for pattern in DURATION_PATTERNS:
        text = re.sub(pattern, "", text)

    text = re.sub(r"[，,。；;、\s]+$", "", text).strip()
    text = re.sub(r"^[，,。；;、\s]+", "", text).strip()

    return text or original


def is_generic_invalid_complaint(text: Optional[str]) -> bool:
    text = normalize_text(text)
    if not text:
        return False
    if text in GENERIC_INVALID_COMPLAINTS:
        return True
    return False


def is_weak_valid_complaint(text: Optional[str]) -> bool:
    text = normalize_text(text)
    if not text:
        return False
    return any(k in text for k in WEAK_VALID_COMPLAINT_KEYWORDS)


def clean_chief_complaint(text: Optional[str]) -> Optional[str]:
    text = normalize_text(text)
    if not text:
        return None

    text = remove_duration_from_complaint(text)
    text = normalize_text(text)

    if not text:
        return None

    if is_generic_invalid_complaint(text) and not is_weak_valid_complaint(text):
        return None

    return text


def next_question_to_string(value: Any) -> Optional[str]:
    if value is None:
        return None

    if isinstance(value, str):
        text = normalize_text(value)
        return text

    if isinstance(value, dict):
        question = normalize_text(value.get("question"))
        return question

    return None


def infer_risk_status_from_text(user_input: Optional[str], current_status: str) -> str:
    text = normalize_text(user_input)
    if not text:
        return current_status

    # 否定句识别
    negation_markers = ["没有", "未见", "无", "否认"]
    has_negation = any(m in text for m in negation_markers)
    mentions_risk = any(term in text for term in HIGH_RISK_TERMS)

    if has_negation and mentions_risk:
        return "none"

    return current_status


def should_remove_complaint_from_symptoms(chief_complaint: Optional[str], symptoms: List[str]) -> List[str]:
    chief = normalize_text(chief_complaint)
    if not chief:
        return symptoms

    cleaned: List[str] = []
    for symptom in symptoms:
        s = normalize_text(symptom)
        if not s:
            continue
        if s == chief:
            continue
        cleaned.append(s)
    return cleaned


def derive_symptoms_status_from_list(symptoms: List[str], current_status: str, user_input: Optional[str] = None) -> str:
    if symptoms:
        return "present"

    if current_status == "none":
        return "none"

    text = normalize_text(user_input) or ""
    neg_markers = ["没有", "未见", "无", "否认"]
    symptom_terms = ["腹痛", "呕吐", "恶心", "头晕", "发热", "咳嗽", "胸痛", "呼吸困难"]

    if any(m in text for m in neg_markers) and any(t in text for t in symptom_terms):
        return "none"

    return "unknown"


def drop_extra_fields(obj: Dict[str, Any]) -> Dict[str, Any]:
    allowed_keys = {
        "chief_complaint",
        "duration",
        "symptoms",
        "symptoms_status",
        "sleep",
        "appetite",
        "stool_urine",
        "risk_flags",
        "risk_flags_status",
        "next_question",
        "summary",
    }
    return {k: v for k, v in obj.items() if k in allowed_keys}


def postprocess_turn_output(
    parsed_output: Dict[str, Any],
    state_json: Optional[Dict[str, Any]] = None,
    user_input: Optional[str] = None,
) -> Dict[str, Any]:
    state_json = state_json or {}
    obj = deepcopy(parsed_output) if isinstance(parsed_output, dict) else {}
    obj = drop_extra_fields(obj)

    chief_complaint = clean_chief_complaint(obj.get("chief_complaint"))
    duration = normalize_text(obj.get("duration"))

    # 如果 chief_complaint 里带时间，拆出来
    if duration is None:
        duration = extract_duration_from_text(obj.get("chief_complaint"))

    chief_complaint = clean_chief_complaint(chief_complaint)

    symptoms = normalize_list_str(obj.get("symptoms"))
    symptoms = should_remove_complaint_from_symptoms(chief_complaint, symptoms)

    symptoms_status = normalize_tri_state(obj.get("symptoms_status"), fallback="unknown")
    risk_flags = normalize_list_str(obj.get("risk_flags"))
    risk_flags_status = normalize_tri_state(obj.get("risk_flags_status"), fallback="unknown")

    # 发热不直接等于持续高热
    filtered_risk_flags: List[str] = []
    for item in risk_flags:
        if item == "持续高热":
            if user_input and any(key in user_input for key in ["持续高热", "高烧不退", "反复高热", "39度以上"]):
                filtered_risk_flags.append(item)
            else:
                continue
        else:
            filtered_risk_flags.append(item)
    risk_flags = filtered_risk_flags

    # 否定句兜底
    risk_flags_status = infer_risk_status_from_text(user_input=user_input, current_status=risk_flags_status)
    if risk_flags_status == "none":
        risk_flags = []

    # 如果 risk_flags 非空，强制 present
    if risk_flags:
        risk_flags_status = "present"

    # 根据 symptoms 列表和状态再做一次统一
    symptoms_status = derive_symptoms_status_from_list(
        symptoms=symptoms,
        current_status=symptoms_status,
        user_input=user_input,
    )

    # 症状升级后，风险需重确认
    old_symptoms_status = normalize_tri_state(state_json.get("symptoms_status"), fallback="unknown")
    old_risk_status = normalize_tri_state(state_json.get("risk_flags_status"), fallback="unknown")
    if old_symptoms_status == "none" and symptoms_status == "present":
        if risk_flags_status != "present":
            risk_flags_status = "unknown"
            risk_flags = []

    next_question = next_question_to_string(obj.get("next_question"))
    summary = normalize_text(obj.get("summary")) or ""

    # summary 太空的话兜底
    if not summary:
        parts = []
        if chief_complaint:
            parts.append(f"用户主诉{chief_complaint}")
        if duration:
            parts.append(f"持续{duration}")
        if symptoms_status == "present" and symptoms:
            parts.append(f"伴有{'、'.join(symptoms)}")
        elif symptoms_status == "none":
            parts.append("已确认无伴随症状")
        if risk_flags_status == "none":
            parts.append("已否认高危表现")
        elif risk_flags_status == "present" and risk_flags:
            parts.append(f"存在高危信号：{'、'.join(risk_flags)}")
        elif risk_flags_status == "unknown":
            parts.append("高危情况尚未确认")
        summary = "，".join(parts) if parts else "本轮信息已结构化抽取。"

    return {
        "chief_complaint": chief_complaint,
        "duration": duration,
        "symptoms": symptoms,
        "symptoms_status": symptoms_status,
        "sleep": normalize_text(obj.get("sleep")),
        "appetite": normalize_text(obj.get("appetite")),
        "stool_urine": normalize_text(obj.get("stool_urine")),
        "risk_flags": risk_flags,
        "risk_flags_status": risk_flags_status,
        "next_question": next_question,
        "summary": summary,
    }