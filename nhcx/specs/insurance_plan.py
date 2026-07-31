from datetime import date, datetime
from decimal import Decimal

from pydantic import UUID4, BaseModel

from care.emr.resources.base import EMRResource
from nhcx.models.insurance_plan import (
    ClaimCondition,
    ClaimExclusion,
    ClaimSupportingInfoRequirement,
    InsurancePlan,
    InsurancePlanBenefit,
    InsurancePlanCoverage,
    InsurancePlanCoverageBenefitLimit,
    InsurancePlanPlan,
    InsurancePlanPlanGeneralCost,
    InsurancePlanPlanSpecificCostBenefitCost,
    InsurancePlanPlanSpecificCostBenefitCostQualifier,
    InsurancePlanQuestionnaire,
)
from nhcx.models.task import Task, TaskUseCaseChoices
from nhcx.services.types.participant import Policy


class InsurancePlanRequestBody(BaseModel):
    policy: Policy
    facility: str


class BenefitLookupBody(BaseModel):
    insurance_plan: UUID4
    plan_tier: UUID4 | None = None
    coverage_type_code: str | None = None
    type_code: str


class InsurancePlanGeneralCostSpec(EMRResource):
    __model__ = InsurancePlanPlanGeneralCost
    __exclude__ = ["plan"]

    id: UUID4 | None = None
    fhir_element_id: str | None = None
    type: dict | None = None
    group_size: int | None = None
    cost_value: Decimal | None = None
    cost_currency: str | None = None
    comment: str | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id


class InsurancePlanCoverageBenefitLimitSpec(EMRResource):
    __model__ = InsurancePlanCoverageBenefitLimit
    __exclude__ = ["benefit"]

    id: UUID4 | None = None
    fhir_element_id: str | None = None
    value_amount: Decimal | None = None
    value_unit: str | None = None
    value_system: str | None = None
    value_code: str | None = None
    code: dict | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id


class InsurancePlanCostQualifierSpec(EMRResource):
    __model__ = InsurancePlanPlanSpecificCostBenefitCostQualifier
    __exclude__ = ["cost"]

    id: UUID4 | None = None
    qualifier: dict | None = None
    qualifier_code: str | None = None
    qualifier_type: str | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id


class InsurancePlanCostSpec(EMRResource):
    __model__ = InsurancePlanPlanSpecificCostBenefitCost
    __exclude__ = ["benefit"]

    id: UUID4 | None = None
    fhir_element_id: str | None = None
    type: dict | None = None
    type_code: str | None = None
    applicability: dict | list | None = None
    value_amount: Decimal | None = None
    value_unit: str | None = None
    qualifiers: list[InsurancePlanCostQualifierSpec] = []

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["qualifiers"] = [
            InsurancePlanCostQualifierSpec.serialize(q).to_json()
            for q in obj.qualifiers.all()
        ]


class ClaimConditionSpec(EMRResource):
    __model__ = ClaimCondition
    __exclude__ = ["parent_content_type", "parent_object_id"]

    id: UUID4 | None = None
    level: str | None = None
    properties: dict | None = None
    procedure_type: str | None = None
    govt_reserved: bool | None = None
    approval_not_required: bool | None = None
    scheduled_tat_approval: bool | None = None
    enhancement_allowed: bool | None = None
    quantity_allowed: int | None = None
    is_day_care: bool | None = None
    implant_applicable: bool | None = None
    multiple_implants_allowed: bool | None = None
    maximum_implants_allowed: int | None = None
    stratification_allowed: bool | None = None
    multiple_stratification_allowed: bool | None = None
    maximum_stratification_allowed: int | None = None
    cyclic_procedure: bool | None = None
    maximum_cycles_allowed: int | None = None
    standalone: bool | None = None
    parent_procedure: str | None = None
    parent_procedures: list[str] = []
    lama_dama_procedure: bool | None = None
    discharge_stages_lama_dama_procedure: str | None = None
    unspecified: bool | None = None
    condition_type: dict | None = None
    code: dict | None = None
    description: str | None = None
    value: dict | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["parent_procedures"] = (
            [c.strip() for c in obj.parent_procedure.split(",") if c.strip()]
            if obj.parent_procedure
            else []
        )


class ClaimExclusionSpec(EMRResource):
    __model__ = ClaimExclusion
    __exclude__ = ["parent_content_type", "parent_object_id"]

    id: UUID4 | None = None
    level: str | None = None
    category: dict | None = None
    category_code: str | None = None
    statements: list[str] | None = None
    items: dict | None = None
    items_codes: list[str] | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id


_REQUIRED_CODES = {"STG", "ADN"}


