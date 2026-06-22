from __future__ import annotations

from app.extractors.registry import get_extractor
from app.extractors.result import ExtractorResult
from app.schemas.report_schemas import RunState


class ExtractorAdapter:
    def extract(
        self,
        text: str,
        *,
        state: RunState | dict | None = None,
        memory: dict | None = None,
        mode: str | None = None,
    ) -> ExtractorResult:
        extractor = get_extractor(mode)
        result = extractor.extract(text, state=state, memory=memory)
        result.metadata["requested_mode"] = mode or "auto"
        result.metadata["adapter"] = "structured_output_adapter"
        return result


def extract_turn_with_adapter(
    text: str,
    *,
    state: RunState | dict | None = None,
    memory: dict | None = None,
    mode: str | None = None,
) -> ExtractorResult:
    return ExtractorAdapter().extract(text, state=state, memory=memory, mode=mode)
