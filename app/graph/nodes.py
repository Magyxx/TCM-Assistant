from __future__ import annotations

import re
from typing import Any
from typing import List

from app.extractors.router import get_extractor_backend
from app.extractors.structured_output_adapter import ExtractorAdapter
from app.graph.state import ConsultationGraphState
from app.memory.manager import MemoryManager
from app.rag.bm25_retriever import BM25Retriever
from app.rag.document_store import LocalTextDocumentStore
from app.rag.evidence_pack import build_evidence_pack
from app.rag.retriever_router import retrieve_evidence_pack
from app.rag.knowledge_loader import ROOT_KNOWLEDGE_FILE
from app.rag.query_builder import build_rag_query
from app.rag.rag_guard import report_text_is_safe
from app.config.settings import AppSettings
from app.report.renderer import build_report_skeleton
from app.safety.report_safety import safety_post_check_report
from app.rules.risk_rules import evaluate_risk_rules
from app.rules.rule_types import RiskEvaluation
from app.schemas.report_schemas import FinalReport, RunState, SAFETY_DISCLAIMER, TurnOutput


FORBIDDEN_NEXT_ACTION_TERMS = (
    "diagnose",
    "diagnosis",
    "prescribe",
    "prescription",
    "replace doctor",
)


def _audit(node: str, status: str = "ok", **extra: Any) -> dict[str, Any]:
    return {"node": node, "status": status, **extra}


def _append_audit(state: ConsultationGraphState, node: str, status: str = "ok", **extra: Any) -> None:
    state.audit_events.append(_audit(node, status, **extra))


def _text_has_any(text: str, terms: list[str]) -> bool:
    return any(term and term in text for term in terms)


def _heuristic_turn_output(text: str, *, mode: str) -> TurnOutput:
    lower = text.lower()
    chief: str | None = None
    chief_terms = [
        "\u80c3\u80c0",
        "\u80c3\u75db",
        "\u8179\u80c0",
        "\u8179\u75db",
        "\u54b3\u55fd",
        "\u5934\u75db",
        "stomach discomfort",
        "stomach bloating",
        "stomach pain",
        "cough",
        "headache",
    ]
    for term in chief_terms:
        if term in text or term in lower:
            chief = term
            break

    duration: str | None = None
    duration_patterns = [
        r"\u534a\u5929",
        r"\u4e00\u5929",
        r"\u4e24\u5929",
        r"\u4e09\u5929",
        r"\u56db\u5929",
        r"\u4e00\u5468",
        r"\u4e24\u5468",
        r"\d+\u5929",
        r"\d+\u5468",
        r"for (one|two|three|four|five|six|seven) days?",
        r"for \d+ days?",
        r"for (one|two|three) weeks?",
        r"for \d+ weeks?",
    ]
    for pattern in duration_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            duration = match.group(0)
            break

    symptoms: list[str] = []
    for term in ["\u6076\u5fc3", "\u53cd\u9178", "\u996d\u540e\u660e\u663e", "nausea", "acid reflux"]:
        if term in text or term in lower:
            symptoms.append(term)
    none_phrases = [
        "\u6ca1\u6709\u5176\u4ed6\u75c7\u72b6",
        "\u65e0\u5176\u4ed6\u75c7\u72b6",
        "no other symptoms",
    ]
    symptoms_status = "none" if _text_has_any(lower, none_phrases) else ("present" if symptoms else "unknown")
    if symptoms_status == "none":
        symptoms = []

    appetite = "\u996d\u540e\u660e\u663e" if "\u996d\u540e\u660e\u663e" in text else None
    negated_risk = any(
        phrase in lower
        for phrase in [
            "no chest pain",
            "no breathing difficulty",
            "no shortness of breath",
        ]
    ) or any(phrase in text for phrase in ["\u6ca1\u6709\u80f8\u75db", "\u65e0\u80f8\u75db"])
    return TurnOutput(
        chief_complaint=chief,
        duration=duration,
        symptoms=list(dict.fromkeys(symptoms)),
        symptoms_status=symptoms_status,
        appetite=appetite,
        risk_flags_status="none" if negated_risk else "unknown",
        summary=f"{mode} graph heuristic structured output.",
        metadata={
            "backend": mode,
            "adapter": "structured_output_adapter",
            "heuristic_fallback": True,
        },
    )


