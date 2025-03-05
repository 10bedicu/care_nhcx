from typing import Any

from rest_framework import status

from care_abdm.abdm.service.request import Request
from care_nhcx.nhcx.services.types.participant import (
    CreateParticipantBody,
    CreateParticipantResponse,
    FetchCertsBody,
    FetchCertsResponse,
    GetPoliciesBody,
    GetPoliciesResponse,
    SearchParticipantBody,
    SearchParticipantResponse,
    UpdateParticipantBody,
    UpdateParticipantResponse,
)
from care_nhcx.nhcx.utils.exceptions import NHCXAPIException


class ParticipantService:
    request = Request("https://apisbx.abdm.gov.in/pmjay/sbxhcx/participanthcxservice")

    @staticmethod
    def headers():
        return {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "bearer_auth": ParticipantService.request.auth_header().get(
                "Authorization"
            ),
        }

    @staticmethod
    def handle_error(error: dict[str, Any] | str) -> str:
        if isinstance(error, list):
            return ParticipantService.handle_error(error[0])

        if isinstance(error, str):
            return error

        # { error: { message: "error message" } }
        if "error" in error:
            return ParticipantService.handle_error(error["error"])

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
    def get_policies(data: GetPoliciesBody) -> GetPoliciesResponse:
        path = "/participant/get/policies"
        response = ParticipantService.request.post(
            path,
            data.model_dump(mode="json", exclude_none=True),
            headers=ParticipantService.headers(),
        )

        if response.status_code != status.HTTP_200_OK:
            raise NHCXAPIException(
                detail=ParticipantService.handle_error(response.json())
            )

        response_data = response.json()
        return GetPoliciesResponse(response_data)

    @staticmethod
    def search_participant(data: SearchParticipantBody) -> SearchParticipantResponse:
        path = "/participant/search"
        response = ParticipantService.request.post(
            path,
            data.model_dump(mode="json", exclude_none=True),
            headers=ParticipantService.headers(),
        )

        if response.status_code != status.HTTP_200_OK:
            raise NHCXAPIException(
                detail=ParticipantService.handle_error(response.json())
            )

        response_data = response.json()
        return SearchParticipantResponse(response_data)

    @staticmethod
    def fetch_certs(data: FetchCertsBody) -> FetchCertsResponse:
        # TODO: consider caching the certs
        path = "/fetch/certs"
        response = ParticipantService.request.post(
            path,
            data.model_dump(mode="json", exclude_none=True),
            headers=ParticipantService.headers(),
        )

        if response.status_code != status.HTTP_200_OK:
            raise NHCXAPIException(
                detail=ParticipantService.handle_error(response.json())
            )

        response_data = response.json()
        return FetchCertsResponse(**response_data)

    @staticmethod
    def create_participant(data: CreateParticipantBody) -> CreateParticipantResponse:
        path = "/participant/create"
        response = ParticipantService.request.post(
            path,
            data.model_dump(mode="json", exclude_none=True),
            headers=ParticipantService.headers(),
        )

        if response.status_code != status.HTTP_200_OK:
            raise NHCXAPIException(
                detail=ParticipantService.handle_error(response.json())
            )

        response_data = response.json()
        return CreateParticipantResponse(**response_data)

    @staticmethod
    def update_participant(data: UpdateParticipantBody) -> UpdateParticipantResponse:
        path = "/participant/update"
        response = ParticipantService.request.post(
            path,
            data.model_dump(mode="json", exclude_none=True),
            headers=ParticipantService.headers(),
        )

        if response.status_code != status.HTTP_200_OK:
            raise NHCXAPIException(
                detail=ParticipantService.handle_error(response.json())
            )

        return UpdateParticipantResponse()
