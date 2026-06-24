from __future__ import annotations

import unittest

from app.rag.evidence_pack import build_evidence_pack
from app.rag.models import EvidenceChunk, EvidencePack


class RagEvidencePackTests(unittest.TestCase):
    def test_evidence_chunk_and_pack_schema_validate(self) -> None:
        chunk = EvidenceChunk(
            chunk_id="c1",
            source_id="source",
            title="title",
            content="general observation guidance",
            score=1.0,
        )
        pack = EvidencePack(
            query="胃胀",
            normalized_query="胃胀",
            chunks=[chunk],
            top_k=1,
        )

        self.assertEqual(pack.result_count, 1)
        self.assertEqual(pack.retrieval_mode, "bm25")
        self.assertEqual(pack.guard_status, "passed")

    def test_build_evidence_pack_uses_bm25_realpath(self) -> None:
        pack = build_evidence_pack("胃胀", top_k=2)

        self.assertTrue(pack.chunks)
        self.assertEqual(pack.retrieval_mode, "bm25")
        self.assertTrue(pack.chunks[0].source_id)
        self.assertTrue(pack.chunks[0].chunk_id)
        self.assertIsInstance(pack.chunks[0].score, float)


if __name__ == "__main__":
    unittest.main()
