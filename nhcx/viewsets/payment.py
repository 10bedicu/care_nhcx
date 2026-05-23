import json
from datetime import UTC, datetime

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from care.emr.api.viewsets.base import EMRBaseViewSet
from nhcx.models.payment import PaymentReconciliation
from nhcx.models.task import Task, TaskUseCaseChoices
from nhcx.services.gateway import GatewayService
from nhcx.specs.payment import PaymentReconciliationRetrieveSpec
from nhcx.utils.dispatch import dispatch
from nhcx.utils.fhir import Fhir
from nhcx.utils.nhcx import NHCX


class PaymentViewSet(EMRBaseViewSet):
    database_model = PaymentReconciliation

    @extend_schema(
        request=None,
        responses={200: PaymentReconciliationRetrieveSpec},
    )
    @action(detail=True, methods=["POST"])
    def acknowledge(self, request, *args, **kwargs):
        payment_reconciliation = self.get_object()
        previous_task = payment_reconciliation.request
        claim = payment_reconciliation.claim

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
            description=f"Response to {previous_task.description or previous_task.identifier}",
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
                }
            ],
            part_of=previous_task,
            claim=claim,
            use_case=TaskUseCaseChoices.PAYMENT_NOTICE_RESPONSE,
        )

        fhir_data = Fhir().create_task_bundle(task)

        with open("payment_notice_acknowledge.json", "w") as f:
            f.write(fhir_data.json())

        fhir_payload = json.loads(fhir_data.json())

        encrypted_payload = NHCX.encrypt(
            data=fhir_payload,
            sender_code=claim.provider.participant_code,
            recipient_code=claim.insurer.get("participant_code"),
            patient_abha_number=claim.patient.abha_number.abha_number,
            correlation_id=previous_task.meta.get("raw_headers", {}).get(
                "x-hcx-correlation_id"
            ),
            status="response.complete",
            workflow_id="",
        )

        dispatch(task, GatewayService.payment_notice__on_request, encrypted_payload)

        return Response(
            PaymentReconciliationRetrieveSpec.serialize(
                payment_reconciliation
            ).model_dump(mode="json"),
            status=status.HTTP_200_OK,
        )
