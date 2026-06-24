from __future__ import annotations

from pathlib import Path

from app.graph.runner import run_p9m1_graph
from app.observability.json_logger import read_graph_events
from app.session.memory_store import MemorySessionStore


def test_json_graph_log_has_required_fields_and_no_secret_text(tmp_path: Path) -> None:
    log_path = tmp_path / "graph_events.jsonl"
    store = MemorySessionStore()
    result = run_p9m1_graph(
        "胃胀一周，没有其他症状，睡眠一般，食欲一般，大便正常，小便正常，没有胸痛",
        session_id="log-test",
        session_store=store,
        graph_events_path=log_path,
        use_langgraph=False,
    )
    events = read_graph_events(log_path)

    assert result["trace_id"]
    assert events
    required = {"trace_id", "session_id", "turn_id", "node", "latency_ms", "timestamp"}
    assert required.issubset(events[0])
    serialized = log_path.read_text(encoding="utf-8")
    assert "OPENAI_API_KEY" not in serialized
    assert "Authorization" not in serialized
    assert "sk-" not in serialized
    assert "胃胀一周" not in serialized
