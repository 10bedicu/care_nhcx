from django.db.models import Max
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from care.emr.api.viewsets.base import EMRBaseViewSet
from care.emr.models import Encounter
from care.emr.models.account import Account
from nhcx.models.claim import Claim
from nhcx.models.claim_consent import ClaimConsent, ClaimConsentStage
from nhcx.services.abha_biometric import AbhaBiometricService
from nhcx.services.participant import ParticipantService
from nhcx.services.types.abha_biometric import (
    AbhaBiometricAuthInitApiBody,
    AbhaBiometricAuthInitBody,
    AbhaBiometricAuthInitResponse,
    AbhaBiometricAuthVerifyApiBody,
    AbhaBiometricAuthVerifyBody,
)
from nhcx.services.types.participant import (
    FetchParticipantsBody,
    FetchParticipantsResponse,
    GetPoliciesBody,
    GetPoliciesResponse,
)


def _resolve_consent_account(encounter, claim):
    if claim and claim.account_id:
        return claim.account
    return Account.objects.filter(primary_encounter=encounter).first()


def _resolve_consent_cycle(account, encounter, claim):
    initiating_encounter_id = claim.encounter_id if claim else None
    if initiating_encounter_id and initiating_encounter_id == encounter.id:
        return 0
    if account is None:
        return 0
    existing = (
        ClaimConsent.objects.filter(account=account, encounter=encounter)
        .exclude(cycle__isnull=True)
        .order_by("cycle")
        .first()
    )
    if existing is not None:
        return existing.cycle
    max_cycle = ClaimConsent.objects.filter(account=account).aggregate(Max("cycle"))[
        "cycle__max"
    ]
    return (max_cycle or 0) + 1


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

    @action(detail=False, methods=["POST"], url_path="participants")
    @extend_schema(
        request=FetchParticipantsBody,
        responses={200: FetchParticipantsResponse},
    )
    def fetch_participants(self, request, *args, **kwargs):
        payload = FetchParticipantsBody(**request.data)
        response = ParticipantService.fetch_participants(payload)
        return Response(response, status=status.HTTP_200_OK)

    @action(detail=False, methods=["POST"], url_path="abha-biometric-auth-init")
    @extend_schema(
        request=AbhaBiometricAuthInitApiBody,
        responses={200: AbhaBiometricAuthInitResponse},
    )
    def abha__biometric__auth__init(self, request, *args, **kwargs):
        body = AbhaBiometricAuthInitApiBody(**request.data)
        service_body = AbhaBiometricAuthInitBody(**body.model_dump())
        init_response = AbhaBiometricService.auth__init(service_body)
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
        claim = None
        if body.claim:
            claim = get_object_or_404(Claim, external_id=body.claim)
        service_body = AbhaBiometricAuthVerifyBody(
            **body.model_dump(exclude={"encounter", "claim"})
        )
        verify_response = AbhaBiometricService.auth__verify(service_body)
        accounts = [a.model_dump(mode="json") for a in verify_response.accounts]
        stage = (
            ClaimConsentStage.PREAUTHORIZATION
            if service_body.process == "Preauth"
            else ClaimConsentStage.CLAIM
        )
        account = _resolve_consent_account(encounter, claim)
        cycle = _resolve_consent_cycle(account, encounter, claim)
        ClaimConsent.objects.update_or_create(
            encounter=encounter,
            payer_id=body.payerId,
            stage=stage,
            defaults={
                "encounter": encounter,
                "payer_id": body.payerId,
                "stage": stage,
                "claim": claim,
                "patient": encounter.patient,
                "account": account,
                "cycle": cycle,
                "token": verify_response.token,
                "expires_in": verify_response.expiresIn,
                "refresh_token": verify_response.refreshToken,
                "refresh_expires_in": verify_response.refreshExpiresIn,
                "accounts": accounts,
            },
        )
        return Response({"message": verify_response.message}, status=status.HTTP_200_OK)
