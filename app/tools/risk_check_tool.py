from __future__ import annotations

from typing import Any, Dict

from app.rules.risk_rules import evaluate_risk_rules


def invoke(payload: Dict[str, Any]) -> Dict[str, Any]:
    evaluation = evaluate_risk_rules(
        str(payload.get("user_input") or ""),
        previous_status=str(payload.get("previous_status") or "unknown"),
    )
    return {
        "risk_status": evaluation.risk_status,
        "risk_flags": evaluation.risk_flags,
        "risk_rule_ids": evaluation.triggered_rule_ids,
        "risk_reasons": evaluation.risk_reasons,
        "negated_rule_ids": evaluation.negated_rule_ids,
    }
