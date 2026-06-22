from __future__ import annotations

from pydantic import BaseModel, Field


class ExperienceMemory(BaseModel):
    case_type: str
    input_pattern: str
    failure_type: str
    fix: str
    source: str = "eval_failure_case"
    contains_pii: bool = False
    authority_level: str = "L4_experience_advisory"
    can_override_structured_facts: bool = False
    metadata: dict[str, object] = Field(default_factory=dict)

