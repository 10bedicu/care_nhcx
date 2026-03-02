
# from care.utils.notification_handler import send_webpush
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from care.emr.api.viewsets.base import EMRBaseViewSet
from nhcx.specs.nhcx_response import (
    EntityTypeChoices,
    NHCXResponse,
    ProtocolStatusChoices,
)
from nhcx.utils.fhir import Fhir
from nhcx.utils.nhcx import NHCX


class CallbackViewSet(EMRBaseViewSet):
    permission_classes = []
    authentication_classes = []

    @extend_schema(
        request=None,
        responses={202: None},
    )
    @action(detail=False, methods=["POST"], url_path="coverageeligibility/on_check")
    def coverage_eligibility__on_check(self, request, *args, **kwargs):
        data = request.data
        payload = data.get("payload")
        headers = NHCX.headers(payload)

        try:
            decrypted_data = NHCX.decrypt(
                recipient_code=headers.get("x-hcx-recipient_code"),
                data=payload,
            )

            (eligibility_response, eligibility_request) = (
                Fhir().process_coverage_eligibility_check_response(
                    decrypted_data,
                    headers,
                )
            )

            # message = {
            #     "type": "MESSAGE",
            #     "from": "coverageelegibility/on_check",
            #     "message": "success" if not eligibility_response.error else "failed",
            # }
            # send_webpush(
            #     username=eligibility_request.created_by.username,
            #     message=json.dumps(message),
            # )

            nhcx_response = NHCXResponse.create_success_response(
                api_call_id=headers.get("x-hcx-api_call_id"),
                correlation_id=headers.get("x-hcx-correlation_id"),
                sender_code=headers.get("x-hcx-sender_code"),
                recipient_code=headers.get("x-hcx-recipient_code"),
                entity_type=EntityTypeChoices.COVERAGE_ELIGIBILITY,
                protocol_status=ProtocolStatusChoices.REQUEST_QUEUED,
            )
            return Response(nhcx_response.model_dump(), status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            nhcx_response = NHCXResponse.create_error_response(
                api_call_id=headers.get("x-hcx-api_call_id"),
                correlation_id=headers.get("x-hcx-correlation_id"),
                error_code="400",
                error_message=f"Decryption failed: {e!s}",
            )
            return Response(
                nhcx_response.model_dump(), status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        request=None,
        responses={202: None},
    )
    @action(detail=False, methods=["POST"], url_path="predetermination/on_submit")
    def pre_determination__on_submit(self, request, *args, **kwargs):
        data = request.data
        payload = data.get("payload")
        headers = NHCX.headers(payload)

        try:
            decrypted_data = NHCX.decrypt(
                recipient_code=headers.get("x-hcx-recipient_code"),
                data=payload,
            )

            (claim_response, claim_request) = Fhir().process_claim_response(
                decrypted_data,
                headers,
            )

            # message = {
            #     "type": "MESSAGE",
            #     "from": "predetermination/on_submit",
            #     "message": "success" if not claim_response.error else "failed",
            # }
            # send_webpush(
            #     username=claim_request.created_by.username,
            #     message=json.dumps(message),
            # )

            nhcx_response = NHCXResponse.create_success_response(
                api_call_id=headers.get("x-hcx-api_call_id"),
                correlation_id=headers.get("x-hcx-correlation_id"),
                sender_code=headers.get("x-hcx-sender_code"),
                recipient_code=headers.get("x-hcx-recipient_code"),
                entity_type=EntityTypeChoices.CLAIM,
                protocol_status=ProtocolStatusChoices.REQUEST_QUEUED,
            )
            return Response(nhcx_response.model_dump(), status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            nhcx_response = NHCXResponse.create_error_response(
                api_call_id=headers.get("x-hcx-api_call_id"),
                correlation_id=headers.get("x-hcx-correlation_id"),
                error_code="400",
                error_message=f"Decryption failed: {e!s}",
            )
            return Response(
                nhcx_response.model_dump(), status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        request=None,
        responses={202: None},
    )
    @action(detail=False, methods=["POST"], url_path="preauth/on_submit")
    def pre_auth__on_submit(self, request, *args, **kwargs):
        data = request.data
        payload = data.get("payload")
        headers = NHCX.headers(payload)

        try:
            decrypted_data = NHCX.decrypt(
                recipient_code=headers.get("x-hcx-recipient_code"),
                data=payload,
            )

            (claim_response, claim_request) = Fhir().process_claim_response(
                decrypted_data,
                headers,
            )

            # message = {
            #     "type": "MESSAGE",
            #     "from": "preauth/on_submit",
            #     "message": "success" if not claim_response.error else "failed",
            # }
            # send_webpush(
            #     username=claim_request.created_by.username,
            #     message=json.dumps(message),
            # )

            nhcx_response = NHCXResponse.create_success_response(
                api_call_id=headers.get("x-hcx-api_call_id"),
                correlation_id=headers.get("x-hcx-correlation_id"),
                sender_code=headers.get("x-hcx-sender_code"),
                recipient_code=headers.get("x-hcx-recipient_code"),
                entity_type=EntityTypeChoices.PREAUTH,
                protocol_status=ProtocolStatusChoices.REQUEST_QUEUED,
            )
            return Response(nhcx_response.model_dump(), status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            nhcx_response = NHCXResponse.create_error_response(
                api_call_id=headers.get("x-hcx-api_call_id"),
                correlation_id=headers.get("x-hcx-correlation_id"),
                error_code="400",
                error_message=f"Decryption failed: {e!s}",
            )
            return Response(
                nhcx_response.model_dump(), status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        request=None,
        responses={202: None},
    )
    @action(detail=False, methods=["POST"], url_path="claim/on_submit")
    def claim__on_submit(self, request, *args, **kwargs):
        data = request.data
        payload = data.get("payload")
        headers = NHCX.headers(payload)

        try:
            decrypted_data = NHCX.decrypt(
                recipient_code=headers.get("x-hcx-recipient_code"),
                data=payload,
            )

            (claim_response, claim_request) = Fhir().process_claim_response(
                decrypted_data,
                headers,
            )

            # message = {
            #     "type": "MESSAGE",
            #     "from": "claim/on_submit",
            #     "message": "success" if not claim_response.error else "failed",
            # }
            # send_webpush(
            #     username=claim_request.created_by.username,
            #     message=json.dumps(message),
            # )

            nhcx_response = NHCXResponse.create_success_response(
                api_call_id=headers.get("x-hcx-api_call_id"),
                correlation_id=headers.get("x-hcx-correlation_id"),
                sender_code=headers.get("x-hcx-sender_code"),
                recipient_code=headers.get("x-hcx-recipient_code"),
                entity_type=EntityTypeChoices.CLAIM,
                protocol_status=ProtocolStatusChoices.REQUEST_QUEUED,
            )

            return Response(nhcx_response.model_dump(), status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            nhcx_response = NHCXResponse.create_error_response(
                api_call_id=headers.get("x-hcx-api_call_id"),
                correlation_id=headers.get("x-hcx-correlation_id"),
                error_code="400",
                error_message=f"Decryption failed: {e!s}",
            )
            return Response(
                nhcx_response.model_dump(), status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        request=None,
        responses={202: None},
    )
    @action(detail=False, methods=["POST"], url_path="communication/request")
    def communication__request(self, request, *args, **kwargs):
        data = request.data
        payload = data.get("payload")
        headers = NHCX.headers(payload)

        try:
            decrypted_data = NHCX.decrypt(
                recipient_code=headers.get("x-hcx-recipient_code"),
                data=payload,
            )

            (task, communication_request, claim) = Fhir().process_communication_request(
                decrypted_data,
                headers,
            )

            nhcx_response = NHCXResponse.create_success_response(
                api_call_id=headers.get("x-hcx-api_call_id"),
                correlation_id=headers.get("x-hcx-correlation_id"),
                sender_code=headers.get("x-hcx-sender_code"),
                recipient_code=headers.get("x-hcx-recipient_code"),
                entity_type=EntityTypeChoices.TASK,
                protocol_status=ProtocolStatusChoices.REQUEST_QUEUED,
            )
            return Response(nhcx_response.model_dump(), status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            nhcx_response = NHCXResponse.create_error_response(
                api_call_id=headers.get("x-hcx-api_call_id"),
                correlation_id=headers.get("x-hcx-correlation_id"),
                error_code="400",
                error_message=f"Decryption failed: {e!s}",
            )
            return Response(
                nhcx_response.model_dump(), status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        request=None,
        responses={202: None},
    )
    @action(detail=False, methods=["POST"], url_path="paymentnotice/request")
    def payment_notice__request(self, request, *args, **kwargs):
        data = request.data
        payload = data.get("payload")
        headers = NHCX.headers(payload)

        try:
            decrypted_data = NHCX.decrypt(
                recipient_code=headers.get("x-hcx-recipient_code"),
                data=payload,
            )

            (task, payment_reconciliation, claim) = (
                Fhir().process_payment_notice_request(
                    decrypted_data,
                    headers,
                )
            )

            nhcx_response = NHCXResponse.create_success_response(
                api_call_id=headers.get("x-hcx-api_call_id"),
                correlation_id=headers.get("x-hcx-correlation_id"),
                sender_code=headers.get("x-hcx-sender_code"),
                recipient_code=headers.get("x-hcx-recipient_code"),
                entity_type=EntityTypeChoices.PAYMENT,
                protocol_status=ProtocolStatusChoices.REQUEST_QUEUED,
            )
            return Response(nhcx_response.model_dump(), status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            nhcx_response = NHCXResponse.create_error_response(
                api_call_id=headers.get("x-hcx-api_call_id"),
                correlation_id=headers.get("x-hcx-correlation_id"),
                error_code="400",
                error_message=f"Decryption failed: {e!s}",
            )
            return Response(
                nhcx_response.model_dump(), status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(
        request=None,
        responses={202: None},
    )
    @action(detail=False, methods=["POST"], url_path="insuranceplan/on_request")
    def insurance_plan__on_request(self, request, *args, **kwargs):
        data = request.data
        payload = data.get("payload")
        headers = NHCX.headers(payload)

        try:
            decrypted_data = NHCX.decrypt(
                recipient_code=headers.get("x-hcx-recipient_code"),
                data=payload,
            )

            (task, insurance_plan) = Fhir().process_insurance_plan_response(
                decrypted_data,
                headers,
            )

            nhcx_response = NHCXResponse.create_success_response(
                api_call_id=headers.get("x-hcx-api_call_id"),
                correlation_id=headers.get("x-hcx-correlation_id"),
                sender_code=headers.get("x-hcx-sender_code"),
                recipient_code=headers.get("x-hcx-recipient_code"),
                entity_type=EntityTypeChoices.PAYMENT,
                protocol_status=ProtocolStatusChoices.REQUEST_QUEUED,
            )
            return Response(nhcx_response.model_dump(), status=status.HTTP_202_ACCEPTED)

        except Exception as e:
            nhcx_response = NHCXResponse.create_error_response(
                api_call_id=headers.get("x-hcx-api_call_id"),
                correlation_id=headers.get("x-hcx-correlation_id"),
                error_code="400",
                error_message=f"Decryption failed: {e!s}",
            )
            return Response(
                nhcx_response.model_dump(), status=status.HTTP_400_BAD_REQUEST
            )
