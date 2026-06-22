import json
import os
from typing import List

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - minimal local env fallback
    ChatOpenAI = None

try:
    from app.prompts.rag_prompt import rag_enhance_prompt
except Exception:  # pragma: no cover
    rag_enhance_prompt = None
from app.rag.hybrid_retriever import retrieve_evidence
from app.schemas.report_schemas import RunState, FinalReport


def build_rag_model() -> ChatOpenAI:
    if ChatOpenAI is None:
        raise ImportError("langchain_openai is not installed")
    return ChatOpenAI(
        temperature=0,
        model=os.getenv("MODEL_NAME", "deepseek-chat"),
        base_url=os.getenv("OPENAI_BASE_URL"),
        api_key=os.getenv("OPENAI_API_KEY"),
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def state_to_rag_query(state: RunState, final_report: FinalReport) -> str:
    """
    根据当前累计状态和基础最终报告构造 BM25 检索 query。

    设计目标：
    1. 强调主诉（主诉优先于伴随症状）
    2. 显式写出伴随症状状态和风险状态
    3. 显式写出当前分级
    4. 更适合 BM25 关键词命中，而不是追求自然语言优雅
    """
    parts: List[str] = []

    # 1. 主诉：重复强调，提升 BM25 对主诉块的命中概率
    if state.chief_complaint:
        parts.append(f"当前主诉重点：{state.chief_complaint}")
        parts.append(f"主诉：{state.chief_complaint}")

    # 2. 持续时间
    if state.duration:
        parts.append(f"持续时间：{state.duration}")

    # 3. 伴随症状与状态
    if state.symptoms_status == "present" and state.symptoms:
        parts.append(f"伴随症状：{'、'.join(state.symptoms)}")
        parts.append("伴随症状状态：已确认存在")
    elif state.symptoms_status == "none":
        parts.append("伴随症状：无明显伴随症状")
        parts.append("伴随症状状态：已确认没有")
    else:
        parts.append("伴随症状状态：尚未完全确认")

    # 4. 风险信号与状态
    if state.risk_flags_status == "present" and state.risk_flags:
        parts.append(f"风险信号：{'、'.join(state.risk_flags)}")
        parts.append("风险状态：已确认存在高风险信号")
    elif state.risk_flags_status == "none":
        parts.append("风险信号：目前未发现明显高风险信号")
        parts.append("风险状态：已确认无明显高风险信号")
    else:
        parts.append("风险状态：尚未完全确认")

    # 5. 分级
    parts.append(f"分级：{final_report.triage_level}")

    # 6. 检索目标提示
    # 明确告诉检索器优先围绕主诉、当前分级、观察建议、风险提示
    parts.append("请优先检索与当前主诉最相关的观察建议、风险提示、就医建议")
    parts.append("若当前无明显高风险信号，优先检索低风险观察建议")
    parts.append("若当前存在高风险信号，优先检索及时就医建议")

    return "；".join(parts)


def extract_json_object_text(raw_text: str) -> str:
    if not raw_text:
        raise ValueError("模型返回为空，无法解析 JSON。")

    text = raw_text.strip()

    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    if text.startswith("{") and text.endswith("}"):
        return text

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

    return text[start:end + 1].strip()


def enhance_final_report_with_rag(
    state: RunState,
    final_report: FinalReport,
    use_llm: bool = True,
    top_k: int = 3,
) -> FinalReport:
    query = state_to_rag_query(state, final_report)
    retrieved_evidence = retrieve_evidence(
        query,
        top_k=top_k,
        mode=os.getenv("RAG_RETRIEVER_MODE", "bm25_only"),
    )
    retrieved_context = "\n".join([f"{i+1}. {doc.content}" for i, doc in enumerate(retrieved_evidence)])

    print("\n===== RAG QUERY =====")
    print(query)
    print("===== END RAG QUERY =====\n")

    print("\n===== RETRIEVED CONTEXT =====")
    print(retrieved_context)
    print("===== END RETRIEVED CONTEXT =====\n")

    enhanced_report = final_report.model_copy(deep=True)
    enhanced_report.metadata = {
        **enhanced_report.metadata,
        "retrieved_evidence": [doc.model_dump() for doc in retrieved_evidence],
        "rag_retriever_mode": os.getenv("RAG_RETRIEVER_MODE", "bm25_only"),
    }

    if not use_llm or ChatOpenAI is None or rag_enhance_prompt is None or not retrieved_evidence:
        enhanced_report.metadata = {
            **enhanced_report.metadata,
            "rag_llm_used": False,
            "rag_fallback_reason": "llm_unavailable_or_no_evidence",
        }
        return enhanced_report

    model = build_rag_model()
    chain = rag_enhance_prompt | model

    response = chain.invoke(
        {
            "final_report_json": json.dumps(final_report.model_dump(), ensure_ascii=False, indent=2),
            "state_json": json.dumps(state.model_dump(), ensure_ascii=False, indent=2),
            "retrieved_context": retrieved_context,
        }
    )

    raw_content = response.content
    json_text = extract_json_object_text(raw_content)
    data = json.loads(json_text)

    enhanced_impression = data.get("impression", final_report.impression)
    enhanced_advice = data.get("advice", final_report.advice)

    if not isinstance(enhanced_advice, list) or not enhanced_advice:
        enhanced_advice = final_report.advice

    enhanced_report.impression = enhanced_impression
    enhanced_report.advice = enhanced_advice
    enhanced_report.metadata = {
        **enhanced_report.metadata,
        "rag_llm_used": True,
    }

    return enhanced_report
