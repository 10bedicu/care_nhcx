import json

from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import filters as drf_filters
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from care.emr.api.viewsets.base import (
    EMRBaseViewSet,
    EMRCreateMixin,
    EMRListMixin,
    EMRRetrieveMixin,
)
from nhcx.models.coverage_eligibility import CoverageEligibilityRequest
from nhcx.services.gateway import GatewayService
from nhcx.specs.coverage_eligibility import (
    CoverageEligibilityRequestCreateSpec,
    CoverageEligibilityRequestListSpec,
    CoverageEligibilityRequestRetrieveSpec,
)
from nhcx.utils.dispatch import dispatch
from nhcx.utils.fhir import Fhir
from nhcx.utils.nhcx import NHCX


class CoverageEligibilityRequestFilter(filters.FilterSet):
    encounter = filters.UUIDFilter(field_name="encounter__external_id")
    patient = filters.UUIDFilter(field_name="patient__external_id")
    facility = filters.UUIDFilter(field_name="provider__facility__external_id")
    purpose = filters.CharFilter(method="filter_purpose")

    def filter_purpose(self, queryset, name, value):
        return queryset.filter(purpose__contains=[value])


class CoverageEligibilityRequestViewSet(
    EMRCreateMixin,
    EMRListMixin,
    EMRRetrieveMixin,
    EMRBaseViewSet,
):
    database_model = CoverageEligibilityRequest
    pydantic_model = CoverageEligibilityRequestCreateSpec
    pydantic_read_model = CoverageEligibilityRequestListSpec
    pydantic_retrieve_model = CoverageEligibilityRequestRetrieveSpec
    filter_backends = [filters.DjangoFilterBackend, drf_filters.OrderingFilter]
    filterset_class = CoverageEligibilityRequestFilter
    ordering_fields = [
        "created_date",
        "modified_date",
    ]

    def get_queryset(self):
        return self.database_model.objects.all().order_by("-modified_date")

    @extend_schema(
        request=None,
        responses={200: CoverageEligibilityRequestRetrieveSpec},
    )
    @action(detail=False, methods=["GET"])
    def latest(self, request, *args, **kwargs):
        filtered_qs = self.filter_queryset(self.get_queryset())

        try:
            coverage_eligibility_request = filtered_qs.latest("created_date")
        except CoverageEligibilityRequest.DoesNotExist:
            return Response({})

        return Response(
            self.get_retrieve_pydantic_model()
            .serialize(coverage_eligibility_request)
            .to_json()
        )

    @extend_schema(
        request=None,
        responses={200: CoverageEligibilityRequestRetrieveSpec},
    )
    @action(detail=True, methods=["POST"])
    def check(self, request, *args, **kwargs):
        coverage_eligibility_request = self.get_object()

        fhir_data = Fhir().create_coverage_eligibility_request_bundle(
            coverage_eligibility_request
        )

        fhir_payload = json.loads(fhir_data.json())

        encrypted_payload = NHCX.encrypt(
            data=fhir_payload,
            sender_code=coverage_eligibility_request.provider.participant_code,
            recipient_code=coverage_eligibility_request.insurer.get("participant_code"),
            patient_abha_number=coverage_eligibility_request.patient.abha_number.abha_number,
            correlation_id=str(coverage_eligibility_request.external_id),
            status="request.initiated",
            log_type="coverage_eligibility_request_check",
        )

        dispatch(
            coverage_eligibility_request,
            GatewayService.coverage_eligibility__check,
            encrypted_payload,
        )

        return Response(
            CoverageEligibilityRequestRetrieveSpec.serialize(
                coverage_eligibility_request
            ).model_dump(mode="json"),
            status=status.HTTP_200_OK,
        )
