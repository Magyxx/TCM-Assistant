from __future__ import annotations

import unittest

from scripts.verify_p12_service_baseline import verify


class P12ServiceBaselineTests(unittest.TestCase):
    def test_service_baseline_inventory_is_complete(self) -> None:
        payload = verify()

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["fastapi_app_import_path"], "app.api.main:app")
        self.assertTrue(payload["session_lifecycle_exists"])
        self.assertTrue(payload["turn_endpoint_exists"])
        self.assertTrue(payload["report_endpoint_exists"])
        self.assertTrue(payload["eval_endpoint_exists"])
        self.assertTrue(payload["health_endpoint_exists"])
        self.assertTrue(payload["openapi"]["exportable"])
        self.assertTrue(payload["sqlite_exists"])
        self.assertTrue(payload["postgresql_ready_schema_exists"])

    def test_required_routes_are_present(self) -> None:
        payload = verify()
        route_checks = payload["route_checks"]

        for key in ["health", "create_session", "turn", "state", "report_get", "report_post"]:
            self.assertTrue(route_checks[key], key)


if __name__ == "__main__":
    unittest.main()
