import json
from datetime import UTC, datetime

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from care.emr.api.viewsets.base import EMRBaseViewSet
from nhcx.models.payment import PaymentNotice
from nhcx.models.task import Task, TaskUseCaseChoices
from nhcx.services.gateway import GatewayService
from nhcx.services.payment import complete_payment_for_notice
from nhcx.specs.payment import PaymentNoticeRetrieveSpec
from nhcx.utils.dispatch import dispatch
from nhcx.utils.fhir import Fhir
from nhcx.utils.nhcx import NHCX
from nhcx.utils.workflow_codes import resolve_payment_acknowledge_workflow


class PaymentViewSet(EMRBaseViewSet):
    database_model = PaymentNotice

    @extend_schema(
        request=None,
        responses={200: PaymentNoticeRetrieveSpec},
    )
    @action(detail=True, methods=["POST"])
    def acknowledge(self, request, *args, **kwargs):
        payment_notice = self.get_object()
        previous_task = payment_notice.request
        claim = payment_notice.claim
        claim_flow_id = (claim.meta or {}).get("claim_flow_id") or str(
            claim.external_id
        )

        task = Task.objects.create(
            status="completed",
            intent=previous_task.intent,
            priority=previous_task.priority,
            code={
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/financialtaskcode",
                        "code": "status",
                    }
                ]
            },
            authored_on=datetime.now(UTC),
            description=f"Received the payment {claim_flow_id}",
            input=[],
            output=[
                {
                    "type": {
                        "coding": [
                            {
                                "system": "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-task-output-type",
                                "code": "status",
                            }
                        ]
                    },
                    "valueCodeableConcept": {
                        "coding": [
                            {
                                "system": "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-task-output-value",
                                "code": "paymentack",
                                "display": "Payment is acknowledged",
                            }
                        ]
                    },
                },
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
            part_of=previous_task,
            claim=claim,
            use_case=TaskUseCaseChoices.PAYMENT_NOTICE_RESPONSE,
            workflow_code=resolve_payment_acknowledge_workflow().value,
        )

        fhir_data = Fhir().create_task_bundle(task)

        fhir_payload = json.loads(fhir_data.json())

        encrypted_payload = NHCX.encrypt(
            data=fhir_payload,
            sender_code=claim.provider.participant_code,
            recipient_code=claim.insurer.get("participant_code"),
            patient_abha_number=claim.insurance[0].get("policy", {}).get("abhanumber"),
            correlation_id=previous_task.meta.get("raw_headers", {}).get(
                "x-hcx-correlation_id"
            ),
            status="response.complete",
            workflow_id=resolve_payment_acknowledge_workflow().value,
            log_type="payment_notice_acknowledge",
        )

        dispatch(task, GatewayService.payment_notice__on_request, encrypted_payload)

        try:
            payment_notice.payment_reconciliation = complete_payment_for_notice(
                payment_notice
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        payment_notice.save(update_fields=["payment_reconciliation", "modified_date"])

        return Response(
            PaymentNoticeRetrieveSpec.serialize(payment_notice).model_dump(mode="json"),
            status=status.HTTP_200_OK,
        )
