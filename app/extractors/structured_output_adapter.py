from __future__ import annotations

from app.extractors.registry import get_extractor
from app.extractors.router import get_extractor_backend
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
        requested_mode = mode or "auto"
        try:
            backend = get_extractor_backend(None if requested_mode == "auto" else requested_mode)
            result = backend.extract(
                text,
                state=state,
                memory=memory,
            )
        except ValueError as exc:
            extractor = get_extractor(mode)
            if mode and getattr(extractor, "mode", None) != mode:
                result = ExtractorResult.schema_failure(
                    mode=mode,
                    raw_output=None,
                    error=str(exc),
                    metadata={"error_type": "unknown_backend"},
                )
            else:
                result = extractor.extract(text, state=state, memory=memory)
        result.metadata["requested_mode"] = mode or "auto"
        result.metadata["adapter"] = "structured_output_adapter"
        result.metadata.setdefault("backend", result.mode)
        return result


def extract_turn_with_adapter(
    text: str,
    *,
    state: RunState | dict | None = None,
    memory: dict | None = None,
    mode: str | None = None,
) -> ExtractorResult:
    return ExtractorAdapter().extract(text, state=state, memory=memory, mode=mode)
