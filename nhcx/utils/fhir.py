import base64
from datetime import UTC, datetime
from functools import wraps
from uuid import uuid4
from zoneinfo import ZoneInfo

from django.db import models, transaction
from django.db.models import Q, Value
from django.db.models.functions import Replace
from fhir.resources.R4B.address import Address
from fhir.resources.R4B.attachment import Attachment
from fhir.resources.R4B.bundle import Bundle, BundleEntry
from fhir.resources.R4B.claim import (
    Claim,
    ClaimCareTeam,
    ClaimDiagnosis,
    ClaimInsurance,
    ClaimItem,
    ClaimPayee,
    ClaimProcedure,
    ClaimRelated,
    ClaimSupportingInfo,
)
from fhir.resources.R4B.claimresponse import ClaimResponse
from fhir.resources.R4B.codeableconcept import CodeableConcept
from fhir.resources.R4B.coding import Coding
from fhir.resources.R4B.communication import Communication, CommunicationPayload
from fhir.resources.R4B.communicationrequest import (
    CommunicationRequest,
    CommunicationRequestPayload,
)
from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.contactpoint import ContactPoint
from fhir.resources.R4B.coverage import Coverage
from fhir.resources.R4B.coverageeligibilityrequest import (
    CoverageEligibilityRequest,
    CoverageEligibilityRequestInsurance,
    CoverageEligibilityRequestItem,
    CoverageEligibilityRequestItemDiagnosis,
    CoverageEligibilityRequestSupportingInfo,
)
from fhir.resources.R4B.coverageeligibilityresponse import CoverageEligibilityResponse
from fhir.resources.R4B.documentreference import (
    DocumentReference,
    DocumentReferenceContent,
)
from fhir.resources.R4B.humanname import HumanName
from fhir.resources.R4B.identifier import Identifier
from fhir.resources.R4B.location import Location
from fhir.resources.R4B.meta import Meta
from fhir.resources.R4B.money import Money
from fhir.resources.R4B.organization import Organization
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.paymentreconciliation import PaymentReconciliation
from fhir.resources.R4B.period import Period
from fhir.resources.R4B.practitioner import Practitioner
from fhir.resources.R4B.quantity import Quantity
from fhir.resources.R4B.questionnaireresponse import (
    QuestionnaireResponse,
    QuestionnaireResponseItem,
    QuestionnaireResponseItemAnswer,
)
from fhir.resources.R4B.reference import Reference
from fhir.resources.R4B.resource import Resource
from fhir.resources.R4B.task import Task, TaskInput, TaskOutput
from pydantic import UUID4, BaseModel

from care.emr.models.base import EMRBaseModel
from care.emr.models.condition import Condition as ConditionModel
from care.emr.models.file_upload import FileUpload
from care.emr.models.file_upload import FileUpload as FileUploadModel
from care.emr.models.patient import Patient as PatientModel
from care.emr.resources.common.coding import Coding as CodingSpec
from care.facility.models import Facility as FacilityModel
from care.users.models import User as UserModel
from care_nhcx.nhcx.specs.claim import ClaimStatusChoices
from nhcx.models.claim import Claim as ClaimModel
from nhcx.models.claim import ClaimResponse as ClaimResponseModel
from nhcx.models.communication import Communication as CommunicationModel
from nhcx.models.communication import CommunicationRequest as CommunicationRequestModel
from nhcx.models.coverage_eligibility import (
    CoverageEligibilityRequest as CoverageEligibilityRequestModel,
)
from nhcx.models.coverage_eligibility import (
    CoverageEligibilityResponse as CoverageEligibilityResponseModel,
)
from nhcx.models.payment import PaymentReconciliation as PaymentReconciliationModel
from nhcx.models.task import Task as TaskModel
from nhcx.models.task import TaskUseCaseChoices
from nhcx.services.types.participant import Participant, Policy
from nhcx.settings import plugin_settings as settings
from nhcx.utils.insurance_plan_ingestor import InsurancePlanIngestor

CARE_IDENTIFIER_SYSTEM = settings.BACKEND_DOMAIN


