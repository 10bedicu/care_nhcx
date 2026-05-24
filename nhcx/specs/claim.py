from datetime import datetime
from enum import Enum
from uuid import uuid4

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
from nhcx.models.insurance_plan import InsurancePlanQuestionnaire
from nhcx.models.provider import Provider
from nhcx.services.participant import ParticipantService
from nhcx.services.types.participant import Policy, SearchParticipantBody
from nhcx.specs.valuesets.claim import (
    NHCX_CLAIM_CARE_TEAM_ROLE_VALUESET,
    NHCX_CLAIM_DIAGNOSIS_CODE_VALUESET,
    NHCX_CLAIM_DIAGNOSIS_TYPE_VALUESET,
    NHCX_CLAIM_PROCEDURE_CODE_VALUESET,
    NHCX_CLAIM_PROCEDURE_TYPE_VALUESET,
    NHCX_CLAIM_RELATED_RELATIONSHIP_VALUESET,
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
    YES = "yes"
    NO = "no"
    UNKNOWN = "unknown"


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
    category: dict
    code: dict
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
    category: dict | None = None
    product_or_service: dict | None = None
    modifier: list[dict] = []
    charge_items: list[UUID4] = []
    program_code: list[dict] = []
    serviced_period: PeriodSpec
    quantity: Quantity | None = None
    unit_price: float | None = None  # in INR
    factor: float | None = None

    @field_validator("charge_items")
    @classmethod
    def validate_charge_items(cls, value):
        for uuid in value:
            if not ChargeItem.objects.filter(external_id=uuid).exists():
                msg = f"Charge item {uuid} not found"
                raise ValidationError(msg)
        return value


class ClaimQuestionnaireResponseAnswerSpec(BaseModel):
    value_boolean: bool | None = None
    value_decimal: float | None = None
    value_integer: int | None = None
    value_date: str | None = None
    value_date_time: str | None = None
    value_time: str | None = None
    value_string: str | None = None
    value_uri: str | None = None
    value_attachment: UUID4 | None = None
    value_coding: dict | None = None
    value_quantity: dict | None = None

    @model_validator(mode="after")
    def validate_at_most_one_value(self):
        values = [
            self.value_boolean,
            self.value_decimal,
            self.value_integer,
            self.value_date,
            self.value_date_time,
            self.value_time,
            self.value_string,
            self.value_uri,
            self.value_attachment,
            self.value_coding,
            self.value_quantity,
        ]
        non_null = [v for v in values if v is not None]
        if len(non_null) > 1:
            raise ValidationError("At most one value field may be set on each answer")
        return self

    @field_validator("value_attachment")
    @classmethod
    def validate_value_attachment(cls, value):
        if value and not FileUpload.objects.filter(external_id=value).exists():
            raise ValidationError("File upload not found")
        return value


class ClaimQuestionnaireResponseItemSpec(BaseModel):
    link_id: str
    text: str | None = None
    answer: list[ClaimQuestionnaireResponseAnswerSpec] = []
    item: list["ClaimQuestionnaireResponseItemSpec"] = []


ClaimQuestionnaireResponseItemSpec.model_rebuild()


class ClaimQuestionnaireResponseSpec(BaseModel):
    """
    Questionnaire responses filled during claim entry, keyed by the
    InsurancePlanQuestionnaire.full_url that the answers belong to.

    `sequence` must be globally unique across all supportingInfo entries on
    the claim (i.e. must not overlap with any sequence in supporting_info).
    Convention: set it to max(supporting_info sequences) + qr_index + 1.

    `category` and `code` map to the supportingInfo entry that references
    this response in the FHIR bundle.
    """

    sequence: int
    questionnaire: str  # InsurancePlanQuestionnaire.full_url (e.g. urn:uuid:...)
    category: dict
    code: dict
    item: list[ClaimQuestionnaireResponseItemSpec] = []


def _collect_required_link_ids(fhir_items: list) -> set[str]:
    """Recursively collect linkIds that are marked required=True in a FHIR Questionnaire items list."""
    required: set[str] = set()
    for item in fhir_items or []:
        if item.get("required", False):
            link_id = item.get("linkId") or item.get("link_id")
            if link_id:
                required.add(link_id)
        required.update(_collect_required_link_ids(item.get("item") or []))
    return required


def _collect_answered_link_ids(response_items) -> set[str]:
    """Recursively collect linkIds that have at least one answer in a QuestionnaireResponse items list."""
    answered: set[str] = set()
    for item in response_items or []:
        if item.answer:
            answered.add(item.link_id)
        answered.update(_collect_answered_link_ids(item.item))
    return answered


class ClaimAccidentSpec(BaseModel):
    date: datetime
    type: dict | None = None
    location: str | None = None


class ClaimPayeeSpec(BaseModel):
    # TODO: add this after understanding field requirements
    pass


class ClaimBaseSpec(EMRResource):
    __model__ = Claim
    __exclude__ = ["patient", "provider", "encounter"]
    __store_metadata__ = True

    id: UUID4 | None = None
    claim_flow_id: str | None = None

    created_date: datetime | None = None
    modified_date: datetime | None = None


class ClaimCreateSpec(ClaimBaseSpec):
    use: ClaimUseChoices
    status: ClaimStatusChoices
    priority: ClaimPriorityChoices
    type: dict
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
    questionnaire_responses: list[ClaimQuestionnaireResponseSpec] = []

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

    @model_validator(mode="after")
    def validate_sequences(self):
        def _check_unique(items, field, label):
            seqs = [getattr(i, field) for i in items]
            if len(seqs) != len(set(seqs)):
                msg = f"Duplicate sequences in {label}"
                raise ValidationError(msg)

        def _check_refs(refs, valid_seqs, ref_label, target_label):
            invalid = set(refs) - valid_seqs
            if invalid:
                msg = f"{ref_label} references unknown {target_label} sequences: {sorted(invalid)}"
                raise ValidationError(msg)

        _check_unique(self.care_team, "sequence", "care_team")
        _check_unique(self.diagnosis, "sequence", "diagnosis")
        _check_unique(self.procedure, "sequence", "procedure")
        _check_unique(self.insurance, "sequence", "insurance")
        _check_unique(self.item, "sequence", "item")

        # supporting_info and questionnaire_responses both contribute to
        # FHIR Claim.supportingInfo — their sequences must be unique together
        supporting_seqs = [s.sequence for s in self.supporting_info]
        qr_seqs = [q.sequence for q in self.questionnaire_responses]
        all_info_seqs = supporting_seqs + qr_seqs
        if len(all_info_seqs) != len(set(all_info_seqs)):
            raise ValidationError(
                "Duplicate sequences across supporting_info and questionnaire_responses"
            )

        valid_care_team_seqs = {ct.sequence for ct in self.care_team}
        valid_diagnosis_seqs = {d.sequence for d in self.diagnosis}
        valid_procedure_seqs = {p.sequence for p in self.procedure}
        valid_info_seqs = set(all_info_seqs)

        for item in self.item:
            _check_refs(
                item.care_team_sequence,
                valid_care_team_seqs,
                "item.care_team_sequence",
                "care_team",
            )
            _check_refs(
                item.diagnosis_sequence,
                valid_diagnosis_seqs,
                "item.diagnosis_sequence",
                "diagnosis",
            )
            _check_refs(
                item.procedure_sequence,
                valid_procedure_seqs,
                "item.procedure_sequence",
                "procedure",
            )
            _check_refs(
                item.information_sequence,
                valid_info_seqs,
                "item.information_sequence",
                "supporting_info/questionnaire_responses",
            )

        all_charge_item_uuids = [
            str(uuid) for item in self.item for uuid in item.charge_items
        ]
        if len(all_charge_item_uuids) != len(set(all_charge_item_uuids)):
            raise ValidationError(
                "The same charge item cannot be linked to multiple items"
            )

        return self

    @model_validator(mode="after")
    def validate_questionnaire_responses_content(self):
        for qr in self.questionnaire_responses:
            questionnaire = (
                InsurancePlanQuestionnaire.objects.filter(
                    full_url=qr.questionnaire
                ).first()
                or InsurancePlanQuestionnaire.objects.filter(
                    url=qr.questionnaire
                ).first()
            )
            if not questionnaire or not questionnaire.items:
                continue

            required_link_ids = _collect_required_link_ids(questionnaire.items)
            if not required_link_ids:
                continue

            answered_link_ids = _collect_answered_link_ids(qr.item)
            missing = required_link_ids - answered_link_ids
            if missing:
                msg = f"Required questionnaire items missing for '{qr.questionnaire}': {sorted(missing)}"
                raise ValidationError(msg)

        return self

    def perform_extra_deserialization(self, is_update, obj):
        if self.encounter:
            obj.encounter = get_object_or_404(Encounter, external_id=self.encounter)

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

        flow_id = str(uuid4())
        if self.related:
            first_related = self.related[0]
            related_claim = Claim.objects.filter(
                external_id=first_related.claim
            ).first()
            if related_claim:
                related_flow_id = (related_claim.meta or {}).get("claim_flow_id")
                if related_flow_id:
                    flow_id = related_flow_id

        obj.meta = obj.meta or {}
        if not obj.meta.get("claim_flow_id"):
            obj.meta["claim_flow_id"] = flow_id


class ClaimResponseRetrieveSpec(EMRResource):
    __model__ = ClaimResponse
    __exclude__ = ["request"]

    use: str | None = None
    status: str | None = None
    outcome: str
    disposition: str | None = None
    # Payer-assigned pre-authorization number — only present on pre-auth approvals.
    # Must be included when submitting the final claim.
    pre_auth_ref: str | None = None
    # Claim-level adjudication list; carries the machine-readable status code
    # (approved / queried / rejected) as opposed to the FHIR outcome enum.
    adjudication: list | None = None
    identifier: list | None = None
    type: dict | None = None
    item: list | None = None
    add_item: list | None = None
    total: list | None = None
    error: list | None = None
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
    questionnaire_responses: list[dict] = []

    dispatched_at: datetime | None = None
    dispatch_error: str = ""
    dispatch_status: str = "pending"

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
                if item.get("charge_items"):
                    parsed["charge_items"] = [
                        ChargeItemReadSpec.serialize(
                            get_object_or_404(ChargeItem, external_id=uuid)
                        ).to_json()
                        for uuid in item.get("charge_items")
                    ]
                mapping["item"].append(parsed)
