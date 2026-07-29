import logging
from typing import Any

from abdm.service.request import Request
from django.core.cache import cache
from rest_framework import status

from nhcx.services.types.participant import (
    CreateParticipantBody,
    CreateParticipantResponse,
    FetchCertsBody,
    FetchCertsResponse,
    FetchParticipantsBody,
    GetPoliciesBody,
    GetPoliciesResponse,
    SearchParticipantBody,
    SearchParticipantResponse,
    UpdateParticipantBody,
    UpdateParticipantResponse,
)
from nhcx.utils.exceptions import NHCXAPIException

logger = logging.getLogger(__name__)

SEARCH_PARTICIPANT_CACHE_KEY = "nhcx:search_participant:{participant_code}"
FETCH_CERTS_CACHE_KEY = "nhcx:fetch_certs:{participant_id}"
PARTICIPANT_CACHE_TIMEOUT = 60 * 60  # 1 hour


class ParticipantService:
    request = Request("https://hcxsbx.abdm.gov.in/participanthcxservice")

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
    def fetch_participants(data: FetchParticipantsBody) -> Any:
        path = "/fetch/participants/list"
        response = ParticipantService.request.post(
            path,
            data.model_dump(mode="json", exclude_none=True),
            headers=ParticipantService.headers(),
        )

        if response.status_code != status.HTTP_200_OK:
            raise NHCXAPIException(
                detail=ParticipantService.handle_error(response.json())
            )

        return response.json()

    @staticmethod
    def search_participant(data: SearchParticipantBody) -> SearchParticipantResponse:
        cache_key = SEARCH_PARTICIPANT_CACHE_KEY.format(
            participant_code=data.participant_code
        )
        cached = cache.get(cache_key)
        if cached:
            logger.debug(
                "Using cached search_participant result for %s",
                data.participant_code,
            )
            return SearchParticipantResponse(cached)

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
        cache.set(cache_key, response_data, PARTICIPANT_CACHE_TIMEOUT)
        return SearchParticipantResponse(response_data)

    @staticmethod
    def fetch_certs(data: FetchCertsBody) -> FetchCertsResponse:
        cache_key = FETCH_CERTS_CACHE_KEY.format(participant_id=data.participantid)
        cached = cache.get(cache_key)
        if cached:
            logger.debug(
                "Using cached fetch_certs result for %s",
                data.participantid,
            )
            return FetchCertsResponse(**cached)

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
        cache.set(cache_key, response_data, PARTICIPANT_CACHE_TIMEOUT)
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
