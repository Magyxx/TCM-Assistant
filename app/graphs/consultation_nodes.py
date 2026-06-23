from __future__ import annotations

import re
from typing import Any, Dict, List

from app.chains.turn_extractor import extract_turn
from app.graphs.consultation_state import ConsultationGraphState
from app.rules.risk_rules import apply_risk_evaluation_to_state, evaluate_risk_rules
from app.safety.report_safety import SAFETY_BOUNDARY_TEXT, safety_post_check_report
from app.schemas.report_schemas import FinalReport, RunState, TurnOutput
from app.rag.evidence_boundary import attach_evidence_pack, build_evidence_pack
from app.rag.boundary import rag_boundary_check
from app.rag.evidence_audit import build_evidence_audit_records, write_evidence_audit_records
from app.rag.evidence_schema import P6EvidencePack, attach_p6_evidence_to_report
from app.rag.p6_runtime_retriever import retrieve_p6_evidence


def _errors(state: ConsultationGraphState) -> List[str]:
    return list(state.get("errors") or [])


def _metrics(state: ConsultationGraphState) -> Dict[str, Any]:
    return dict(state.get("metrics") or {})


def _state_merge_blocked(state: ConsultationGraphState) -> bool:
    return bool(state.get("state_merge_blocked"))


def _dedupe(items: List[str]) -> List[str]:
    return list(dict.fromkeys([item for item in items if item]))


def _fallback_missing_core_fields(run_state: RunState) -> List[str]:
    missing: List[str] = []
    if not run_state.chief_complaint:
        missing.append("chief_complaint")
    if not run_state.duration:
        missing.append("duration")
    if run_state.symptoms_status == "unknown":
        missing.append("symptoms_status")
    if run_state.risk_flags_status == "unknown":
        missing.append("risk_flags_status")
    return missing


def _get_missing_core_fields(run_state: RunState) -> List[str]:
    try:
        from app.chains.report_chain import get_missing_core_fields

        return get_missing_core_fields(run_state)
    except Exception:
        return _fallback_missing_core_fields(run_state)


def _fallback_decide_next_question(run_state: RunState) -> str | None:
    if run_state.risk_flags_status == "present":
        return None
    if run_state.chief_complaint is None:
        return "请具体说一下你最主要的不舒服是什么，比如哪里不舒服，或者是胃痛、咳嗽、头晕、腹泻、胸闷这类具体表现？"
    if run_state.duration is None:
        return "这种情况持续多久了，或者是从什么时候开始的？"
    if run_state.symptoms_status == "unknown":
        return "除了这个主要不适外，还有没有其他伴随症状？如果没有也可以直接说没有。"
    if run_state.risk_flags_status == "unknown":
        return "最近有没有出现胸痛、呼吸困难、持续高热、便血、呕血、意识模糊，或突然明显加重的情况？如果没有可以直接说没有。"
    return None


def _decide_next_question(run_state: RunState) -> str | None:
    try:
        from app.chains.report_chain import decide_next_question

        return decide_next_question(run_state)
    except Exception:
        return _fallback_decide_next_question(run_state)


def _fallback_merge_turn_fields(old_state: RunState, turn_output: TurnOutput, user_input: str) -> RunState:
    new_state = old_state.model_copy(deep=True)

    if turn_output.chief_complaint:
        new_state.chief_complaint = turn_output.chief_complaint
    if turn_output.duration:
        new_state.duration = turn_output.duration
    if turn_output.symptoms:
        new_state.symptoms = _dedupe(new_state.symptoms + turn_output.symptoms)
        new_state.symptoms_status = "present"
    elif turn_output.symptoms_status == "none" and new_state.symptoms_status != "present":
        new_state.symptoms_status = "none"

    if turn_output.risk_flags:
        new_state.risk_flags = _dedupe(new_state.risk_flags + turn_output.risk_flags)
        new_state.risk_flags_status = "present"
    elif turn_output.risk_flags_status == "none" and new_state.risk_flags_status != "present":
        new_state.risk_flags_status = "none"

    if turn_output.sleep:
        new_state.sleep = turn_output.sleep
    if turn_output.appetite:
        new_state.appetite = turn_output.appetite
    if turn_output.stool_urine:
        new_state.stool_urine = turn_output.stool_urine
    if turn_output.summary:
        new_state.summary = turn_output.summary

    return new_state


