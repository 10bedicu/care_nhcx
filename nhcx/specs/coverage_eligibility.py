from datetime import datetime
from enum import Enum

from django.shortcuts import get_object_or_404
from pydantic import UUID4, BaseModel, Field, field_validator, model_validator
from rest_framework.exceptions import ValidationError

from care.emr.models.charge_item import ChargeItem
from care.emr.models.condition import Condition
from care.emr.models.encounter import Encounter
from care.emr.models.file_upload import FileUpload
from care.emr.models.patient import Patient
from care.emr.models.scheduling.booking import TokenBooking
from care.emr.resources.base import EMRResource, PeriodSpec
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
    NHCX_COVERAGE_ELIGIBILITY_REQUEST_ITEM_DIAGNOSIS_CODE_VALUESET,
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
    sequence: int
    supporting_info_sequence: list[int] = []
    category: dict | None = None
    product_or_service: dict | None = None
    modifier: list[dict] = []
    charge_items: list[UUID4] = []
    quantity: Quantity | None = None
    unit_price: float | None = None  # in INR
    diagnosis: list[CoverageEligibilityRequestItemDiagnosisSpec] = []

    @field_validator("charge_items")
    @classmethod
    def validate_charge_items(cls, value):
        for uuid in value:
            if not ChargeItem.objects.filter(external_id=uuid).exists():
                msg = f"Charge item {uuid} not found"
                raise ValidationError(msg)
        return value


class CoverageEligibilityRequestBaseSpec(EMRResource):
    __model__ = CoverageEligibilityRequest
    __exclude__ = ["patient", "facility", "encounter", "appointment"]
    id: UUID4 = None

    created_date: datetime | None = None
    modified_date: datetime | None = None


class CoverageEligibilityRequestCreateSpec(CoverageEligibilityRequestBaseSpec):
    status: CoverageEligibilityRequestStatusChoices
    priority: CoverageEligibilityRequestPriorityChoices
    purpose: list[CoverageEligibilityRequestPurposeChoices] = Field([], min_length=1)
    facility: UUID4
    patient: UUID4
    encounter: UUID4 | None = None
    appointment: UUID4 | None = None
    supporting_info: list[CoverageEligibilityRequestSupportingInfoSpec] = []
    insurance: list[CoverageEligibilityRequestInsuranceSpec] = Field([], min_length=1)
    item: list[CoverageEligibilityRequestItemSpec] = []

    @field_validator("encounter")
    @classmethod
    def validate_encounter(cls, value):
        if value and not Encounter.objects.filter(external_id=value).exists():
            raise ValidationError("Encounter not found")
        return value

    @field_validator("appointment")
    @classmethod
    def validate_appointment(cls, value):
        if value and not TokenBooking.objects.filter(external_id=value).exists():
            raise ValidationError("Appointment not found")
        return value

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

    @model_validator(mode="after")
    def validate_sequences(self):
        def _check_unique(items, field, label):
            seqs = [getattr(i, field) for i in items]
            if len(seqs) != len(set(seqs)):
                msg = f"Duplicate sequences in {label}"
                raise ValidationError(msg)

        _check_unique(self.supporting_info, "sequence", "supporting_info")
        _check_unique(self.item, "sequence", "item")

        valid_info_seqs = {s.sequence for s in self.supporting_info}
        for item in self.item:
            invalid = set(item.supporting_info_sequence) - valid_info_seqs
            if invalid:
                msg = f"item.supporting_info_sequence references unknown supporting_info sequences: {sorted(invalid)}"
                raise ValidationError(msg)

        all_charge_item_uuids = [
            str(uuid) for item in self.item for uuid in item.charge_items
        ]
        if len(all_charge_item_uuids) != len(set(all_charge_item_uuids)):
            raise ValidationError(
                "The same charge item cannot be linked to multiple items"
            )

        return self

    def perform_extra_deserialization(self, is_update, obj):
        if self.encounter:
            obj.encounter = get_object_or_404(Encounter, external_id=self.encounter)

        if self.appointment:
            obj.appointment = get_object_or_404(
                TokenBooking, external_id=self.appointment
            )

        obj.patient = get_object_or_404(Patient, external_id=self.patient)
        obj.provider = get_object_or_404(Provider, facility__external_id=self.facility)

        try:
            insurer = ParticipantService.search_participant(
                data=SearchParticipantBody(
                    participant_code="1518@hcx"  # TODO: REPLACE_AFTER_TESTING: replace this with self.insurance[0].policy.payerid after testing
                )
            )
            obj.insurer = insurer.model_dump(mode="json")
        except NHCXAPIException as e:
            raise ValidationError(e.detail) from e


