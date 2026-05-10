import json
from datetime import UTC, datetime

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from care.emr.api.viewsets.base import EMRBaseViewSet, EMRRetrieveMixin
from nhcx.models.provider import Provider
from nhcx.models.task import Task, TaskUseCaseChoices
from nhcx.services.gateway import GatewayService
from nhcx.settings import plugin_settings as settings
from nhcx.specs.insurance_plan import (
    InsurancePlanRequestBody,
    InsurancePlanRetrieveSpec,
)
from nhcx.utils.fhir import Fhir
from nhcx.utils.nhcx import NHCX


class InsurancePlanViewSet(EMRRetrieveMixin, EMRBaseViewSet):
    pydantic_retrieve_model = InsurancePlanRetrieveSpec

    def get_object(self):
        try:
            task = Task.objects.filter(
                identifier=self.kwargs[self.lookup_field],
                use_case=TaskUseCaseChoices.INSURANCE_PLAN_REQUEST,
                focus_type__isnull=False,
                focus_id__isnull=False,
            ).latest("created_date")
        except Task.DoesNotExist as err:
            from django.http import Http404

            raise Http404("No Task matches the given query.") from err
        return task.focus

    @action(detail=False, methods=["POST"])
    @extend_schema(
        request=InsurancePlanRequestBody,
        responses={200: None},
    )
    def request(self, request, *args, **kwargs):
        data = InsurancePlanRequestBody(**request.data)
        provider = get_object_or_404(Provider, facility__external_id=data.facility)

        task = Task.objects.create(
            identifier=str(data.policy.sno),  # This is set to filter the insurance plan
            status="requested",
            intent="order",
            priority="routine",
            code={
                "coding": [
                    {
                        "system": "http://terminology.hl7.org/CodeSystem/financialtaskcode",
                        "code": "status",
                    }
                ]
            },
            authored_on=datetime.now(UTC),
            description=f"Request for insurance plan {data.policy.sno}",
            input=[
                {
                    "type": {
                        "coding": [
                            {
                                "system": "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-task-input-type-code",
                                "code": "policyNumber",
                                "display": "PolicyNumber",
                            }
                        ]
                    },
                    "valueString": data.policy.productname
                    if settings.PAYER == "PMJAY"
                    else "100217",  # TODO: REPLACE_AFTER_TESTING: replace this with self.insurance[0].policy.payerid after testing
                },
                {
                    "type": {
                        "coding": [
                            {
                                "system": "https://nrces.in/ndhm/fhir/r4/CodeSystem/ndhm-task-input-type-code",
                                "code": "providerId",
                                "display": "ProviderId",
                            }
                        ]
                    },
                    "valueString": provider.facility.healthfacility.hf_id
                    if settings.PAYER == "PMJAY"
                    else "32722",  # TODO: REPLACE_AFTER_TESTING: replace this with self.insurance[0].policy.payerid after testing
                },
            ],
            output=[],
            use_case=TaskUseCaseChoices.INSURANCE_PLAN_REQUEST,
        )

        fhir_data = Fhir().create_task_bundle(task)

        with open("insurance_plan_request.json", "w") as f:
            f.write(fhir_data.json())

        fhir_payload = json.loads(fhir_data.json())

        print("_--------------------------------_")
        print(fhir_payload)
        print("_--------------------------------_")

        encrypted_payload = NHCX.encrypt(
            data=fhir_payload,
            sender_code=provider.participant_code,
            recipient_code=data.policy.payerid
            if settings.PAYER == "PMJAY"
            else "1000003538@hcx",  # TODO: REPLACE_AFTER_TESTING: replace this with self.insurance[0].policy.payerid after testing
            patient_abha_number=data.policy.abhanumber,
            correlation_id=str(task.external_id),
            status="request.initiated",
            workflow_id="",
        )

        print("_--------------------------------_")
        print(encrypted_payload)
        print("_--------------------------------_")

        _response = GatewayService.insurance_plan__request(encrypted_payload)

        return Response(
            {},
            status=status.HTTP_200_OK,
        )
