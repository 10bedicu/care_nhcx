from typing import Any

from abdm.service.request import Request
from rest_framework import status

from nhcx.services.types.gateway import (
    AbhaBiometricAuthInitBody,
    AbhaBiometricAuthInitResponse,
    AbhaBiometricAuthVerifyBody,
    AbhaBiometricAuthVerifyResponse,
)
from nhcx.utils.exceptions import NHCXAPIException


class GatewayService:
    request = Request("https://apisbx.abdm.gov.in/hcx")

    @staticmethod
    def headers():
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "bearer_auth": GatewayService.request.auth_header().get("Authorization"),
        }

    @staticmethod
    def handle_error(error: dict[str, Any] | str) -> str:
        if isinstance(error, list):
            return GatewayService.handle_error(error[0])

        if isinstance(error, str):
            return error

        # { error: { message: "error message" } }
        if "error" in error:
            return GatewayService.handle_error(error["error"])

        # { message: "error message" }
        if "message" in error:
            return error["message"]

        # { field_name: "error message" }
        if isinstance(error, dict) and len(error) >= 1:
            error.pop("code", None)
            error.pop("timestamp", None)
            return "".join(list(map(lambda x: str(x), list(error.values()))))

        return "Unknown error occurred at NHCX's end while processing the request. Please try again later."

    @staticmethod
    def coverage_eligibility__check(payload: str) -> dict:
        path = "/v1/coverageeligibility/check"

        response = GatewayService.request.post(
            path,
            {"type": "JWEPayload", "payload": payload},
            headers=GatewayService.headers(),
        )

        if response.status_code != status.HTTP_202_ACCEPTED:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        return response.json()

    @staticmethod
    def insurance_plan__request(payload: str) -> dict:
        path = "/v1/insuranceplan/request"

        response = GatewayService.request.post(
            path,
            {"type": "JWEPayload", "payload": payload},
            headers=GatewayService.headers(),
        )

        if response.status_code != status.HTTP_202_ACCEPTED:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        return response.json()

    @staticmethod
    def predetermination__submit(payload: str) -> dict:
        path = "/v1/predetermination/submit"

        response = GatewayService.request.post(
            path,
            {"type": "JWEPayload", "payload": payload},
            headers=GatewayService.headers(),
        )

        if response.status_code != status.HTTP_202_ACCEPTED:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        return response.json()

    @staticmethod
    def pre_auth__submit(payload: str) -> dict:
        path = "/v1/preauth/submit"

        response = GatewayService.request.post(
            path,
            {"type": "JWEPayload", "payload": payload},
            headers=GatewayService.headers(),
        )

        if response.status_code != status.HTTP_202_ACCEPTED:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        return response.json()

    @staticmethod
    def claim__submit(payload: str) -> dict:
        path = "/v1/claim/submit"

        response = GatewayService.request.post(
            path,
            {"type": "JWEPayload", "payload": payload},
            headers=GatewayService.headers(),
        )

        if response.status_code != status.HTTP_202_ACCEPTED:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        return response.json()

    @staticmethod
    def communication__on_request(payload: str) -> dict:
        path = "/v1/communication/on_request"

        response = GatewayService.request.post(
            path,
            {"type": "JWEPayload", "payload": payload},
            headers=GatewayService.headers(),
        )

        if response.status_code != status.HTTP_202_ACCEPTED:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        return response.json()

    @staticmethod
    def payment_notice__on_request(payload: str) -> dict:
        path = "/v1/paymentnotice/on_request"

        response = GatewayService.request.post(
            path,
            {"type": "JWEPayload", "payload": payload},
            headers=GatewayService.headers(),
        )

        if response.status_code != status.HTTP_202_ACCEPTED:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        return response.json()

    @staticmethod
    def abha__biometric__auth__init(
        body: AbhaBiometricAuthInitBody,
    ) -> AbhaBiometricAuthInitResponse:
        path = "/abha/biometric/auth/init"

        scope_map = {
            "FINGERPRINT": "bio",
            "IRIS": "iris",
            "FACE_AUTH": "face",
        }
        payload = {
            "scope": [
                "abha-login",
                f"aadhaar-{scope_map.get(body.authMode, 'bio')}-verify",
            ],
            "loginHint": "abha-number",
            "loginId": body.abhaNumber,
            "otpSystem": "aadhaar",
            "authMode": body.authMode,
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": GatewayService.request.auth_header().get("Authorization"),
            "process": body.process,
            "payerid": body.payerId,
        }

        response = GatewayService.request.post(
            path,
            payload,
            headers=headers,
        )

        if response.status_code != status.HTTP_200_OK:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        response_data = response.json()
        return AbhaBiometricAuthInitResponse(**response_data)

    @staticmethod
    def abha__biometric__auth__verify(
        body: AbhaBiometricAuthVerifyBody,
    ) -> AbhaBiometricAuthVerifyResponse:
        path = "/abha/biometric/auth/verify"

        scope_map = {
            "FINGERPRINT": "bio",
            "IRIS": "iris",
            "FACE_AUTH": "face",
        }
        auth_method_map = {
            "FINGERPRINT": "fingerPrintAuthPid",
            "IRIS": "irisAuthPid",
            "FACE_AUTH": "faceAuthPid",
        }
        payload = {
            "scope": [
                "abha-login",
                f"aadhaar-{scope_map.get(body.authMode, 'bio')}-verify",
            ],
            "authData": {
                "authMethods": [scope_map.get(body.authMode, "bio")],
                scope_map.get(body.authMode, "bio"): {
                    "txnId": body.txnId,
                    auth_method_map.get(
                        body.authMode, "fingerPrintAuthPid"
                    ): body.authData,
                },
            },
            "authMode": body.authMode,
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": GatewayService.request.auth_header().get("Authorization"),
            "process": body.process,
            "payerid": body.payerId,
        }

        response = GatewayService.request.post(
            path,
            payload,
            headers=headers,
        )

        if response.status_code != status.HTTP_200_OK:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        response_data = response.json()
        return AbhaBiometricAuthVerifyResponse(**response_data)
