import json
from datetime import datetime
from typing import Literal, TypedDict
from uuid import uuid4

from jwcrypto import jwe, jwk

from nhcx.models.provider import Provider
from nhcx.services.participant import ParticipantService
from nhcx.services.types.participant import FetchCertsBody
from nhcx.utils.exceptions import NHCXInternalException


class NHCX:
    class HeadersParams(TypedDict):
        class ErrorDetails(TypedDict):
            code: str | None
            message: str | None
            trace: str | None

        sender_code: str
        recipient_code: str
        patient_abha_number: str
        correlation_id: str
        request_id: str | None
        api_call_id: str | None
        workflow_id: str | None
        status: (
            Literal[
                "request.initiated",
                "response.partial",
                "response.complete",
                "response.failed",
            ]
            | None
        )
        debug_flag: Literal["ERROR", "INFO", "DEBUG"] | None
        error_details: ErrorDetails | None
        debug_details: ErrorDetails | None

    @staticmethod
    def prepare_headers(
        **header_params: HeadersParams,
    ) -> dict:
        sender_code = header_params.get("sender_code")
        recipient_code = header_params.get("recipient_code")
        patient_abha_number = header_params.get("patient_abha_number")
        correlation_id = header_params.get("correlation_id")

        if not sender_code:
            raise NHCXInternalException("Sender code is mandatory in headers")

        if not recipient_code:
            raise NHCXInternalException("Recipient code is mandatory in headers")

        if not patient_abha_number:
            raise NHCXInternalException("Patient ABHA number is mandatory in headers")

        if not correlation_id:
            raise NHCXInternalException("Correlation ID is mandatory in headers")

        return {
            "alg": "RSA-OAEP-256",
            "enc": "A256GCM",
            "x-hcx-timestamp": datetime.now()
            .astimezone()
            .replace(microsecond=0)
            .isoformat(),
            "x-hcx-sender_code": sender_code,
            "x-hcx-recipient_code": recipient_code,
            "x-hcx-ben-abha-id": patient_abha_number,
            "x-hcx-correlation_id": correlation_id,
            "x-hcx-request_id": header_params.get("request_id") or str(uuid4()),
            "x-hcx-api_call_id": header_params.get("api_call_id") or str(uuid4()),
            "x-hcx-workflow_id": header_params.get("workflow_id") or "1",
            "x-hcx-status": header_params.get("status") or "request.initiated",
            "x-hcx-debug_flag": header_params.get("debug_flag") or "ERROR",
            "x-hcx-error_details": header_params.get("error_details") or None,
            "x-hcx-debug_details": header_params.get("debug_details") or None,
        }

    @staticmethod
    def encrypt(
        data: dict,
        **header_params: HeadersParams,
    ) -> str:
        recipient_code = header_params["recipient_code"]

        if not recipient_code:
            raise NHCXInternalException("Recipient code is required for encryption")

        if not data or not isinstance(data, dict):
            raise NHCXInternalException("Data to be encrypted should be a dictionary")

        recipient_encryption_key = ParticipantService.fetch_certs(
            FetchCertsBody(participantid=recipient_code)
        ).encryption_cert

        headers = NHCX.prepare_headers(**header_params)

        jwe_payload = jwe.JWE(
            str(json.dumps(data)),
            recipient=jwk.JWK.from_pem(recipient_encryption_key.encode("utf-8")),
            protected=json.dumps(headers),
        )
        return jwe_payload.serialize(compact=True)

    @staticmethod
    def decrypt(recipient_code: str, data: str) -> dict:
        if not data:
            raise NHCXInternalException("Data to be decrypted cannot be None or empty")

        if not isinstance(data, str):
            raise NHCXInternalException("Data to be decrypted must be a string")

        provider = Provider.objects.filter(participant_code=recipient_code).first()
        private_key = provider.encryption_private_key if provider else None

        if not private_key:
            raise NHCXInternalException("Private key not found for the recipient")

        try:
            private_key = jwk.JWK.from_pem(private_key.encode("utf-8"))
            jwe_token = jwe.JWE()
            jwe_token.deserialize(data, key=private_key)
            payload = jwe_token.payload.decode("utf-8")
            return dict(json.loads(payload))
        except Exception as e:
            error_message = f"Failed to decrypt data: {e!s}"
            raise NHCXInternalException(error_message) from e

    @staticmethod
    def headers(data: str) -> HeadersParams:
        jwe_token = jwe.JWE()
        jwe_token.deserialize(data)
        return jwe_token.jose_header
