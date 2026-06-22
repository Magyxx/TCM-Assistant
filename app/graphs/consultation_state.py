from __future__ import annotations

from typing import Any, Dict, List, Optional, TypedDict

from app.schemas.report_schemas import FinalReport, RunState, TurnOutput


class ConsultationGraphState(TypedDict, total=False):
    user_input: str
    normalized_input: str
    run_state: RunState
    turn_output: Optional[TurnOutput]
    final_report: Optional[FinalReport]
    extraction_result: Dict[str, Any]
    schema_valid: bool
    json_valid: bool
    raw_llm_json_valid: bool
    final_schema_pass: bool
    fallback_used: bool
    extraction_mode: str
    extractor_mode: str
    extractor_mode_requested: str
    model_name: Optional[str]
    error_type: Optional[str]
    strategy: Optional[str]
    error_message_preview: Optional[str]
    graph_runtime: str
    errors: List[str]
    risk_status: Optional[str]
    risk_reasons: List[str]
    triggered_rule_ids: List[str]
    missing_core_fields: List[str]
    retrieved_evidence: List[Dict[str, Any]]
    rag_evidence_pack: Dict[str, Any]
    p6b_rag_evidence_pack: Dict[str, Any]
    p6b_rag_trace: Dict[str, Any]
    rag_enabled: bool
    safety_issues: List[str]
    metrics: Dict[str, Any]
    done: bool
