from __future__ import annotations

from typing import Any, Dict

from app.graph.consultation_graph import run_consultation_graph
from app.schemas.report_schemas import RunState


class P8WorkflowAdapter:
    def run(
        self,
        run_state: RunState | None,
        user_input: str,
        *,
        extractor_mode: str | None = None,
        rag_enabled: bool = True,
        use_langgraph: bool = True,
    ) -> Dict[str, Any]:
        return run_consultation_graph(
            run_state,
            user_input,
            use_langgraph=use_langgraph,
            extractor_mode=extractor_mode,
            rag_enabled=rag_enabled,
        )


def run_p8_workflow(
    run_state: RunState | None,
    user_input: str,
    *,
    extractor_mode: str | None = None,
    rag_enabled: bool = True,
    use_langgraph: bool = True,
) -> Dict[str, Any]:
    return P8WorkflowAdapter().run(
        run_state,
        user_input,
        extractor_mode=extractor_mode,
        rag_enabled=rag_enabled,
        use_langgraph=use_langgraph,
    )
