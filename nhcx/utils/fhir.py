from datetime import UTC, datetime
from functools import wraps
from uuid import uuid4

from django.db import models
from django.db.models import Value
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
from fhir.resources.R4B.humanname import HumanName
from fhir.resources.R4B.identifier import Identifier
from fhir.resources.R4B.meta import Meta
from fhir.resources.R4B.money import Money
from fhir.resources.R4B.organization import Organization
from fhir.resources.R4B.patient import Patient
from fhir.resources.R4B.period import Period
from fhir.resources.R4B.practitioner import Practitioner
from fhir.resources.R4B.quantity import Quantity
from fhir.resources.R4B.reference import Reference
from fhir.resources.R4B.resource import Resource
from pydantic import UUID4, BaseModel

from care.emr.models.base import EMRBaseModel
from care.emr.models.condition import Condition as ConditionModel
from care.emr.models.file_upload import FileUpload
from care.emr.models.patient import Patient as PatientModel
from care.emr.resources.common.coding import Coding as CodingSpec
from care.facility.models import Facility as FacilityModel
from care.users.models import User as UserModel
from nhcx.models.claim import Claim as ClaimModel
from nhcx.models.claim import ClaimResponse as ClaimResponseModel
from nhcx.models.coverage_eligibility import (
    CoverageEligibilityRequest as CoverageEligibilityRequestModel,
)
from nhcx.models.coverage_eligibility import (
    CoverageEligibilityResponse as CoverageEligibilityResponseModel,
)
from nhcx.services.types.participant import Participant, Policy
from nhcx.settings import plugin_settings as settings

CARE_IDENTIFIER_SYSTEM = settings.BACKEND_DOMAIN


