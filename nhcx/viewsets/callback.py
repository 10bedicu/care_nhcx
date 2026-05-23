import json
import logging

from django.core.exceptions import ValidationError
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from care.emr.api.viewsets.base import EMRBaseViewSet
from nhcx.models.claim import Claim
from nhcx.models.coverage_eligibility import CoverageEligibilityRequest
from nhcx.models.inbound_envelope import (
    CallbackTypeChoices,
    EnvelopeStatusChoices,
    NHCXInboundEnvelope,
)
from nhcx.models.task import Task
from nhcx.specs.nhcx_response import (
    EntityTypeChoices,
    NHCXResponse,
    ProtocolStatusChoices,
)
from nhcx.tasks.process_callback import process_nhcx_callback
from nhcx.utils.nhcx import NHCX

logger = logging.getLogger(__name__)

# NHCX gateway tags ProtocolResponse messages with this status when the request
# was rejected by the gateway or the recipient. Anything else (response.complete
# etc.) is a benign ack we just persist for audit and move on.
_PROTOCOL_ERROR_STATUS = "response.error"

# Models we'll try to attach a ProtocolResponse error to. The outbound viewsets
# all set NHCX correlation_id = <one of these>.external_id, so a single
# external_id lookup across these three covers every flow.
_ANCHOR_MODELS = (Task, Claim, CoverageEligibilityRequest)

# Sentinel status we write onto the anchor row so frontends can render a
# "request failed, please try again" banner with the error message from meta.
_ANCHOR_FAILED_STATUS = "failed"

# Statuses that mean "we've already accepted this correlation, don't re-enqueue".
# FAILED is excluded on purpose: operators may want to fix-and-replay, and a
# gateway re-delivery on a previously-failed envelope is a legitimate retry.
_DEDUPE_STATUSES = (
    EnvelopeStatusChoices.PENDING,
    EnvelopeStatusChoices.PROCESSING,
    EnvelopeStatusChoices.COMPLETED,
)


def _enqueue_callback(
    request,
    callback_type: CallbackTypeChoices,
    entity_type: EntityTypeChoices,
):
    """
    Common pipeline for every NHCX inbound webhook:

        peek headers -> dedupe by correlation_id -> persist envelope ->
        enqueue Celery task -> return 202.

    Bad JWE envelopes get a synchronous 400 (gateway shouldn't retry those).
    Everything else is acknowledged immediately.
    """
    data = request.data or {}
    payload = data.get("payload")

    # ProtocolResponse messages share the same URL but carry no payload. They
    # come in two flavours:
    #   * response.complete / similar acks  -> persist + ack (no celery work)
    #   * response.error                    -> persist + flip the anchor row
    #                                          to "failed" so the UI can react
    if data.get("type") == "ProtocolResponse":
        return _handle_protocol_response(request, callback_type)

    if not payload:
        logger.info("Inbound NHCX callback with no payload; ignoring: %s", data)
        return Response({}, status=status.HTTP_202_ACCEPTED)

    try:
        headers = NHCX.headers(payload)
    except Exception as exc:
        return Response(
            NHCXResponse.create_error_response(
                api_call_id="",
                correlation_id="",
                error_code="400",
                error_message=f"Bad JWE envelope: {exc}",
            ).model_dump(),
            status=status.HTTP_400_BAD_REQUEST,
        )

    correlation_id = headers.get("x-hcx-correlation_id") or ""
    api_call_id = headers.get("x-hcx-api_call_id") or ""
    sender_code = headers.get("x-hcx-sender_code") or ""
    recipient_code = headers.get("x-hcx-recipient_code") or ""

    success_response = NHCXResponse.create_success_response(
        api_call_id=api_call_id,
        correlation_id=correlation_id,
        sender_code=sender_code,
        recipient_code=recipient_code,
        entity_type=entity_type,
        protocol_status=ProtocolStatusChoices.REQUEST_QUEUED,
    ).model_dump()

    # Idempotency: same gateway correlation already in-flight/done? ack and exit.
    if (
        correlation_id
        and NHCXInboundEnvelope.objects.filter(
            callback_type=callback_type,
            correlation_id=correlation_id,
            status__in=_DEDUPE_STATUSES,
        ).exists()
    ):
        return Response(success_response, status=status.HTTP_202_ACCEPTED)

    envelope = NHCXInboundEnvelope.objects.create(
        correlation_id=correlation_id,
        api_call_id=api_call_id,
        callback_type=callback_type,
        recipient_code=recipient_code,
        raw_payload=payload,
        headers=headers,
    )
    process_nhcx_callback.delay(envelope.pk)

    return Response(success_response, status=status.HTTP_202_ACCEPTED)


