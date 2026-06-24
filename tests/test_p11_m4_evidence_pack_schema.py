from __future__ import annotations

import unittest

from app.rag.evidence_pack import build_evidence_pack
from app.rag.models import EvidenceChunk, EvidencePack


class P11M4EvidencePackSchemaTests(unittest.TestCase):
    def test_evidence_pack_schema_has_required_chunk_fields(self) -> None:
        pack = build_evidence_pack("stomach discomfort observation guidance", top_k=2)
        payload = pack.model_dump()
        validated = EvidencePack.model_validate(payload)

        self.assertTrue(validated.chunks)
        self.assertEqual(validated.retrieval_mode, "bm25")
        self.assertEqual(validated.guard_status, "passed")
        for chunk in validated.chunks:
            self.assertIsInstance(chunk, EvidenceChunk)
            self.assertTrue(chunk.chunk_id)
            self.assertTrue(chunk.source_id)
            self.assertTrue(chunk.title)
            self.assertTrue(chunk.content)
            self.assertIsInstance(chunk.score, float)
            self.assertTrue(chunk.source_type)
            self.assertTrue(chunk.trust_level)


if __name__ == "__main__":
    unittest.main()
