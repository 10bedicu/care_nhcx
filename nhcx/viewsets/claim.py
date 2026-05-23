import json
from datetime import UTC, datetime

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
from nhcx.models.claim import Claim
from nhcx.models.member_biometric_auth import MemberBiometricAuth
from nhcx.models.task import Task, TaskUseCaseChoices
from nhcx.services.gateway import GatewayService
from nhcx.specs.claim import (
    ClaimCreateSpec,
    ClaimListSpec,
    ClaimRetrieveSpec,
    ClaimUseChoices,
)
from nhcx.specs.task import TaskListSpec, TaskRetrieveSpec
from nhcx.utils.dispatch import dispatch
from nhcx.utils.fhir import Fhir
from nhcx.utils.nhcx import NHCX


class ClaimFilter(filters.FilterSet):
    encounter = filters.UUIDFilter(field_name="encounter__external_id")
    patient = filters.UUIDFilter(field_name="patient__external_id")
    facility = filters.UUIDFilter(field_name="provider__facility__external_id")


class ClaimViewSet(
    EMRCreateMixin,
    EMRListMixin,
    EMRRetrieveMixin,
    EMRBaseViewSet,
):
    database_model = Claim
    pydantic_model = ClaimCreateSpec
    pydantic_read_model = ClaimListSpec
    pydantic_retrieve_model = ClaimRetrieveSpec
    filter_backends = [filters.DjangoFilterBackend, drf_filters.OrderingFilter]
    filterset_class = ClaimFilter
    ordering_fields = [
        "created_date",
        "modified_date",
    ]

    def get_queryset(self):
        return self.database_model.objects.all().order_by("-modified_date")

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

    @extend_schema(
        request=None,
        responses={200: ClaimRetrieveSpec},
    )
    @action(detail=True, methods=["POST"])
    def submit(self, request, *args, **kwargs):
        claim = self.get_object()

        fhir_data = Fhir().create_claim_bundle(claim)

        with open("claim_submit.json", "w") as f:
            f.write(fhir_data.json())

        fhir_payload = json.loads(fhir_data.json())

        encrypted_payload = NHCX.encrypt(
            data=fhir_payload,
            sender_code=claim.provider.participant_code,
            recipient_code=claim.insurer.get("participant_code"),
            patient_abha_number=claim.patient.abha_number.abha_number,
            correlation_id=str(claim.external_id),
            status="request.initiated",
            workflow_id="15" if claim.use == ClaimUseChoices.CLAIM else "12",
        )

        biometric_auth = MemberBiometricAuth.objects.filter(
            encounter=claim.encounter,
            patient=claim.patient,
            payer_id=claim.insurer.get("participant_code"),
        ).first()
        biometric_auth_token = biometric_auth.token if biometric_auth else None

        if claim.use == ClaimUseChoices.CLAIM:
            dispatch(claim, GatewayService.claim__submit, encrypted_payload)
        elif claim.use == ClaimUseChoices.PRE_AUTHORIZATION:
            dispatch(
                claim,
                GatewayService.pre_auth__submit,
                encrypted_payload,
                biometric_auth_token,
            )
        elif claim.use == ClaimUseChoices.PRE_DETERMINATION:
            dispatch(claim, GatewayService.predetermination__submit, encrypted_payload)

        return Response(
            ClaimRetrieveSpec.serialize(claim).model_dump(mode="json"),
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=None,
        responses={200: TaskListSpec},
    )
    @action(detail=True, methods=["GET"])
    def tasks(self, request, *args, **kwargs):
        claim = self.get_object()

        tasks = Task.objects.filter(claim=claim).order_by("-modified_date")

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(tasks, request)

        if page is not None:
            data = [TaskListSpec.serialize(task).to_json() for task in page]
            return paginator.get_paginated_response(data)

        data = [TaskListSpec.serialize(task).to_json() for task in tasks]
        return Response(data, status=status.HTTP_200_OK)

    @extend_schema(
        request=None,
        responses={200: TaskRetrieveSpec},
    )
    @action(detail=True, methods=["POST"])
    def cancel(self, request, *args, **kwargs):
        claim = self.get_object()

        # TODO: add reason code to the body

        task = Task.objects.create(
            status="requested",
            intent="order",
            priority="routine",
            code={
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/financialtaskcode",
                        "code": "cancel",
                    }
                ]
            },
            authored_on=datetime.now(UTC),
            description=f"Cancel the claim {claim.external_id}",
            input=[
                {
                    "type": {
                        "coding": [
                            {
                                "system": "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-task-input-type-code",
                                "code": "claimNumber",
                            }
                        ]
                    },
                    "valueString": str(claim.external_id),
                },
                {
                    "type": {
                        "coding": [
                            {
                                "system": "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-task-input-type-code",
                                "code": "initimationNumber",
                            }
                        ]
                    },
                    "valueString": str(claim.external_id),
                },
            ],
            output=[],
            claim=claim,
            use_case=TaskUseCaseChoices.CANCEL_REQUEST,
        )

        fhir_data = Fhir().create_task_bundle(task)

        with open("claim_cancel_request.json", "w") as f:
            f.write(fhir_data.json())

        fhir_payload = json.loads(fhir_data.json())

        encrypted_payload = NHCX.encrypt(
            data=fhir_payload,
            sender_code=claim.provider.participant_code,
            recipient_code=claim.insurer.get("participant_code"),
            patient_abha_number=claim.patient.abha_number.abha_number,
            correlation_id=str(task.external_id),
            status="request.initiated",
            workflow_id="",
        )

        dispatch(task, GatewayService.task__submit, encrypted_payload)

        return Response(
            TaskRetrieveSpec.serialize(task).model_dump(mode="json"),
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=None,
        responses={200: TaskRetrieveSpec},
    )
    @action(detail=True, methods=["POST"])
    def reprocess(self, request, *args, **kwargs):
        claim = self.get_object()

        # TODO: add reason code to the body

        task = Task.objects.create(
            status="requested",
            intent="order",
            priority="routine",
            code={
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/financialtaskcode",
                        "code": "reprocess",
                    }
                ]
            },
            authored_on=datetime.now(UTC),
            description=f"Reprocess the claim {claim.external_id}",
            reason_code={
                "coding": [
                    {
                        "system": "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-reason-code",
                        "code": "claimrejected",
                        "display": "Reprocess request due to claim rejected by payer",
                    }
                ]
            },
            input=[
                {
                    "type": {
                        "coding": [
                            {
                                "system": "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-task-input-type-code",
                                "code": "claimNumber",
                            }
                        ]
                    },
                    "valueString": str(claim.external_id),
                },
            ],
            output=[],
            claim=claim,
            use_case=TaskUseCaseChoices.REPROCESS_REQUEST,
        )

        fhir_data = Fhir().create_task_bundle(task)

        with open("claim_cancel_request.json", "w") as f:
            f.write(fhir_data.json())

        fhir_payload = json.loads(fhir_data.json())

        encrypted_payload = NHCX.encrypt(
            data=fhir_payload,
            sender_code=claim.provider.participant_code,
            recipient_code=claim.insurer.get("participant_code"),
            patient_abha_number=claim.patient.abha_number.abha_number,
            correlation_id=str(task.external_id),
            status="request.initiated",
            workflow_id="",
        )

        dispatch(task, GatewayService.task__submit, encrypted_payload)

        return Response(
            TaskRetrieveSpec.serialize(task).model_dump(mode="json"),
            status=status.HTTP_200_OK,
        )
