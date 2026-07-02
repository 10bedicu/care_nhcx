import json
from datetime import UTC, datetime

from django.contrib.contenttypes.models import ContentType
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from care.emr.api.viewsets.base import EMRBaseViewSet, EMRCreateMixin, EMRRetrieveMixin
from nhcx.models.communication import Communication
from nhcx.models.task import Task, TaskUseCaseChoices
from nhcx.services.gateway import GatewayService
from nhcx.specs.claim import ClaimUseChoices
from nhcx.specs.communication import (
    CommunicationCreateSpec,
    CommunicationRetrieveSpec,
    CommunicationStatusChoices,
)
from nhcx.utils.dispatch import dispatch
from nhcx.utils.fhir import Fhir
from nhcx.utils.nhcx import NHCX


class CommunicationViewSet(
    EMRCreateMixin,
    EMRRetrieveMixin,
    EMRBaseViewSet,
):
    database_model = Communication
    pydantic_model = CommunicationCreateSpec
    pydantic_retrieve_model = CommunicationRetrieveSpec

    @extend_schema(
        request=None,
        responses={200: CommunicationRetrieveSpec},
    )
    @action(detail=True, methods=["POST"])
    def send(self, request, *args, **kwargs):
        communication = self.get_object()
        previous_task = communication.based_on.based_on
        claim = communication.about

        workflow_code = "151" if claim.use == ClaimUseChoices.CLAIM else "19"

        task = Task.objects.create(
            status="completed",
            intent=previous_task.intent,
            priority=previous_task.priority,
            code={
                "coding": [
                    {
                        "system": "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-task-codes",
                        "code": "deliver",
                    }
                ]
            },
            authored_on=datetime.now(UTC),
            description=f"Response to {previous_task.description or previous_task.identifier}",
            input=[
                {
                    "type": {
                        "coding": [
                            {
                                "system": "http://terminology.hl7.org/CodeSystem/financialtaskinputtype",
                                "code": "include",
                            }
                        ]
                    },
                    "valueReference": {
                        "reference": f"urn:uuid:{communication.external_id}",
                        "display": "Communication",
                    },
                }
            ],
            output=[],
            part_of=previous_task,
            claim=claim,
            use_case=TaskUseCaseChoices.COMMUNICATION_RESPONSE,
            focus_type=ContentType.objects.get_for_model(Communication),
            focus_id=communication.id,
            workflow_code=workflow_code,
        )

        communication.part_of = task
        communication.status = CommunicationStatusChoices.COMPLETED
        communication.sent = datetime.now(UTC)
        communication.save()

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
            workflow_id=workflow_code,
            log_type="communication_send",
        )

        dispatch(task, GatewayService.communication__on_request, encrypted_payload)

        return Response(
            CommunicationRetrieveSpec.serialize(communication).model_dump(mode="json"),
            status=status.HTTP_200_OK,
        )
