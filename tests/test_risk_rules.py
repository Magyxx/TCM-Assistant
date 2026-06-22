from __future__ import annotations

from app.rules.risk_rules import evaluate_risk_rules


def test_negated_fever_and_chest_pain_do_not_trigger_high_risk() -> None:
    evaluation = evaluate_risk_rules("没有发热，也不胸痛")

    assert evaluation.risk_status == "none"
    assert "P0_RISK_CHEST_PAIN" not in evaluation.triggered_rule_ids
    assert "P0_RISK_CHEST_PAIN" in evaluation.negated_rule_ids
    assert "P0_RISK_HIGH_FEVER" in evaluation.negated_rule_ids


def test_chest_pain_with_dyspnea_triggers_high_risk() -> None:
    evaluation = evaluate_risk_rules("胸痛伴呼吸困难")

    assert evaluation.risk_status == "present"
    assert {"P0_RISK_CHEST_PAIN", "P0_RISK_DYSPNEA"}.issubset(set(evaluation.triggered_rule_ids))
    assert all(match.evidence_text for match in evaluation.matches)
    assert all(match.negated is False for match in evaluation.matches)
