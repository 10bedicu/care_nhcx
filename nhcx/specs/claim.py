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
from care.emr.resources.base import EMRResource, PeriodSpec
from care.emr.resources.charge_item.spec import ChargeItemReadSpec
from care.emr.resources.common.quantity import Quantity
from care.emr.resources.condition.spec import ConditionReadSpec
from care.emr.resources.encounter.spec import User
from care.emr.resources.file_upload.spec import FileUploadRetrieveSpec
from care.emr.resources.user.spec import UserSpec
from care.emr.utils.valueset_coding_type import ValueSetBoundCoding
from nhcx.models.claim import Claim, ClaimResponse
from nhcx.models.provider import Provider
from nhcx.services.participant import ParticipantService
from nhcx.services.types.participant import Policy, SearchParticipantBody
from nhcx.specs.valuesets.claim import (
    NHCX_CLAIM_ACCIDENT_TYPE_VALUESET,
    NHCX_CLAIM_CARE_TEAM_ROLE_VALUESET,
    NHCX_CLAIM_DIAGNOSIS_CODE_VALUESET,
    NHCX_CLAIM_DIAGNOSIS_TYPE_VALUESET,
    NHCX_CLAIM_ITEM_CATEGORY_VALUESET,
    NHCX_CLAIM_PROCEDURE_CODE_VALUESET,
    NHCX_CLAIM_PROCEDURE_TYPE_VALUESET,
    NHCX_CLAIM_PRODUCT_OR_SERVICE_VALUESET,
    NHCX_CLAIM_PROGRAM_CODE_VALUESET,
    NHCX_CLAIM_RELATED_RELATIONSHIP_VALUESET,
    NHCX_CLAIM_SUPPORTING_INFO_CATEGORY_VALUESET,
    NHCX_CLAIM_SUPPORTING_INFO_CODE_VALUESET,
    NHCX_CLAIM_TYPE_VALUESET,
)
from nhcx.utils.exceptions import NHCXAPIException


class ClaimUseChoices(str, Enum):
    CLAIM = "claim"
    PRE_AUTHORIZATION = "preauthorization"
    PRE_DETERMINATION = "predetermination"


class ClaimStatusChoices(str, Enum):
    ACTIVE = "active"
    CANCELLED = "cancelled"
    DRAFT = "draft"
    ENTERED_IN_ERROR = "entered-in-error"


class ClaimPriorityChoices(str, Enum):
    STAT = "stat"
    NORMAL = "normal"
    DEFERRED = "deferred"


class ClaimDiagnosisOnAdmissionChoices(str, Enum):
    YES = "y"
    NO = "n"
    UNKNOWN = "u"
    UNDETERMINED = "w"


class ClaimCareTeamSpec(BaseModel):
    sequence: int
    provider: UUID4
    responsible: bool | None = None
    role: ValueSetBoundCoding[NHCX_CLAIM_CARE_TEAM_ROLE_VALUESET.slug] | None = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value):
        if not User.objects.filter(external_id=value).exists():
            raise ValidationError("User not found")
        return value


class ClaimDiagnosisSpec(BaseModel):
    sequence: int
    type: list[ValueSetBoundCoding[NHCX_CLAIM_DIAGNOSIS_TYPE_VALUESET.slug]] = Field(
        [], min_length=1
    )
    diagnosis_reference: UUID4 | None = None
    diagnosis_code: (
        ValueSetBoundCoding[NHCX_CLAIM_DIAGNOSIS_CODE_VALUESET.slug] | None
    ) = None
    on_admission: ClaimDiagnosisOnAdmissionChoices | None = None

    @field_validator("diagnosis_reference")
    @classmethod
    def validate_diagnosis_reference(cls, value):
        if value and not Condition.objects.filter(external_id=value).exists():
            raise ValidationError("Condition not found")
        return value

    @model_validator(mode="after")
    def validate_diagnosis_reference_or_code(self):
        if self.diagnosis_reference is None and self.diagnosis_code is None:
            raise ValidationError(
                "Either diagnosis_reference or diagnosis_code must be present"
            )
        if self.diagnosis_reference is not None and self.diagnosis_code is not None:
            raise ValidationError(
                "Only one of diagnosis_reference or diagnosis_code must be present"
            )
        if self.diagnosis_reference is not None:
            condition = get_object_or_404(
                Condition, external_id=self.diagnosis_reference
            )
            self.diagnosis_code = condition.code
        return self


