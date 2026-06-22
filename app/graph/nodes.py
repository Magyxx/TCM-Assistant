from __future__ import annotations

import re
from typing import List

from app.extractors.router import get_extractor_backend
from app.extractors.structured_output_adapter import ExtractorAdapter
from app.graph.state import ConsultationGraphState
from app.memory.manager import MemoryManager
from app.rag.bm25_retriever import BM25Retriever
from app.rag.document_store import LocalTextDocumentStore
from app.rag.evidence_pack import build_evidence_pack
from app.rag.knowledge_loader import ROOT_KNOWLEDGE_FILE
from app.rag.query_builder import build_rag_query
from app.rag.rag_guard import report_text_is_safe
from app.safety.report_safety import safety_post_check_report
from app.rules.risk_rules import evaluate_risk_rules
from app.schemas.report_schemas import FinalReport, RunState, SAFETY_DISCLAIMER, TurnOutput


FORBIDDEN_NEXT_ACTION_TERMS = (
    "diagnose",
    "diagnosis",
    "prescribe",
    "prescription",
    "replace doctor",
)


def _missing_core_fields(run_state: RunState) -> List[str]:
    missing: list[str] = []
    if not run_state.chief_complaint:
        missing.append("chief_complaint")
    if not run_state.duration:
        missing.append("duration")
    if run_state.symptoms_status == "unknown":
        missing.append("symptoms_status")
    if run_state.risk_flags_status == "unknown":
        missing.append("risk_flags_status")
    return missing


def _safe_followup_question(run_state: RunState) -> str | None:
    if run_state.risk_flags_status == "present":
        return None
    if not run_state.chief_complaint:
        return "Please describe the main discomfort you want to organize first."
    if not run_state.duration:
        return "How long has this main discomfort been present?"
    if run_state.symptoms_status == "unknown":
        return "Are there any accompanying symptoms? If not, please say none."
    if run_state.risk_flags_status == "unknown":
        return "Are there risk signals such as chest pain, breathing difficulty, persistent high fever, bleeding, confusion, or sudden severe worsening?"
    return None


def _record_safety_issues(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in FORBIDDEN_NEXT_ACTION_TERMS if term in lowered]


