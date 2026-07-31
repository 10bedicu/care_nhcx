import json
from datetime import UTC, datetime
from itertools import chain

from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import filters as drf_filters
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from care.emr.api.viewsets.base import (
    EMRBaseViewSet,
    EMRListMixin,
    EMRRetrieveMixin,
)
from nhcx.models.insurance_plan import (
    InsurancePlan,
    InsurancePlanBenefit,
    InsurancePlanCoverage,
    InsurancePlanCoverageBenefit,
    InsurancePlanQuestionnaire,
)
from nhcx.models.provider import Provider
from nhcx.models.task import Task, TaskUseCaseChoices
from nhcx.services.gateway import GatewayService
from nhcx.settings import plugin_settings as settings
from nhcx.specs.insurance_plan import (
    BenefitLookupBody,
    ClaimConditionSpec,
    ClaimExclusionSpec,
    ClaimSupportingInfoRequirementSpec,
    InsurancePlanBenefitDetailSpec,
    InsurancePlanBenefitListSpec,
    InsurancePlanCoverageDetailSpec,
    InsurancePlanCoverageSpec,
    InsurancePlanListSpec,
    InsurancePlanPlanSpec,
    InsurancePlanQuestionnaireDetailSpec,
    InsurancePlanQuestionnaireListSpec,
    InsurancePlanRequestBody,
    InsurancePlanRetrieveSpec,
    _attach_questionnaire_lookup,
    _detach_questionnaire_lookup,
)
from nhcx.utils.dispatch import dispatch
from nhcx.utils.fhir import Fhir
from nhcx.utils.nhcx import NHCX
from nhcx.utils.swagger import pydantic_list


class InsurancePlanFilter(filters.FilterSet):
    name = filters.CharFilter(lookup_expr="icontains")
    status = filters.CharFilter()
    identifier_value = filters.CharFilter()


class InsurancePlanBenefitFilter(filters.FilterSet):
    insurance_plan = filters.UUIDFilter(field_name="insurance_plan__external_id")
    plan_tier = filters.UUIDFilter(field_name="plan__external_id")
    coverage = filters.UUIDFilter(field_name="coverage__external_id")

    type_code = filters.CharFilter()
    coverage_type_code = filters.CharFilter()
    plan_type_code = filters.CharFilter()
    specialty_category_code = filters.CharFilter()
    procedure_type = filters.CharFilter()

    q = filters.CharFilter(method="filter_q")

    def filter_q(self, queryset, name, value):
        return queryset.filter(
            Q(type_display__icontains=value) | Q(type_code__icontains=value)
        )

    min_cost_gte = filters.NumberFilter(field_name="min_cost", lookup_expr="gte")
    max_cost_lte = filters.NumberFilter(field_name="max_cost", lookup_expr="lte")

    authorization_required = filters.BooleanFilter()
    is_day_care = filters.BooleanFilter()
    implant_applicable = filters.BooleanFilter()
    stratification_allowed = filters.BooleanFilter()
    has_copayment = filters.BooleanFilter()
    has_deductible = filters.BooleanFilter()
    has_waiting_period = filters.BooleanFilter()
    has_stratification_qualifier = filters.BooleanFilter()
    has_implant_qualifier = filters.BooleanFilter()
    has_consumable_qualifier = filters.BooleanFilter()
    has_questionnaire = filters.BooleanFilter()
    requires_supporting_info = filters.BooleanFilter()


