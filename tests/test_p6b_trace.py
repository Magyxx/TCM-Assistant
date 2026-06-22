import unittest

from app.observability.trace import P6B_RAG_TRACE_FIELDS, build_p6b_rag_trace, trace_schema_pass
from app.rag.evidence_schema import P6B_INDEX_VERSION, P6B_RETRIEVAL_MODE, P6EvidenceChunk


def _evidence(source_id: str, chunk_id: str) -> P6EvidenceChunk:
    return P6EvidenceChunk(
        source_id=source_id,
        chunk_id=chunk_id,
        title="title",
        content="content",
        score=1.0,
        retrieval_mode=P6B_RETRIEVAL_MODE,
        index_version=P6B_INDEX_VERSION,
        chunk_hash="sha256:" + chunk_id.encode("utf-8").hex().ljust(64, "0")[:64],
        source_rights_status="internal_owned",
        source_safety_status="reviewed",
        source_provenance_status="reviewed",
    )


class P6BTraceTests(unittest.TestCase):
    def test_trace_contains_exact_runtime_rag_schema(self) -> None:
        trace = build_p6b_rag_trace(
            session_id="session-1",
            turn_id="2",
            trace_id="trace-1",
            rag_runtime_enabled=True,
            rag_index_path="knowledge/indexes/p6_bm25_index.json",
            rag_index_version=P6B_INDEX_VERSION,
            chunk_schema_version="kb.chunk.v0",
            source_manifest_version="kb.source_manifest.v0",
            evidence=[
                _evidence("synthetic_p6_policy_001", "chunk-b"),
                _evidence("synthetic_p6_policy_001", "chunk-a"),
            ],
            retrieval_mode=P6B_RETRIEVAL_MODE,
            fallback_used=False,
            fallback_reason=None,
            rag_boundary_pass=True,
            latency_ms=12,
        )

        self.assertEqual(set(trace), set(P6B_RAG_TRACE_FIELDS))
        self.assertEqual(trace["session_id"], "session-1")
        self.assertEqual(trace["turn_id"], "2")
        self.assertEqual(trace["trace_id"], "trace-1")
        self.assertEqual(trace["retrieved_evidence_count"], 2)
        self.assertEqual(trace["retrieved_chunk_ids"], ["chunk-b", "chunk-a"])
        self.assertEqual(trace["retrieved_source_ids"], ["synthetic_p6_policy_001"])
        self.assertFalse(trace["fallback_used"])
        self.assertIsNone(trace["fallback_reason"])
        self.assertTrue(trace["rag_boundary_pass"])
        self.assertTrue(trace_schema_pass([trace]))

    def test_trace_schema_rejects_missing_or_extra_fields(self) -> None:
        trace = {field: None for field in P6B_RAG_TRACE_FIELDS}
        missing = dict(trace)
        missing.pop("latency_ms")
        extra = {**trace, "unexpected": True}

        self.assertFalse(trace_schema_pass([missing]))
        self.assertFalse(trace_schema_pass([extra]))


if __name__ == "__main__":
    unittest.main()
