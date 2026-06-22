from __future__ import annotations

import unittest

from app.memory.privacy import assert_l4_safe, contains_pii


class P7MemoryPrivacyTests(unittest.TestCase):
    def test_l4_rejects_pii_and_raw_patient_text_flags(self) -> None:
        self.assertTrue(contains_pii("phone 13800138000"))
        self.assertFalse(assert_l4_safe([{"contains_raw_patient_text": True}]))
        self.assertTrue(assert_l4_safe([{"item_id": "knowledge", "contains_pii": False}]))


if __name__ == "__main__":
    unittest.main()