class Fhir:
    _IST = ZoneInfo("Asia/Kolkata")

    def __init__(self):
        self._profiles = {}
        self._resource_id_url_map = {}

        self._participants_external_id_map = {}
        self._policies_external_id_map = {}

    @classmethod
    def _to_ist(cls, dt: datetime) -> str:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)
        return dt.astimezone(cls._IST).replace(microsecond=0).isoformat()

    @classmethod
    def _ist_period(cls, start: str | None, end: str | None) -> Period | None:
        if not start and not end:
            return None
        return Period(
            start=cls._to_ist(datetime.fromisoformat(start)) if start else None,
            end=cls._to_ist(datetime.fromisoformat(end)) if end else None,
        )

    @staticmethod
    def cache_profiles(resource_type: str):
        def decorator(func):
            @wraps(func)
            def wrapper(self, model_instance: EMRBaseModel, *args, **kwargs):
                if not hasattr(model_instance, "external_id"):
                    err = f"{model_instance.__class__.__name__} does not have 'external_id' attribute"
                    raise AttributeError(err)

                cache_key_prefix = kwargs.get("cache_key_prefix", "")
                cache_key_id = str(model_instance.external_id)
                cache_key_suffix = kwargs.get("cache_key_suffix", "")
                cache_key = f"{resource_type}/{cache_key_prefix}{cache_key_id}{cache_key_suffix}"

                if cache_key in self._profiles:
                    return self._profiles[cache_key]

                result = func(self, model_instance, *args, **kwargs)

                self._profiles[cache_key] = result
                self._resource_id_url_map[cache_key] = str(model_instance.external_id)
                return result

            return wrapper

        return decorator

    def cached_profiles(self):
        return list(
            filter(lambda profile: profile is not None, self._profiles.values())
        )

    def _reference_url(self, resource: Resource = None):
        if resource is None:
            return ""

        key = f"{resource.resource_type}/{resource.id}"
        return f"urn:uuid:{self._resource_id_url_map.get(key, resource.id or uuid4())}"

    def _reference(self, resource: Resource = None):
        if resource is None:
            return None

        return Reference(reference=self._reference_url(resource))

    @cache_profiles(Patient.get_resource_type())
    def _patient(self, patient: PatientModel):
        id = str(patient.external_id)

        return Patient(
            id=id,
            meta=Meta(
                profile=["https://nrces.in/ndhm/fhir/r4/StructureDefinition/Patient"],
            ),
            identifier=[
                # FIXME: remove this once we have a real identifier
                Identifier(
                    value="SBXSTG007",
                    system="https://bis.pmjay.gov.in",
                    type=CodeableConcept(
                        coding=[
                            Coding(
                                system="https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-identifier-type-code",
                                code="PMJAY",
                                display="Pradhan Mantri Jan Aarogya Yojana (PMJAY) ID",
                            )
                        ]
                    ),
                ),
                # Identifier(
                #     value="",
                #     system="https://bis.pmjay.gov.in",
                #     type=CodeableConcept(
                #         coding=[
                #             Coding(
                #                 system="http://terminology.hl7.org/CodeSystem/v2-0203",
                #                 code="JHN",
                #                 display="Jurisdictional health number",
                #             )
                #         ]
                #     ),
                # ),
                Identifier(
                    value=id,
                    system=f"{CARE_IDENTIFIER_SYSTEM}/patient",
                    type=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://terminology.hl7.org/CodeSystem/v2-0203",
                                code="MR",
                                display="Medical Record Number",
                            )
                        ]
                    ),
                ),
            ],
            name=[HumanName(text=patient.name)],
            telecom=[
                *(
                    [ContactPoint(system="phone", value=patient.phone_number)]
                    if patient.phone_number
                    else []
                ),
                *(
                    [ContactPoint(system="phone", value=patient.emergency_phone_number)]
                    if patient.emergency_phone_number
                    else []
                ),
            ],
            gender=patient.gender,
            birthDate=patient.date_of_birth.isoformat()
            if patient.date_of_birth
            else None,
            address=[
                Address(
                    line=[patient.address],
                    postalCode=patient.pincode,
                    country="IN",
                ),
                *(
                    [
                        Address(
                            line=[patient.permanent_address],
                            postalCode=patient.pincode,
                            country="IN",
                        )
                    ]
                    if patient.permanent_address != patient.address
                    else []
                ),
            ],
        )

    @cache_profiles(Practitioner.get_resource_type())
    def _practitioner(self, user: UserModel):
        id = str(user.external_id)

        return Practitioner(
            id=id,
            meta=Meta(
                profile=[
                    "https://nrces.in/ndhm/fhir/r4/StructureDefinition/Practitioner"
                ],
            ),
            identifier=[
                Identifier(
                    value=id,
                    type=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://terminology.hl7.org/CodeSystem/v2-0203",
                                code="PRN",
                                display="Provider number",
                            )
                        ]
                    ),
                ),
                Identifier(
                    type=CodeableConcept(
                        coding=[
                            Coding(
                                system="https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-identifier-type-code",
                                code="HPIN",
                                display="Health Practitioner ID issued by NDHM",
                            )
                        ]
                    ),
                    system="https://hpr.abdm.gov.in",
                    value="khavinshankar@hpr.abdm",
                ),
            ],
            name=[HumanName(text=user.full_name)],
            telecom=[
                *(
                    [ContactPoint(system="phone", value=user.phone_number)]
                    if user.phone_number
                    else []
                ),
                *(
                    [ContactPoint(system="email", value=user.email)]
                    if user.email
                    else []
                ),
            ],
            gender={
                "1": "male",
                "2": "female",
                "3": "other",
            }.get(user.gender, "unknown"),
            birthDate=user.date_of_birth,
        )

    @cache_profiles(Organization.get_resource_type())
    def _organization(self, facility: FacilityModel):
        id = str(facility.external_id)

        if facility.name == "SHA HP":
            return Organization(
                id=id,
                meta={
                    "profile": [
                        "https://nrces.in/ndhm/fhir/r4/StructureDefinition/Organization"
                    ]
                },
                identifier=[
                    # FIXME: remove this once we have a real identifier
                    {
                        "type": {
                            "coding": [
                                {
                                    "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                                    "code": "NIIP",
                                    "display": "National Insurance Payor Identifier (Payor)",
                                }
                            ]
                        },
                        "system": "https://facility.abdm.gov.in",
                        "value": "1518",
                    }
                ],
                active=True,
                type=[
                    {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/organization-type",
                                "code": "pay",
                                "display": "Payer",
                            }
                        ]
                    }
                ],
                name="SHA HP",
                contact=[{"telecom": [{"system": "phone", "value": "8272905341"}]}],
            )

        return Organization(
            id=id,
            meta=Meta(
                profile=[
                    "https://nrces.in/ndhm/fhir/r4/StructureDefinition/Organization"
                ],
            ),
            identifier=[
                # FIXME: add health facility id
                # {
                #         "type": {
                #             "coding": [
                #                 {
                #                     "system": "http://terminology.hl7.org/CodeSystem/v2-0203",
                #                     "code": "NPI",
                #                     "display": "National provider identifier",
                #                 }
                #             ]
                #         },
                #         "system": "https://facility.abdm.gov.in",
                #         "value": "IN1910000151",
                #     }
                Identifier(
                    # FIXME: remove this once we have a real identifier
                    type=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://terminology.hl7.org/CodeSystem/v2-0203",
                                code="NPI",
                                display="National provider identifier",
                            )
                        ]
                    ),
                    system="https://facility.abdm.gov.in",
                    value="IN2910001986",
                ),
                Identifier(
                    system="https://facility.abdm.gov.in",
                    value="IN2910001986",
                    type=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://terminology.hl7.org/CodeSystem/v2-0203",
                                code="FI",
                                display="Facility ID",
                            )
                        ]
                    ),
                ),
            ],
            type=[
                CodeableConcept(
                    coding=[
                        Coding(
                            system="http://terminology.hl7.org/CodeSystem/organization-type",
                            code="prov",
                            display="Healthcare Provider",
                        )
                    ]
                )
            ],
            name=facility.name,
            telecom=[
                *(
                    [ContactPoint(system="phone", value=facility.phone_number)]
                    if facility.phone_number
                    else []
                )
            ],
            address=[
                Address(
                    line=[facility.address],
                    postalCode=facility.pincode,
                    country="IN",
                )
            ]
            if facility.address
            else None,
        )

    @cache_profiles(Location.get_resource_type())
    def _location(self, facility: FacilityModel):
        id = str(facility.external_id)

        return Location(
            id=id,
            identifier=[
                # FIXME: add health facility id
                Identifier(
                    system=f"{CARE_IDENTIFIER_SYSTEM}/facility",
                    value=id,
                    type=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://terminology.hl7.org/CodeSystem/v2-0203",
                                code="FI",
                                display="Facility ID",
                            )
                        ]
                    ),
                )
            ],
            type=[
                CodeableConcept(
                    coding=[
                        Coding(
                            system="http://terminology.hl7.org/CodeSystem/organization-type",
                            code="prov",
                            display="Healthcare Provider",
                        )
                    ]
                )
            ],
            name=facility.name,
            telecom=[
                *(
                    [ContactPoint(system="phone", value=facility.phone_number)]
                    if facility.phone_number
                    else []
                )
            ],
            address=Address(
                line=[facility.address],
                postalCode=facility.pincode,
                country="IN",
            )
            if facility.address
            else None,
        )

    @cache_profiles(Condition.get_resource_type())
    def _condition(self, condition: ConditionModel):
        id = str(condition.external_id)

        return Condition(
            id=id,
            meta=Meta(
                profile=["https://nrces.in/ndhm/fhir/r4/StructureDefinition/Condition"],
            ),
            # FIXME: expand this
            code=CodeableConcept(
                coding=[Coding(**condition.code)],
            ),
            subject=self._reference(self._patient(condition.patient)),
        )

    def _attachment(self, attachment: FileUpload):
        id = str(attachment.external_id)
        content_type, content = attachment.files_manager.file_contents(attachment)

        return Attachment(
            id=id,
            title=attachment.name,
            contentType=content_type,
            data=base64.b64encode(content),
        )

    def _coding(self, coding: CodingSpec | None):
        if coding is None:
            return None

        return Coding(
            code=coding.code,
            display=coding.display,
            system=coding.system,
        )

    def _coding_to_codable_concept(self, coding: CodingSpec | None):
        if coding is None:
            return None

        return CodeableConcept(coding=[self._coding(coding)])

    def _participant_to_organization(self, participant: Participant):
        if participant.participant_id not in self._participants_external_id_map:
            self._participants_external_id_map[participant.participant_id] = uuid4()

        id = str(self._participants_external_id_map[participant.participant_id])

        # FIXME: expand this
        return self._organization(
            FacilityModel(
                external_id=id,
                id=participant.participant_id,
                name=participant.participant_name,
            )
        )

    @cache_profiles(DocumentReference.get_resource_type())
    def _document_reference(self, file: FileUploadModel):
        id = str(file.external_id)
        content_type, content = file.files_manager.file_contents(file)

        return DocumentReference(
            id=id,
            meta=Meta(
                profile=[
                    "https://nrces.in/ndhm/fhir/r4/StructureDefinition/DocumentReference"
                ],
            ),
            identifier=[Identifier(value=id)],
            status="current",
            type=CodeableConcept(text=file.internal_name.split(".")[0]),
            content=[
                DocumentReferenceContent(
                    attachment=Attachment(
                        contentType=content_type, data=base64.b64encode(content)
                    )
                )
            ],
            author=[self._reference(self._practitioner(file.created_by))],
        )

    class CoverageModel(BaseModel):
        external_id: UUID4
        policy: Policy
        insurer: Participant

    @cache_profiles(Coverage.get_resource_type())
    def _coverage(self, coverage: CoverageModel):
        id = str(coverage.external_id)

        return Coverage(
            id=id,
            meta=Meta(
                profile=["https://nrces.in/ndhm/fhir/r4/StructureDefinition/Coverage"],
            ),
            # FIXME: remove this once we have a real identifier
            identifier=[
                Identifier(
                    type=CodeableConcept(
                        coding=[
                            Coding(
                                system="http://terminology.hl7.org/CodeSystem/v2-0203",
                                code="NH",
                                display="National Health Plan Identifier",
                            )
                        ]
                    ),
                    system="https://payer.nha.gov.in",
                    value="PMJAY/HP/S/G",
                )
            ],
            subscriberId=coverage.policy.memberid,
            beneficiary=self._reference(
                self._patient(
                    PatientModel.objects.annotate(
                        abha_number_parsed=Replace(
                            "abha_number__abha_number",
                            Value("-"),
                            Value(""),
                            output_field=models.CharField(),
                        )
                    )
                    .filter(
                        Q(
                            abha_number_parsed=coverage.policy.abhanumber.replace(
                                "-", ""
                            )
                        )
                        | Q(abha_number__mobile=coverage.policy.mobilenumber)
                        | Q(external_id="2b970012-eb54-4fb1-a670-1d053c9513cd")
                    )
                    .first()
                )
            ),
            payor=[
                self._reference(self._participant_to_organization(coverage.insurer))
            ],
            status="active",
            period=self._ist_period(
                coverage.policy.period.start, coverage.policy.period.end
            )
            if coverage.policy.period
            else None,
        )

    @cache_profiles(CommunicationRequest.get_resource_type())
    def _communication_request(self, request: CommunicationRequestModel):
        id = str(request.external_id)

        return CommunicationRequest(
            id=id,
            meta=Meta(
                profile=[
                    "https://nrces.in/ndhm/fhir/r4/StructureDefinition/CommunicationRequest"
                ],
            ),
            identifier=[Identifier(value=request.identifier)],
            status=request.status,
            priority=request.priority,
            category=[CodeableConcept(**category) for category in request.category]
            if request.category
            else None,
            authoredOn=self._to_ist(request.authored_on)
            if request.authored_on
            else None,
            payload=[
                CommunicationRequestPayload(**payload) for payload in request.payload
            ]
            if request.payload
            else None,
        )

    @cache_profiles(Communication.get_resource_type())
    def _communication(
        self, communication: CommunicationModel, for_content_transfer=False
    ):
        id = str(communication.external_id)

        return Communication(
            id=id,
            meta=Meta(
                profile=[
                    "https://nrces.in/ndhm/fhir/r4/StructureDefinition/Communication"
                ],
            ),
            identifier=[Identifier(value=id)],
            status=communication.status,
            priority=communication.priority,
            category=[
                self._coding_to_codable_concept(CodingSpec(**coding))
                for coding in communication.category
            ],
            sent=self._to_ist(communication.sent) if communication.sent else None,
            payload=[
                CommunicationPayload(
                    contentString=payload.get("content_string"),
                    contentAttachment=self._attachment(
                        FileUpload.objects.filter(
                            external_id=payload.get("content_attachment")
                        ).first()
                    )
                    if payload.get("content_attachment")
                    else None,
                )
                for payload in communication.payload
            ],
            basedOn=[
                self._reference(self._communication_request(communication.based_on))
            ]
            if not for_content_transfer
            else None,
        )

    def _policy_to_coverage(self, policy: Policy, insurer: Participant):
        if policy.sno not in self._policies_external_id_map:
            self._policies_external_id_map[policy.sno] = uuid4()

        external_id = self._policies_external_id_map[policy.sno]
        return self._coverage(
            self.CoverageModel(external_id=external_id, policy=policy, insurer=insurer)
        )

    def _coverage_eligibility_request(self, request: CoverageEligibilityRequestModel):
        id = str(request.external_id)

        return CoverageEligibilityRequest(
            id=id,
            meta=Meta(
                profile=[
                    "https://nrces.in/ndhm/fhir/r4/StructureDefinition/CoverageEligibilityRequest"
                ],
            ),
            identifier=[Identifier(value=id)],
            status=request.status,
            priority=self._coding_to_codable_concept(
                CodingSpec(
                    system="http://terminology.hl7.org/CodeSystem/processpriority",
                    code=request.priority,
                )
            ),
            purpose=request.purpose,
            created=self._to_ist(request.created_date),
            patient=self._reference(self._patient(request.patient)),
            enterer=self._reference(self._practitioner(request.created_by)),
            provider=self._reference(self._organization(request.provider.facility)),
            insurer=self._reference(
                self._participant_to_organization(Participant(**request.insurer))
            ),
            facility=self._reference(
                self._location(
                    self._override_facility_external_id(
                        request.provider.facility, uuid4()
                    )
                )
            ),
            supportingInfo=[
                CoverageEligibilityRequestSupportingInfo(
                    sequence=supporting_info.get("sequence"),
                    information=self._reference(
                        self._communication(
                            CommunicationModel(
                                external_id=uuid4(),
                                status="completed",
                                payload=[
                                    {
                                        "content_string": supporting_info.get(
                                            "value_string"
                                        ),
                                        "content_attachment": supporting_info.get(
                                            "value_attachment"
                                        ),
                                    }
                                ],
                            ),
                            for_content_transfer=True,
                        ),
                    ),
                )
                for supporting_info in request.supporting_info
            ],
            insurance=[
                CoverageEligibilityRequestInsurance(
                    focal=insurance.get("focal"),
                    coverage=self._reference(
                        self._policy_to_coverage(
                            Policy(**insurance.get("policy")),
                            Participant(**request.insurer),
                        )
                    ),
                )
                for insurance in request.insurance
            ],
            item=[
                CoverageEligibilityRequestItem(
                    supportingInfoSequence=item.get("supporting_info_sequence"),
                    category=self._coding_to_codable_concept(
                        CodingSpec(**item.get("category"))
                    ),
                    productOrService=self._coding_to_codable_concept(
                        CodingSpec(**item.get("product_or_service"))
                    ),
                    quantity=Quantity(**item.get("quantity")),
                    unitPrice=Money(value=item.get("unit_price"), currency="INR"),
                    diagnosis=[
                        CoverageEligibilityRequestItemDiagnosis(
                            diagnosisReference=self._reference(
                                self._condition(
                                    ConditionModel.objects.filter(
                                        external_id=diagnosis.get("diagnosis_reference")
                                    ).first()
                                )
                            )
                            if diagnosis.get("diagnosis_reference")
                            else None,
                            diagnosisCodeableConcept=self._coding_to_codable_concept(
                                CodingSpec(**diagnosis.get("diagnosis_code"))
                            )
                            if not diagnosis.get("diagnosis_reference")
                            else None,
                        )
                        for diagnosis in item.get("diagnosis") or []
                    ],
                    modifier=[
                        self._coding_to_codable_concept(CodingSpec(**modifier))
                        for modifier in item.get("modifier", [])
                    ]
                    or None,
                )
                for item in request.item
            ],
        )

    def _override_facility_external_id(
        self, facility: FacilityModel, new_external_id
    ) -> FacilityModel:
        from copy import copy

        cloned = copy(facility)
        cloned.external_id = new_external_id
        return cloned

    def _qr_item(self, item: dict) -> QuestionnaireResponseItem:
        return QuestionnaireResponseItem(
            linkId=item["link_id"],
            text=item.get("text"),
            answer=[
                QuestionnaireResponseItemAnswer(
                    valueBoolean=answer.get("value_boolean"),
                    valueDecimal=answer.get("value_decimal"),
                    valueInteger=answer.get("value_integer"),
                    valueDate=answer.get("value_date"),
                    valueDateTime=answer.get("value_date_time"),
                    valueTime=answer.get("value_time"),
                    valueString=answer.get("value_string"),
                    valueUri=answer.get("value_uri"),
                    valueCoding=Coding(**answer["value_coding"])
                    if answer.get("value_coding")
                    else None,
                    valueQuantity=Quantity(**answer["value_quantity"])
                    if answer.get("value_quantity")
                    else None,
                    valueAttachment=self._attachment(file_upload)
                    if answer.get("value_attachment")
                    and (
                        file_upload := FileUpload.objects.filter(
                            external_id=answer.get("value_attachment")
                        ).first()
                    )
                    else None,
                )
                for answer in item.get("answer", [])
            ]
            or None,
            item=[self._qr_item(child) for child in item.get("item", [])] or None,
        )

    def _questionnaire_response(
        self, qr_data: dict, patient: PatientModel
    ) -> QuestionnaireResponse:
        qr_id = str(uuid4())

        qr = QuestionnaireResponse(
            id=qr_id,
            meta=Meta(
                profile=[
                    "https://nrces.in/ndhm/fhir/r4/StructureDefinition/QuestionnaireResponse"
                ],
            ),
            status="completed",
            questionnaire=qr_data["questionnaire"],
            subject=self._reference(self._patient(patient)),
            authored=self._to_ist(datetime.now(UTC)),
            item=[self._qr_item(item) for item in qr_data.get("item", [])] or None,
        )

        cache_key = f"QuestionnaireResponse/{qr_id}"
        self._profiles[cache_key] = qr
        self._resource_id_url_map[cache_key] = qr_id

        return qr

    def _claim(self, claim: ClaimModel):
        id = str(claim.external_id)

        _all_si_seqs = [
            si.get("sequence", 0) for si in (claim.supporting_info or [])
        ] + [qr.get("sequence", 0) for qr in (claim.questionnaire_responses or [])]
        _next_seq = (max(_all_si_seqs) + 1) if _all_si_seqs else 1
        _raw_dt = (
            claim.encounter.period.get("start")
            if claim.encounter and claim.encounter.period
            else None
        )
        _encounter_dt = (
            self._to_ist(datetime.fromisoformat(_raw_dt))
            if _raw_dt
            else self._to_ist(claim.created_date)
        )

        return Claim(
            id=id,
            meta=Meta(
                profile=["https://nrces.in/ndhm/fhir/r4/StructureDefinition/Claim"],
            ),
            identifier=[
                Identifier(
                    type=CodeableConcept(
                        coding=[
                            Coding(
                                system="https://www.nrces.in/preview/ndhm/fhir/r4/ValueSet-ndhm-identifier-type-code.html",
                                code="CLN",
                                display="Claim number",
                            )
                        ]
                    ),
                    system=f"urn:uuid:{id}",
                    value=id,
                )
            ],
            status=claim.status,
            type=self._coding_to_codable_concept(CodingSpec(**claim.type)),
            use=claim.use,
            priority=self._coding_to_codable_concept(
                CodingSpec(
                    system="http://terminology.hl7.org/CodeSystem/processpriority",
                    code=claim.priority,
                )
            ),
            created=self._to_ist(claim.created_date),
            billablePeriod=Period(**claim.billable_period)
            if claim.billable_period
            else None,
            patient=self._reference(self._patient(claim.patient)),
            enterer=self._reference(self._practitioner(claim.created_by)),
            provider=self._reference(self._organization(claim.provider.facility)),
            insurer=self._reference(
                self._participant_to_organization(Participant(**claim.insurer))
            ),
            insurance=[
                ClaimInsurance(
                    sequence=insurance.get("sequence"),
                    focal=insurance.get("focal"),
                    coverage=self._reference(
                        self._policy_to_coverage(
                            Policy(**insurance.get("policy")),
                            Participant(**claim.insurer),
                        )
                    ),
                )
                for insurance in claim.insurance
            ],
            payee=ClaimPayee(
                type=CodeableConcept(
                    coding=[
                        Coding(
                            system="http://terminology.hl7.org/CodeSystem/payeetype",
                            code="provider",
                        )
                    ],
                ),
                party=self._reference(self._organization(claim.provider.facility)),
            ),
            related=[
                ClaimRelated(
                    claim=self._reference(
                        self._claim(
                            ClaimModel.objects.filter(
                                external_id=related.get("claim")
                            ).first()
                        )
                    ),
                    relationship=self._coding_to_codable_concept(
                        CodingSpec(**related.get("relationship"))
                    )
                    if related.get("relationship")
                    else None,
                    reference=Identifier(value=related.get("reference"))
                    if related.get("reference")
                    else None,
                )
                for related in claim.related
            ]
            if claim.related
            else None,
            careTeam=[
                ClaimCareTeam(
                    sequence=care_team.get("sequence"),
                    provider=self._reference(
                        self._practitioner(
                            UserModel.objects.filter(
                                external_id=care_team.get("provider")
                            ).first()
                        )
                    ),
                    responsible=care_team.get("responsible"),
                    role=self._coding_to_codable_concept(
                        CodingSpec(**care_team.get("role"))
                    )
                    if care_team.get("role")
                    else None,
                )
                for care_team in claim.care_team
            ]
            if claim.care_team
            else [
                ClaimCareTeam(
                    sequence=1,
                    provider=self._reference(
                        self._organization(claim.provider.facility)
                    ),
                    responsible=True,
                )
            ],
            diagnosis=[
                ClaimDiagnosis(
                    sequence=diagnosis.get("sequence"),
                    type=[
                        self._coding_to_codable_concept(CodingSpec(**diagnosis_type))
                        for diagnosis_type in diagnosis.get("type")
                    ]
                    if diagnosis.get("type")
                    else None,
                    diagnosisReference=self._reference(
                        self._condition(
                            ConditionModel.objects.filter(
                                external_id=diagnosis.get("diagnosis_reference")
                            ).first()
                        )
                    )
                    if diagnosis.get("diagnosis_reference")
                    else None,
                    diagnosisCodeableConcept=self._coding_to_codable_concept(
                        CodingSpec(**diagnosis.get("diagnosis_code"))
                    )
                    if not diagnosis.get("diagnosis_reference")
                    else None,
                    onAdmission=self._coding_to_codable_concept(
                        CodingSpec(
                            system="http://terminology.hl7.org/CodeSystem/ex-diagnosis-on-admission",
                            code=diagnosis.get("on_admission"),
                        )
                    )
                    if diagnosis.get("on_admission")
                    else None,
                )
                for diagnosis in claim.diagnosis
            ]
            if claim.diagnosis
            else None,
            procedure=[
                ClaimProcedure(
                    sequence=procedure.get("sequence"),
                    type=[
                        self._coding_to_codable_concept(CodingSpec(**procedure_type))
                        for procedure_type in procedure.get("type")
                    ]
                    if procedure.get("type")
                    else None,
                    procedureReference=self._reference(
                        self._condition(
                            ConditionModel.objects.filter(
                                external_id=procedure.get("procedure_reference")
                            ).first()
                        )
                    )
                    if procedure.get("procedure_reference")
                    else None,
                    procedureCodeableConcept=self._coding_to_codable_concept(
                        CodingSpec(**procedure.get("procedure_code"))
                    )
                    if not procedure.get("procedure_reference")
                    else None,
                    date=procedure.get("date") if procedure.get("date") else None,
                )
                for procedure in claim.procedure
            ]
            if claim.procedure
            else None,
            supportingInfo=(
                [
                    ClaimSupportingInfo(
                        sequence=supporting_info.get("sequence"),
                        category=self._coding_to_codable_concept(
                            CodingSpec(**supporting_info.get("category"))
                        ),
                        code=self._coding_to_codable_concept(
                            CodingSpec(**supporting_info.get("code"))
                        ),
                        timingPeriod=Period(**supporting_info.get("timing"))
                        if supporting_info.get("timing")
                        else None,
                        valueString=supporting_info.get("value_string"),
                        valueAttachment=self._attachment(si_file)
                        if supporting_info.get("value_attachment")
                        and (
                            si_file := FileUpload.objects.filter(
                                external_id=supporting_info.get("value_attachment")
                            ).first()
                        )
                        else None,
                    )
                    for supporting_info in claim.supporting_info
                ]
                if claim.supporting_info
                else []
            )
            + [
                ClaimSupportingInfo(
                    sequence=qr_data.get("sequence"),
                    category=self._coding_to_codable_concept(
                        CodingSpec(**qr_data.get("category"))
                    ),
                    code=self._coding_to_codable_concept(
                        CodingSpec(**qr_data.get("code"))
                    ),
                    valueReference=self._reference(
                        self._questionnaire_response(qr_data, claim.patient)
                    ),
                )
                for qr_data in (claim.questionnaire_responses or [])
            ]
            + [
                ClaimSupportingInfo(
                    sequence=_next_seq,
                    category=self._coding_to_codable_concept(
                        CodingSpec(
                            system="https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-supportinginfo-category",
                            code="ONS",
                            display="Period, start or end dates of aspects of the Condition. (e.g. admission, discharge etc)",
                        )
                    ),
                    code=self._coding_to_codable_concept(
                        CodingSpec(
                            system="https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-supportinginfo-code",
                            code="ADDD",
                            display="Admission date -Discharge date",
                        )
                    ),
                    valueString=_encounter_dt,
                ),
                ClaimSupportingInfo(
                    sequence=_next_seq + 1,
                    category=self._coding_to_codable_concept(
                        CodingSpec(
                            system="https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-supportinginfo-category",
                            code="OTH",
                            display="Other",
                        )
                    ),
                    code=self._coding_to_codable_concept(
                        CodingSpec(
                            system="https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-supportinginfo-code",
                            code="EDT",
                            display="EncounterDateTime",
                        )
                    ),
                    valueString=_encounter_dt,
                ),
            ]
            or None,
            item=[
                ClaimItem(
                    id=f"item-{item.get('sequence')}",
                    sequence=item.get("sequence"),
                    careTeamSequence=item.get("care_team_sequence"),
                    diagnosisSequence=item.get("diagnosis_sequence"),
                    procedureSequence=item.get("procedure_sequence"),
                    informationSequence=item.get("information_sequence"),
                    category=self._coding_to_codable_concept(
                        CodingSpec(**item.get("category"))
                    )
                    if item.get("category")
                    else None,
                    productOrService=self._coding_to_codable_concept(
                        CodingSpec(**item.get("product_or_service"))
                    )
                    if item.get("product_or_service")
                    else None,
                    modifier=[
                        self._coding_to_codable_concept(CodingSpec(**modifier))
                        for modifier in item.get("modifier", [])
                    ]
                    or None,
                    programCode=[
                        self._coding_to_codable_concept(CodingSpec(**program_code))
                        for program_code in item.get("program_code")
                    ]
                    if item.get("program_code")
                    else None,
                    servicedPeriod=self._ist_period(
                        item.get("serviced_period", {}).get("start"),
                        item.get("serviced_period", {}).get("end"),
                    ),
                    unitPrice=Money(
                        value=item.get("unit_price"),
                        currency="INR",
                    )
                    if item.get("unit_price")
                    else None,
                    quantity=Quantity(
                        value=item.get("quantity", {}).get("value"),
                        unit=item.get("quantity", {})
                        .get("unit", {})
                        .get("display", "1*"),
                        system=item.get("quantity", {})
                        .get("unit", {})
                        .get("system", "http://unitsofmeasure.org"),
                        code=item.get("quantity", {}).get("unit", {}).get("code", "1"),
                    )
                    if item.get("quantity")
                    else None,
                    net=Money(
                        value=(
                            float(item.get("unit_price", 0))
                            * float(item.get("quantity", {}).get("value", 1))
                        ),
                        currency="INR",
                    ),
                    factor=item.get("factor"),
                )
                for item in claim.item
            ]
            if claim.item
            else None,
            total=Money(
                value=(
                    sum(
                        float(item.get("unit_price", 0))
                        * float(item.get("quantity", {}).get("value", 1))
                        for item in claim.item
                    )
                ),
                currency="INR",
            ),
        )

    def _task(self, task: TaskModel):
        id = str(task.external_id)

        if task.use_case == TaskUseCaseChoices.COMMUNICATION_RESPONSE:
            self._communication(task.focus)

        return Task(
            id=id,
            meta=Meta(
                profile=["https://nrces.in/ndhm/fhir/r4/StructureDefinition/Task"],
            ),
            identifier=[Identifier(value=id)],
            status=task.status,
            intent=task.intent,
            priority=task.priority,
            code=CodeableConcept(**task.code) if task.code else None,
            authoredOn=task.authored_on,
            description=task.description,
            reasonCode=CodeableConcept(**task.reason_code)
            if task.reason_code
            else None,
            input=[TaskInput(**_input) for _input in task.input]
            if task.input
            else None,
            output=[TaskOutput(**output) for output in task.output]
            if task.output
            else None,
        )

    def _bundle_entry(self, resource: Resource):
        return BundleEntry(fullUrl=self._reference_url(resource), resource=resource)

    def create_coverage_eligibility_request_bundle(
        self,
        coverage_eligibility_request: CoverageEligibilityRequestModel,
    ):
        id = str(coverage_eligibility_request.external_id)

        return Bundle(
            id=id,
            meta=Meta(
                profile=[
                    "https://nrces.in/ndhm/fhir/r4/StructureDefinition/CoverageEligibilityRequestBundle"
                ],
                lastUpdated=self._to_ist(coverage_eligibility_request.modified_date),
            ),
            identifier=Identifier(value=id, system=f"{CARE_IDENTIFIER_SYSTEM}/bundle"),
            type="collection",
            timestamp=self._to_ist(datetime.now(UTC)),
            entry=[
                self._bundle_entry(
                    self._coverage_eligibility_request(coverage_eligibility_request)
                ),
                *[self._bundle_entry(profile) for profile in self.cached_profiles()],
            ],
        )

    def create_claim_bundle(self, claim: ClaimModel):
        id = str(claim.external_id)

        return Bundle(
            id=id,
            meta=Meta(
                profile=[
                    "https://nrces.in/ndhm/fhir/r4/StructureDefinition/ClaimBundle"
                ],
                lastUpdated=self._to_ist(claim.modified_date),
            ),
            identifier=Identifier(value=id, system=f"{CARE_IDENTIFIER_SYSTEM}/bundle"),
            type="collection",
            timestamp=self._to_ist(datetime.now(UTC)),
            entry=[
                self._bundle_entry(self._claim(claim)),
                *[self._bundle_entry(profile) for profile in self.cached_profiles()],
            ],
        )

    def create_task_bundle(self, task: TaskModel):
        id = str(task.external_id)

        return Bundle(
            id=id,
            meta=Meta(
                profile=[
                    "https://nrces.in/ndhm/fhir/r4/StructureDefinition/TaskBundle"
                ],
                lastUpdated=self._to_ist(task.modified_date),
            ),
            identifier=Identifier(value=id, system=f"{CARE_IDENTIFIER_SYSTEM}/bundle"),
            type="collection",
            timestamp=self._to_ist(datetime.now(UTC)),
            entry=[
                self._bundle_entry(self._task(task)),
                *[self._bundle_entry(profile) for profile in self.cached_profiles()],
            ],
        )

    @staticmethod
    def _build_bundle_index(bundle_entries: list) -> dict:
        """Return a fullUrl -> resource dict for fast reference resolution."""
        return {
            entry.get("fullUrl"): entry.get("resource")
            for entry in bundle_entries
            if entry.get("fullUrl") and entry.get("resource")
        }

    @staticmethod
    def _resolve_ref(reference: str, bundle_index: dict) -> dict | None:
        """
        Resolve a FHIR relative or absolute reference against the bundle index.
        Handles both urn:uuid: and https:// fullUrls.
        """
        if not reference:
            return None
        resource = bundle_index.get(reference)
        if resource:
            return resource
        # Fallback: match by suffix (absolute URL vs urn:uuid mismatch)
        for url, res in bundle_index.items():
            if url and url.endswith(reference.split("/")[-1]):
                return res
        return None

    @staticmethod
    def _extract_identifier(identifiers: list, code: str) -> str | None:
        """Extract a specific identifier value by type code from a FHIR identifier list."""
        for ident in identifiers or []:
            codings = ident.get("type", {}).get("coding", [])
            if any(c.get("code") == code for c in codings):
                return ident.get("value")
        return None

    @staticmethod
    def _resolve_patient_fields(patient_resource: dict | None) -> dict:
        """Extract flat identity fields from a FHIR Patient resource."""
        if not patient_resource:
            return {"pmjay_id": None, "abha_id": None, "name": None, "dob": None, "gender": None}
        identifiers = patient_resource.get("identifier", [])
        name_list = patient_resource.get("name", [])
        name = None
        if name_list:
            name = name_list[0].get("text") or " ".join(name_list[0].get("given", []))
        return {
            "pmjay_id": Fhir._extract_identifier(identifiers, "PMJAY"),
            "abha_id": Fhir._extract_identifier(identifiers, "ABHA"),
            "name": name,
            "dob": patient_resource.get("birthDate"),
            "gender": patient_resource.get("gender"),
        }

    @staticmethod
    def _resolve_coverage_fields(coverage_resource: dict | None) -> dict:
        """Extract flat plan fields from a FHIR Coverage resource."""
        if not coverage_resource:
            return {"plan_name": None, "plan_id": None, "policy_period": None}
        classes = coverage_resource.get("class", [])
        period = coverage_resource.get("period")
        return {
            "plan_name": classes[0].get("name") if classes else None,
            "plan_id": classes[0].get("value") if classes else None,
            "policy_period": {"start": period.get("start"), "end": period.get("end")} if period else None,
        }

    @staticmethod
    def _parse_item_balance(benefits: list) -> dict | None:
        """Extract balance dict from validation-response benefits."""
        allowed = next((b.get("allowedMoney") for b in benefits if b.get("allowedMoney")), None)
        used = next((b.get("usedMoney") for b in benefits if b.get("usedMoney")), None)
        if not (allowed or used):
            return None
        return {
            "allowed": allowed or {"value": 0.0, "currency": "INR"},
            "used": used or {"value": 0.0, "currency": "INR"},
        }

    @staticmethod
    def _parse_item_procedure(item: dict, benefits: list) -> dict:
        """Extract procedure dict from benefits/auth-requirements item."""
        pos_codings = (item.get("productOrService") or {}).get("coding", [])
        category_codings = (item.get("category") or {}).get("coding", [])
        allowed_money = next((b.get("allowedMoney") for b in benefits if b.get("allowedMoney")), None)

        required_documents = []
        required_questionnaires = []
        for supporting in item.get("authorizationSupporting") or []:
            text = supporting.get("text", "")
            code_entry = (supporting.get("coding") or [{}])[0]
            if text.startswith("fullUrl:"):
                required_questionnaires.append({
                    "id": code_entry.get("code", ""),
                    "display": code_entry.get("display", ""),
                    "url": text.removeprefix("fullUrl:").strip(),
                })
            else:
                required_documents.append({
                    "code": code_entry.get("code", ""),
                    "display": code_entry.get("display", ""),
                })

        return {
            "code": pos_codings[0].get("code") if pos_codings else None,
            "display": pos_codings[0].get("display") if pos_codings else None,
            "category": {"code": category_codings[0].get("code"), "display": category_codings[0].get("display")} if category_codings else None,
            "excluded": item.get("excluded", False),
            "allowed_amount": allowed_money,
            "authorization_required": item.get("authorizationRequired", False),
            "required_documents": required_documents,
            "required_questionnaires": required_questionnaires,
        }

    @staticmethod
    def _parse_insurances(
        fhir_insurance: list,
        bundle_index: dict,
        primary_pmjay_id: str | None,
    ) -> list[dict]:
        """
        Dereference the FHIR insurance array into a flat, self-contained list
        of InsuranceEntry dicts matching InsuranceEntrySpec.

        Each entry resolves Coverage → Patient from the bundle index so that
        consumers never need to touch the raw bundle.
        """
        entries = []
        for ins in fhir_insurance or []:
            coverage_ref = (ins.get("coverage") or {}).get("reference")
            coverage_resource = Fhir._resolve_ref(coverage_ref, bundle_index)

            patient_ref = (coverage_resource.get("beneficiary") or {}).get("reference") if coverage_resource else None
            patient_resource = Fhir._resolve_ref(patient_ref, bundle_index) if patient_ref else None

            patient_fields = Fhir._resolve_patient_fields(patient_resource)
            coverage_fields = Fhir._resolve_coverage_fields(coverage_resource)
            pmjay_id = patient_fields["pmjay_id"]

            entry: dict = {
                "pmjay_id": pmjay_id or "",
                "is_primary": pmjay_id == primary_pmjay_id if pmjay_id else False,
                **patient_fields,
                "inforce": ins.get("inforce", False),
                **coverage_fields,
                "balance": None,
                "procedure": None,
            }

            items = ins.get("item") or []
            if items:
                item = items[0]
                benefits = item.get("benefit") or []
                if any("usedMoney" in b for b in benefits):
                    entry["balance"] = Fhir._parse_item_balance(benefits)
                else:
                    entry["procedure"] = Fhir._parse_item_procedure(item, benefits)

            entries.append(entry)
        return entries

    def process_coverage_eligibility_check_response(
        self, response: dict, headers: dict
    ):
        # Using construct to avoid fhir validation errors
        coverage_eligibility_response_bundle = Bundle.construct(**response)
        bundle_entries = coverage_eligibility_response_bundle.entry or []

        cer_resource = next(
            (
                entry.get("resource")
                for entry in bundle_entries
                if entry.get("resource", {}).get("resourceType")
                == "CoverageEligibilityResponse"
            ),
            None,
        )
        coverage_eligibility_response = CoverageEligibilityResponse.construct(
            **cer_resource
        )

        request_id = headers.get("x-hcx-correlation_id")
        coverage_eligibility_request_instance = (
            CoverageEligibilityRequestModel.objects.filter(external_id=request_id)
        ).first()

        # Determine the primary PMJAY ID from the original request bundle entry.
        # The CoverageEligibilityRequest in the bundle has insurance[0].coverage
        # pointing to a Coverage with subscriberId = the requesting patient's PMJAY ID.
        bundle_index = self._build_bundle_index(bundle_entries)
        primary_pmjay_id = None
        req_resource = next(
            (
                entry.get("resource")
                for entry in bundle_entries
                if entry.get("resource", {}).get("resourceType")
                == "CoverageEligibilityRequest"
            ),
            None,
        )
        if req_resource:
            req_insurances = req_resource.get("insurance") or []
            if req_insurances:
                req_cov_ref = (req_insurances[0].get("coverage") or {}).get(
                    "reference"
                )
                req_coverage = self._resolve_ref(req_cov_ref, bundle_index)
                if req_coverage:
                    primary_pmjay_id = req_coverage.get("subscriberId")

        insurances = self._parse_insurances(
            fhir_insurance=coverage_eligibility_response.insurance,
            bundle_index=bundle_index,
            primary_pmjay_id=primary_pmjay_id,
        )

        coverage_eligibility_response_instance = (
            CoverageEligibilityResponseModel.objects.create(
                request=coverage_eligibility_request_instance,
                outcome=coverage_eligibility_response.outcome,
                error=coverage_eligibility_response.error,
                disposition=coverage_eligibility_response.disposition,
                insurance=insurances,
                meta={
                    "raw_response": response,
                    "raw_headers": headers,
                },
            )
        )

        return (
            coverage_eligibility_response_instance,
            coverage_eligibility_request_instance,
        )

    def process_claim_response(self, response: dict, headers: dict):
        # Using construct to avoid fhir validation errors
        claim_response_bundle = Bundle.construct(**response)

        claim_response = ClaimResponse.construct(
            **next(
                filter(
                    lambda entry: entry.get("resource", {}).get("resourceType")
                    == "ClaimResponse",
                    claim_response_bundle.entry,
                )
            ).get("resource")
        )

        request_id = headers.get("x-hcx-correlation_id")

        claim_instance = ClaimModel.objects.filter(external_id=request_id).first()

        # TODO: use ClaimResponseSpec to create the instance
        claim_response_instance = ClaimResponseModel.objects.create(
            request=claim_instance,
            outcome=claim_response.outcome,
            error=claim_response.error,
            disposition=claim_response.disposition,
            item=claim_response.item,
            add_item=claim_response.addItem,
            total=claim_response.total,
            meta={
                "raw_response": response,
                "raw_headers": headers,
            },
        )

        return (claim_response_instance, claim_instance)

    def process_communication_request(self, response: dict, headers: dict):
        # Using construct to avoid fhir validation errors
        communication_request_bundle = Bundle.construct(**response)

        task = Task.construct(
            **next(
                filter(
                    lambda entry: entry.get("resource", {}).get("resourceType")
                    == "Task",
                    communication_request_bundle.entry,
                )
            ).get("resource")
        )

        communication_request = CommunicationRequest.construct(
            **next(
                filter(
                    lambda entry: entry.get("resource", {}).get("resourceType")
                    == "CommunicationRequest",
                    communication_request_bundle.entry,
                )
            ).get("resource")
        )

        claim_request = Claim.construct(
            **next(
                filter(
                    lambda entry: entry.get("resource", {}).get("resourceType")
                    == "Claim",
                    communication_request_bundle.entry,
                )
            ).get("resource")
        )
        request_id = claim_request.id

        claim_instance = ClaimModel.objects.filter(external_id=request_id).first()

        with transaction.atomic():
            # TODO: use TaskSpec to create the instance
            task_instance = TaskModel.objects.create(
                identifier=task.id,
                status=task.status,
                intent=task.intent,
                priority=task.priority,
                code=task.code,
                authored_on=task.authoredOn,
                description=task.description,
                reason_code=task.reasonCode,
                input=task.input,
                output=task.output,
                claim=claim_instance,
                use_case=TaskUseCaseChoices.COMMUNICATION_REQUEST,
                meta={
                    "raw_response": response,
                    "raw_headers": headers,
                },
            )

            # TODO: use CommunicationRequestSpec to create the instance
            communication_request_instance = CommunicationRequestModel.objects.create(
                identifier=communication_request.id,
                status=communication_request.status,
                priority=communication_request.priority,
                category=communication_request.category,
                authored_on=communication_request.authoredOn,
                payload=communication_request.payload,
                based_on=task_instance,
                about=claim_instance,
                meta={
                    "raw_response": response,
                    "raw_headers": headers,
                },
            )

            task_instance.focus = communication_request_instance
            task_instance.save()

        return (task_instance, communication_request_instance, claim_instance)

    def process_payment_notice_request(self, response: dict, headers: dict):
        # Using construct to avoid fhir validation errors
        payment_notice_request_bundle = Bundle.construct(**response)

        task = Task.construct(
            **next(
                filter(
                    lambda entry: entry.get("resource", {}).get("resourceType")
                    == "Task",
                    payment_notice_request_bundle.entry,
                )
            ).get("resource")
        )

        payment_reconciliation = PaymentReconciliation.construct(
            **next(
                filter(
                    lambda entry: entry.get("resource", {}).get("resourceType")
                    == "PaymentReconciliation",
                    payment_notice_request_bundle.entry,
                )
            ).get("resource")
        )

        claim_request = Claim.construct(
            **next(
                filter(
                    lambda entry: entry.get("resource", {}).get("resourceType")
                    == "Claim",
                    payment_notice_request_bundle.entry,
                ),
                {},
            ).get("resource", {})
        )
        request_id = claim_request.id or payment_notice_request_bundle.id
        # TODO: verify if bundle id is claim id in production

        claim_instance = ClaimModel.objects.filter(external_id=request_id).first()

        with transaction.atomic():
            # TODO: use TaskSpec to create the instance
            task_instance = TaskModel.objects.create(
                identifier=task.id,
                status=task.status,
                intent=task.intent,
                priority=task.priority,
                code=task.code,
                authored_on=task.authoredOn,
                description=task.description,
                reason_code=task.reasonCode,
                input=task.input,
                output=task.output,
                claim=claim_instance,
                use_case=TaskUseCaseChoices.PAYMENT_NOTICE_REQUEST,
                meta={
                    "raw_response": response,
                    "raw_headers": headers,
                },
            )

            # TODO: use CommunicationRequestSpec to create the instance
            payment_reconciliation_instance = PaymentReconciliationModel.objects.create(
                identifier=payment_reconciliation.id,
                status=payment_reconciliation.status,
                period=payment_reconciliation.period,
                outcome=payment_reconciliation.outcome,
                disposition=payment_reconciliation.disposition,
                payment_date=payment_reconciliation.paymentDate,
                payment_amount=payment_reconciliation.paymentAmount,
                payment_identifier=payment_reconciliation.paymentIdentifier,
                detail=payment_reconciliation.detail,
                process_note=payment_reconciliation.processNote,
                request=task_instance,
                claim=claim_instance,
                meta={
                    "raw_response": response,
                    "raw_headers": headers,
                },
            )

            task_instance.focus = payment_reconciliation_instance
            task_instance.save()

        return (task_instance, payment_reconciliation_instance, claim_instance)

    def process_insurance_plan_response(self, response: dict, headers: dict):
        task = TaskModel.objects.filter(
            external_id=headers.get("x-hcx-correlation_id")
        ).first()
        if not task:
            raise Exception("Correlation ID not found")

        # NDHM InsurancePlan bundles are large (often 50-100 MB once decrypted)
        # so we skip the pydantic round-trip and hand the raw bundle dict
        # directly to the ingestor, which fans the tree out into ~25-30k rows
        # using bulk_create inside a single transaction.
        insurance_plan_instance = InsurancePlanIngestor(
            bundle=response,
            task=task,
            raw_response=response,
            raw_headers=headers,
        ).run()

        task.focus = insurance_plan_instance
        task.save()

        return (task, insurance_plan_instance)

    def process_task_response(self, response: dict, headers: dict):
        # FIXME: make this dynamic to handle cancel and reprocess responses

        # Using construct to avoid fhir validation errors
        task_response_bundle = Bundle.construct(**response)

        task_request = TaskModel.objects.filter(
            external_id=headers.get("x-hcx-correlation_id")
        ).first()
        if not task_request:
            raise Exception("Correlation ID not found")

        task = Task.construct(
            **next(
                filter(
                    lambda entry: entry.get("resource", {}).get("resourceType")
                    == "Task",
                    task_response_bundle.entry,
                )
            ).get("resource")
        )

        claim_response = ClaimResponse.construct(
            **next(
                filter(
                    lambda entry: entry.get("resource", {}).get("resourceType")
                    == "ClaimResponse",
                    task_response_bundle.entry,
                )
            ).get("resource")
        )

        claim_instance = task_request.claim

        with transaction.atomic():
            # TODO: use TaskSpec to create the instance
            task_instance = TaskModel.objects.create(
                identifier=task.id,
                status=task.status,
                intent=task.intent,
                priority=task.priority,
                code=task.code,
                authored_on=task.authoredOn,
                description=task.description,
                reason_code=task.reasonCode,
                input=task.input,
                output=task.output,
                claim=claim_instance,
                use_case=TaskUseCaseChoices.CANCEL_RESPONSE,
                meta={
                    "raw_response": response,
                    "raw_headers": headers,
                },
            )

            # TODO: use ClaimResponseSpec to create the instance
            claim_response_instance = ClaimResponseModel.objects.create(
                request=claim_instance,
                outcome=claim_response.outcome,
                error=claim_response.error,
                disposition=claim_response.disposition,
                item=claim_response.item,
                add_item=claim_response.addItem,
                total=claim_response.total,
                meta={
                    "raw_response": response,
                    "raw_headers": headers,
                },
            )

            task_instance.part_of = task_request
            task_instance.focus = claim_response_instance
            task_instance.save()

            if task_instance.code.get("coding")[0].get("code") == "approve":
                claim_instance.status = ClaimStatusChoices.CANCELLED
                claim_instance.save()

        return (task_instance, claim_response_instance, claim_instance)
