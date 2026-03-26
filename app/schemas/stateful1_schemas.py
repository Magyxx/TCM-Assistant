from pydantic import BaseModel, Field
from typing import List, Optional, Literal

# 三态：未确认 / 无 / 有
TriState = Literal["unknown", "none", "present"]


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

    # 风险字段
    risk_flags: List[str] = Field(default_factory=list)
    risk_flags_status: TriState = "unknown"

    # 输出控制
    next_question: Optional[str] = None
    summary: Optional[str] = None

    # 调试计数
    turn_count: int = 0


class TurnOutput(BaseModel):
    # 本轮提取结果，和累计状态分开
    chief_complaint: Optional[str] = None
    duration: Optional[str] = None

    symptoms: List[str] = Field(default_factory=list)
    symptoms_status: TriState = "unknown"

    sleep: Optional[str] = None
    appetite: Optional[str] = None
    stool_urine: Optional[str] = None

    risk_flags: List[str] = Field(default_factory=list)
    risk_flags_status: TriState = "unknown"

    next_question: Optional[str] = None
    summary: Optional[str] = None