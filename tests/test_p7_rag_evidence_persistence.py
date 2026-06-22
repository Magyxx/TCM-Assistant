from __future__ import annotations

import unittest

from app.rag.evidence_schema import (
    P6EvidenceChunk,
    P6EvidencePack,
    evidence_pack_to_storage_records,
    summarize_evidence_persistence,
)


class P7RagEvidencePersistenceTests(unittest.TestCase):
    def test_retrieved_and_used_evidence_are_distinct(self) -> None:
        pack = P6EvidencePack(
            query="query",
            evidence=[
                P6EvidenceChunk(
                    source_id="source",
                    chunk_id="chunk-1",
                    title="title",
                    content="content",
                    score=1,
                    retrieval_mode="p6b_runtime_bm25",
                    index_version="kb.index.v0",
                    chunk_hash="sha256:" + "a" * 64,
                    source_rights_status="internal_owned",
                    source_safety_status="reviewed",
                    source_provenance_status="reviewed",
                )
            ],
            source_manifest_version="kb.source_registry.v1",
            index_path="knowledge/indexes/p6_bm25_index.json",
            chunks_path="knowledge/processed/p6_chunks.jsonl",
            source_manifest_path="knowledge/sources/source_registry.json",
        )
        records = evidence_pack_to_storage_records(
            pack,
            session_id="s1",
            turn_id="t1",
            used_chunk_ids={"chunk-1"},
            used_in_report_section="report.metadata",
        )
        summary = summarize_evidence_persistence(records)

        self.assertEqual(len(records), 1)
        self.assertTrue(records[0].is_used)
        self.assertTrue(summary.rag_evidence_persistence_pass)


if __name__ == "__main__":
    unittest.main()