class InsurancePlanViewSet(EMRListMixin, EMRRetrieveMixin, EMRBaseViewSet):
    database_model = InsurancePlan
    pydantic_read_model = InsurancePlanListSpec
    pydantic_retrieve_model = InsurancePlanRetrieveSpec
    filter_backends = [filters.DjangoFilterBackend, drf_filters.OrderingFilter]
    filterset_class = InsurancePlanFilter
    ordering_fields = ["created_date", "modified_date", "name"]

    def get_queryset(self):
        return InsurancePlan.objects.all().order_by("-modified_date")

    @action(detail=False, methods=["POST"])
    @extend_schema(request=InsurancePlanRequestBody, responses={200: None})
    def request(self, request, *args, **kwargs):
        data = InsurancePlanRequestBody(**request.data)
        provider = get_object_or_404(Provider, facility__external_id=data.facility)

        task = Task.objects.create(
            identifier=str(data.policy.sno),
            status="requested",
            intent="order",
            priority="routine",
            code={
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/financialtaskcode",
                        "code": "status",
                    }
                ]
            },
            authored_on=datetime.now(UTC),
            description=f"Request for insurance plan {data.policy.sno}",
            input=[
                {
                    "type": {
                        "coding": [
                            {
                                "system": "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-task-input-type-code",
                                "code": "policyNumber",
                                "display": "PolicyNumber",
                            }
                        ]
                    },
                    "valueString": data.policy.productid,
                },
                {
                    "type": {
                        "coding": [
                            {
                                "system": "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-task-input-type-code",
                                "code": "providerId",
                                "display": "ProviderId",
                            }
                        ]
                    },
                    "valueString": provider.facility.healthfacility.hf_id,
                },
            ],
            output=[],
            use_case=TaskUseCaseChoices.INSURANCE_PLAN_REQUEST,
            workflow_code="",
        )

        fhir_data = Fhir().create_task_bundle(task)
        fhir_payload = json.loads(fhir_data.json())
        encrypted_payload = NHCX.encrypt(
            data=fhir_payload,
            sender_code=provider.participant_code,
            recipient_code=data.policy.payerid,
            patient_abha_number=data.policy.abhanumber,
            correlation_id=str(task.external_id),
            status="request.initiated",
            workflow_id="",
            log_type="insurance_plan_request",
        )
        dispatch(task, GatewayService.insurance_plan__request, encrypted_payload)

        return Response({"task_id": str(task.external_id)}, status=status.HTTP_200_OK)

    @extend_schema(responses={200: pydantic_list(InsurancePlanPlanSpec)})
    @action(detail=True, methods=["GET"])
    def plans(self, request, *args, **kwargs):
        ip = self.get_object()
        plans = ip.plans.all().prefetch_related("general_costs", "benefits")
        return Response([InsurancePlanPlanSpec.serialize(p).to_json() for p in plans])

    @extend_schema(responses={200: pydantic_list(InsurancePlanCoverageSpec)})
    @action(detail=True, methods=["GET"])
    def coverages(self, request, *args, **kwargs):
        ip = self.get_object()
        coverages = ip.coverages.all().prefetch_related("benefits")
        return Response(
            [InsurancePlanCoverageSpec.serialize(c).to_json() for c in coverages]
        )

    @extend_schema(responses={200: dict})
    @action(detail=True, methods=["GET"])
    def extensions(self, request, *args, **kwargs):
        ip = self.get_object()
        return Response(_serialise_extensions_for(ip))

    @extend_schema(responses={200: pydantic_list(InsurancePlanQuestionnaireListSpec)})
    @action(detail=True, methods=["GET"])
    def questionnaires(self, request, *args, **kwargs):
        ip = self.get_object()
        qs = ip.questionnaires.all().order_by("title")
        return Response(
            [InsurancePlanQuestionnaireListSpec.serialize(q).to_json() for q in qs]
        )


class InsurancePlanCoverageViewSet(EMRRetrieveMixin, EMRBaseViewSet):
    database_model = InsurancePlanCoverage
    pydantic_retrieve_model = InsurancePlanCoverageDetailSpec

    def get_queryset(self):
        return InsurancePlanCoverage.objects.all()

    @extend_schema(responses={200: dict})
    @action(detail=True, methods=["GET"])
    def extensions(self, request, *args, **kwargs):
        coverage = self.get_object()
        return Response(_serialise_extensions_for(coverage))

    @extend_schema(responses={200: pydantic_list(InsurancePlanBenefitListSpec)})
    @action(detail=True, methods=["GET"])
    def benefits(self, request, *args, **kwargs):
        coverage = self.get_object()
        benefits = (
            InsurancePlanBenefit.objects.filter(
                insurance_plan=coverage.insurance_plan,
                coverage_type_code=coverage.type_code or "",
            )
            .select_related("plan")
            .order_by("type_display")
        )
        return Response(
            [InsurancePlanBenefitListSpec.serialize(b).to_json() for b in benefits]
        )


class InsurancePlanBenefitViewSet(EMRListMixin, EMRRetrieveMixin, EMRBaseViewSet):
    database_model = InsurancePlanBenefit
    pydantic_read_model = InsurancePlanBenefitListSpec
    pydantic_retrieve_model = InsurancePlanBenefitDetailSpec
    filter_backends = [filters.DjangoFilterBackend, drf_filters.OrderingFilter]
    filterset_class = InsurancePlanBenefitFilter
    ordering_fields = [
        "type_display",
        "min_cost",
        "max_cost",
        "max_limit_amount",
        "created_date",
    ]

    def get_queryset(self):
        return (
            InsurancePlanBenefit.objects.all()
            .select_related("plan")
            .order_by("type_display")
        )

    @extend_schema(responses={200: dict})
    @action(detail=True, methods=["GET"])
    def extensions(self, request, *args, **kwargs):
        benefit = self.get_object()
        return Response(_rolled_up_extensions_for_benefit(benefit))

    @extend_schema(responses={200: pydantic_list(ClaimSupportingInfoRequirementSpec)})
    @action(detail=True, methods=["GET"])
    def requirements(self, request, *args, **kwargs):
        benefit = self.get_object()
        sisrs = _collect_sisrs_for_benefit(benefit)
        _attach_questionnaire_lookup(benefit.insurance_plan)
        try:
            payload = [
                ClaimSupportingInfoRequirementSpec.serialize(s).to_json() for s in sisrs
            ]
        finally:
            _detach_questionnaire_lookup()
        return Response(payload)

    @extend_schema(responses={200: pydantic_list(InsurancePlanQuestionnaireListSpec)})
    @action(detail=True, methods=["GET"])
    def questionnaires(self, request, *args, **kwargs):
        benefit = self.get_object()
        if not benefit.questionnaire_fhir_ids:
            return Response([])
        qs = benefit.insurance_plan.questionnaires.filter(
            fhir_id__in=benefit.questionnaire_fhir_ids
        )
        return Response(
            [InsurancePlanQuestionnaireListSpec.serialize(q).to_json() for q in qs]
        )

    @extend_schema(
        request=BenefitLookupBody, responses={200: InsurancePlanBenefitDetailSpec}
    )
    @action(detail=False, methods=["POST"])
    def lookup(self, request, *args, **kwargs):
        """Resolve the priced benefit row by (insurance_plan, plan_tier?,
        coverage_type_code?, type_code). When ``plan_tier`` is omitted on a
        multi-plan IP the first match is returned."""
        body = BenefitLookupBody(**request.data)
        qs = InsurancePlanBenefit.objects.filter(
            insurance_plan__external_id=body.insurance_plan,
            type_code=body.type_code,
        )
        if body.plan_tier:
            qs = qs.filter(plan__external_id=body.plan_tier)
        if body.coverage_type_code:
            qs = qs.filter(coverage_type_code=body.coverage_type_code)
        benefit = qs.first()
        if not benefit:
            return Response(
                {
                    "errors": [
                        {"type": "object_not_found", "msg": "No matching benefit"}
                    ]
                },
                status=404,
            )
        return Response(self.get_retrieve_pydantic_model().serialize(benefit).to_json())


