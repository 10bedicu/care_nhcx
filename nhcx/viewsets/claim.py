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
from nhcx.models.claim_consent import ClaimConsent, ClaimConsentStage
from nhcx.models.task import Task, TaskUseCaseChoices
from nhcx.services.gateway import GatewayService
from nhcx.specs.claim import (
    ClaimCreateSpec,
    ClaimListSpec,
    ClaimRetrieveSpec,
    ClaimSubmitRequestSpec,
    ClaimTaskActionRequestSpec,
    ClaimUseChoices,
    default_cancel_reason_code,
    default_reprocess_reason_code,
    resolve_task_description,
)
from nhcx.specs.task import TaskListSpec, TaskRetrieveSpec
from nhcx.utils.dispatch import dispatch
from nhcx.utils.fhir import Fhir
from nhcx.utils.nhcx import NHCX
from nhcx.utils.workflow_codes import (
    resolve_cancel_workflow,
    resolve_claim_submission_workflow,
    resolve_reprocess_workflow,
)


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
        request=ClaimSubmitRequestSpec,
        responses={200: ClaimRetrieveSpec},
    )
    @action(detail=True, methods=["POST"])
    def submit(self, request, *args, **kwargs):
        claim = self.get_object()

        submit_request = ClaimSubmitRequestSpec.model_validate(request.data or {})
        workflow_code = resolve_claim_submission_workflow(
            claim, force_resubmit=submit_request.resubmit
        )

        fhir_data = Fhir().create_claim_bundle(claim)

        fhir_payload = json.loads(fhir_data.json())

        encrypted_payload = NHCX.encrypt(
            data=fhir_payload,
            sender_code=claim.provider.participant_code,
            recipient_code=claim.insurer.get("participant_code"),
            patient_abha_number=claim.patient.abha_number.abha_number,
            correlation_id=str(claim.external_id),
            status="request.initiated",
            workflow_id=workflow_code.value,
            log_type="claim_submit",
        )

        consent_stage = (
            ClaimConsentStage.CLAIM
            if claim.use == ClaimUseChoices.CLAIM
            else ClaimConsentStage.PREAUTHORIZATION
        )
        claim_consent = ClaimConsent.objects.filter(
            encounter=claim.encounter,
            patient=claim.patient,
            payer_id=claim.insurer.get("participant_code"),
            stage=consent_stage,
        ).first()
        biometric_auth_token = claim_consent.token if claim_consent else None

        if claim.use == ClaimUseChoices.CLAIM:
            dispatch(
                claim,
                GatewayService.claim__submit,
                encrypted_payload,
                biometric_auth_token,
            )
        elif claim.use == ClaimUseChoices.PRE_AUTHORIZATION:
            dispatch(
                claim,
                GatewayService.pre_auth__submit,
                encrypted_payload,
                biometric_auth_token,
            )
        elif claim.use == ClaimUseChoices.PRE_DETERMINATION:
            dispatch(
                claim,
                GatewayService.predetermination__submit,
                encrypted_payload,
                biometric_auth_token,
            )

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
        request=ClaimTaskActionRequestSpec,
        responses={200: TaskRetrieveSpec},
    )
    @action(detail=True, methods=["POST"])
    def cancel(self, request, *args, **kwargs):
        claim = self.get_object()
        claim_flow_id = (claim.meta or {}).get("claim_flow_id") or str(
            claim.external_id
        )

        workflow_code = resolve_cancel_workflow(claim)

        body = ClaimTaskActionRequestSpec(
            **(request.data if isinstance(request.data, dict) else {})
        )
        reason_code = body.reason_code or default_cancel_reason_code()
        description = resolve_task_description(claim, body.description, "Cancel")

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
            description=description,
            reason_code={"coding": [reason_code.model_dump(mode="json")]},
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
                    "valueString": claim_flow_id,
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
                    "valueString": claim_flow_id,
                },
            ],
            output=[],
            claim=claim,
            use_case=TaskUseCaseChoices.CANCEL_REQUEST,
        )

        fhir_data = Fhir().create_task_bundle(task)

        fhir_payload = json.loads(fhir_data.json())

        encrypted_payload = NHCX.encrypt(
            data=fhir_payload,
            sender_code=claim.provider.participant_code,
            recipient_code=claim.insurer.get("participant_code"),
            patient_abha_number=claim.patient.abha_number.abha_number,
            correlation_id=str(task.external_id),
            status="request.initiated",
            workflow_id=workflow_code.value,
            log_type="claim_cancel_request",
        )

        dispatch(task, GatewayService.task__submit, encrypted_payload)

        return Response(
            TaskRetrieveSpec.serialize(task).model_dump(mode="json"),
            status=status.HTTP_200_OK,
        )

    @extend_schema(
        request=ClaimTaskActionRequestSpec,
        responses={200: TaskRetrieveSpec},
    )
    @action(detail=True, methods=["POST"])
    def reprocess(self, request, *args, **kwargs):
        claim = self.get_object()
        claim_flow_id = (claim.meta or {}).get("claim_flow_id") or str(
            claim.external_id
        )

        workflow_code = resolve_reprocess_workflow(claim)

        body = ClaimTaskActionRequestSpec(
            **(request.data if isinstance(request.data, dict) else {})
        )
        reason_code = body.reason_code or default_reprocess_reason_code()
        description = resolve_task_description(claim, body.description, "Reprocess")

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
            description=description,
            reason_code={"coding": [reason_code.model_dump(mode="json")]},
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
                    "valueString": claim_flow_id,
                },
            ],
            output=[],
            claim=claim,
            use_case=TaskUseCaseChoices.REPROCESS_REQUEST,
        )

        fhir_data = Fhir().create_task_bundle(task)

        fhir_payload = json.loads(fhir_data.json())

        encrypted_payload = NHCX.encrypt(
            data=fhir_payload,
            sender_code=claim.provider.participant_code,
            recipient_code=claim.insurer.get("participant_code"),
            patient_abha_number=claim.patient.abha_number.abha_number,
            correlation_id=str(task.external_id),
            status="request.initiated",
            workflow_id=workflow_code.value,
            log_type="claim_reprocess_request",
        )

        dispatch(task, GatewayService.task__submit, encrypted_payload)

        return Response(
            TaskRetrieveSpec.serialize(task).model_dump(mode="json"),
            status=status.HTTP_200_OK,
        )
