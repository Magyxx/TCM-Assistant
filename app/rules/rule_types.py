from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List, Literal, Optional

from app.schemas.report_schemas import TriState


RiskLevel = Literal["caution", "urgent"]


@dataclass(frozen=True)
class RiskRule:
    rule_id: str
    name: str
    description: str
    trigger_keywords: List[str]
    negation_sensitive: bool
    risk_level: RiskLevel
    reason_template: str
    risk_flag: str
    detector: Optional[Callable[[str], bool]] = None


@dataclass
class RiskRuleMatch:
    rule_id: str
    name: str
    risk_flag: str
    risk_level: RiskLevel
    keyword: str
    reason: str


@dataclass
class RiskEvaluation:
    risk_status: Optional[TriState]
    risk_flags: List[str] = field(default_factory=list)
    triggered_rule_ids: List[str] = field(default_factory=list)
    risk_reasons: List[str] = field(default_factory=list)
    matches: List[RiskRuleMatch] = field(default_factory=list)
    negated_rule_ids: List[str] = field(default_factory=list)

    @property
    def has_risk(self) -> bool:
        return self.risk_status == "present"
