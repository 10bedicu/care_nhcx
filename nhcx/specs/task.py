from datetime import datetime

from pydantic import UUID4

from care.emr.resources.base import EMRResource
from care.emr.resources.user.spec import UserSpec
from nhcx.models.communication import Communication, CommunicationRequest
from nhcx.models.insurance_plan import InsurancePlan
from nhcx.models.payment import PaymentReconciliation
from nhcx.models.task import Task
from nhcx.specs.communication import (
    CommunicationRequestRetrieveSpec,
    CommunicationRetrieveSpec,
)
from nhcx.specs.insurance_plan import InsurancePlanRetrieveSpec
from nhcx.specs.payment import PaymentReconciliationRetrieveSpec


class TaskBaseSpec(EMRResource):
    __model__ = Task
    __exclude__ = ["part_of", "claim", "focus"]

    id: UUID4 | None = None

    created_date: datetime | None = None
    modified_date: datetime | None = None


class TaskListSpec(TaskBaseSpec):
    identifier: str | None = None
    status: str
    intent: str
    priority: str | None = None
    code: dict | None = None
    authored_on: datetime | None = None
    description: str | None = None
    reason_code: dict | None = None
    input: list[dict] | None = None
    output: list[dict] | None = None
    use_case: str
    claim: UUID4 | None = None
    part_of: UUID4 | None = None
    focus: UUID4 | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["claim"] = obj.claim.external_id if obj.claim else None
        mapping["part_of"] = obj.part_of.external_id if obj.part_of else None

        if obj.created_by:
            mapping["created_by"] = UserSpec.serialize(obj.created_by).to_json()
        if obj.updated_by:
            mapping["updated_by"] = UserSpec.serialize(obj.updated_by).to_json()

        if obj.focus:
            if isinstance(obj.focus, Communication):
                mapping["focus"] = CommunicationRetrieveSpec.serialize(
                    obj.focus
                ).to_json()
            if isinstance(obj.focus, CommunicationRequest):
                mapping["focus"] = CommunicationRequestRetrieveSpec.serialize(
                    obj.focus
                ).to_json()
            if isinstance(obj.focus, PaymentReconciliation):
                mapping["focus"] = PaymentReconciliationRetrieveSpec.serialize(
                    obj.focus
                ).to_json()
            if isinstance(obj.focus, InsurancePlan):
                mapping["focus"] = InsurancePlanRetrieveSpec.serialize(
                    obj.focus
                ).to_json()


class TaskRetrieveSpec(TaskListSpec):
    pass
