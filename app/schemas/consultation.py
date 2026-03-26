from pydantic import BaseModel, Field
from typing import List, Optional

class ConsultationResult(BaseModel):
    chief_complaint: Optional[str] = None
    duration: Optional[str] = None
    symptoms: List[str] = Field(default_factory=list)
    sleep: Optional[str] = None
    appetite: Optional[str] = None
    stool_urine: Optional[str] = None
    risk_flags: List[str] = Field(default_factory=list)
    next_question: Optional[str] = None
    summary: Optional[str] = None
