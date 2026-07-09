from typing import Any

from abdm.service.request import Request
from rest_framework import status

from nhcx.utils.exceptions import NHCXAPIException


class GatewayService:
    request = Request("https://hcxsbx.abdm.gov.in")

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
        path = "/coverageeligibilityhcxservice/v1/coverageeligibility/check"

        response = GatewayService.request.post(
            path,
            {"payload": payload},
            headers=GatewayService.headers(),
        )

        if response.status_code != status.HTTP_202_ACCEPTED:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        return response.json()

    @staticmethod
    def insurance_plan__request(payload: str) -> dict:
        path = "/insuranceplanhcxservice/v1/insuranceplan/request"

        response = GatewayService.request.post(
            path,
            {"payload": payload},
            headers=GatewayService.headers(),
        )

        if response.status_code != status.HTTP_202_ACCEPTED:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        return response.json()

    @staticmethod
    def predetermination__submit(payload: str) -> dict:
        path = "/predeterminationhcxservice/v1/predetermination/submit"

        response = GatewayService.request.post(
            path,
            {"payload": payload},
            headers=GatewayService.headers(),
        )

        if response.status_code != status.HTTP_202_ACCEPTED:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        return response.json()

    @staticmethod
    def pre_auth__submit(payload: str) -> dict:
        path = "/preauthhcxservice/v1/preauth/submit"

        response = GatewayService.request.post(
            path,
            {"payload": payload},
            headers=GatewayService.headers(),
        )

        if response.status_code != status.HTTP_202_ACCEPTED:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        return response.json()

    @staticmethod
    def claim__submit(payload: str) -> dict:
        path = "/claimhcxservice/v1/claim/submit"

        response = GatewayService.request.post(
            path,
            {"payload": payload},
            headers=GatewayService.headers(),
        )

        if response.status_code != status.HTTP_202_ACCEPTED:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        return response.json()

    @staticmethod
    def communication__on_request(payload: str) -> dict:
        path = "/communicationhcxservice/v1/communication/on_request"

        response = GatewayService.request.post(
            path,
            {"payload": payload},
            headers=GatewayService.headers(),
        )

        if response.status_code != status.HTTP_202_ACCEPTED:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        return response.json()

    @staticmethod
    def task__submit(payload: str) -> dict:
        path = "/taskhcxservice/v1/task/submit"

        response = GatewayService.request.post(
            path,
            {"payload": payload},
            headers=GatewayService.headers(),
        )

        if response.status_code != status.HTTP_202_ACCEPTED:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        return response.json()

    @staticmethod
    def payment_notice__on_request(payload: str) -> dict:
        path = "/servicehcxpayment/v1/paymentnotice/on_request"

        response = GatewayService.request.post(
            path,
            {"type": "JWEPayload", "payload": payload},
            headers=GatewayService.headers(),
        )

        if response.status_code != status.HTTP_202_ACCEPTED:
            raise NHCXAPIException(detail=GatewayService.handle_error(response.json()))

        return response.json()
