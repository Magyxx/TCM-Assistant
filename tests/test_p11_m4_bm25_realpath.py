from __future__ import annotations

import unittest
from unittest.mock import patch

from app.config.settings import AppSettings
from app.rag.retriever_router import retrieve_evidence_pack


class P11M4BM25RealpathTests(unittest.TestCase):
    def test_bm25_realpath_returns_evidence_pack(self) -> None:
        pack = retrieve_evidence_pack(
            "stomach discomfort observation guidance",
            top_k=2,
            settings=AppSettings(ENABLE_RAG=True, RAG_BACKEND="bm25_realpath"),
        )

        self.assertEqual(pack.backend, "bm25_realpath")
        self.assertFalse(pack.skipped)
        self.assertTrue(pack.chunks)
        self.assertTrue(pack.chunks[0].source_id)
        self.assertTrue(pack.chunks[0].chunk_id)

    def test_bm25_realpath_failure_degrades_to_skipped_pack(self) -> None:
        def raise_runtime_error(*args, **kwargs):
            raise RuntimeError("forced")

        with patch("app.rag.retriever_router.build_realpath_evidence_pack", raise_runtime_error):
            pack = retrieve_evidence_pack(
                "stomach discomfort",
                top_k=2,
                settings=AppSettings(ENABLE_RAG=True, RAG_BACKEND="bm25_realpath"),
            )

        self.assertTrue(pack.skipped)
        self.assertEqual(pack.chunks, [])
        self.assertTrue(pack.skip_reason.startswith("bm25_realpath_failed:"))


if __name__ == "__main__":
    unittest.main()
