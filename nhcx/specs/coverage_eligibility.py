from datetime import datetime
from enum import Enum

from django.shortcuts import get_object_or_404
from pydantic import UUID4, BaseModel, field_validator, model_validator
from rest_framework.exceptions import ValidationError

from care.emr.models.charge_item import ChargeItem
from care.emr.models.condition import Condition
from care.emr.models.file_upload import FileUpload
from care.emr.models.patient import Patient
from care.emr.resources.base import EMRResource
from care.emr.resources.charge_item.spec import ChargeItemReadSpec
from care.emr.resources.common.quantity import Quantity
from care.emr.resources.condition.spec import ConditionReadSpec
from care.emr.resources.file_upload.spec import FileUploadRetrieveSpec
from care.emr.resources.user.spec import UserSpec
from care.emr.utils.valueset_coding_type import ValueSetBoundCoding
from nhcx.models.coverage_eligibility import (
    CoverageEligibilityRequest,
    CoverageEligibilityResponse,
)
from nhcx.models.provider import Provider
from nhcx.services.participant import ParticipantService
from nhcx.services.types.participant import Policy, SearchParticipantBody
from nhcx.specs.valuesets.coverage_eligibility import (
    NHCX_COVERAGE_ELIGIBILITY_REQUEST_ITEM_CATEGORY_VALUESET,
    NHCX_COVERAGE_ELIGIBILITY_REQUEST_ITEM_DIAGNOSIS_CODE_VALUESET,
    NHCX_COVERAGE_ELIGIBILITY_REQUEST_PRODUCT_OR_SERVICE_VALUESET,
)
from nhcx.utils.exceptions import NHCXAPIException


