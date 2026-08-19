from datetime import datetime

from pydantic import UUID4

from care.emr.resources.base import EMRResource
from nhcx.models.claim_consent import ClaimConsent


class ClaimConsentRetrieveSpec(EMRResource):
    __model__ = ClaimConsent
    __exclude__ = ["encounter", "patient", "claim", "account"]

    id: UUID4 | None = None
    created_date: datetime | None = None
    modified_date: datetime | None = None
    stage: str
    payer_id: str
    claim: UUID4 | None = None
    encounter: UUID4 | None = None
    patient: UUID4 | None = None
    account: UUID4 | None = None
    cycle: int | None = None
    expires_in: int
    refresh_expires_in: int
    accounts: list[dict] = []

    @classmethod
    def perform_extra_serialization(cls, mapping, obj, *args, **kwargs):
        super().perform_extra_serialization(mapping, obj, *args, **kwargs)
        mapping["encounter"] = obj.encounter.external_id
        mapping["patient"] = obj.patient.external_id
        mapping["claim"] = obj.claim.external_id if obj.claim else None
        mapping["account"] = obj.account.external_id if obj.account else None
