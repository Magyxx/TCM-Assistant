from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.graphs.consultation_graph import NODE_SEQUENCE, run_consultation_graph
from app.memory.consultation_memory import ConsultationMemoryManager
from app.schemas.report_schemas import RunState


P4_WORKFLOW_PHASE = "P4.1"
P4_RUNTIME_PHASE = "P4.5"


@dataclass(frozen=True)
class WorkflowTraceStep:
    name: str
    status: str = "completed"
    deterministic: bool = True
    permission_level: str = "internal"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "deterministic": self.deterministic,
            "permission_level": self.permission_level,
        }


@dataclass(frozen=True)
class P4WorkflowResult:
    graph_output: Dict[str, Any]
    trace: List[WorkflowTraceStep]
    boundary: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_output": self.graph_output,
            "trace": [step.to_dict() for step in self.trace],
            "boundary": self.boundary,
        }


class P4WorkflowAdapter:
    """Wrap the existing consultation flow without changing public API bodies."""

    def __init__(self, memory_manager: Optional[ConsultationMemoryManager] = None) -> None:
        self.memory_manager = memory_manager or ConsultationMemoryManager()

    def _trace(self, graph_output: Dict[str, Any]) -> List[WorkflowTraceStep]:
        errors = list(graph_output.get("errors") or [])
        status = "completed_with_errors" if errors else "completed"
        return [WorkflowTraceStep(name=name, status=status) for name, _ in NODE_SEQUENCE]

    def _boundary(self, graph_output: Dict[str, Any]) -> Dict[str, Any]:
        run_state = graph_output.get("run_state") or RunState()
        final_report = getattr(run_state, "final_report", None)
        return {
            "phase": P4_RUNTIME_PHASE,
            "api_contract_changed": False,
            "response_body_schema_changed": False,
            "sqlite_schema_changed": False,
            "pydantic_schema_changed": False,
            "risk_rule_first": True,
            "llm_can_overwrite_risk_status": False,
            "rag_can_overwrite_core_state": False,
            "memory_is_user_profile": False,
            "diagnosis_system": False,
            "final_report_present": final_report is not None,
        }

    def run(
        self,
        run_state: RunState | None,
        user_input: str,
        *,
        extractor_mode: str | None = None,
        rag_enabled: bool = True,
        use_langgraph: bool = True,
    ) -> Dict[str, Any]:
        previous_state = (run_state or RunState()).model_copy(deep=True)
        graph_output = run_consultation_graph(
            previous_state,
            user_input,
            use_langgraph=use_langgraph,
            extractor_mode=extractor_mode,
            rag_enabled=rag_enabled,
        )
        candidate_state = graph_output.get("run_state") or previous_state
        checked_state = self.memory_manager.enforce_high_risk_sticky(previous_state, candidate_state)
        trace = self._trace(graph_output)
        memory_snapshot = self.memory_manager.update(
            previous_state=previous_state,
            current_state=checked_state,
            user_input=user_input,
            trace=[step.to_dict() for step in trace],
        )
        boundary = self._boundary({**graph_output, "run_state": checked_state})

        checked_state = checked_state.model_copy(deep=True)
        checked_state.metadata = {
            **checked_state.metadata,
            "p4_workflow": {
                "phase": P4_WORKFLOW_PHASE,
                "runtime_phase": P4_RUNTIME_PHASE,
                "adapter": "P4WorkflowAdapter",
                "wrapped_existing_flow": True,
                "trace": [step.to_dict() for step in trace],
                "boundary": boundary,
            },
            "p4_memory": memory_snapshot.model_dump(),
        }
        if checked_state.final_report is not None:
            checked_state.final_report.metadata = {
                **checked_state.final_report.metadata,
                "p4_workflow_phase": P4_WORKFLOW_PHASE,
                "field_sources": memory_snapshot.field_sources,
                "p4_boundary": boundary,
            }

        return {
            **graph_output,
            "run_state": checked_state,
            "p4_trace": [step.to_dict() for step in trace],
            "p4_boundary": boundary,
            "p4_memory": memory_snapshot.model_dump(),
        }


def run_p4_workflow(
    run_state: RunState | None,
    user_input: str,
    *,
    extractor_mode: str | None = None,
    rag_enabled: bool = True,
    use_langgraph: bool = True,
) -> Dict[str, Any]:
    return P4WorkflowAdapter().run(
        run_state,
        user_input,
        extractor_mode=extractor_mode,
        rag_enabled=rag_enabled,
        use_langgraph=use_langgraph,
    )