class CoverageEligibilityRequestStatusChoices(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    DRAFT = "draft"
    ENTERED_IN_ERROR = "entered-in-error"


class CoverageEligibilityRequestPriorityChoices(str, Enum):
    STAT = "stat"
    NORMAL = "normal"
    DEFERRED = "deferred"


class CoverageEligibilityRequestPurposeChoices(str, Enum):
    AUTH_REQUIREMENTS = "auth-requirements"
    BENEFITS = "benefits"
    DISCOVERY = "discovery"
    VALIDATION = "validation"


class CoverageEligibilityRequestSupportingInfoSpec(BaseModel):
    sequence: int
    value_string: str | None = None
    value_attachment: UUID4 | None = None

    @field_validator("value_attachment")
    @classmethod
    def validate_value_attachment(cls, value):
        if value and not FileUpload.objects.filter(external_id=value).exists():
            raise ValidationError("File upload not found")
        return value

    @model_validator(mode="after")
    def validate_value_string_or_attachment(self):
        if self.value_string is None and self.value_attachment is None:
            raise ValidationError(
                "Either value_string or value_attachment must be present"
            )
        if self.value_string is not None and self.value_attachment is not None:
            raise ValidationError(
                "Only one of value_string or value_attachment must be present"
            )
        return self


class CoverageEligibilityRequestInsuranceSpec(BaseModel):
    focal: bool
    policy: Policy


class CoverageEligibilityRequestItemDiagnosisSpec(BaseModel):
    diagnosis_reference: UUID4 | None = None
    diagnosis_code: (
        ValueSetBoundCoding[
            NHCX_COVERAGE_ELIGIBILITY_REQUEST_ITEM_DIAGNOSIS_CODE_VALUESET.slug
        ]
        | None
    ) = None

    @field_validator("diagnosis_reference")
    @classmethod
    def validate_diagnosis_reference(cls, value):
        if value and not Condition.objects.filter(external_id=value).exists():
            raise ValidationError("Condition not found")
        return value

    @model_validator(mode="after")
    def validate_diagnosis_reference_or_code(self):
        if self.diagnosis_reference is not None and self.diagnosis_code is not None:
            raise ValidationError(
                "Only one of diagnosis_reference or diagnosis_code must be present"
            )
        if self.diagnosis_reference is None and self.diagnosis_code is None:
            raise ValidationError(
                "Either diagnosis_reference or diagnosis_code must be present"
            )
        if self.diagnosis_reference is not None:
            condition = get_object_or_404(
                Condition, external_id=self.diagnosis_reference
            )
            self.diagnosis_code = condition.code
        return self


class CoverageEligibilityRequestItemSpec(BaseModel):
    supporting_info_sequence: list[int] = []
    category: ValueSetBoundCoding[
        NHCX_COVERAGE_ELIGIBILITY_REQUEST_ITEM_CATEGORY_VALUESET.slug
    ]
    product_or_service: (
        ValueSetBoundCoding[
            NHCX_COVERAGE_ELIGIBILITY_REQUEST_PRODUCT_OR_SERVICE_VALUESET.slug
        ]
        | None
    ) = None
    charge_item: UUID4 | None = None
    quantity: Quantity | None = None
    unit_price: float | None = None  # in INR
    diagnosis: list[CoverageEligibilityRequestItemDiagnosisSpec] = []

    @field_validator("charge_item")
    @classmethod
    def validate_charge_item(cls, value):
        if value and not ChargeItem.objects.filter(external_id=value).exists():
            raise ValidationError("Charge item not found")
        return value

    @model_validator(mode="after")
    def validate_charge_item_or_product_or_service(self):
        if self.charge_item is None and self.product_or_service is None:
            raise ValidationError(
                "Either charge_item or product_or_service must be present"
            )
        if self.charge_item is not None and self.product_or_service is not None:
            raise ValidationError(
                "Only one of charge_item or product_or_service must be present"
            )
        if self.charge_item is not None:
            charge_item = get_object_or_404(ChargeItem, external_id=self.charge_item)
            if charge_item.code is None:
                raise ValidationError("Charge item code is required")
            self.product_or_service = charge_item.code
            self.quantity = {
                "value": charge_item.quantity,
            }
            for component in charge_item.unit_price_components:
                if component.amount:
                    self.unit_price += component.amount
        return self


class CoverageEligibilityRequestBaseSpec(EMRResource):
    __model__ = CoverageEligibilityRequest
    __exclude__ = ["patient", "facility"]
    id: UUID4 = None

    created_date: datetime | None = None
    modified_date: datetime | None = None


class CoverageEligibilityRequestCreateSpec(CoverageEligibilityRequestBaseSpec):
    status: CoverageEligibilityRequestStatusChoices
    priority: CoverageEligibilityRequestPriorityChoices
    purpose: list[CoverageEligibilityRequestPurposeChoices]
    facility: UUID4
    patient: UUID4
    supporting_info: list[CoverageEligibilityRequestSupportingInfoSpec]
    insurance: list[CoverageEligibilityRequestInsuranceSpec]
    item: list[CoverageEligibilityRequestItemSpec]

    @field_validator("patient")
    @classmethod
    def validate_patient(cls, value):
        patient = Patient.objects.filter(external_id=value).first()
        if not patient:
            raise ValidationError("Patient not found")
        if not hasattr(patient, "abha_number"):
            raise ValidationError("Patient abha number is required")
        return value

    @field_validator("facility")
    @classmethod
    def validate_facility(cls, value):
        if not Provider.objects.filter(facility__external_id=value).exists():
            raise ValidationError("Provider not found")
        return value

    def perform_extra_deserialization(self, is_update, obj):
        obj.patient = get_object_or_404(Patient, external_id=self.patient)
        obj.provider = get_object_or_404(Provider, facility__external_id=self.facility)

        try:
            insurer = ParticipantService.search_participant(
                data=SearchParticipantBody(
                    participant_code=self.insurance[0].policy.payerid
                )
            )
            obj.insurer = insurer.model_dump(mode="json")
        except NHCXAPIException as e:
            raise ValidationError(e.detail) from e


class CoverageEligibilityResponseRetrieveSpec(EMRResource):
    __model__ = CoverageEligibilityResponse
    __exclude__ = ["request"]

    outcome: str
    disposition: str | None = None
    insurance: dict | None = None
    error: dict | None = None

    created_date: datetime
    modified_date: datetime


class CoverageEligibilityRequestListSpec(CoverageEligibilityRequestBaseSpec):
    status: str
    priority: str
    purpose: list[str]
    insurer: dict
    supporting_info: list[dict]
    insurance: list[dict]
    item: list[dict]

    provider: UUID4
    patient: UUID4
    latest_response: dict | None = None
    created_by: dict | None = None
    updated_by: dict | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id

        latest_response = (
            CoverageEligibilityResponse.objects.filter(
                request__coverage__external_id=obj.external_id
            )
            .order_by("-created_date")
            .first()
        )
        if latest_response:
            mapping["latest_response"] = (
                CoverageEligibilityResponseRetrieveSpec.serialize(
                    latest_response
                ).to_json()
            )

        if obj.created_by:
            mapping["created_by"] = UserSpec.serialize(obj.created_by).to_json()
        if obj.updated_by:
            mapping["updated_by"] = UserSpec.serialize(obj.updated_by).to_json()


class CoverageEligibilityRequestRetrieveSpec(CoverageEligibilityRequestBaseSpec):
    status: str
    priority: str
    purpose: list[str]
    insurer: dict
    supporting_info: list[dict]
    insurance: list[dict]
    item: list[dict]

    provider: UUID4
    patient: UUID4
    latest_response: dict | None = None
    created_by: dict | None = None
    updated_by: dict | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id

        latest_response = (
            CoverageEligibilityResponse.objects.filter(
                request__coverage__external_id=obj.external_id
            )
            .order_by("-created_date")
            .first()
        )
        if latest_response:
            mapping["latest_response"] = (
                CoverageEligibilityResponseRetrieveSpec.serialize(
                    latest_response
                ).to_json()
            )

        if obj.created_by:
            mapping["created_by"] = UserSpec.serialize(obj.created_by).to_json()
        if obj.updated_by:
            mapping["updated_by"] = UserSpec.serialize(obj.updated_by).to_json()

        if obj.supporting_info:
            mapping["supporting_info"] = []
            for supporting_info in obj.supporting_info:
                parsed = {**supporting_info}
                if supporting_info.get("attachment"):
                    attachment = FileUpload.objects.get(
                        external_id=supporting_info.get("attachment")
                    )
                    parsed["attachment"] = FileUploadRetrieveSpec.serialize(
                        attachment
                    ).to_json()
                mapping["supporting_info"].append(parsed)

        if obj.item:
            mapping["item"] = []
            for item in obj.item:
                parsed = {**item}
                if item.get("charge_item"):
                    charge_item = get_object_or_404(
                        ChargeItem, external_id=item.get("charge_item")
                    )
                    parsed["charge_item"] = ChargeItemReadSpec.serialize(
                        charge_item
                    ).to_json()

                if item.get("diagnosis"):
                    mapping["diagnosis"] = []
                    for diagnosis in item.get("diagnosis"):
                        parsed = {**diagnosis}
                        if diagnosis.get("diagnosis_reference"):
                            condition = get_object_or_404(
                                Condition,
                                external_id=diagnosis.get("diagnosis_reference"),
                            )
                            parsed["diagnosis_reference"] = ConditionReadSpec.serialize(
                                condition
                            ).to_json()
                        mapping["diagnosis"].append(parsed)

                mapping["item"].append(parsed)
