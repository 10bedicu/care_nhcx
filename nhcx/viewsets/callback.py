import json

from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from care.emr.api.viewsets.base import EMRBaseViewSet
from care.utils.notification_handler import send_webpush
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
        headers = request.headers

        print("--------------------------------")
        print("raw data", data, payload)
        print("headers", headers, data.get("headers"))
        print("--------------------------------")

        if not payload:
            return Response(
                {"detail": "Payload is required for decryption"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            decrypted_data = NHCX.decrypt(
                recipient_code="1000004181@hcx",
                data=payload,
            )

            (eligibility_response, eligibility_request) = (
                Fhir().process_coverage_eligibility_check_response(decrypted_data)
            )

            print("--------------------------------")
            print(eligibility_response)
            print(eligibility_request)
            print("--------------------------------")

            message = {
                "type": "MESSAGE",
                "from": "coverageelegibility/on_check",
                "message": "success" if not eligibility_response.error else "failed",
            }
            send_webpush(
                username=eligibility_request.created_by.username,
                message=json.dumps(message),
            )

            return Response({}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            print(f"Decryption error: {e}")
            return Response(
                {"detail": f"Decryption failed: {e!s}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        request=None,
        responses={202: None},
    )
    @action(detail=False, methods=["POST"], url_path="predetermination/on_submit")
    def pre_determination__on_submit(self, request, *args, **kwargs):
        data = request.data
        payload = data.get("payload")
        headers = request.headers

        print("--------------------------------")
        print("raw data", data, payload)
        print("headers", headers, data.get("headers"))
        print("--------------------------------")

        if not payload:
            return Response(
                {"detail": "Payload is required for decryption"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            decrypted_data = NHCX.decrypt(
                recipient_code="1000004181@hcx",
                data=payload,
            )

            (claim_response, claim_request) = Fhir().process_claim_response(
                decrypted_data
            )

            print("--------------------------------")
            print(claim_response)
            print(claim_request)
            print("--------------------------------")

            message = {
                "type": "MESSAGE",
                "from": "predetermination/on_submit",
                "message": "success" if not claim_response.error else "failed",
            }
            send_webpush(
                username=claim_request.created_by.username,
                message=json.dumps(message),
            )

            return Response({}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            print(f"Decryption error: {e}")
            return Response(
                {"detail": f"Decryption failed: {e!s}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        request=None,
        responses={202: None},
    )
    @action(detail=False, methods=["POST"], url_path="preauth/on_submit")
    def pre_auth__on_submit(self, request, *args, **kwargs):
        data = request.data
        payload = data.get("payload")
        headers = request.headers

        print("--------------------------------")
        print("raw data", data, payload)
        print("headers", headers, data.get("headers"))
        print("--------------------------------")

        if not payload:
            return Response(
                {"detail": "Payload is required for decryption"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            decrypted_data = NHCX.decrypt(
                recipient_code="1000004181@hcx",
                data=payload,
            )

            (claim_response, claim_request) = Fhir().process_claim_response(
                decrypted_data
            )

            print("--------------------------------")
            print(claim_response)
            print(claim_request)
            print("--------------------------------")

            message = {
                "type": "MESSAGE",
                "from": "preauth/on_submit",
                "message": "success" if not claim_response.error else "failed",
            }
            send_webpush(
                username=claim_request.created_by.username,
                message=json.dumps(message),
            )

            return Response({}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            print(f"Decryption error: {e}")
            return Response(
                {"detail": f"Decryption failed: {e!s}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        request=None,
        responses={202: None},
    )
    @action(detail=False, methods=["POST"], url_path="claim/on_submit")
    def claim__on_submit(self, request, *args, **kwargs):
        data = request.data
        payload = data.get("payload")
        headers = request.headers

        print("--------------------------------")
        print("raw data", data, payload)
        print("headers", headers, data.get("headers"))
        print("--------------------------------")

        if not payload:
            return Response(
                {"detail": "Payload is required for decryption"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            decrypted_data = NHCX.decrypt(
                recipient_code="1000004181@hcx",
                data=payload,
            )

            (claim_response, claim_request) = Fhir().process_claim_response(
                decrypted_data
            )

            print("--------------------------------")
            print(claim_response)
            print(claim_request)
            print("--------------------------------")

            message = {
                "type": "MESSAGE",
                "from": "claim/on_submit",
                "message": "success" if not claim_response.error else "failed",
            }
            send_webpush(
                username=claim_request.created_by.username,
                message=json.dumps(message),
            )

            return Response({}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            print(f"Decryption error: {e}")
            return Response(
                {"detail": f"Decryption failed: {e!s}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @extend_schema(
        request=None,
        responses={202: None},
    )
    @action(detail=False, methods=["POST"], url_path="claim/on_submit")
    def claim__on_submit(self, request, *args, **kwargs):
        data = request.data
        payload = data.get("payload")
        headers = request.headers

        print("--------------------------------")
        print("raw data", data, payload)
        print("headers", headers, data.get("headers"))
        print("--------------------------------")

        if not payload:
            return Response(
                {"detail": "Payload is required for decryption"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            decrypted_data = NHCX.decrypt(
                recipient_code="1000004181@hcx",
                data=payload,
            )

            (claim_response, claim_request) = Fhir().process_claim_response(
                decrypted_data
            )

            print("--------------------------------")
            print(claim_response)
            print(claim_request)
            print("--------------------------------")

            message = {
                "type": "MESSAGE",
                "from": "claim/on_submit",
                "message": "success" if not claim_response.error else "failed",
            }
            send_webpush(
                username=claim_request.created_by.username,
                message=json.dumps(message),
            )

            return Response({}, status=status.HTTP_202_ACCEPTED)
        except Exception as e:
            print(f"Decryption error: {e}")
            return Response(
                {"detail": f"Decryption failed: {e!s}"},
                status=status.HTTP_400_BAD_REQUEST,
            )
