from datetime import datetime

from pydantic import UUID4, BaseModel

from care.emr.resources.base import EMRResource
from nhcx.models.insurance_plan import InsurancePlan
from nhcx.models.task import Task, TaskUseCaseChoices
from nhcx.services.types.participant import Policy


class InsurancePlanRequestBody(BaseModel):
    policy: Policy
    facility: str


class InsurancePlanBaseSpec(EMRResource):
    __model__ = InsurancePlan
    __exclude__ = ["request"]

    id: UUID4 | None = None

    created_date: datetime | None = None
    modified_date: datetime | None = None


class InsurancePlanListSpec(InsurancePlanBaseSpec):
    identifier: str
    text: str | None = None
    extension: list[dict] | None = None
    product_identifier: dict | None = None
    status: str
    type: dict | None = None
    name: str
    alias: list[dict] | None = None
    period: dict | None = None
    contact: list[dict] | None = None
    coverage: list[dict] | None = None
    plan: list[dict] | None = None
    request: UUID4

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["request"] = obj.request.external_id


class InsurancePlanRetrieveSpec(InsurancePlanListSpec):
    latest_request: UUID4 | None = None
    latest_request_date: datetime | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        super().perform_extra_serialization(mapping, obj)

        identifier = obj.request.identifier
        latest_request = Task.objects.filter(
            identifier=identifier, use_case=TaskUseCaseChoices.INSURANCE_PLAN_REQUEST
        ).last()
        if latest_request:
            mapping["latest_request"] = latest_request.external_id
            mapping["latest_request_date"] = latest_request.created_date
