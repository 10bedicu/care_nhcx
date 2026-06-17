from datetime import datetime

from pydantic import UUID4

from care.emr.resources.base import EMRResource
from care.emr.resources.payment_reconciliation.spec import (
    PaymentReconciliationReadSpec,
)
from nhcx.models.payment import PaymentNotice


class PaymentNoticeRetrieveSpec(EMRResource):
    __model__ = PaymentNotice
    __exclude__ = ["request", "claim", "payment_reconciliation"]

    id: UUID4 | None = None

    identifier: str
    status: str
    period: dict | None
    outcome: str | None
    disposition: str | None
    payment_date: datetime
    payment_amount: float
    payment_identifier: str | None
    detail: list | None
    process_note: list | None
    request: UUID4
    claim: UUID4
    payment_reconciliation: dict | None = None

    created_date: datetime | None = None
    modified_date: datetime | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["request"] = obj.request.external_id
        mapping["claim"] = obj.claim.external_id
        if obj.payment_reconciliation:
            mapping["payment_reconciliation"] = (
                PaymentReconciliationReadSpec.serialize(
                    obj.payment_reconciliation
                ).to_json()
            )