def _sisr_is_required(code_code: str | None) -> bool:
    """Return True when the supporting-info document is mandatory.

    PMJAY encodes mandatoriness directly in the code:
      - MAND-prefixed codes  →  specific mandatory diagnostic/clinical docs
      - STG                  →  Standard Treatment Guidelines questionnaire
      - ADN                  →  Aadhaar identity proof (universal)
    All other codes (ODN, …) are conditional / on-demand.
    """
    if not code_code:
        return False
    return code_code.startswith("MAND") or code_code in _REQUIRED_CODES


class ClaimSupportingInfoRequirementSpec(EMRResource):
    """``questionnaire`` is resolved at serialise time by matching
    ``documentation_url`` against the IP's bundled Questionnaires; when no
    match is found the field stays null and the frontend renders the raw
    ``documentation_url`` as an external link."""

    __model__ = ClaimSupportingInfoRequirement
    __exclude__ = ["parent_content_type", "parent_object_id"]

    id: UUID4 | None = None
    level: str | None = None
    category: dict | None = None
    category_code: str | None = None
    code: dict | None = None
    code_code: str | None = None
    documentation_url: str | None = None
    questionnaire: dict | None = None
    is_required: bool = False

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["is_required"] = _sisr_is_required(obj.code_code)
        lookup = getattr(cls, "_questionnaire_lookup", None)
        if lookup and obj.documentation_url:
            qid = lookup.get(obj.documentation_url)
            if not qid and "/" in obj.documentation_url:
                tail = obj.documentation_url.rsplit("/", 1)[-1]
                qid = lookup.get(tail) or lookup.get(f"Questionnaire/{tail}")
            if qid:
                titles = getattr(cls, "_questionnaire_titles", {})
                full_urls = getattr(cls, "_questionnaire_full_urls", {})
                external_ids = getattr(cls, "_questionnaire_external_ids", {})
                mapping["questionnaire"] = {
                    "id": external_ids.get(qid, ""),
                    "fhir_id": qid,
                    "title": titles.get(qid, ""),
                    "full_url": full_urls.get(qid, ""),
                }


class InsurancePlanQuestionnaireListSpec(EMRResource):
    __model__ = InsurancePlanQuestionnaire
    __exclude__ = ["insurance_plan", "items", "subject_type", "url", "full_url"]

    id: UUID4 | None = None
    fhir_id: str | None = None
    title: str | None = None
    status: str | None = None
    purpose: str | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id


class InsurancePlanQuestionnaireDetailSpec(EMRResource):
    __model__ = InsurancePlanQuestionnaire
    __exclude__ = ["insurance_plan"]

    id: UUID4 | None = None
    fhir_id: str | None = None
    full_url: str | None = None
    url: str | None = None
    title: str | None = None
    status: str | None = None
    subject_type: list | None = None
    purpose: str | None = None
    items: list | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id


class InsurancePlanPlanSpec(EMRResource):
    __model__ = InsurancePlanPlan
    __exclude__ = ["insurance_plan"]

    id: UUID4 | None = None
    fhir_element_id: str | None = None
    identifiers: list | None = None
    type: dict | None = None
    type_code: str | None = None
    type_display: str | None = None
    n_benefits: int | None = None
    general_costs: list[InsurancePlanGeneralCostSpec] = []

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["type_display"] = _flatten_display_value(obj.type)
        mapping["n_benefits"] = obj.benefits.count()
        mapping["general_costs"] = [
            InsurancePlanGeneralCostSpec.serialize(g).to_json()
            for g in obj.general_costs.all()
        ]


class InsurancePlanCoverageSpec(EMRResource):
    __model__ = InsurancePlanCoverage
    __exclude__ = ["insurance_plan"]

    id: UUID4 | None = None
    fhir_element_id: str | None = None
    type: dict | None = None
    type_code: str | None = None
    type_display: str | None = None
    n_benefits: int | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["n_benefits"] = obj.benefits.count()


class InsurancePlanCoverageDetailSpec(InsurancePlanCoverageSpec):
    n_conditions: int | None = None
    n_exclusions: int | None = None
    n_supporting_info_requirements: int | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        super().perform_extra_serialization(mapping, obj)
        mapping["n_conditions"] = obj.claim_conditions.count()
        mapping["n_exclusions"] = obj.claim_exclusions.count()
        mapping["n_supporting_info_requirements"] = (
            obj.supporting_info_requirements.count()
        )