def _merge_turn_fields(old_state: RunState, turn_output: TurnOutput, user_input: str) -> RunState:
    try:
        from app.chains.report_chain import merge_turn_fields

        return merge_turn_fields(old_state, turn_output, user_input)
    except Exception:
        return _fallback_merge_turn_fields(old_state, turn_output, user_input)


def _fallback_generate_final_report(run_state: RunState) -> FinalReport:
    missing = _fallback_missing_core_fields(run_state)
    info_complete = len(missing) == 0
    triage_level = "urgent_visit" if run_state.risk_flags_status == "present" else ("observe" if info_complete else "followup")

    summary_parts = [
        f"主诉：{run_state.chief_complaint or '暂未明确'}",
        f"持续时间：{run_state.duration or '暂未明确'}",
        f"伴随症状状态：{run_state.symptoms_status}",
        f"风险状态：{run_state.risk_flags_status}",
    ]
    if run_state.symptoms:
        summary_parts.append(f"伴随症状：{'、'.join(run_state.symptoms)}")
    if run_state.risk_flags:
        summary_parts.append(f"风险信号：{'、'.join(run_state.risk_flags)}")

    if triage_level == "urgent_visit":
        impression = f"当前问诊信息提示存在需要警惕的风险信号，建议尽快线下就医进一步评估。{SAFETY_BOUNDARY_TEXT}"
        advice = [
            "建议尽快前往线下医疗机构评估。",
            "就医前可整理主诉、持续时间、伴随症状和变化过程。",
            SAFETY_BOUNDARY_TEXT,
        ]
    elif not info_complete:
        impression = f"当前问诊信息仍不完整，建议继续补充核心信息。{SAFETY_BOUNDARY_TEXT}"
        advice = [
            "建议继续补充主诉、持续时间、伴随症状和风险情况。",
            SAFETY_BOUNDARY_TEXT,
        ]
    else:
        impression = f"当前核心问诊信息已整理，暂未见明确高风险信号，可继续观察变化。{SAFETY_BOUNDARY_TEXT}"
        advice = [
            "建议记录症状变化，若持续不缓解、加重或出现高风险表现，应及时线下就医。",
            SAFETY_BOUNDARY_TEXT,
        ]

    return FinalReport(
        summary="\n".join(summary_parts),
        impression=impression,
        advice=advice,
        triage_level=triage_level,
        info_complete=info_complete,
        missing_core_fields=missing,
        followup_needed=not info_complete,
        metadata={
            "triggered_rule_ids": run_state.triggered_rule_ids,
            "risk_reasons": run_state.risk_reasons,
            "fallback_report_generator": True,
            "safety_boundary": SAFETY_BOUNDARY_TEXT,
        },
    )


def _generate_final_report(run_state: RunState) -> FinalReport:
    try:
        from app.chains.report_chain import generate_final_report

        return generate_final_report(run_state)
    except Exception:
        return _fallback_generate_final_report(run_state)


def normalize_input(state: ConsultationGraphState) -> ConsultationGraphState:
    user_input = state.get("user_input", "")
    normalized = re.sub(r"\s+", " ", str(user_input)).strip()
    return {
        **state,
        "normalized_input": normalized,
        "errors": _errors(state),
        "metrics": _metrics(state),
    }


