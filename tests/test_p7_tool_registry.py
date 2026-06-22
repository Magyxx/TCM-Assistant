from __future__ import annotations

import unittest

from app.tools.registry import build_p7_registry


class P7ToolRegistryTests(unittest.TestCase):
    def test_definitions_use_p7_permission_schema(self) -> None:
        definitions = build_p7_registry().definitions()

        self.assertEqual(len(definitions), 5)
        self.assertTrue(all(item.permission_level in {"low", "medium", "high"} for item in definitions))
        self.assertTrue(all(isinstance(item.side_effect, bool) for item in definitions))
        self.assertTrue(all(item.version for item in definitions))


if __name__ == "__main__":
    unittest.main()
