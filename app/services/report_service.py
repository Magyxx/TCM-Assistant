from __future__ import annotations

from typing import Any

from app.schemas.report_schemas import SAFETY_DISCLAIMER
from app.services.consultation_service import ConsultationService


class ReportService:
    def __init__(self, consultation_service: ConsultationService | None = None) -> None:
        self.consultation_service = consultation_service or ConsultationService()

    def get_report(self, session_id: str) -> dict[str, Any]:
        return self.consultation_service.get_report(session_id)

    def safety_disclaimer(self) -> str:
        return SAFETY_DISCLAIMER
