from __future__ import annotations

import unittest

from app.rag.evidence_pack import build_evidence_pack


class P11M4EvidenceMetadataTests(unittest.TestCase):
    def test_evidence_chunks_have_source_metadata(self) -> None:
        pack = build_evidence_pack("stomach discomfort observation guidance", top_k=2)

        self.assertTrue(pack.chunks)
        for chunk in pack.chunks:
            self.assertTrue(chunk.source_id)
            self.assertTrue(chunk.title)
            self.assertTrue(chunk.source_type)
            self.assertTrue(chunk.trust_level)
            self.assertIn("source_path", chunk.metadata)
            self.assertIn("retriever_type", chunk.metadata)


if __name__ == "__main__":
    unittest.main()