def _record_error_callback(request):
    """
    NHCX gateway reports request failures via /error/response and (more
    commonly) via ProtocolResponse messages on the regular callback URLs.

    Both shapes land here when posted to /error/response. We route
    ProtocolResponse through the shared handler so the same anchor-update
    logic applies; everything else falls back to a generic envelope persist.
    """
    data = getattr(request, "data", None) or {}
    if isinstance(data, dict) and data.get("type") == "ProtocolResponse":
        return _handle_protocol_response(request, CallbackTypeChoices.ERROR_RESPONSE)

    body_repr = _stringify_body(request)
    correlation_id, api_call_id, recipient_code, hdrs, err_msg = (
        _extract_error_metadata(request)
    )

    envelope = NHCXInboundEnvelope.objects.create(
        correlation_id=correlation_id,
        api_call_id=api_call_id,
        callback_type=CallbackTypeChoices.ERROR_RESPONSE,
        recipient_code=recipient_code,
        raw_payload=body_repr,
        headers=hdrs,
        status=EnvelopeStatusChoices.COMPLETED,
        processed_at=timezone.now(),
        error_message=err_msg[:8000],
    )

    if correlation_id and err_msg:
        _attach_error_to_anchor(
            correlation_id=correlation_id,
            error_details={"message": err_msg},
            callback_type=CallbackTypeChoices.ERROR_RESPONSE,
            envelope_id=envelope.pk,
        )

    return Response({}, status=status.HTTP_202_ACCEPTED)


def _handle_protocol_response(request, callback_type: CallbackTypeChoices):
    """
    NHCX gateway/recipient acks ride the regular callback URLs with
    ``type="ProtocolResponse"`` and headers as top-level keys (no JWE).

    Always persist the envelope (so every ack is auditable). If
    ``x-hcx-status == "response.error"``, also walk back to the originating
    Task / Claim / CoverageEligibilityRequest by correlation_id and:

      * set its ``status`` to "failed"
      * stamp ``meta["last_error"]`` with the full error block

    The frontend can then surface "request failed, please try again" from a
    single ``status == "failed"`` check.
    """
    data = getattr(request, "data", None) or {}
    headers = {
        k: v for k, v in data.items() if isinstance(k, str) and k.startswith("x-hcx-")
    }

    nhcx_status = headers.get("x-hcx-status") or ""
    correlation_id = headers.get("x-hcx-correlation_id") or ""
    api_call_id = headers.get("x-hcx-api_call_id") or ""
    recipient_code = headers.get("x-hcx-recipient_code") or ""

    error_details = headers.get("x-hcx-error_details") or {}
    error_message = ""
    if isinstance(error_details, dict):
        error_message = error_details.get("message") or ""

    envelope = NHCXInboundEnvelope.objects.create(
        correlation_id=correlation_id,
        api_call_id=api_call_id,
        callback_type=callback_type,
        recipient_code=recipient_code,
        raw_payload=_stringify_body(request),
        headers=headers,
        status=EnvelopeStatusChoices.COMPLETED,
        processed_at=timezone.now(),
        error_message=error_message[:8000],
    )

    if nhcx_status == _PROTOCOL_ERROR_STATUS and correlation_id:
        _attach_error_to_anchor(
            correlation_id=correlation_id,
            error_details=error_details if isinstance(error_details, dict) else {},
            callback_type=callback_type,
            envelope_id=envelope.pk,
        )

    return Response({}, status=status.HTTP_202_ACCEPTED)


