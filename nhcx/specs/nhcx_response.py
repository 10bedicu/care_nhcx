from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel


class ProtocolStatusChoices(str, Enum):
    REQUEST_QUEUED = "request.queued"
    REQUEST_DISPATCHED = "request.dispatched"
    REQUEST_ERROR = "request.error"


class EntityTypeChoices(str, Enum):
    COVERAGE_ELIGIBILITY = "coverageeligibility"
    PREAUTH = "preauth"
    CLAIM = "claim"
    TASK = "task"
    PAYMENT = "payment"
    INSURANCE_PLAN = "insuranceplan"


class NHCXError(BaseModel):
    code: str = ""
    message: str = ""


class NHCXResult(BaseModel):
    sender_code: str
    recipient_code: str
    entity_type: EntityTypeChoices | None = None
    protocol_status: ProtocolStatusChoices


class NHCXResponse(BaseModel):
    timestamp: str
    api_call_id: str
    correlation_id: str
    result: NHCXResult | None = None
    error: NHCXError | None = None

    @classmethod
    def create_success_response(
        cls,
        api_call_id: str,
        correlation_id: str,
        sender_code: str,
        recipient_code: str,
        entity_type: EntityTypeChoices | None = None,
        protocol_status: ProtocolStatusChoices = ProtocolStatusChoices.REQUEST_QUEUED,
    ) -> "NHCXResponse":
        return cls(
            timestamp=datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S:%f")[:-3],
            api_call_id=api_call_id,
            correlation_id=correlation_id,
            result=NHCXResult(
                sender_code=sender_code,
                recipient_code=recipient_code,
                entity_type=entity_type,
                protocol_status=protocol_status,
            ),
            error=None,
        )

    @classmethod
    def create_error_response(
        cls,
        api_call_id: str,
        correlation_id: str,
        error_code: str,
        error_message: str,
    ) -> "NHCXResponse":
        return cls(
            timestamp=datetime.now(UTC).strftime("%d/%m/%Y %H:%M:%S:%f")[:-3],
            api_call_id=api_call_id,
            correlation_id=correlation_id,
            result=None,
            error=NHCXError(
                code=error_code,
                message=error_message,
            ),
        )
