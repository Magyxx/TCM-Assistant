from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Literal

# 三态：未确认 / 无 / 有
TriState = Literal["unknown", "none", "present"]
RiskStatus = TriState

# 问诊完成后的分级
TriageLevel = Literal["observe", "followup", "urgent_visit"]

SAFETY_DISCLAIMER = (
    "本系统仅用于问诊信息整理和风险提示，不构成诊断或治疗建议，不能替代医生判断。"
    "如出现持续高热、胸痛、呼吸困难、便血、呕血、意识异常、剧烈腹痛等高风险信号，应及时线下就医。"
)


class FinalReport(BaseModel):
    # 问诊完成后的结构化输出
    summary: str
    impression: str
    advice: List[str] = Field(default_factory=list)
    triage_level: TriageLevel
    info_complete: bool
    missing_core_fields: List[str] = Field(default_factory=list)
    followup_needed: bool
    safety_disclaimer: str = SAFETY_DISCLAIMER
    evidence_citations: List[Dict[str, Any]] = Field(default_factory=list)
    evidence_ids: List[str] = Field(default_factory=list)
    citation_coverage: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class RunState(BaseModel):
    # 核心字段
    chief_complaint: Optional[str] = None
    duration: Optional[str] = None

    # 伴随症状
    symptoms: List[str] = Field(default_factory=list)
    symptoms_status: TriState = "unknown"

    # 其他非核心字段
    sleep: Optional[str] = None
    appetite: Optional[str] = None
    stool_urine: Optional[str] = None
    stool: Optional[str] = None
    urination: Optional[str] = None

    # 风险字段
    risk_flags: List[str] = Field(default_factory=list)
    risk_flags_status: TriState = "unknown"
    risk_reasons: List[str] = Field(default_factory=list)
    triggered_rule_ids: List[str] = Field(default_factory=list)

    # 本轮/最终输出
    next_question: Optional[str] = None
    summary: Optional[str] = None
    final_report: Optional[FinalReport] = None

    # 调试计数
    turn_count: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TurnOutput(BaseModel):
    # 本轮提取结果，和累计状态分开
    chief_complaint: Optional[str] = None
    duration: Optional[str] = None

    symptoms: List[str] = Field(default_factory=list)
    symptoms_status: TriState = "unknown"

    sleep: Optional[str] = None
    appetite: Optional[str] = None
    stool_urine: Optional[str] = None
    stool: Optional[str] = None
    urination: Optional[str] = None

    risk_flags: List[str] = Field(default_factory=list)
    risk_flags_status: TriState = "unknown"

    next_question: Optional[str] = None
    summary: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