def _attach_error_to_anchor(
    correlation_id: str,
    error_details: dict,
    callback_type: CallbackTypeChoices,
    envelope_id: int,
):
    """
    Mark the originating outbound request as failed so the UI can prompt
    the user to retry. Three places get touched on the anchor row:

      * ``status``           -> "failed" (legacy banner trigger)
      * ``meta["last_error"]`` -> full structured error block (audit)
      * ``dispatch_error``     -> short text version for list/detail views;
                                  read alongside ``dispatched_at`` to know
                                  "we sent it at T, payer rejected with X".

    Task additionally gets an entry appended to ``output`` (FHIR-style
    audit trail).

    Returns the touched instance for testability, or None if no anchor was
    found for this correlation_id.
    """
    error_block = {
        "source": "nhcx_protocol_response",
        "callback_type": str(callback_type),
        "envelope_id": envelope_id,
        "code": error_details.get("code") or "",
        "message": error_details.get("message") or "",
        "trace": error_details.get("trace") or "",
        "received_at": timezone.now().isoformat(),
    }

    dispatch_error_text = (
        f"{error_block['code']}: {error_block['message']}".strip(": ")
        if error_block["code"] or error_block["message"]
        else f"NHCX {callback_type} error"
    )

    for model in _ANCHOR_MODELS:
        try:
            instance = model.objects.filter(external_id=correlation_id).first()
        except (ValueError, ValidationError):
            # external_id is a UUIDField; non-UUID correlation_id can't match.
            return None
        if instance is None:
            continue

        meta = instance.meta or {}
        meta["last_error"] = error_block
        instance.meta = meta
        instance.status = _ANCHOR_FAILED_STATUS
        instance.dispatch_error = dispatch_error_text[:8000]
        if getattr(instance, "dispatched_at", None) is None:
            instance.dispatched_at = timezone.now()

        update_fields = [
            "status",
            "meta",
            "dispatch_error",
            "dispatched_at",
            "modified_date",
        ]
        if hasattr(instance, "output") and isinstance(instance.output, list):
            instance.output = [*(instance.output or []), error_block]
            update_fields.append("output")

        instance.save(update_fields=update_fields)
        logger.info(
            "Marked %s(external_id=%s) failed from NHCX error %s/%s",
            model.__name__,
            correlation_id,
            error_block["code"],
            callback_type,
        )
        return instance

    logger.warning(
        "NHCX error received but no anchor found for correlation_id=%s callback=%s",
        correlation_id,
        callback_type,
    )
    return None


def _stringify_body(request) -> str:
    """Best-effort serialization of an inbound body to a single text column."""
    data = getattr(request, "data", None)
    if isinstance(data, (dict, list)):
        try:
            return json.dumps(data)
        except (TypeError, ValueError):
            pass
    try:
        return request.body.decode("utf-8", errors="replace")
    except Exception:
        return repr(getattr(request, "body", b""))


def _extract_error_metadata(request):
    """
    Pull correlation_id / api_call_id / error message from whatever shape
    the gateway sent. Supports two common shapes:

      1) Plain NHCXResponse JSON   -> top-level correlation_id / api_call_id / error.message
      2) JWE-wrapped envelope      -> headers carry x-hcx-* claims
    """
    correlation_id = ""
    api_call_id = ""
    recipient_code = ""
    headers: dict = {}
    error_message = ""

    data = getattr(request, "data", None) or {}
    if isinstance(data, dict):
        correlation_id = data.get("correlation_id") or ""
        api_call_id = data.get("api_call_id") or ""
        err = data.get("error") or {}
        if isinstance(err, dict):
            error_message = err.get("message") or ""

        payload = data.get("payload")
        if payload:
            try:
                jwe_headers = NHCX.headers(payload)
                headers = jwe_headers or {}
                correlation_id = (
                    correlation_id or headers.get("x-hcx-correlation_id") or ""
                )
                api_call_id = api_call_id or headers.get("x-hcx-api_call_id") or ""
                recipient_code = headers.get("x-hcx-recipient_code") or ""
            except Exception as exc:
                logger.debug("NHCX error/response payload not JWE-parseable: %s", exc)

    return correlation_id, api_call_id, recipient_code, headers, error_message