class ClaimProcedureSpec(BaseModel):
    sequence: int
    type: list[ValueSetBoundCoding[NHCX_CLAIM_PROCEDURE_TYPE_VALUESET.slug]] = []
    date: datetime | None = None
    procedure_reference: UUID4 | None = None
    procedure_code: (
        ValueSetBoundCoding[NHCX_CLAIM_PROCEDURE_CODE_VALUESET.slug] | None
    ) = None

    @field_validator("procedure_reference")
    @classmethod
    def validate_procedure_reference(cls, value):
        # if value and not Procedure.objects.filter(external_id=value).exists():
        #     raise ValidationError("Procedure not found")
        return value

    @model_validator(mode="after")
    def validate_procedure_reference_or_code(self):
        if self.procedure_reference is None and self.procedure_code is None:
            raise ValidationError(
                "Either procedure_reference or procedure_code must be present"
            )
        if self.procedure_reference is not None and self.procedure_code is not None:
            raise ValidationError(
                "Only one of procedure_reference or procedure_code must be present"
            )
        if self.procedure_reference is not None:
            # procedure = get_object_or_404(Procedure, external_id=self.procedure_reference)
            # self.procedure_code = procedure.code
            pass
        return self


class ClaimRelatedSpec(BaseModel):
    claim: UUID4
    relationship: (
        ValueSetBoundCoding[NHCX_CLAIM_RELATED_RELATIONSHIP_VALUESET.slug] | None
    ) = None
    reference: str | None = None

    @field_validator("claim")
    @classmethod
    def validate_claim(cls, value):
        if not Claim.objects.filter(external_id=value).exists():
            raise ValidationError("Claim not found")
        return value


class ClaimInsuranceSpec(BaseModel):
    sequence: int
    focal: bool
    policy: Policy


class ClaimSupportingInfoSpec(BaseModel):
    sequence: int
    category: ValueSetBoundCoding[NHCX_CLAIM_SUPPORTING_INFO_CATEGORY_VALUESET.slug]
    code: ValueSetBoundCoding[NHCX_CLAIM_SUPPORTING_INFO_CODE_VALUESET.slug]
    timing: PeriodSpec | None = None
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


class ClaimItemSpec(BaseModel):
    sequence: int
    care_team_sequence: list[int] = []
    diagnosis_sequence: list[int] = []
    procedure_sequence: list[int] = []
    information_sequence: list[int] = []
    category: ValueSetBoundCoding[NHCX_CLAIM_ITEM_CATEGORY_VALUESET.slug] | None = None
    product_or_service: (
        ValueSetBoundCoding[NHCX_CLAIM_PRODUCT_OR_SERVICE_VALUESET.slug] | None
    ) = None
    charge_item: UUID4 | None = None
    program_code: list[ValueSetBoundCoding[NHCX_CLAIM_PROGRAM_CODE_VALUESET.slug]] = []
    serviced_period: PeriodSpec | None = None
    quantity: Quantity | None = None
    unit_price: float | None = None  # in INR
    factor: float | None = None

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


class ClaimAccidentSpec(BaseModel):
    date: datetime
    type: ValueSetBoundCoding[NHCX_CLAIM_ACCIDENT_TYPE_VALUESET.slug] | None = None
    location: str | None = None


class ClaimPayeeSpec(BaseModel):
    # TODO: add this after understanding field requirements
    pass


class ClaimBaseSpec(EMRResource):
    __model__ = Claim
    __exclude__ = ["patient", "provider", "encounter"]
    id: UUID4 | None = None

    created_date: datetime | None = None
    modified_date: datetime | None = None


class ClaimCreateSpec(ClaimBaseSpec):
    use: ClaimUseChoices
    status: ClaimStatusChoices
    priority: ClaimPriorityChoices
    type: ValueSetBoundCoding[NHCX_CLAIM_TYPE_VALUESET.slug]
    facility: UUID4
    patient: UUID4
    encounter: UUID4 | None = None
    billable_period: PeriodSpec | None = None
    related: list[ClaimRelatedSpec] = []
    care_team: list[ClaimCareTeamSpec] = []
    supporting_info: list[ClaimSupportingInfoSpec] = []
    procedure: list[ClaimProcedureSpec] = []
    diagnosis: list[ClaimDiagnosisSpec] = Field([], min_length=1)
    insurance: list[ClaimInsuranceSpec] = Field([], min_length=1)
    item: list[ClaimItemSpec] = Field([], min_length=1)
    accident: ClaimAccidentSpec | None = None
    payee: ClaimPayeeSpec | None = None

    @field_validator("encounter")
    @classmethod
    def validate_encounter(cls, value):
        if value and not Encounter.objects.filter(external_id=value).exists():
            raise ValidationError("Encounter not found")
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

    def perform_extra_deserialization(self, is_update, obj):
        if self.encounter:
            obj.encounter = get_object_or_404(Encounter, external_id=self.encounter)

        obj.patient = get_object_or_404(Patient, external_id=self.patient)
        obj.provider = get_object_or_404(Provider, facility__external_id=self.facility)

        try:
            insurer = ParticipantService.search_participant(
                data=SearchParticipantBody(
                    participant_code="1000003538@hcx"  # TODO: REPLACE_AFTER_TESTING: replace this with self.insurance[0].policy.payerid after testing
                )
            )
            obj.insurer = insurer.model_dump(mode="json")
        except NHCXAPIException as e:
            raise ValidationError(e.detail) from e


