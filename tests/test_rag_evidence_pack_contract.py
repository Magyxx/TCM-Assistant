from __future__ import annotations

import unittest

from app.config.settings import AppSettings
from app.rag.evidence import CORE_STATE_FIELDS, EvidencePack, assert_no_core_field_overwrite
from app.rag.retriever_router import retrieve_evidence_pack
from app.tools.rag_search_tool import invoke


class P1F0RagEvidencePackContractTests(unittest.TestCase):
    def test_pack_dump_validate_and_no_core_overwrite(self) -> None:
        pack = retrieve_evidence_pack("胃胀", settings=AppSettings(ENABLE_RAG=True, RAG_BACKEND="bm25_stub"))
        payload = pack.model_dump()
        self.assertIsInstance(EvidencePack.model_validate(payload), EvidencePack)
        self.assertTrue(assert_no_core_field_overwrite(payload))
        self.assertFalse(CORE_STATE_FIELDS.intersection(payload.keys()))

    def test_tool_returns_evidence_pack_and_disabled_skips(self) -> None:
        result = invoke({"query": "胃胀", "top_k": 2})
        self.assertIn("evidence_pack", result)
        disabled = invoke({"query": "胃胀", "enable_rag": False})
        self.assertTrue(disabled["evidence_pack"]["skipped"])
        self.assertEqual(disabled["evidence_pack"]["skip_reason"], "rag_disabled_by_config")


if __name__ == "__main__":
    unittest.main()
