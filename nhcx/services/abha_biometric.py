import base64
from typing import Any

from abdm.service.request import Request
from rest_framework import status

from nhcx.models.claim_consent import ClaimConsent, ClaimConsentStage
from nhcx.services.types.abha_biometric import (
    AbhaBiometricAuthInitBody,
    AbhaBiometricAuthInitResponse,
    AbhaBiometricAuthRefreshBody,
    AbhaBiometricAuthRefreshResponse,
    AbhaBiometricAuthVerifyBody,
    AbhaBiometricAuthVerifyResponse,
)
from nhcx.utils.exceptions import NHCXAPIException


class AbhaBiometricService:
    request = Request(" https://apisbx.abdm.gov.in/hcx")

    SCOPE_MAP = {
        "FINGERPRINT": "bio",
        "IRIS": "iris",
        "FACE_AUTH": "face",
    }

    AUTH_METHOD_MAP = {
        "FINGERPRINT": "fingerPrintAuthPid",
        "IRIS": "irisAuthPid",
        "FACE_AUTH": "faceAuthPid",
    }

    @staticmethod
    def handle_error(error: dict[str, Any] | str) -> str:
        if isinstance(error, list):
            return AbhaBiometricService.handle_error(error[0])

        if isinstance(error, str):
            return error

        if "error" in error:
            return AbhaBiometricService.handle_error(error["error"])

        if "message" in error:
            return error["message"]

        if isinstance(error, dict) and len(error) >= 1:
            error.pop("code", None)
            error.pop("timestamp", None)
            return "".join(list(map(lambda x: str(x), list(error.values()))))

        return "Unknown error occurred at NHCX's end while processing the request. Please try again later."

    @staticmethod
    def _biometric_headers(process: str, payer_id: str) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": AbhaBiometricService.request.auth_header().get(
                "Authorization"
            ),
            "process": process,
            "payerid": payer_id,
        }

    @staticmethod
    def auth__init(
        body: AbhaBiometricAuthInitBody,
    ) -> AbhaBiometricAuthInitResponse:
        path = "/abha/biometric/auth/init"
        scope = AbhaBiometricService.SCOPE_MAP.get(body.authMode, "bio")
        payload = {
            "scope": [
                "abha-login",
                f"aadhaar-{scope}-verify",
            ],
            "loginHint": "abha-number",
            "loginId": body.abhaNumber,
            "otpSystem": "aadhaar",
            "authMode": body.authMode,
        }

        response = AbhaBiometricService.request.post(
            path,
            payload,
            headers=AbhaBiometricService._biometric_headers(body.process, body.payerId),
        )

        if response.status_code != status.HTTP_200_OK:
            raise NHCXAPIException(
                detail=AbhaBiometricService.handle_error(response.json())
            )

        return AbhaBiometricAuthInitResponse(**response.json())

    @staticmethod
    def auth__verify(
        body: AbhaBiometricAuthVerifyBody,
    ) -> AbhaBiometricAuthVerifyResponse:
        path = "/abha/biometric/auth/verify"
        scope = AbhaBiometricService.SCOPE_MAP.get(body.authMode, "bio")
        auth_method = AbhaBiometricService.AUTH_METHOD_MAP.get(
            body.authMode, "fingerPrintAuthPid"
        )
        payload = {
            "scope": [
                "abha-login",
                f"aadhaar-{scope}-verify",
            ],
            "authData": {
                "authMethods": [scope],
                scope: {
                    "txnId": body.txnId,
                    auth_method: base64.b64encode(body.authData.encode("utf-8")).decode(
                        "utf-8"
                    ),
                },
            },
            "authMode": body.authMode,
        }

        response = AbhaBiometricService.request.post(
            path,
            payload,
            headers=AbhaBiometricService._biometric_headers(body.process, body.payerId),
        )

        if response.status_code != status.HTTP_200_OK:
            raise NHCXAPIException(
                detail=AbhaBiometricService.handle_error(response.json())
            )

        return AbhaBiometricAuthVerifyResponse(**response.json())

    @staticmethod
    def auth__refresh_member_token(
        claim_consent: ClaimConsent,
    ) -> ClaimConsent:
        process = (
            "Discharge" if claim_consent.stage == ClaimConsentStage.CLAIM else "Preauth"
        )
        refresh_response = AbhaBiometricService.auth__refresh(
            AbhaBiometricAuthRefreshBody(
                process=process,
                payerId=claim_consent.payer_id,
                refreshToken=claim_consent.refresh_token,
            )
        )

        claim_consent.token = refresh_response.token
        claim_consent.expires_in = refresh_response.expiresIn
        claim_consent.refresh_token = refresh_response.refreshToken
        claim_consent.refresh_expires_in = refresh_response.refreshExpiresIn
        claim_consent.save()
        return claim_consent

    @staticmethod
    def auth__refresh(
        body: AbhaBiometricAuthRefreshBody,
    ) -> AbhaBiometricAuthRefreshResponse:
        path = "/abha/biometric/auth/refresh/token"

        headers = {
            **AbhaBiometricService._biometric_headers(body.process, body.payerId),
            "refreshToken": body.refreshToken,
        }

        response = AbhaBiometricService.request.get(
            path,
            headers=headers,
        )

        if response.status_code != status.HTTP_200_OK:
            raise NHCXAPIException(
                detail=AbhaBiometricService.handle_error(response.json())
            )

        return AbhaBiometricAuthRefreshResponse(**response.json())