class MoneySpec(BaseModel):
    value: float
    currency: str = "INR"


class BalanceSpec(BaseModel):
    allowed: MoneySpec
    used: MoneySpec


class RequiredDocumentSpec(BaseModel):
    code: str
    display: str


class RequiredQuestionnaireSpec(BaseModel):
    id: str
    display: str
    url: str


class InsuranceEntryItemSpec(BaseModel):
    code: str
    display: str | None = None
    category: dict | None = None
    excluded: bool = False
    allowed_amount: MoneySpec | None = None
    authorization_required: bool = False
    required_documents: list[RequiredDocumentSpec] = []
    required_questionnaires: list[RequiredQuestionnaireSpec] = []


class InsuranceEntrySpec(BaseModel):
    pmjay_id: str
    is_primary: bool = False

    name: str | None = None
    dob: str | None = None
    gender: str | None = None
    abha_id: str | None = None

    inforce: bool = False
    plan_name: str | None = None
    plan_id: str | None = None
    policy_period: PeriodSpec | None = None

    balance: BalanceSpec | None = None
    items: list[InsuranceEntryItemSpec] = []


class CoverageEligibilityResponseRetrieveSpec(EMRResource):
    __model__ = CoverageEligibilityResponse
    __exclude__ = ["request", "insurance"]

    outcome: str
    disposition: str | None = None
    insurances: list[InsuranceEntrySpec] | None = None
    error: dict | None = None
    request: UUID4

    created_date: datetime
    modified_date: datetime

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["request"] = obj.request.external_id
        mapping["insurances"] = obj.insurance


class CoverageEligibilityRequestListSpec(CoverageEligibilityRequestBaseSpec):
    status: str
    priority: str
    purpose: list[str]
    insurer: dict
    supporting_info: list[dict]
    insurance: list[dict]
    item: list[dict]

    dispatched_at: datetime | None = None
    dispatch_error: str = ""
    dispatch_status: str = "pending"

    provider: UUID4
    patient: UUID4
    encounter: UUID4 | None = None
    appointment: UUID4 | None = None
    latest_response: dict | None = None
    created_by: dict | None = None
    updated_by: dict | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["provider"] = obj.provider.external_id
        mapping["patient"] = obj.patient.external_id
        mapping["encounter"] = obj.encounter.external_id if obj.encounter else None
        mapping["appointment"] = (
            obj.appointment.external_id if obj.appointment else None
        )

        latest_response = (
            CoverageEligibilityResponse.objects.filter(
                request__external_id=obj.external_id
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


class CoverageEligibilityRequestLinkEncounterSpec(BaseModel):
    encounter: UUID4


class CoverageEligibilityRequestRetrieveSpec(CoverageEligibilityRequestListSpec):
    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        super().perform_extra_serialization(mapping, obj)

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
                parsed_item = {**item}
                if item.get("charge_items"):
                    parsed_item["charge_items"] = [
                        ChargeItemReadSpec.serialize(
                            get_object_or_404(ChargeItem, external_id=uuid)
                        ).to_json()
                        for uuid in item.get("charge_items")
                    ]

                if item.get("diagnosis"):
                    parsed_item["diagnosis"] = []
                    for diagnosis in item.get("diagnosis"):
                        parsed_diagnosis = {**diagnosis}
                        if diagnosis.get("diagnosis_reference"):
                            condition = get_object_or_404(
                                Condition,
                                external_id=diagnosis.get("diagnosis_reference"),
                            )
                            parsed_diagnosis["diagnosis_reference"] = (
                                ConditionReadSpec.serialize(condition).to_json()
                            )
                        parsed_item["diagnosis"].append(parsed_diagnosis)

                mapping["item"].append(parsed_item)