def extract_turn_node(state: ConsultationGraphState) -> ConsultationGraphState:
    run_state = state.get("run_state") or RunState()
    user_input = state.get("normalized_input") or state.get("user_input") or ""

    result = extract_turn(
        run_state,
        user_input,
        extractor_mode=state.get("extractor_mode_requested"),
    )
    metrics = _metrics(state)
    metrics["last_extraction_mode"] = result.mode
    metrics["last_extractor_mode"] = result.extractor_mode or result.mode
    metrics["last_strategy"] = result.strategy
    metrics["last_model_name"] = result.model_name
    metrics["last_error_type"] = result.error_type
    metrics["last_error_message_preview"] = result.error_message_preview
    metrics["last_json_valid"] = result.json_valid
    metrics["last_schema_valid"] = result.schema_valid
    metrics["last_raw_llm_json_valid"] = result.raw_llm_json_valid
    metrics["last_final_schema_pass"] = result.final_schema_pass
    metrics["last_fallback_used"] = result.fallback_used

    errors = _errors(state)
    if result.error:
        errors.append(result.error)

    return {
        **state,
        "run_state": run_state,
        "turn_output": result.turn_output,
        "extraction_result": result.to_dict(),
        "extraction_mode": result.mode,
        "extractor_mode": result.extractor_mode or result.mode,
        "strategy": result.strategy,
        "model_name": result.model_name,
        "error_type": result.error_type,
        "error_message_preview": result.error_message_preview,
        "json_valid": result.json_valid,
        "schema_valid": result.schema_valid,
        "raw_llm_json_valid": result.raw_llm_json_valid,
        "final_schema_pass": result.final_schema_pass,
        "fallback_used": result.fallback_used,
        "errors": errors,
        "metrics": metrics,
    }


def validate_turn(state: ConsultationGraphState) -> ConsultationGraphState:
    turn_output = state.get("turn_output")
    errors = _errors(state)

    if turn_output is None:
        errors.append("TurnOutput schema validation failed: extractor returned None.")
        return {
            **state,
            "turn_output": None,
            "schema_valid": False,
            "state_merge_blocked": True,
            "errors": errors,
        }

    try:
        validated = TurnOutput.model_validate(turn_output)
        return {
            **state,
            "turn_output": validated,
            "schema_valid": True,
        }
    except Exception as exc:
        errors.append(f"TurnOutput schema validation failed: {exc}")
        fallback = TurnOutput(summary="本轮抽取未通过结构校验，已回退为空结构。")
        return {
            **state,
            "turn_output": fallback,
            "schema_valid": False,
            "state_merge_blocked": True,
            "errors": errors,
        }


def merge_state(state: ConsultationGraphState) -> ConsultationGraphState:
    run_state = state.get("run_state") or RunState()
    if _state_merge_blocked(state):
        return {
            **state,
            "run_state": run_state,
        }

    turn_output = state.get("turn_output") or TurnOutput()
    user_input = state.get("normalized_input") or state.get("user_input") or ""

    merged = _merge_turn_fields(run_state, turn_output, user_input)
    merged.turn_count += 1
    extraction_counts = dict(merged.metadata.get("extraction_counts") or {})
    extraction_counts["total"] = int(extraction_counts.get("total", 0)) + 1
    extraction_counts["json_valid"] = int(extraction_counts.get("json_valid", 0)) + int(bool(state.get("json_valid")))
    extraction_counts["schema_valid"] = int(extraction_counts.get("schema_valid", 0)) + int(bool(state.get("schema_valid")))
    extraction_counts["raw_llm_json_valid"] = int(extraction_counts.get("raw_llm_json_valid", 0)) + int(bool(state.get("raw_llm_json_valid")))
    extraction_counts["final_schema_pass"] = int(extraction_counts.get("final_schema_pass", 0)) + int(bool(state.get("final_schema_pass")))
    extraction_counts["fallback_used"] = int(extraction_counts.get("fallback_used", 0)) + int(bool(state.get("fallback_used")))
    merged.metadata = {
        **merged.metadata,
        "graph_runtime": state.get("graph_runtime"),
        "extractor_mode_requested": state.get("extractor_mode_requested"),
        "last_extractor_mode": state.get("extractor_mode"),
        "last_extraction_mode": state.get("extraction_mode"),
        "last_strategy": state.get("strategy"),
        "last_model_name": state.get("model_name"),
        "last_error_type": state.get("error_type"),
        "last_error_message_preview": state.get("error_message_preview"),
        "last_json_valid": state.get("json_valid"),
        "last_schema_valid": state.get("schema_valid"),
        "last_raw_llm_json_valid": state.get("raw_llm_json_valid"),
        "last_final_schema_pass": state.get("final_schema_pass"),
        "last_fallback_used": state.get("fallback_used"),
        "extraction_counts": extraction_counts,
    }

    return {
        **state,
        "run_state": merged,
    }