class Fhir:
    def __init__(self):
        self._profiles = {}
        self._resource_id_url_map = {}

        self._participants_external_id_map = {}
        self._policies_external_id_map = {}

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
                self._resource_id_url_map[cache_key] = uuid4()
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
        return f"urn:uuid:{self._resource_id_url_map.get(key, uuid4())}"

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
                # FIXME: add abha number
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
                )
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
                )
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

        return Organization(
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

    @cache_profiles(Condition.get_resource_type())
    def _condition(self, condition: ConditionModel):
        id = str(condition.external_id)

        return Condition(
            id=id,
            # FIXME: expand this
            # identifier=[Identifier(value=id)],
            # category=[
            #     CodeableConcept(
            #         coding=[
            #             Coding(
            #                 system="http://terminology.hl7.org/CodeSystem/condition-category",
            #                 code=condition.category,
            #                 display=condition.category,
            #             )
            #         ],
            #     )
            # ],
            # verificationStatus=CodeableConcept(
            #     coding=[
            #         Coding(
            #             system="http://terminology.hl7.org/CodeSystem/condition-ver-status",
            #             code=condition.verification_status,
            #             display=condition.verification_status,
            #         )
            #     ]
            # ),
            code=CodeableConcept(
                coding=[Coding(**condition.code)],
            ),
            subject=self._reference(self._patient(condition.patient)),
        )

    def _attachment(self, attachment: FileUpload):
        id = str(attachment.external_id)
        url = attachment.files_manager.read_signed_url(attachment)

        return Attachment(
            id=id,
            title=attachment.name,
            url=url,
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
            identifier=[Identifier(value=id)],
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
                        abha_number_parsed=coverage.policy.abhanumber.replace("-", "")
                    )
                    .first()
                )
            ),
            payor=[
                self._reference(self._participant_to_organization(coverage.insurer))
            ],
            status="active",
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
            status=request.coverage.status,
            priority=self._coding_to_codable_concept(
                CodingSpec(
                    system="http://terminology.hl7.org/CodeSystem/processpriority",
                    code=request.priority,
                )
            ),
            purpose=request.purpose,
            created=request.created_date.isoformat(),
            patient=self._reference(self._patient(request.patient)),
            enterer=self._reference(self._practitioner(request.created_by)),
            provider=self._reference(self._organization(request.provider.facility)),
            insurer=self._reference(
                self._participant_to_organization(Participant(**request.insurer))
            ),
            supportingInfo=[
                CoverageEligibilityRequestSupportingInfo(
                    sequence=supporting_info.get("sequence"),
                    information=[
                        # FIXME: add support for observation and document reference
                    ],
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
                        for diagnosis in item.get("diagnosis")
                    ],
                )
                for item in request.item
            ],
        )

    def _claim(self, claim: ClaimModel):
        id = str(claim.external_id)

        return Claim(
            id=id,
            meta=Meta(
                profile=["https://nrces.in/ndhm/fhir/r4/StructureDefinition/Claim"],
            ),
            identifier=[Identifier(value=id)],
            status=claim.status,
            type=self._coding_to_codable_concept(CodingSpec(**claim.type)),
            use=claim.use,
            priority=self._coding_to_codable_concept(
                CodingSpec(
                    system="http://terminology.hl7.org/CodeSystem/processpriority",
                    code=claim.priority,
                )
            ),
            created=claim.created_date.isoformat(),
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
                    reference=related.get("reference"),
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
                    type=self._coding_to_codable_concept(
                        CodingSpec(**diagnosis.get("type"))
                    )
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
                    type=self._coding_to_codable_concept(
                        CodingSpec(**procedure.get("type"))
                    )
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
                    date=procedure.get("date").isoformat()
                    if procedure.get("date")
                    else None,
                )
                for procedure in claim.procedure
            ]
            if claim.procedure
            else None,
            supportingInfo=[
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
                    valueAttachment=self._attachment(
                        FileUpload.objects.filter(
                            external_id=supporting_info.get("value_attachment")
                        ).first()
                    )
                    if supporting_info.get("value_attachment")
                    else None,
                )
                for supporting_info in claim.supporting_info
            ]
            if claim.supporting_info
            else None,
            item=[
                ClaimItem(
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
                    programCode=[
                        self._coding_to_codable_concept(CodingSpec(**program_code))
                        for program_code in item.get("program_code")
                    ]
                    if item.get("program_code")
                    else None,
                    servicedPeriod=Period(**item.get("serviced_period"))
                    if item.get("serviced_period")
                    else None,
                    unitPrice=Money(
                        value=item.get("unit_price"),
                        currency="INR",
                    )
                    if item.get("unit_price")
                    else None,
                    quantity=Quantity(**item.get("quantity"))
                    if item.get("quantity")
                    else None,
                    net=Money(
                        value=(
                            (item.get("unit_price", 0))
                            * (item.get("quantity", {}).get("value", 1))
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
                        (item.get("unit_price", 0))
                        * (item.get("quantity", {}).get("value", 1))
                        for item in claim.item
                    )
                ),
                currency="INR",
            ),
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
                    "https://ig.hcxprotocol.io/v0.7.1/StructureDefinition-CoverageEligibilityRequestBundle.html"
                ],
                lastUpdated=coverage_eligibility_request.modified_date.isoformat(),
            ),
            identifier=Identifier(value=id, system=f"{CARE_IDENTIFIER_SYSTEM}/bundle"),
            type="collection",
            timestamp=datetime.now(UTC).isoformat(),
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
                    "https://ig.hcxprotocol.io/v0.7.1/StructureDefinition-ClaimRequestBundle.html"
                ],
                lastUpdated=claim.modified_date.isoformat(),
            ),
            identifier=Identifier(value=id, system=f"{CARE_IDENTIFIER_SYSTEM}/bundle"),
            type="collection",
            timestamp=datetime.now(UTC).isoformat(),
            entry=[
                self._bundle_entry(self._claim(claim)),
                *[self._bundle_entry(profile) for profile in self.cached_profiles()],
            ],
        )

    def process_coverage_eligibility_check_response(
        self, response: dict, headers: dict | None = None
    ):
        # Using construct to avoid fhir validation errors
        coverage_eligibility_response_bundle = Bundle.construct(**response)

        coverage_eligibility_response = CoverageEligibilityResponse.construct(
            **next(
                filter(
                    lambda entry: entry.get("resource", {}).get("resourceType")
                    == "CoverageEligibilityResponse",
                    coverage_eligibility_response_bundle.entry,
                )
            ).get("resource")
        )

        coverage_eligibility_request = CoverageEligibilityRequest.construct(
            **next(
                filter(
                    lambda entry: entry.get("resource", {}).get("resourceType")
                    == "CoverageEligibilityRequest",
                    coverage_eligibility_response_bundle.entry,
                )
            ).get("resource")
        )
        request_id = coverage_eligibility_request.id

        coverage_eligibility_request_instance = (
            CoverageEligibilityRequestModel.objects.filter(external_id=request_id)
        ).first()

        # TODO: use CoverageEligibilityResponseSpec to create the instance
        coverage_eligibility_response_instance = (
            CoverageEligibilityResponseModel.objects.create(
                request=coverage_eligibility_request_instance,
                outcome=coverage_eligibility_response.outcome,
                error=coverage_eligibility_response.error,
                disposition=coverage_eligibility_response.disposition,
                insurance=coverage_eligibility_response.insurance,
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

    def process_claim_response(self, response: dict, headers: dict | None = None):
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

        claim_request = Claim.construct(
            **next(
                filter(
                    lambda entry: entry.get("resource", {}).get("resourceType")
                    == "Claim",
                    claim_response_bundle.entry,
                )
            ).get("resource")
        )
        request_id = claim_request.id

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