class InsurancePlanQuestionnaireViewSet(EMRRetrieveMixin, EMRBaseViewSet):
    database_model = InsurancePlanQuestionnaire
    pydantic_retrieve_model = InsurancePlanQuestionnaireDetailSpec

    def get_queryset(self):
        return InsurancePlanQuestionnaire.objects.all()


def _serialise_extensions_for(parent_obj):
    """Serialise extensions directly attached to ``parent_obj`` (one of
    InsurancePlan / Coverage / CoverageBenefit / Plan / SpecificCostBenefit)
    via its GenericRelation reverse accessors."""
    conditions = list(parent_obj.claim_conditions.all())
    exclusions = list(parent_obj.claim_exclusions.all())
    sisrs = list(parent_obj.supporting_info_requirements.all())

    insurance_plan = _resolve_insurance_plan(parent_obj)
    _attach_questionnaire_lookup(insurance_plan)
    try:
        sisr_payload = [
            ClaimSupportingInfoRequirementSpec.serialize(s).to_json() for s in sisrs
        ]
    finally:
        _detach_questionnaire_lookup()

    return {
        "conditions": [ClaimConditionSpec.serialize(c).to_json() for c in conditions],
        "exclusions": [ClaimExclusionSpec.serialize(e).to_json() for e in exclusions],
        "supporting_info_requirements": sisr_payload,
    }


def _resolve_insurance_plan(obj):
    if isinstance(obj, InsurancePlan):
        return obj
    if hasattr(obj, "insurance_plan"):
        return obj.insurance_plan
    return None


def _collect_sisrs_for_benefit(benefit):
    cov_benefits = InsurancePlanCoverageBenefit.objects.filter(
        coverage=benefit.coverage, type_code=benefit.type_code
    ).prefetch_related("supporting_info_requirements")
    sisrs = list(
        chain.from_iterable(
            cb.supporting_info_requirements.all() for cb in cov_benefits
        )
    )
    if benefit.specific_cost_benefit_id:
        sisrs = (
            list(benefit.specific_cost_benefit.supporting_info_requirements.all())
            + sisrs
        )
    return sisrs


def _rolled_up_extensions_for_benefit(benefit):
    cov_benefits = InsurancePlanCoverageBenefit.objects.filter(
        coverage=benefit.coverage, type_code=benefit.type_code
    ).prefetch_related(
        "claim_conditions", "claim_exclusions", "supporting_info_requirements"
    )
    cov_conditions = list(
        chain.from_iterable(cb.claim_conditions.all() for cb in cov_benefits)
    )
    cov_exclusions = list(
        chain.from_iterable(cb.claim_exclusions.all() for cb in cov_benefits)
    )
    cov_sisrs = list(
        chain.from_iterable(
            cb.supporting_info_requirements.all() for cb in cov_benefits
        )
    )
    sc_conditions = []
    sc_exclusions = []
    sc_sisrs = []
    if benefit.specific_cost_benefit_id:
        scb = benefit.specific_cost_benefit
        sc_conditions = list(scb.claim_conditions.all())
        sc_exclusions = list(scb.claim_exclusions.all())
        sc_sisrs = list(scb.supporting_info_requirements.all())

    _attach_questionnaire_lookup(benefit.insurance_plan)
    try:
        sisr_payload = [
            ClaimSupportingInfoRequirementSpec.serialize(s).to_json()
            for s in sc_sisrs + cov_sisrs
        ]
    finally:
        _detach_questionnaire_lookup()

    return {
        "conditions": [
            ClaimConditionSpec.serialize(c).to_json()
            for c in sc_conditions + cov_conditions
        ],
        "exclusions": [
            ClaimExclusionSpec.serialize(e).to_json()
            for e in sc_exclusions + cov_exclusions
        ],
        "supporting_info_requirements": sisr_payload,
    }
