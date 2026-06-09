from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from care.emr.api.viewsets.base import EMRBaseViewSet
from care.emr.models import Encounter
from nhcx.models.claim_consent import ClaimConsent, ClaimConsentStage
from nhcx.services.gateway import GatewayService
from nhcx.services.participant import ParticipantService
from nhcx.services.types.gateway import (
    AbhaBiometricAuthInitApiBody,
    AbhaBiometricAuthInitBody,
    AbhaBiometricAuthInitResponse,
    AbhaBiometricAuthVerifyApiBody,
    AbhaBiometricAuthVerifyBody,
)
from nhcx.services.types.participant import GetPoliciesBody, GetPoliciesResponse


class GatewayViewSet(EMRBaseViewSet):
    @action(detail=False, methods=["POST"], url_path="get_policies")
    @extend_schema(
        request=GetPoliciesBody,
        responses={200: GetPoliciesResponse},
    )
    def get_policies(self, request, *args, **kwargs):
        payload = GetPoliciesBody(**request.data)
        response = ParticipantService.get_policies(payload)
        return Response(response.model_dump(mode="json"), status=status.HTTP_200_OK)

    @action(detail=False, methods=["POST"], url_path="abha-biometric-auth-init")
    @extend_schema(
        request=AbhaBiometricAuthInitApiBody,
        responses={200: AbhaBiometricAuthInitResponse},
    )
    def abha__biometric__auth__init(self, request, *args, **kwargs):
        body = AbhaBiometricAuthInitApiBody(**request.data)
        service_body = AbhaBiometricAuthInitBody(**body.model_dump())
        init_response = GatewayService.abha__biometric__auth__init(service_body)
        return Response(
            init_response.model_dump(mode="json"), status=status.HTTP_200_OK
        )

    @action(detail=False, methods=["POST"], url_path="abha-biometric-auth-verify")
    @extend_schema(
        request=AbhaBiometricAuthVerifyApiBody,
        responses={
            200: {
                "type": "object",
                "properties": {
                    "message": {"type": "string"},
                },
            }
        },
    )
    def abha__biometric__auth__verify(self, request, *args, **kwargs):
        body = AbhaBiometricAuthVerifyApiBody(**request.data)
        encounter = get_object_or_404(Encounter, external_id=body.encounter)
        service_body = AbhaBiometricAuthVerifyBody(
            **body.model_dump(exclude={"encounter"})
        )
        verify_response = GatewayService.abha__biometric__auth__verify(service_body)
        accounts = [a.model_dump(mode="json") for a in verify_response.accounts]
        stage = (
            ClaimConsentStage.PREAUTHORIZATION
            if service_body.process == "Preauth"
            else ClaimConsentStage.CLAIM
        )
        ClaimConsent.objects.update_or_create(
            encounter=encounter,
            payer_id=body.payerId,
            stage=stage,
            defaults={
                "encounter": encounter,
                "payer_id": body.payerId,
                "stage": stage,
                "patient": encounter.patient,
                "token": verify_response.token,
                "expires_in": verify_response.expiresIn,
                "refresh_token": verify_response.refreshToken,
                "refresh_expires_in": verify_response.refreshExpiresIn,
                "accounts": accounts,
            },
        )
        return Response({"message": verify_response.message}, status=status.HTTP_200_OK)
