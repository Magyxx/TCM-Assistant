from __future__ import annotations

import json
import unittest

from app.extractors.local_lora_extractor import extract_with_local_lora
from app.rules.risk_rules import apply_risk_evaluation_to_state, evaluate_risk_rules
from app.schemas.report_schemas import RunState


class _Message:
    def __init__(self, content: str) -> None:
        self.content = content


class _Choice:
    def __init__(self, content: str) -> None:
        self.message = _Message(content)


class _Completion:
    def __init__(self, content: str) -> None:
        self.choices = [_Choice(content)]


class _Completions:
    def __init__(self, content: str) -> None:
        self.content = content

    def create(self, **kwargs):
        return _Completion(self.content)


class _Chat:
    def __init__(self, content: str) -> None:
        self.completions = _Completions(content)


class _Client:
    def __init__(self, content: str) -> None:
        self.chat = _Chat(content)


class LocalLoraSchemaGuardTests(unittest.TestCase):
    def test_schema_failure_does_not_mutate_runstate(self) -> None:
        state = RunState(
            chief_complaint="existing complaint",
            risk_flags_status="present",
            risk_flags=["existing red flag"],
        )
        before = state.model_dump()
        invalid_schema_json = json.dumps(
            {
                "chief_complaint": "new complaint",
                "symptoms": "not a list",
                "symptoms_status": "present",
                "risk_flags": [],
                "risk_flags_status": "unknown",
            }
        )

        result = extract_with_local_lora(state, "new complaint", client=_Client(invalid_schema_json))

        self.assertFalse(result.success)
        self.assertTrue(result.json_valid)
        self.assertFalse(result.schema_valid)
        self.assertIsNone(result.turn_output)
        self.assertEqual(state.model_dump(), before)

    def test_local_lora_model_risk_claim_does_not_own_final_risk_status(self) -> None:
        model_claim = json.dumps(
            {
                "chief_complaint": "stomach discomfort",
                "duration": None,
                "symptoms": [],
                "symptoms_status": "unknown",
                "risk_flags": ["model-only red flag"],
                "risk_flags_status": "present",
                "summary": "Model claimed risk, but deterministic rules must own final risk.",
            }
        )

        result = extract_with_local_lora(
            RunState(),
            "stomach discomfort after dinner",
            client=_Client(model_claim),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.turn_output.risk_flags_status, "unknown")
        self.assertEqual(result.turn_output.risk_flags, [])

        evaluation = evaluate_risk_rules("stomach discomfort after dinner")
        checked = apply_risk_evaluation_to_state(RunState(), evaluation)
        self.assertNotEqual(checked.risk_flags_status, "present")
        self.assertEqual(checked.risk_flags, [])


if __name__ == "__main__":
    unittest.main()