def normalize_input(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    updated.normalized_input = re.sub(r"\s+", " ", updated.user_input).strip()
    updated.metrics["normalize_input"] = "ok"
    updated.trace.append({"node": "normalize_input", "status": "ok"})
    return updated


def extract_turn_node(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    user_input = updated.normalized_input or updated.user_input
    result = ExtractorAdapter().extract(
        user_input,
        state=updated.run_state,
        memory=updated.memory.model_dump(),
        mode=updated.extractor_mode_requested,
    )
    metadata = result.metadata
    updated.turn_output = result.turn_output
    updated.extraction_result = result.model_dump()
    updated.extraction_mode = str(metadata.get("legacy_mode") or result.mode)
    updated.extractor_mode = result.mode
    updated.strategy = metadata.get("strategy")
    updated.model_name = metadata.get("model_name")
    updated.error_type = metadata.get("error_type")
    updated.skip_reason = result.skip_reason
    updated.error_message_preview = metadata.get("error_message_preview")
    updated.json_valid = bool(metadata.get("json_valid"))
    updated.schema_valid = result.schema_pass
    updated.raw_llm_json_valid = bool(metadata.get("raw_llm_json_valid"))
    updated.final_schema_pass = result.schema_pass
    updated.fallback_used = result.fallback_used
    updated.metrics["extract_turn"] = result.mode
    updated.metrics["extractor_adapter"] = metadata.get("adapter")
    if result.error and not result.skip_reason:
        updated.errors.append(result.error)
    return updated


def validate_turn(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    try:
        updated.turn_output = TurnOutput.model_validate(updated.turn_output)
        updated.schema_valid = True
        updated.metrics["validate_turn"] = "ok"
    except Exception as exc:
        updated.turn_output = None
        updated.schema_valid = False
        updated.errors.append(f"turn_output_schema_invalid:{exc.__class__.__name__}")
        updated.metrics["validate_turn"] = "failed"
    return updated


def memory_update(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    manager = MemoryManager()
    user_input = updated.normalized_input or updated.user_input
    next_turn_count = updated.run_state.turn_count + 1
    updated.memory = manager.apply_turn(
        memory=updated.memory,
        previous_state=updated.run_state,
        turn_output=updated.turn_output,
        user_input=user_input,
        raw_text=user_input,
        turn_id=f"turn-{next_turn_count}",
        turn_index=next_turn_count,
        extractor_mode=updated.extractor_mode or updated.extractor_mode_requested,
    )
    exported = manager.export_run_state(updated.memory, base_state=updated.run_state)
    exported.turn_count = next_turn_count
    updated.run_state = exported
    updated.metrics["memory_update"] = "ok"
    return updated


def risk_check(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    manager = MemoryManager()
    user_input = updated.normalized_input or updated.user_input
    evaluation = evaluate_risk_rules(user_input, previous_status=updated.run_state.risk_flags_status)
    updated.memory = manager.apply_risk_evaluation(
        memory=updated.memory,
        risk_evaluation=evaluation,
        turn_id=f"turn-{updated.run_state.turn_count}",
        raw_text=user_input,
    )
    exported = manager.export_run_state(updated.memory, base_state=updated.run_state)
    exported.turn_count = updated.run_state.turn_count
    exported.metadata = {
        **exported.metadata,
        "last_risk_rule_eval": {
            "risk_status": evaluation.risk_status,
            "triggered_rule_ids": list(evaluation.triggered_rule_ids),
            "negated_rule_ids": list(evaluation.negated_rule_ids),
            "risk_reasons": list(evaluation.risk_reasons),
        },
    }
    updated.run_state = exported
    updated.risk_status = updated.run_state.risk_flags_status
    updated.risk_reasons = list(updated.run_state.risk_reasons)
    updated.triggered_rule_ids = list(updated.run_state.triggered_rule_ids)
    updated.metrics["risk_check"] = "ok"
    return updated


def plan_next_action(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    run_state = updated.run_state.model_copy(deep=True)
    missing = _missing_core_fields(run_state)
    updated.missing_core_fields = missing

    if run_state.risk_flags_status == "present":
        run_state.next_question = None
        updated.next_action = "advise_timely_offline_medical_evaluation"
        updated.done = True
    elif missing:
        run_state.next_question = _safe_followup_question(run_state)
        updated.next_action = "ask_followup"
        updated.done = False
    else:
        run_state.next_question = None
        updated.next_action = "ready_for_structured_consultation_summary"
        updated.done = True

    updated.safety_issues = _record_safety_issues(" ".join([updated.next_action, run_state.next_question or ""]))
    updated.run_state = run_state
    updated.metrics["plan_next_action"] = "ok"
    return updated


def rag_retrieve(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    if not updated.rag_enabled:
        updated.rag_skip_reason = "rag_disabled"
        updated.metrics["rag_retrieve"] = "skipped"
        return updated

    if updated.next_action != "ready_for_structured_consultation_summary":
        updated.rag_skip_reason = "not_report_ready"
        updated.metrics["rag_retrieve"] = "skipped"
        return updated

    query = build_rag_query(updated.run_state, memory=updated.memory)
    try:
        pack = build_evidence_pack(query, top_k=3)
    except Exception as exc:
        updated.rag_skip_reason = f"rag_retrieval_failed:{exc.__class__.__name__}"
        updated.metrics["rag_retrieve"] = "skipped"
        return updated

    updated.evidence_pack = pack.model_dump()
    updated.retrieved_evidence = [chunk.model_dump() for chunk in pack.chunks]
    updated.retrieved_evidence_count = len(pack.chunks)
    updated.rag_skip_reason = None if pack.chunks else "no_evidence"
    updated.metrics["rag_retrieve"] = "ok" if pack.chunks else "empty"
    updated.metrics["retrieved_evidence_count"] = updated.retrieved_evidence_count
    if not report_text_is_safe(" ".join(pack.notes)):
        updated.safety_issues.append("rag_notes_safety_boundary")
    return updated

__all__ = [
    "extract_turn_node",
    "memory_update",
    "normalize_input",
    "plan_next_action",
    "rag_retrieve",
    "risk_check",
    "validate_turn",
]


P9_FOLLOWUP_PRIORITY = [
    "chief_complaint",
    "duration",
    "accompanying_symptoms",
    "sleep",
    "appetite",
    "stool",
    "urination",
    "risk_flags",
]

P9_FOLLOWUP_QUESTIONS = {
    "chief_complaint": "请先描述这次最主要的不适是什么？",
    "duration": "这个主要不适大约持续多久了？",
    "accompanying_symptoms": "是否还有伴随症状？如果没有，也可以直接说没有。",
    "sleep": "最近睡眠情况怎么样？",
    "appetite": "最近食欲或饭量有没有变化？",
    "stool": "最近大便情况有没有异常？",
    "urination": "最近小便情况有没有异常？",
    "risk_flags": "是否有胸痛、呼吸困难、持续高热、便血、呕血、剧烈腹痛或意识异常等风险信号？",
}


def _trace(state: ConsultationGraphState, node: str, status: str = "ok", **extra: object) -> None:
    state.trace.append({"node": node, "status": status, **extra})


def _p9_missing_core_fields(run_state: RunState) -> list[str]:
    missing: list[str] = []
    if not run_state.chief_complaint:
        missing.append("chief_complaint")
    if not run_state.duration:
        missing.append("duration")
    if run_state.symptoms_status == "unknown":
        missing.append("accompanying_symptoms")
    if not run_state.sleep:
        missing.append("sleep")
    if not run_state.appetite:
        missing.append("appetite")
    if not (run_state.stool or run_state.stool_urine):
        missing.append("stool")
    if not (run_state.urination or run_state.stool_urine):
        missing.append("urination")
    if run_state.risk_flags_status == "unknown":
        missing.append("risk_flags")
    return missing


def _merge_optional_field(run_state: RunState, turn_output: TurnOutput, field_name: str) -> None:
    value = getattr(turn_output, field_name, None)
    if value not in (None, "", [], {}, "unknown"):
        setattr(run_state, field_name, value)


def extract_turn(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    backend = get_extractor_backend(updated.extractor_mode_requested or None)
    user_input = updated.normalized_input or updated.user_input
    try:
        output = backend.extract_turn(user_input, state=updated.run_state)
    except NotImplementedError as exc:
        updated.errors.append(str(exc))
        output = TurnOutput(
            summary=str(exc),
            metadata={"backend": getattr(backend, "mode", "unknown"), "error_type": "reserved_backend"},
        )
    updated.turn_output = output
    updated.turns.append(output)
    updated.extractor_mode = getattr(backend, "mode", updated.extractor_mode_requested)
    updated.extraction_result = output.model_dump()
    updated.fallback_used = bool(output.metadata.get("fallback_used"))
    updated.raw_llm_json_valid = bool(output.metadata.get("raw_llm_json_valid"))
    updated.final_schema_pass = True
    _trace(updated, "extract_turn", "ok", backend=updated.extractor_mode)
    return updated


def merge_state(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    if updated.turn_output is None:
        updated.errors.append("merge_state:no_turn_output")
        _trace(updated, "merge_state", "skipped")
        return updated

    run_state = updated.run_state.model_copy(deep=True)
    for field in [
        "chief_complaint",
        "duration",
        "symptoms",
        "symptoms_status",
        "sleep",
        "appetite",
        "stool_urine",
        "stool",
        "urination",
        "next_question",
        "summary",
    ]:
        _merge_optional_field(run_state, updated.turn_output, field)
    run_state.turn_count += 1
    run_state.metadata = {
        **run_state.metadata,
        "p9_last_turn_output": updated.turn_output.model_dump(),
        "extractor_backend": updated.extractor_mode,
    }
    updated.run_state = run_state
    _trace(updated, "merge_state", "ok")
    return updated


def risk_rule_check(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    user_input = updated.normalized_input or updated.user_input
    evaluation = evaluate_risk_rules(user_input, previous_status=updated.run_state.risk_flags_status)
    run_state = updated.run_state.model_copy(deep=True)

    if evaluation.risk_status == "present":
        run_state.risk_flags_status = "present"
        run_state.risk_flags = list(dict.fromkeys(run_state.risk_flags + evaluation.risk_flags))
        run_state.risk_reasons = list(dict.fromkeys(run_state.risk_reasons + evaluation.risk_reasons))
        run_state.triggered_rule_ids = list(dict.fromkeys(run_state.triggered_rule_ids + evaluation.triggered_rule_ids))
    elif evaluation.risk_status == "none" and run_state.risk_flags_status != "present":
        run_state.risk_flags_status = "none"

    events = []
    for match in evaluation.matches:
        events.append(
            {
                "rule_id": match.rule_id,
                "risk_level": match.risk_level,
                "triage_level": "urgent_visit",
                "reason": match.reason,
                "evidence_text": match.evidence_text or match.keyword,
                "negated": bool(match.negated),
            }
        )
    for rule_id in evaluation.negated_rule_ids:
        events.append(
            {
                "rule_id": rule_id,
                "risk_level": "urgent",
                "triage_level": "urgent_visit",
                "reason": "用户明确否定该风险信号。",
                "evidence_text": user_input,
                "negated": True,
            }
        )

    run_state.metadata = {
        **run_state.metadata,
        "last_risk_rule_eval": {
            "risk_status": evaluation.risk_status,
            "triggered_rule_ids": evaluation.triggered_rule_ids,
            "negated_rule_ids": evaluation.negated_rule_ids,
            "risk_reasons": evaluation.risk_reasons,
            "events": events,
        },
    }
    updated.run_state = run_state
    updated.risk_status = run_state.risk_flags_status
    updated.risk_reasons = list(run_state.risk_reasons)
    updated.risk_events = events
    updated.triggered_rule_ids = list(run_state.triggered_rule_ids)
    _trace(updated, "risk_rule_check", "ok", risk_status=updated.risk_status)
    return updated


def decide_next(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    missing = _p9_missing_core_fields(updated.run_state)
    updated.missing_core_fields = missing
    if updated.run_state.risk_flags_status == "present":
        updated.next_action = "safety_report"
        updated.next_question = None
    elif missing:
        updated.next_action = "ask_followup"
    else:
        updated.next_action = "retrieve_knowledge"
        updated.next_question = None
    _trace(updated, "decide_next", "ok", next_action=updated.next_action, missing_core_fields=missing)
    return updated


def ask_followup(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    if updated.next_action != "ask_followup":
        _trace(updated, "ask_followup", "skipped")
        return updated
    asked = {
        str(item.get("field"))
        for item in updated.trace
        if item.get("node") == "ask_followup" and item.get("field")
    }
    field = next((item for item in P9_FOLLOWUP_PRIORITY if item in updated.missing_core_fields and item not in asked), None)
    field = field or (updated.missing_core_fields[0] if updated.missing_core_fields else "chief_complaint")
    question = P9_FOLLOWUP_QUESTIONS[field]
    updated.next_question = question
    updated.run_state.next_question = question
    _trace(updated, "ask_followup", "ok", field=field)
    return updated


def retrieve_knowledge(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    if updated.next_action != "retrieve_knowledge" or not updated.rag_enabled:
        updated.rag_skip_reason = "not_ready_or_disabled"
        _trace(updated, "retrieve_knowledge", "skipped")
        return updated
    query = build_rag_query(updated.run_state)
    store = LocalTextDocumentStore(ROOT_KNOWLEDGE_FILE) if ROOT_KNOWLEDGE_FILE.exists() else LocalTextDocumentStore()
    retriever = BM25Retriever(document_store=store)
    evidence = retriever.retrieve_p9(query, top_k=3)
    updated.p9_evidence = evidence
    updated.retrieved_evidence = [item.model_dump() for item in evidence]
    updated.retrieved_evidence_count = len(evidence)
    updated.rag_skip_reason = None if evidence else "no_evidence"
    _trace(updated, "retrieve_knowledge", "ok" if evidence else "empty", count=len(evidence))
    return updated


def generate_report(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    if updated.next_action == "ask_followup":
        _trace(updated, "generate_report", "skipped", reason="followup_needed")
        return updated

    run_state = updated.run_state
    summary = (
        f"主诉：{run_state.chief_complaint or '未完整提供'}；"
        f"持续时间：{run_state.duration or '未提供'}；"
        f"风险状态：{run_state.risk_flags_status}。"
    )
    if run_state.risk_flags_status == "present":
        impression = "当前问诊信息中出现需要优先关注的风险信号，应以线下医疗评估为先。"
        advice = [
            "建议及时线下就医或联系当地急救/医疗服务，由医生进一步评估。",
            "在就医前可记录症状开始时间、变化、伴随表现和既往信息，供医生参考。",
        ]
        triage_level = "urgent_visit"
    else:
        evidence_notes = [chunk.content for chunk in updated.p9_evidence[:2]]
        impression = "当前信息可作为问诊整理参考，暂未由规则引擎识别到明确高风险信号。"
        if evidence_notes:
            impression += " 检索资料提示应继续关注持续时间、伴随症状和风险信号。"
        advice = [
            "建议继续记录症状变化、持续时间、饮食睡眠和二便情况。",
            "如后续出现胸痛、呼吸困难、持续高热、便血、呕血、剧烈腹痛或意识异常，应及时线下就医。",
        ]
        if evidence_notes:
            advice.append("参考知识片段：" + evidence_notes[0][:80])
        triage_level = "observe"

    report = FinalReport(
        summary=summary,
        impression=impression,
        advice=advice,
        triage_level=triage_level,
        info_complete=not bool(updated.missing_core_fields),
        missing_core_fields=list(updated.missing_core_fields),
        followup_needed=False,
        safety_disclaimer=SAFETY_DISCLAIMER,
        metadata={
            "triggered_rule_ids": list(run_state.triggered_rule_ids),
            "risk_reasons": list(run_state.risk_reasons),
            "retrieved_chunk_ids": [chunk.chunk_id for chunk in updated.p9_evidence],
            "rag_core_fields_read_only": True,
        },
    )
    updated.final_report = report
    updated.run_state.final_report = report
    _trace(updated, "generate_report", "ok")
    return updated


def safety_check(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    if updated.final_report is None:
        _trace(updated, "safety_check", "skipped")
        return updated
    result = safety_post_check_report(updated.final_report)
    updated.final_report = result.report
    updated.run_state.final_report = result.report
    updated.safety_issues = result.issues
    _trace(updated, "safety_check", "ok", rewritten=result.rewritten, issues=result.issues)
    return updated


def export_result(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    _trace(updated, "export_result", "ok")
    updated.exported_result = {
        "session_id": updated.session_id,
        "user_input": updated.user_input,
        "normalized_input": updated.normalized_input,
        "extracted_turn_output": updated.turn_output.model_dump() if updated.turn_output else None,
        "run_state": updated.run_state.model_dump(),
        "risk_status": updated.run_state.risk_flags_status,
        "risk_reasons": updated.risk_events or updated.risk_reasons,
        "risk_rule_ids": list(updated.run_state.triggered_rule_ids),
        "missing_core_fields": list(updated.missing_core_fields),
        "next_question": updated.next_question or updated.run_state.next_question,
        "retrieved_evidence": [item.model_dump() for item in updated.p9_evidence],
        "final_report": updated.final_report.model_dump() if updated.final_report else None,
        "trace": list(updated.trace),
        "errors": list(updated.errors),
        "metrics": dict(updated.metrics),
    }
    return updated