def _merge_turn_outputs(primary: TurnOutput | None, fallback: TurnOutput) -> TurnOutput:
    if primary is None:
        return fallback
    data = primary.model_dump()
    fallback_data = fallback.model_dump()
    for key, value in fallback_data.items():
        current = data.get(key)
        if current in (None, "", [], {}, "unknown") and value not in (None, "", [], {}, "unknown"):
            data[key] = value
    metadata = {**fallback.metadata, **(primary.metadata or {})}
    if fallback.metadata.get("heuristic_fallback"):
        metadata["heuristic_fallback"] = True
    data["metadata"] = metadata
    return TurnOutput.model_validate(data)


def _fallback_risk_evaluation(text: str, previous_status: str = "unknown") -> RiskEvaluation:
    evaluation = evaluate_risk_rules(text, previous_status=previous_status)
    if evaluation.risk_status is not None:
        return evaluation
    lower = text.lower()
    if any(term in lower for term in ["chest pain", "breathing difficulty", "shortness of breath"]):
        return RiskEvaluation(
            risk_status="present",
            risk_flags=["offline medical evaluation signal"],
            triggered_rule_ids=["P8_GRAPH_RULE_EN_HIGH_RISK"],
            risk_reasons=["User text mentions a high-risk signal that requires offline medical evaluation."],
        )
    if any(term in text for term in ["\u80f8\u75db", "\u547c\u5438\u56f0\u96be"]):
        return RiskEvaluation(
            risk_status="present",
            risk_flags=["high-risk signal"],
            triggered_rule_ids=["P8_GRAPH_RULE_ZH_HIGH_RISK"],
            risk_reasons=["User text mentions a high-risk signal that requires offline medical evaluation."],
        )
    return evaluation


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
    _append_audit(updated, "normalize_input")
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
    if result.schema_pass:
        heuristic_output = _heuristic_turn_output(user_input, mode=result.mode)
        updated.turn_output = _merge_turn_outputs(result.turn_output, heuristic_output)
    else:
        updated.turn_output = result.turn_output
    updated.extraction_result = result.model_dump()
    updated.extraction_result["turn_output"] = (
        updated.turn_output.model_dump() if updated.turn_output is not None else None
    )
    updated.extraction_mode = str(metadata.get("legacy_mode") or result.mode)
    requested_mode = str(metadata.get("requested_mode") or "")
    updated.extractor_mode = requested_mode if requested_mode and requested_mode != "auto" else result.mode
    updated.strategy = metadata.get("strategy")
    updated.model_name = metadata.get("model_name")
    updated.error_type = metadata.get("error_type")
    updated.skip_reason = result.skip_reason
    updated.error_message_preview = metadata.get("error_message_preview")
    updated.json_valid = bool(metadata.get("json_valid"))
    updated.schema_valid = result.schema_pass
    updated.raw_llm_json_valid = bool(metadata.get("raw_llm_json_valid"))
    updated.final_schema_pass = bool(metadata.get("final_schema_pass", result.schema_pass))
    updated.fallback_used = result.fallback_used
    updated.metrics["extract_turn"] = result.mode
    updated.metrics["extractor_adapter"] = metadata.get("adapter")
    updated.metrics["extractor_backend"] = metadata.get("backend") or result.mode
    if result.skip_reason:
        updated.metrics["extractor_skip_reason"] = result.skip_reason
    if result.error and not result.skip_reason:
        updated.errors.append(result.error)
    _append_audit(
        updated,
        "extract_turn",
        mode=updated.extractor_mode,
        backend=metadata.get("backend") or result.mode,
        schema_pass=result.schema_pass,
        fallback_used=result.fallback_used,
        skip_reason=result.skip_reason,
        heuristic_fallback=bool(updated.turn_output and updated.turn_output.metadata.get("heuristic_fallback")),
    )
    return updated


