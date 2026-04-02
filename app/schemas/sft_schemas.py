from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field

try:
    # 优先复用现有项目中的三态定义，避免训练数据与主流程脱节
    from app.schemas.report_schemas import TriState  # type: ignore
except Exception:
    TriState = Literal["unknown", "none", "present"]


SFTTaskType = Literal["report_turn_extraction"]
DifficultyLevel = Literal["easy", "medium", "hard"]
DataSourceType = Literal["manual", "test_case", "dialog_log", "augmented"]


class SFTSampleInput(BaseModel):
    """单轮抽取任务的输入。"""

    state_json: Dict[str, Any] = Field(
        ..., description="问诊前累计状态，直接对应当前项目中的 RunState 序列化结果"
    )
    user_input: str = Field(..., min_length=1, description="当前轮用户输入")


class SFTSampleOutput(BaseModel):
    """单轮抽取任务的标准输出。尽量与 TurnOutput 对齐。"""

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
    summary: str = ""


class SFTSampleMeta(BaseModel):
    """便于后续按来源、难度、错误类型进行筛选和回归。"""

    source: DataSourceType = "manual"
    difficulty: DifficultyLevel = "medium"
    tags: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class SFTSample(BaseModel):
    task: SFTTaskType = "report_turn_extraction"
    id: str = Field(..., min_length=1)
    system_prompt: str = Field(..., min_length=1)
    input: SFTSampleInput
    output: SFTSampleOutput
    meta: SFTSampleMeta = Field(default_factory=SFTSampleMeta)


class SFTMessagesSample(BaseModel):
    """转换给聊天微调框架使用的 messages 格式。"""

    id: str
    task: SFTTaskType = "report_turn_extraction"
    messages: List[Dict[str, str]]
    meta: SFTSampleMeta = Field(default_factory=SFTSampleMeta)