class InsurancePlanListSpec(EMRResource):
    __model__ = InsurancePlan
    __exclude__ = [
        "request",
        "additional_identifiers",
        "alias",
        "owned_by",
        "administered_by",
        "contact",
        "raw_bundle_id",
        "source_system",
    ]

    id: UUID4 | None = None
    fhir_id: str | None = None
    identifier_system: str | None = None
    identifier_value: str | None = None
    status: str | None = None
    type: list | dict | None = None
    type_code: str | None = None
    name: str | None = None
    period_start: date | None = None
    period_end: date | None = None
    owned_by_name: str | None = None
    administered_by_name: str | None = None
    n_plans: int | None = None
    n_coverages: int | None = None
    n_benefits: int | None = None
    n_questionnaires: int | None = None
    created_date: datetime | None = None
    modified_date: datetime | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["owned_by_name"] = _organisation_display(obj.owned_by)
        mapping["administered_by_name"] = _organisation_display(obj.administered_by)
        mapping["n_plans"] = obj.plans.count()
        mapping["n_coverages"] = obj.coverages.count()
        mapping["n_benefits"] = obj.benefits.count()
        mapping["n_questionnaires"] = obj.questionnaires.count()


class InsurancePlanRetrieveSpec(InsurancePlanListSpec):
    additional_identifiers: list | None = None
    alias: list | None = None
    owned_by: dict | None = None
    administered_by: dict | None = None
    contact: list | None = None
    plans: list[InsurancePlanPlanSpec] = []
    n_conditions: int | None = None
    n_exclusions: int | None = None
    n_supporting_info_requirements: int | None = None
    latest_request: UUID4 | None = None
    latest_request_date: datetime | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        super().perform_extra_serialization(mapping, obj)
        mapping["plans"] = [
            InsurancePlanPlanSpec.serialize(p).to_json() for p in obj.plans.all()
        ]
        mapping["n_conditions"] = obj.claim_conditions.count()
        mapping["n_exclusions"] = obj.claim_exclusions.count()
        mapping["n_supporting_info_requirements"] = (
            obj.supporting_info_requirements.count()
        )
        if getattr(obj, "request", None) and obj.request.identifier:
            latest = (
                Task.objects.filter(
                    identifier=obj.request.identifier,
                    use_case=TaskUseCaseChoices.INSURANCE_PLAN_REQUEST,
                )
                .order_by("-created_date")
                .first()
            )
            if latest:
                mapping["latest_request"] = latest.external_id
                mapping["latest_request_date"] = latest.created_date


class InsurancePlanBenefitListSpec(EMRResource):
    __model__ = InsurancePlanBenefit
    __exclude__ = [
        "insurance_plan",
        "plan",
        "coverage",
        "specific_cost_benefit",
        "coverage_benefit_fhir_ids",
        "questionnaire_fhir_ids",
    ]

    id: UUID4 | None = None
    type_code: str | None = None
    type_display: str | None = None
    coverage_type_code: str | None = None
    coverage_type_display: str | None = None
    plan_type_code: str | None = None
    plan_type_display: str | None = None
    plan_id: UUID4 | None = None
    specialty_category_code: str | None = None
    specialty_category_display: str | None = None
    min_cost: Decimal | None = None
    max_cost: Decimal | None = None
    max_limit_amount: Decimal | None = None
    cost_count: int | None = None
    qualifier_count: int | None = None
    authorization_required: bool | None = None
    is_day_care: bool | None = None
    implant_applicable: bool | None = None
    stratification_allowed: bool | None = None
    procedure_type: str | None = None
    has_stratification_qualifier: bool | None = None
    has_implant_qualifier: bool | None = None
    has_consumable_qualifier: bool | None = None
    has_questionnaire: bool | None = None
    requires_supporting_info: bool | None = None
    supporting_info_count: int | None = None
    condition_count: int | None = None
    exclusion_count: int | None = None

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        mapping["id"] = obj.external_id
        mapping["plan_id"] = obj.plan.external_id if obj.plan_id else None