def risk_rule_check(state: ConsultationGraphState) -> ConsultationGraphState:
    run_state = state.get("run_state") or RunState()
    if _state_merge_blocked(state):
        return {
            **state,
            "run_state": run_state,
            "risk_status": None,
            "risk_reasons": [],
            "triggered_rule_ids": [],
        }

    user_input = state.get("normalized_input") or state.get("user_input") or ""
    evaluation = evaluate_risk_rules(user_input, previous_status=run_state.risk_flags_status)
    checked = apply_risk_evaluation_to_state(run_state, evaluation)

    return {
        **state,
        "run_state": checked,
        "risk_status": evaluation.risk_status,
        "risk_reasons": evaluation.risk_reasons,
        "triggered_rule_ids": evaluation.triggered_rule_ids,
    }


def decide_next(state: ConsultationGraphState) -> ConsultationGraphState:
    run_state = state.get("run_state") or RunState()
    if _state_merge_blocked(state):
        return {
            **state,
            "run_state": run_state,
            "missing_core_fields": _get_missing_core_fields(run_state),
            "done": False,
        }

    run_state = run_state.model_copy(deep=True)
    run_state.next_question = _decide_next_question(run_state)
    missing = _get_missing_core_fields(run_state)
    done = run_state.next_question is None

    return {
        **state,
        "run_state": run_state,
        "missing_core_fields": missing,
        "done": done,
    }


def ask_followup(state: ConsultationGraphState) -> ConsultationGraphState:
    if _state_merge_blocked(state):
        return state

    run_state = state.get("run_state") or RunState()
    if state.get("done"):
        return state
    if run_state.next_question:
        return state

    run_state = run_state.model_copy(deep=True)
    run_state.next_question = _decide_next_question(run_state)
    return {
        **state,
        "run_state": run_state,
    }


def _state_to_retrieval_query(run_state: RunState) -> str:
    parts: List[str] = []
    if run_state.chief_complaint:
        parts.append(f"主诉：{run_state.chief_complaint}")
    if run_state.duration:
        parts.append(f"持续时间：{run_state.duration}")
    if run_state.symptoms:
        parts.append(f"伴随症状：{'、'.join(run_state.symptoms)}")
    if run_state.risk_flags:
        parts.append(f"风险信号：{'、'.join(run_state.risk_flags)}")
    parts.append(f"风险状态：{run_state.risk_flags_status}")
    parts.append("检索观察建议、风险提示、就医建议")
    return "；".join(parts)


def _state_to_p6b_retrieval_query(run_state: RunState) -> str:
    base_query = _state_to_retrieval_query(run_state)
    # The committed P6 fixture is synthetic English policy text, so runtime
    # retrieval adds stable boundary terms without changing RunState.
    expansion = (
        " information organization evidence citation advice explanation "
        "digestive discomfort duration appetite stool symptom changes "
        "chest pain chest tightness dyspnea blood in stool vomiting blood "
        "persistent high fever urgent offline care red flag"
    )
    return f"{base_query} {expansion}"


