from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import filters as drf_filters
from rest_framework.decorators import action
from rest_framework.response import Response

from care.emr.api.viewsets.base import (
    EMRBaseViewSet,
    EMRCreateMixin,
    EMRDestroyMixin,
    EMRListMixin,
    EMRRetrieveMixin,
)
from nhcx.models.coverage_eligibility import CoverageEligibilityRequest
from nhcx.specs.coverage_eligibility import (
    CoverageEligibilityRequestCreateSpec,
    CoverageEligibilityRequestRetrieveSpec,
    CoverageEligibilityRequestStatusChoices,
)


class CoverageEligibilityRequestFilter(filters.FilterSet):
    patient = filters.UUIDFilter(field_name="patient__external_id")
    facility = filters.UUIDFilter(field_name="provider__facility__external_id")


class CoverageEligibilityRequestViewSet(
    EMRCreateMixin,
    EMRListMixin,
    EMRRetrieveMixin,
    EMRDestroyMixin,
    EMRBaseViewSet,
):
    database_model = CoverageEligibilityRequest
    pydantic_model = CoverageEligibilityRequestCreateSpec
    pydantic_retrieve_model = CoverageEligibilityRequestRetrieveSpec
    filter_backends = [filters.DjangoFilterBackend, drf_filters.OrderingFilter]
    filterset_class = CoverageEligibilityRequestFilter
    ordering_fields = [
        "created_date",
        "modified_date",
    ]

    def perform_destroy(self, instance):
        instance.status = CoverageEligibilityRequestStatusChoices.ENTERED_IN_ERROR
        instance.save()
        super().perform_destroy(instance)

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
