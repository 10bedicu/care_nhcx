from django.db.models import Q
from django.shortcuts import get_object_or_404
from django_filters import rest_framework as filters
from drf_spectacular.utils import extend_schema
from rest_framework import filters as drf_filters
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from care.emr.api.viewsets.base import (
    EMRBaseViewSet,
    EMRCreateMixin,
    EMRDestroyMixin,
    EMRListMixin,
    EMRRetrieveMixin,
)
from care.emr.models.encounter import Encounter
from nhcx.models import DispatchStatusChoices
from nhcx.models.coverage_eligibility import CoverageEligibilityRequest
from nhcx.specs.coverage_eligibility import (
    CoverageEligibilityRequestCreateSpec,
    CoverageEligibilityRequestLinkEncounterSpec,
    CoverageEligibilityRequestListSpec,
    CoverageEligibilityRequestRetrieveSpec,
)
from nhcx.utils.coverage_eligibility_check import (
    create_wallet_check_from_request,
    dispatch_coverage_eligibility_check,
)
from nhcx.utils.coverage_eligibility_dedupe import dedupe_requests_by_policy
from nhcx.utils.coverage_eligibility_link import link_encounter_to_request


class CoverageEligibilityRequestFilter(filters.FilterSet):
    encounter = filters.UUIDFilter(method="filter_encounter")
    appointment = filters.UUIDFilter(field_name="appointment__external_id")
    patient = filters.UUIDFilter(field_name="patient__external_id")
    facility = filters.UUIDFilter(field_name="provider__facility__external_id")
    purpose = filters.CharFilter(method="filter_purpose")
    created_after = filters.IsoDateTimeFilter(field_name="created_date", lookup_expr="gte")
    encounter__isnull = filters.BooleanFilter(field_name="encounter", lookup_expr="isnull")
    is_automatic = filters.BooleanFilter(field_name="is_automatic")

    def filter_encounter(self, queryset, name, value):
        return queryset.filter(
            Q(encounter__external_id=value)
            | Q(appointment__associated_encounter__external_id=value)
        )

    def filter_purpose(self, queryset, name, value):
        return queryset.filter(purpose__contains=[value])


class CoverageEligibilityRequestViewSet(
    EMRCreateMixin,
    EMRListMixin,
    EMRRetrieveMixin,
    EMRDestroyMixin,
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

    def validate_destroy(self, instance):
        # Only un-dispatched drafts can be removed; once a request has been sent
        # to the payer it is an immutable record of what was submitted.
        if instance.dispatch_status != DispatchStatusChoices.PENDING:
            raise ValidationError(
                "This coverage eligibility request has already been submitted "
                "to the payer and can no longer be removed."
            )

    def list(self, request, *args, **kwargs):
        unique_by_policy = request.query_params.get(
            "unique_by_policy", ""
        ).lower() in {"true", "1", "yes"}
        if not unique_by_policy:
            return super().list(request, *args, **kwargs)

        queryset = self.filter_queryset(self.get_queryset())
        deduped = dedupe_requests_by_policy(list(queryset))
        paginator = self.pagination_class()
        page = paginator.paginate_queryset(deduped, request)
        if page is not None:
            data = [self.serialize_list(obj) for obj in page]
            return paginator.get_paginated_response(data)
        data = [self.serialize_list(obj) for obj in deduped]
        return Response(data)

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

        if not coverage_eligibility_request.encounter_id:
            appointment = coverage_eligibility_request.appointment
            if appointment and appointment.associated_encounter_id:
                coverage_eligibility_request.encounter = (
                    appointment.associated_encounter
                )
                coverage_eligibility_request.save(update_fields=["encounter"])

        requires_encounter = "auth-requirements" in coverage_eligibility_request.purpose
        if requires_encounter and not coverage_eligibility_request.encounter_id:
            raise ValidationError(
                "An encounter is required before submitting the coverage eligibility request"
            )

        dispatch_coverage_eligibility_check(coverage_eligibility_request)

        return Response(
            CoverageEligibilityRequestRetrieveSpec.serialize(
                coverage_eligibility_request
            ).model_dump(mode="json"),
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=None,
        responses={200: CoverageEligibilityRequestRetrieveSpec},
    )
    @action(detail=True, methods=["POST"], url_path="wallet_check")
    def wallet_check(self, request, *args, **kwargs):
        source = self.get_object()

        wallet_request = create_wallet_check_from_request(source)

        return Response(
            CoverageEligibilityRequestRetrieveSpec.serialize(wallet_request).model_dump(
                mode="json"
            ),
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=CoverageEligibilityRequestLinkEncounterSpec,
        responses={200: CoverageEligibilityRequestRetrieveSpec},
    )
    @action(detail=True, methods=["POST"], url_path="link_encounter")
    def link_encounter(self, request, *args, **kwargs):
        coverage_eligibility_request = self.get_object()
        body = CoverageEligibilityRequestLinkEncounterSpec.model_validate(
            request.data
        )
        encounter = get_object_or_404(
            Encounter.objects.select_related("facility", "patient"),
            external_id=body.encounter,
        )
        link_encounter_to_request(coverage_eligibility_request, encounter)
        coverage_eligibility_request.refresh_from_db()

        return Response(
            CoverageEligibilityRequestRetrieveSpec.serialize(
                coverage_eligibility_request
            ).model_dump(mode="json"),
            status=status.HTTP_200_OK,
        )