def retrieve_knowledge(state: ConsultationGraphState) -> ConsultationGraphState:
    if _state_merge_blocked(state):
        return {
            **state,
            "retrieved_evidence": [],
            "p6b_rag_evidence_pack": {},
            "p6b_rag_trace": {},
        }

    if not state.get("done"):
        return state
    if state.get("rag_enabled") is False:
        return {
            **state,
            "retrieved_evidence": [],
            "p6b_rag_evidence_pack": {},
            "p6b_rag_trace": {},
        }

    run_state = state.get("run_state") or RunState()
    query = _state_to_p6b_retrieval_query(run_state)

    try:
        before = run_state.model_copy(deep=True)
        pack, trace = retrieve_p6_evidence(query, top_k=3)
        boundary = rag_boundary_check(before, run_state, pack)
        trace = {**trace, "rag_boundary_pass": boundary["passed"]}
        evidence = [item.model_dump() for item in pack.evidence]
    except Exception as exc:
        errors = _errors(state)
        errors.append(f"p6b_runtime_rag_failed_closed: {exc}")
        return {
            **state,
            "retrieved_evidence": [],
            "rag_evidence_pack": {},
            "p6b_rag_evidence_pack": {},
            "p6b_rag_trace": {
                "rag_runtime_enabled": True,
                "fallback_used": False,
                "fallback_reason": None,
                "rag_boundary_pass": False,
                "error": str(exc),
            },
            "errors": errors,
        }

    return {
        **state,
        "retrieved_evidence": evidence,
        "rag_evidence_pack": pack.model_dump(),
        "p6b_rag_evidence_pack": pack.model_dump(),
        "p6b_rag_trace": trace,
    }


def generate_report(state: ConsultationGraphState) -> ConsultationGraphState:
    if _state_merge_blocked(state):
        return {
            **state,
            "final_report": None,
        }

    run_state = state.get("run_state") or RunState()
    if not state.get("done"):
        run_state = run_state.model_copy(deep=True)
        run_state.final_report = None
        return {
            **state,
            "run_state": run_state,
            "final_report": None,
        }

    report = _generate_final_report(run_state)
    report.metadata = {
        **report.metadata,
        "retrieved_evidence": state.get("retrieved_evidence") or [],
        "p4_rag_evidence_pack": state.get("rag_evidence_pack") or {},
        "p6b_rag_trace": state.get("p6b_rag_trace") or {},
        "graph_mode": True,
    }
    if state.get("p6b_rag_evidence_pack"):
        try:
            p6_pack = P6EvidencePack.model_validate(state["p6b_rag_evidence_pack"])
            report = attach_p6_evidence_to_report(
                report,
                p6_pack,
            )
            trace = state.get("p6b_rag_trace") or {}
            if p6_pack.evidence and isinstance(trace, dict):
                write_evidence_audit_records(
                    build_evidence_audit_records(
                        p6_pack,
                        trace,
                        query_id=str(trace.get("turn_id") or "report"),
                        used_in_report_section="report.metadata",
                        core_state_mutated=False,
                    )
                )
        except Exception as exc:
            errors = _errors(state)
            errors.append(f"p6b_attach_evidence_failed: {exc}")
            state = {**state, "errors": errors}
    elif state.get("rag_evidence_pack"):
        report = attach_evidence_pack(report, build_evidence_pack(run_state, top_k=3, mode="bm25_only"))

    run_state = run_state.model_copy(deep=True)
    run_state.final_report = report
    return {
        **state,
        "run_state": run_state,
        "final_report": report,
    }


def safety_post_check(state: ConsultationGraphState) -> ConsultationGraphState:
    report = state.get("final_report")
    if report is None:
        return {
            **state,
            "safety_issues": [],
        }

    result = safety_post_check_report(report)
    run_state = state.get("run_state") or RunState()
    run_state = run_state.model_copy(deep=True)
    run_state.final_report = result.report

    return {
        **state,
        "run_state": run_state,
        "final_report": result.report,
        "safety_issues": result.issues,
    }