class ClaimResponseRetrieveSpec(EMRResource):
    __model__ = ClaimResponse
    __exclude__ = ["request"]

    outcome: str
    disposition: str | None = None
    item: dict | None = None
    add_item: dict | None = None
    total: dict | None = None
    error: dict | None = None
    request: UUID4

    created_date: datetime | None = None
    modified_date: datetime | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["request"] = obj.request.external_id


class ClaimListSpec(ClaimBaseSpec):
    use: str
    status: str
    priority: str
    type: dict | None = None
    insurer: dict
    billable_period: dict | None = None
    related: list[dict] = []
    care_team: list[dict] = []
    supporting_info: list[dict] = []
    procedure: list[dict] = []
    diagnosis: list[dict] = []
    insurance: list[dict] = []
    item: list[dict] = []
    accident: dict | None = None
    payee: dict | None = None

    provider: UUID4
    patient: UUID4
    encounter: UUID4 | None = None
    latest_response: dict | None = None
    created_by: dict | None = None
    updated_by: dict | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["provider"] = obj.provider.external_id
        mapping["patient"] = obj.patient.external_id
        mapping["encounter"] = obj.encounter.external_id if obj.encounter else None

        latest_response = (
            ClaimResponse.objects.filter(request=obj).order_by("-created_date").first()
        )
        if latest_response:
            mapping["latest_response"] = ClaimResponseRetrieveSpec.serialize(
                latest_response
            ).to_json()

        if obj.created_by:
            mapping["created_by"] = UserSpec.serialize(obj.created_by).to_json()
        if obj.updated_by:
            mapping["updated_by"] = UserSpec.serialize(obj.updated_by).to_json()


class ClaimRetrieveSpec(ClaimListSpec):
    @classmethod
    def perform_extra_serialization(cls, mapping, obj):  # noqa: PLR0912
        super().perform_extra_serialization(mapping, obj)

        if obj.related:
            mapping["related"] = []
            for related in obj.related:
                parsed = {**related}
                claim = Claim.objects.get(external_id=related.get("claim"))
                parsed["claim"] = ClaimRetrieveSpec.serialize(claim).to_json()
                mapping["related"].append(parsed)

        if obj.care_team:
            mapping["care_team"] = []
            for care_team in obj.care_team:
                parsed = {**care_team}
                provider = User.objects.get(external_id=care_team.get("provider"))
                parsed["provider"] = UserSpec.serialize(provider).to_json()
                mapping["care_team"].append(parsed)

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

        if obj.diagnosis:
            mapping["diagnosis"] = []
            for diagnosis in obj.diagnosis:
                parsed = {**diagnosis}
                if diagnosis.get("diagnosis_reference"):
                    condition = Condition.objects.get(
                        external_id=diagnosis.get("diagnosis_reference")
                    )
                    parsed["diagnosis_reference"] = ConditionReadSpec.serialize(
                        condition
                    ).to_json()
                mapping["diagnosis"].append(parsed)

        if obj.procedure:
            mapping["procedure"] = []
            for procedure in obj.procedure:
                parsed = {**procedure}
                if procedure.get("procedure_reference"):
                    # procedure = get_object_or_404(Procedure, external_id=procedure.get("procedure_reference"))
                    # parsed["procedure_reference"] = ProcedureReadSpec.serialize(procedure).to_json()
                    pass
                mapping["procedure"].append(parsed)

        if obj.item:
            mapping["item"] = []
            for item in obj.item:
                parsed = {**item}
                if item.get("charge_item"):
                    charge_item = ChargeItem.objects.get(
                        external_id=item.get("charge_item")
                    )
                    parsed["charge_item"] = ChargeItemReadSpec.serialize(
                        charge_item
                    ).to_json()
                mapping["item"].append(parsed)