def validate_turn(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    try:
        updated.turn_output = TurnOutput.model_validate(updated.turn_output)
        updated.schema_valid = True
        updated.metrics["validate_turn"] = "ok"
        updated.trace.append({"node": "validate_turn", "status": "ok"})
        _append_audit(updated, "validate_turn")
    except Exception as exc:
        updated.turn_output = None
        updated.schema_valid = False
        updated.errors.append(f"turn_output_schema_invalid:{exc.__class__.__name__}")
        updated.metrics["validate_turn"] = "failed"
        updated.trace.append({"node": "validate_turn", "status": "failed", "error_type": exc.__class__.__name__})
        _append_audit(updated, "validate_turn", "failed", error_type=exc.__class__.__name__)
    return updated


def memory_update(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    manager = MemoryManager()
    user_input = updated.normalized_input or updated.user_input
    next_turn_count = updated.run_state.turn_count + 1
    before_event_count = len(updated.memory.audit_events)
    updated.memory = manager.apply_turn(
        memory=updated.memory,
        previous_state=updated.run_state,
        turn_output=updated.turn_output,
        user_input=user_input,
        raw_text=user_input,
        turn_id=updated.turn_id or f"turn-{next_turn_count}",
        turn_index=next_turn_count,
        session_id=updated.session_id,
        extractor_mode=updated.extractor_mode or updated.extractor_mode_requested,
    )
    exported = manager.export_run_state(updated.memory, base_state=updated.run_state)
    exported.turn_count = next_turn_count
    updated.run_state = exported
    updated.audit_events.extend(
        event.model_dump() for event in updated.memory.audit_events[before_event_count:]
    )
    updated.run_state.metadata = {
        **updated.run_state.metadata,
        "p8_graph_audit_events": list(updated.audit_events),
    }
    updated.metrics["memory_update"] = "ok"
    _append_audit(updated, "memory_update", memory_manager="MemoryManager.apply_turn")
    return updated


def risk_check(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    manager = MemoryManager()
    user_input = updated.normalized_input or updated.user_input
    before_event_count = len(updated.memory.audit_events)
    evaluation = _fallback_risk_evaluation(user_input, previous_status=updated.run_state.risk_flags_status)
    updated.memory = manager.apply_risk_evaluation(
        memory=updated.memory,
        risk_evaluation=evaluation,
        turn_id=updated.turn_id or f"turn-{updated.run_state.turn_count}",
        raw_text=user_input,
        session_id=updated.session_id,
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
    updated.audit_events.extend(
        event.model_dump() for event in updated.memory.audit_events[before_event_count:]
    )
    updated.risk_rule_ids = list(updated.run_state.triggered_rule_ids)
    updated.metrics["risk_check"] = "ok"
    _append_audit(
        updated,
        "risk_check",
        risk_status=updated.risk_status,
        risk_rule_ids=list(updated.risk_rule_ids),
    )
    return updated


def plan_next_action(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    run_state = updated.run_state.model_copy(deep=True)
    missing = _missing_core_fields(run_state)
    updated.missing_core_fields = missing

    if run_state.risk_flags_status == "present":
        run_state.next_question = None
        updated.next_question = None
        updated.next_action = "advise_timely_offline_medical_evaluation"
        updated.done = True
    elif missing:
        run_state.next_question = _safe_followup_question(run_state)
        updated.next_question = run_state.next_question
        updated.next_action = "ask_followup"
        updated.done = False
    else:
        run_state.next_question = None
        updated.next_question = None
        updated.next_action = "ready_for_structured_consultation_summary"
        updated.done = True

    updated.safety_issues = _record_safety_issues(" ".join([updated.next_action, run_state.next_question or ""]))
    updated.run_state = run_state
    updated.metrics["plan_next_action"] = "ok"
    _append_audit(updated, "plan_next_action", next_action=updated.next_action)
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
    p1_pack = retrieve_evidence_pack(
        query,
        top_k=3,
        settings=AppSettings(ENABLE_RAG=True, RAG_BACKEND="bm25_realpath"),
    )
    p1_payload = p1_pack.model_dump()
    skeleton = build_report_skeleton(
        session_id=updated.session_id,
        state=updated.run_state.model_dump(),
        evidence_pack=p1_payload,
    )
    updated.run_state.metadata = {
        **updated.run_state.metadata,
        "p1_f1_evidence_pack": p1_payload,
        "p1_f1_report_skeleton": skeleton.model_dump(),
        "p1_f1_rag_core_field_overwrite_blocked": True,
    }
    updated.metrics["p1_f1_evidence_backend"] = p1_pack.backend
    updated.metrics["p1_f1_report_skeleton"] = "generated"
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
    if field_name in {"chief_complaint", "duration"} and getattr(run_state, field_name, None):
        return
    if value not in (None, "", [], {}, "unknown"):
        setattr(run_state, field_name, value)


def extract_turn(state: ConsultationGraphState) -> ConsultationGraphState:
    updated = state.model_copy(deep=True)
    backend = get_extractor_backend(updated.extractor_mode_requested or None)
    user_input = updated.normalized_input or updated.user_input
    result = backend.extract(
        user_input,
        state=updated.run_state,
        memory=updated.memory.model_dump(),
    )
    output = result.turn_output
    updated.turn_output = output
    if output is not None:
        updated.turns.append(output)
    updated.extractor_mode = getattr(backend, "mode", updated.extractor_mode_requested)
    updated.extraction_result = result.model_dump()
    updated.extraction_result["turn_output"] = output.model_dump() if output is not None else None
    metadata = result.metadata
    updated.fallback_used = result.fallback_used
    updated.raw_llm_json_valid = bool(metadata.get("raw_llm_json_valid"))
    updated.json_valid = bool(metadata.get("json_valid"))
    updated.schema_valid = result.schema_pass
    updated.final_schema_pass = bool(metadata.get("final_schema_pass", result.schema_pass))
    updated.skip_reason = result.skip_reason
    updated.error_type = metadata.get("error_type")
    updated.error_message_preview = metadata.get("error_message_preview")
    if result.error and not result.skip_reason:
        updated.errors.append(result.error)
    _trace(
        updated,
        "extract_turn",
        "ok" if result.schema_pass or result.skip_reason else "failed",
        backend=updated.extractor_mode,
        schema_pass=result.schema_pass,
        fallback_used=result.fallback_used,
        skip_reason=result.skip_reason,
    )
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

    accumulated_negated_rule_ids = list(
        dict.fromkeys(
            list(run_state.metadata.get("negated_rule_ids") or [])
            + list(evaluation.negated_rule_ids)
        )
    )
    run_state.metadata = {
        **run_state.metadata,
        "negated_rule_ids": accumulated_negated_rule_ids,
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
    asked.update(str(item) for item in updated.run_state.metadata.get("asked_followup_fields", []) if item)
    field = next((item for item in P9_FOLLOWUP_PRIORITY if item in updated.missing_core_fields and item not in asked), None)
    field = field or (updated.missing_core_fields[0] if updated.missing_core_fields else "chief_complaint")
    question = P9_FOLLOWUP_QUESTIONS[field]
    updated.next_question = question
    updated.run_state.next_question = question
    updated.run_state.metadata = {
        **updated.run_state.metadata,
        "asked_followup_fields": list(dict.fromkeys([*asked, field])),
    }
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
    p1_pack = retrieve_evidence_pack(
        query,
        top_k=3,
        settings=AppSettings(ENABLE_RAG=True, RAG_BACKEND="bm25_realpath"),
    )
    updated.evidence_pack = p1_pack.model_dump()
    updated.run_state.metadata = {
        **updated.run_state.metadata,
        "p1_f1_evidence_pack": updated.evidence_pack,
        "p1_f1_rag_core_field_overwrite_blocked": True,
    }
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
            "p1_f1_evidence_pack": dict(updated.evidence_pack),
        },
    )
    skeleton = build_report_skeleton(
        session_id=updated.session_id,
        state=run_state.model_dump(),
        evidence_pack=dict(updated.evidence_pack) if updated.evidence_pack else None,
    )
    report.metadata = {
        **report.metadata,
        "p1_f1_report_skeleton": skeleton.model_dump(),
    }
    updated.final_report = report
    updated.run_state.final_report = report
    updated.run_state.next_question = None
    updated.next_question = None
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
        "extraction_result": dict(updated.extraction_result),
        "schema_valid": updated.schema_valid,
        "raw_llm_json_valid": updated.raw_llm_json_valid,
        "final_schema_pass": updated.final_schema_pass,
        "fallback_used": updated.fallback_used,
        "skip_reason": updated.skip_reason,
        "audit_events": list(updated.audit_events),
        "run_state": updated.run_state.model_dump(),
        "risk_status": updated.run_state.risk_flags_status,
        "risk_reasons": updated.risk_events or updated.risk_reasons,
        "risk_rule_ids": list(updated.run_state.triggered_rule_ids),
        "missing_core_fields": list(updated.missing_core_fields),
        "next_question": updated.next_question or updated.run_state.next_question,
        "retrieved_evidence": [item.model_dump() for item in updated.p9_evidence],
        "p1_evidence_pack": dict(updated.evidence_pack),
        "p1_report_skeleton": (
            updated.final_report.metadata.get("p1_f1_report_skeleton")
            if updated.final_report and isinstance(updated.final_report.metadata, dict)
            else None
        ),
        "final_report": updated.final_report.model_dump() if updated.final_report else None,
        "trace": list(updated.trace),
        "errors": list(updated.errors),
        "metrics": dict(updated.metrics),
    }
    return updated