class CallbackViewSet(EMRBaseViewSet):
    permission_classes = []
    authentication_classes = []

    @extend_schema(request=None, responses={202: None})
    @action(detail=False, methods=["POST"], url_path="coverageeligibility/on_check")
    def coverage_eligibility__on_check(self, request, *args, **kwargs):
        return _enqueue_callback(
            request,
            CallbackTypeChoices.COVERAGE_ELIGIBILITY_ON_CHECK,
            EntityTypeChoices.COVERAGE_ELIGIBILITY,
        )

    @extend_schema(request=None, responses={202: None})
    @action(detail=False, methods=["POST"], url_path="predetermination/on_submit")
    def pre_determination__on_submit(self, request, *args, **kwargs):
        return _enqueue_callback(
            request,
            CallbackTypeChoices.PREDETERMINATION_ON_SUBMIT,
            EntityTypeChoices.CLAIM,
        )

    @extend_schema(request=None, responses={202: None})
    @action(detail=False, methods=["POST"], url_path="preauth/on_submit")
    def pre_auth__on_submit(self, request, *args, **kwargs):
        return _enqueue_callback(
            request,
            CallbackTypeChoices.PREAUTH_ON_SUBMIT,
            EntityTypeChoices.PREAUTH,
        )

    @extend_schema(request=None, responses={202: None})
    @action(detail=False, methods=["POST"], url_path="claim/on_submit")
    def claim__on_submit(self, request, *args, **kwargs):
        return _enqueue_callback(
            request,
            CallbackTypeChoices.CLAIM_ON_SUBMIT,
            EntityTypeChoices.CLAIM,
        )

    @extend_schema(request=None, responses={202: None})
    @action(detail=False, methods=["POST"], url_path="communication/request")
    def communication__request(self, request, *args, **kwargs):
        return _enqueue_callback(
            request,
            CallbackTypeChoices.COMMUNICATION_REQUEST,
            EntityTypeChoices.TASK,
        )

    @extend_schema(request=None, responses={202: None})
    @action(detail=False, methods=["POST"], url_path="paymentnotice/request")
    def payment_notice__request(self, request, *args, **kwargs):
        return _enqueue_callback(
            request,
            CallbackTypeChoices.PAYMENT_NOTICE_REQUEST,
            EntityTypeChoices.PAYMENT,
        )

    @extend_schema(request=None, responses={202: None})
    @action(detail=False, methods=["POST"], url_path="insuranceplan/on_request")
    def insurance_plan__on_request(self, request, *args, **kwargs):
        return _enqueue_callback(
            request,
            CallbackTypeChoices.INSURANCE_PLAN_ON_REQUEST,
            EntityTypeChoices.INSURANCE_PLAN,
        )

    @extend_schema(request=None, responses={202: None})
    @action(detail=False, methods=["POST"], url_path="task/on_submit")
    def task__on_submit(self, request, *args, **kwargs):
        return _enqueue_callback(
            request,
            CallbackTypeChoices.TASK_ON_SUBMIT,
            EntityTypeChoices.TASK,
        )

    @extend_schema(request=None, responses={202: None})
    @action(detail=False, methods=["POST"], url_path="error/response")
    def error__response(self, request, *args, **kwargs):
        return _record_error_callback(request)
