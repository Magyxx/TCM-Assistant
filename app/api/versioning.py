from __future__ import annotations

from typing import Final


SERVICE_NAME: Final[str] = "TCM-Assistant"
API_VERSION: Final[str] = "v1"
API_CONTRACT_STATUS: Final[str] = "frozen"
API_STAGE: Final[str] = "P3.4"
API_VERSION_HEADER: Final[str] = "X-API-Version"
VERSION_ENDPOINT_SUPPORTED: Final[bool] = True
VERSIONED_ALIAS_SUPPORTED: Final[bool] = False


def version_info() -> dict[str, str]:
    return {
        "service": SERVICE_NAME,
        "api_version": API_VERSION,
        "stage": API_STAGE,
        "contract_status": API_CONTRACT_STATUS,
    }
