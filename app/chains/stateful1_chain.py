import os
import json
from typing import Dict, Any

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from app.schemas.stateful1_schemas import RunState, TurnOutput
from app.prompts.stateful1_prompt import STATEFUL_SYSTEM_PROMPT

load_dotenv()


def build_model():
    llm = ChatOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        model=os.getenv("MODEL_NAME"),
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

structured_llm = build_model()
stateful_chain = prompt | structured_llm


def state_to_json_dict(state: RunState) -> Dict[str, Any]:
    return state.model_dump()


def parse_turn_output(raw_content: str) -> TurnOutput:
    """
    将模型返回的 JSON 字符串解析为 TurnOutput
    """
    try:
        data = json.loads(raw_content)
        return TurnOutput.model_validate(data)
    except Exception as e:
        raise ValueError(f"模型输出无法解析为合法 JSON: {raw_content}") from e


def merge_state(old_state: RunState, turn_output: TurnOutput) -> RunState:
    """
    将本轮输出合并到累计状态中
    关键原则：
    1. 新值非空时覆盖旧值
    2. 三态字段优先更新
    3. 不要因为本轮没提到就把旧值清掉
    """
    new_state = old_state.model_copy(deep=True)

    # 核心字段
    if turn_output.chief_complaint:
        new_state.chief_complaint = turn_output.chief_complaint

    if turn_output.duration:
        new_state.duration = turn_output.duration

    # symptoms
    if turn_output.symptoms_status in ("unknown", "none", "present"):
        new_state.symptoms_status = turn_output.symptoms_status

    if turn_output.symptoms_status == "present":
        if turn_output.symptoms:
            new_state.symptoms = turn_output.symptoms
    elif turn_output.symptoms_status == "none":
        new_state.symptoms = []

    # risk_flags
    if turn_output.risk_flags_status in ("unknown", "none", "present"):
        new_state.risk_flags_status = turn_output.risk_flags_status

    if turn_output.risk_flags_status == "present":
        if turn_output.risk_flags:
            new_state.risk_flags = turn_output.risk_flags
    elif turn_output.risk_flags_status == "none":
        new_state.risk_flags = []

    # 非核心字段
    if turn_output.sleep:
        new_state.sleep = turn_output.sleep

    if turn_output.appetite:
        new_state.appetite = turn_output.appetite

    if turn_output.stool_urine:
        new_state.stool_urine = turn_output.stool_urine

    if turn_output.summary:
        new_state.summary = turn_output.summary

    # next_question 统一由程序决定，不直接相信模型输出
    new_state.next_question = decide_next_question(new_state)

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
        return "请先描述一下你最主要的不舒服是什么？"

    if state.duration is None:
        return "这种情况持续多久了，或者是从什么时候开始的？"

    if state.symptoms_status == "unknown":
        return "除了这个主要不适外，还有没有其他伴随症状，比如腹痛、反酸、恶心、乏力、头晕等？如果没有也可以直接说没有。"

    if state.risk_flags_status == "unknown":
        return "最近有没有出现胸痛、呼吸困难、持续高热、便血、呕血、意识模糊，或突然明显加重的情况？如果没有可以直接说没有。"

    return None


def generate_final_summary(state: RunState) -> str:
    """
    当核心字段齐全后，用于前端/命令行展示的总结
    """
    parts = []

    if state.chief_complaint:
        parts.append(f"主诉：{state.chief_complaint}")
    if state.duration:
        parts.append(f"持续时间：{state.duration}")

    if state.symptoms_status == "present":
        parts.append(f"伴随症状：{'、'.join(state.symptoms)}")
    elif state.symptoms_status == "none":
        parts.append("伴随症状：已确认无明显伴随症状")

    if state.risk_flags_status == "present":
        parts.append(f"风险提示：{'、'.join(state.risk_flags)}，建议尽快线下就医")
    elif state.risk_flags_status == "none":
        parts.append("风险判断：目前未发现明显高风险信号")

    if state.summary:
        parts.append(f"摘要：{state.summary}")

    return "\n".join(parts)


def run_turn(state: RunState, user_input: str) -> RunState:
    """
    执行一轮：
    1. 把当前累计状态 + 用户输入传给模型
    2. 得到本轮结构化输出
    3. merge 到累计状态
    """
    response = stateful_chain.invoke(
        {
            "state_json": json.dumps(state_to_json_dict(state), ensure_ascii=False),
            "user_input": user_input,
        }
    )

    raw_content = response.content
    turn_output = parse_turn_output(raw_content)
    updated_state = merge_state(state, turn_output)
    return updated_state