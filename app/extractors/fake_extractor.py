from __future__ import annotations

import time

from app.extractors.base import BackendResult, backend_result_from_turn_output
from app.schemas.report_schemas import RunState


def extract_with_fake_backend(state: RunState, user_input: str) -> BackendResult:
    started = time.perf_counter()
    from app.chains.turn_extractor import build_fake_turn_output

    turn_output = build_fake_turn_output(state, user_input)
    return backend_result_from_turn_output(
        "fake",
        turn_output,
        model_name="fake",
        latency_ms=round((time.perf_counter() - started) * 1000, 3),
    )
