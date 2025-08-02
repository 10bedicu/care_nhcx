import json
from datetime import datetime
from uuid import uuid4

from jwcrypto import jwe, jwk

from nhcx.models.provider import Provider
from nhcx.services.participant import ParticipantService
from nhcx.services.types.participant import FetchCertsBody
from nhcx.utils.exceptions import NHCXInternalException


class NHCX:
    @staticmethod
    def headers(
        sender_code: str,
        recipient_code: str,
        patient_abha_number: str,
        request_id: str = str(uuid4()),
        correlation_id: str = str(uuid4()),
    ) -> dict:
        if not sender_code:
            raise NHCXInternalException("Sender code is required for encryption")

        if not recipient_code:
            raise NHCXInternalException("Recipient code is required for encryption")

        headers = {
            "alg": "RSA-OAEP-256",
            "enc": "A256GCM",
            "x-hcx-timestamp": datetime.now()
            .astimezone()
            .replace(microsecond=0)
            .isoformat(),
            "x-hcx-status": "request.initiated",
            "x-hcx-api_call_id": str(uuid4()),
            "x-hcx-workflow_id": "1",
            "x-hcx-sender_code": sender_code,
            "x-hcx-recipient_code": recipient_code,
            "x-hcx-request_id": request_id,
            "x-hcx-correlation_id": correlation_id,
            "x-hcx-ben-abha-id": patient_abha_number,
        }

        print("HEADERS", headers)

        return headers

    @staticmethod
    def encrypt(
        sender_code: str,
        recipient_code: str,
        patient_abha_number: str,
        data: dict,
        correlation_id: str | None = None,
    ) -> str:
        if not recipient_code:
            raise NHCXInternalException("Recipient code is required for encryption")

        if not sender_code:
            raise NHCXInternalException("Sender code is required for encryption")

        if not data or not isinstance(data, dict):
            raise NHCXInternalException("Data to be encrypted should be a dictionary")

        recipient_encryption_key = ParticipantService.fetch_certs(
            FetchCertsBody(participantid=recipient_code)
        ).encryption_cert

        headers = NHCX.headers(
            sender_code,
            recipient_code,
            patient_abha_number,
            correlation_id=correlation_id,
        )

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
