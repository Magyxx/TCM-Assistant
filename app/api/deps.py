from __future__ import annotations

from app.storage.sqlite_store import P7SQLiteStore, get_default_store
from app.services.consultation_service import ConsultationService
from app.services.eval_service import EvalService
from app.tools.registry import build_p7_registry

_consultation_service_override: ConsultationService | None = None
_eval_service_override: EvalService | None = None


def get_p7_store() -> P7SQLiteStore:
    return get_default_store()


def get_p7_tools():
    return build_p7_registry()


def get_consultation_service() -> ConsultationService:
    return _consultation_service_override or ConsultationService()


def set_consultation_service_override(service: ConsultationService | None) -> None:
    global _consultation_service_override
    _consultation_service_override = service


def get_eval_service() -> EvalService:
    return _eval_service_override or EvalService()


def set_eval_service_override(service: EvalService | None) -> None:
    global _eval_service_override
    _eval_service_override = service
