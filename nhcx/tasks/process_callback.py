"""
Celery worker side of the NHCX callback pipeline.

The webhook view persists an ``NHCXInboundEnvelope`` (still JWE-encrypted)
and returns 202 immediately. We pick it up here, decrypt, and dispatch to
the matching ``Fhir().process_*`` handler. All heavy lifting (RSA decrypt,
bundle parse, bulk ingest) happens off the HTTP worker so the gateway
never times out.

Retries: ``autoretry_for=(Exception,)`` with exponential backoff covers
transient DB / decrypt failures. The envelope row is updated with status,
attempts and error_message on every try so failed callbacks are visible
and replayable.
"""

from celery import shared_task
from celery.utils.log import get_task_logger

from nhcx.models.inbound_envelope import (
    CallbackTypeChoices,
    EnvelopeStatusChoices,
    NHCXInboundEnvelope,
)
from nhcx.utils.fhir import Fhir
from nhcx.utils.nhcx import NHCX

logger = get_task_logger(__name__)


def _dispatch_table():
    """
    callback_type -> bound method on a fresh Fhir() instance.

    Built lazily inside the task so Fhir() is constructed once per worker
    invocation; Fhir.__init__ touches NHCX/ABDM clients which we don't
    want to spin up at import time.
    """
    fhir = Fhir()
    return {
        CallbackTypeChoices.COVERAGE_ELIGIBILITY_ON_CHECK: (
            fhir.process_coverage_eligibility_check_response
        ),
        CallbackTypeChoices.PREDETERMINATION_ON_SUBMIT: fhir.process_claim_response,
        CallbackTypeChoices.PREAUTH_ON_SUBMIT: fhir.process_claim_response,
        CallbackTypeChoices.CLAIM_ON_SUBMIT: fhir.process_claim_response,
        CallbackTypeChoices.COMMUNICATION_REQUEST: fhir.process_communication_request,
        CallbackTypeChoices.PAYMENT_NOTICE_REQUEST: fhir.process_payment_notice_request,
        CallbackTypeChoices.INSURANCE_PLAN_ON_REQUEST: (
            fhir.process_insurance_plan_response
        ),
        CallbackTypeChoices.TASK_ON_SUBMIT: fhir.process_task_response,
    }


@shared_task(
    bind=True,
    name="nhcx.process_nhcx_callback",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_jitter=True,
    max_retries=3,
)
def process_nhcx_callback(self, envelope_id: int):
    envelope = NHCXInboundEnvelope.objects.filter(pk=envelope_id).first()
    if envelope is None:
        logger.warning("NHCX envelope %s not found; skipping", envelope_id)
        return

    if envelope.status == EnvelopeStatusChoices.COMPLETED:
        logger.info("NHCX envelope %s already completed; skipping", envelope_id)
        return

    envelope.mark_processing()
    logger.info(
        "Processing NHCX envelope id=%s type=%s correlation_id=%s attempt=%s",
        envelope.pk,
        envelope.callback_type,
        envelope.correlation_id,
        envelope.attempts,
    )

    try:
        decrypted = NHCX.decrypt(
            recipient_code=envelope.recipient_code,
            data=envelope.raw_payload,
        )

        handler = _dispatch_table().get(envelope.callback_type)
        if handler is None:
            # Choices field guards against this in normal flow; raise to
            # produce a permanent failure rather than silently swallowing.
            msg = f"No handler registered for callback_type={envelope.callback_type}"
            raise ValueError(msg)

        handler(decrypted, envelope.headers or {})

    except Exception as exc:
        envelope.mark_failed(f"{type(exc).__name__}: {exc}")
        logger.exception(
            "NHCX envelope %s failed on attempt %s", envelope.pk, envelope.attempts
        )
        raise

    envelope.mark_completed()
    logger.info("NHCX envelope %s completed", envelope.pk)
