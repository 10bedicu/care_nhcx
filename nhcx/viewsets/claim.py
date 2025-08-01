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
from nhcx.models.claim import Claim
from nhcx.specs.claim import ClaimCreateSpec, ClaimRetrieveSpec, ClaimStatusChoices


class ClaimFilter(filters.FilterSet):
    encounter = filters.UUIDFilter(field_name="encounter__external_id")
    patient = filters.UUIDFilter(field_name="patient__external_id")
    facility = filters.UUIDFilter(field_name="provider__facility__external_id")


class ClaimViewSet(
    EMRCreateMixin,
    EMRListMixin,
    EMRRetrieveMixin,
    EMRDestroyMixin,
    EMRBaseViewSet,
):
    database_model = Claim
    pydantic_model = ClaimCreateSpec
    pydantic_retrieve_model = ClaimRetrieveSpec
    filter_backends = [filters.DjangoFilterBackend, drf_filters.OrderingFilter]
    filterset_class = ClaimFilter
    ordering_fields = [
        "created_date",
        "modified_date",
    ]

    def perform_destroy(self, instance):
        instance.status = ClaimStatusChoices.ENTERED_IN_ERROR
        instance.save()
        super().perform_destroy(instance)

    @extend_schema(
        request=None,
        responses={200: ClaimRetrieveSpec},
    )
    @action(detail=False, methods=["GET"])
    def latest(self, request, *args, **kwargs):
        filtered_qs = self.filter_queryset(self.get_queryset())

        try:
            claim = filtered_qs.latest("created_date")
        except Claim.DoesNotExist:
            return Response({})

        return Response(self.get_retrieve_pydantic_model().serialize(claim).to_json())
