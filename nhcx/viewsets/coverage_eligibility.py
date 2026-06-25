import json

from django.db.models import Q
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
from nhcx.models import DispatchStatusChoices
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
    encounter = filters.UUIDFilter(method="filter_encounter")
    appointment = filters.UUIDFilter(field_name="appointment__external_id")
    patient = filters.UUIDFilter(field_name="patient__external_id")
    facility = filters.UUIDFilter(field_name="provider__facility__external_id")
    purpose = filters.CharFilter(method="filter_purpose")

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

        # An encounter anchors auth-requirements / claim flows. A pure validation
        # check (wallet balance + demographic verification) can run before an
        # encounter exists, e.g. at registration / appointment time.
        requires_encounter = "auth-requirements" in coverage_eligibility_request.purpose
        if requires_encounter and not coverage_eligibility_request.encounter_id:
            raise ValidationError(
                "An encounter is required before submitting the coverage eligibility request"
            )

        fhir_data = Fhir().create_coverage_eligibility_request_bundle(
            coverage_eligibility_request
        )

        fhir_payload = json.loads(fhir_data.json())

        coverage_eligibility_request.workflow_code = "1"
        coverage_eligibility_request.save(
            update_fields=["workflow_code", "modified_date"]
        )

        encrypted_payload = NHCX.encrypt(
            data=fhir_payload,
            sender_code=coverage_eligibility_request.provider.participant_code,
            recipient_code=coverage_eligibility_request.insurer.get("participant_code"),
            patient_abha_number=coverage_eligibility_request.patient.abha_number.abha_number,
            correlation_id=str(coverage_eligibility_request.external_id),
            status="request.initiated",
            workflow_id="1",
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
