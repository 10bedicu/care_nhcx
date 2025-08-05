from datetime import datetime

from pydantic import UUID4

from care.emr.resources.base import EMRResource
from nhcx.models.payment import PaymentReconciliation


class PaymentReconciliationRetrieveSpec(EMRResource):
    __model__ = PaymentReconciliation
    __exclude__ = ["request", "claim"]

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

    created_date: datetime | None = None
    modified_date: datetime | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["request"] = obj.request.external_id
        mapping["claim"] = obj.claim.external_id