class InsurancePlanBenefitDetailSpec(InsurancePlanBenefitListSpec):
    __exclude__ = [
        "insurance_plan",
        "plan",
        "coverage",
        "specific_cost_benefit",
    ]

    coverage_id: UUID4 | None = None
    specific_cost_benefit_id: UUID4 | None = None
    coverage_benefit_fhir_ids: list[str] = []
    questionnaire_fhir_ids: list[str] = []
    costs: list[InsurancePlanCostSpec] = []
    limits: list[InsurancePlanCoverageBenefitLimitSpec] = []
    conditions: list[ClaimConditionSpec] = []
    exclusions: list[ClaimExclusionSpec] = []
    supporting_info_requirements: list[ClaimSupportingInfoRequirementSpec] = []
    questionnaires: list[InsurancePlanQuestionnaireListSpec] = []

    @classmethod
    def perform_extra_serialization(cls, mapping, obj):
        super().perform_extra_serialization(mapping, obj)
        mapping["coverage_id"] = obj.coverage.external_id if obj.coverage_id else None
        if obj.specific_cost_benefit_id:
            mapping["specific_cost_benefit_id"] = obj.specific_cost_benefit.external_id

        if obj.specific_cost_benefit_id:
            mapping["costs"] = [
                InsurancePlanCostSpec.serialize(c).to_json()
                for c in obj.specific_cost_benefit.costs.all()
            ]
        else:
            mapping["costs"] = []

        from nhcx.models.insurance_plan import InsurancePlanCoverageBenefit

        cov_benefits = list(
            InsurancePlanCoverageBenefit.objects.filter(
                coverage=obj.coverage,
                type_code=obj.type_code,
            ).prefetch_related(
                "limits",
                "claim_conditions",
                "claim_exclusions",
                "supporting_info_requirements",
            )
        )
        limits = []
        cov_conditions = []
        cov_exclusions = []
        cov_sisrs = []
        for cb in cov_benefits:
            for lim in cb.limits.all():
                limits.append(
                    InsurancePlanCoverageBenefitLimitSpec.serialize(lim).to_json()
                )
            cov_conditions.extend(cb.claim_conditions.all())
            cov_exclusions.extend(cb.claim_exclusions.all())
            cov_sisrs.extend(cb.supporting_info_requirements.all())
        mapping["limits"] = limits

        sc_conditions = []
        sc_exclusions = []
        sc_sisrs = []
        if obj.specific_cost_benefit_id:
            scb = obj.specific_cost_benefit
            sc_conditions = list(scb.claim_conditions.all())
            sc_exclusions = list(scb.claim_exclusions.all())
            sc_sisrs = list(scb.supporting_info_requirements.all())

        mapping["conditions"] = [
            ClaimConditionSpec.serialize(c).to_json()
            for c in sc_conditions + cov_conditions
        ]
        mapping["exclusions"] = [
            ClaimExclusionSpec.serialize(e).to_json()
            for e in sc_exclusions + cov_exclusions
        ]
        _attach_questionnaire_lookup(obj.insurance_plan)
        try:
            mapping["supporting_info_requirements"] = [
                ClaimSupportingInfoRequirementSpec.serialize(s).to_json()
                for s in sc_sisrs + cov_sisrs
            ]
        finally:
            _detach_questionnaire_lookup()

        if obj.questionnaire_fhir_ids:
            qs = obj.insurance_plan.questionnaires.filter(
                fhir_id__in=obj.questionnaire_fhir_ids
            )
            mapping["questionnaires"] = [
                InsurancePlanQuestionnaireListSpec.serialize(q).to_json() for q in qs
            ]
        else:
            mapping["questionnaires"] = []


def _flatten_display_value(codeable_concept):
    """Mirror of nhcx.models.insurance_plan._flatten_display for spec layer."""
    if not codeable_concept:
        return ""
    if isinstance(codeable_concept, list):
        codeable_concept = codeable_concept[0] if codeable_concept else None
        if not codeable_concept:
            return ""
    if not isinstance(codeable_concept, dict):
        return ""
    text = codeable_concept.get("text")
    if text:
        return text
    coding = codeable_concept.get("coding") or []
    if not coding:
        return ""
    first = coding[0] or {}
    return first.get("display") or first.get("code") or ""


def _organisation_display(organisation):
    if not organisation or not isinstance(organisation, dict):
        return ""
    return organisation.get("name") or _flatten_display_value(organisation.get("type"))


def _attach_questionnaire_lookup(insurance_plan):
    """Stash a SISR.documentation_url -> Questionnaire lookup on the spec
    class so ``perform_extra_serialization`` can resolve the questionnaire
    field without an N+1 query."""
    lookup = {}
    titles = {}
    full_urls = {}
    external_ids = {}
    for q in insurance_plan.questionnaires.all():
        titles[q.fhir_id] = q.title or ""
        full_urls[q.fhir_id] = q.full_url or ""
        external_ids[q.fhir_id] = str(q.external_id)
        for key in (q.full_url, q.url, q.fhir_id):
            if key:
                lookup[key] = q.fhir_id
        if q.fhir_id:
            lookup[f"Questionnaire/{q.fhir_id}"] = q.fhir_id
    ClaimSupportingInfoRequirementSpec._questionnaire_lookup = lookup  # noqa: SLF001
    ClaimSupportingInfoRequirementSpec._questionnaire_titles = titles  # noqa: SLF001
    ClaimSupportingInfoRequirementSpec._questionnaire_full_urls = full_urls  # noqa: SLF001
    ClaimSupportingInfoRequirementSpec._questionnaire_external_ids = external_ids  # noqa: SLF001


def _detach_questionnaire_lookup():
    ClaimSupportingInfoRequirementSpec._questionnaire_lookup = None  # noqa: SLF001
    ClaimSupportingInfoRequirementSpec._questionnaire_titles = None  # noqa: SLF001
    ClaimSupportingInfoRequirementSpec._questionnaire_full_urls = None  # noqa: SLF001
    ClaimSupportingInfoRequirementSpec._questionnaire_external_ids = None  # noqa: SLF001
