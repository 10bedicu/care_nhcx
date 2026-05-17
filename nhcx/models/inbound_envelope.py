from django.db import models
from django.utils import timezone

from care.emr.models.base import EMRBaseModel


class CallbackTypeChoices(models.TextChoices):
    """One value per inbound NHCX webhook URL we expose."""

    COVERAGE_ELIGIBILITY_ON_CHECK = (
        "coverageeligibility_on_check",
        "coverageeligibility/on_check",
    )
    PREDETERMINATION_ON_SUBMIT = (
        "predetermination_on_submit",
        "predetermination/on_submit",
    )
    PREAUTH_ON_SUBMIT = ("preauth_on_submit", "preauth/on_submit")
    CLAIM_ON_SUBMIT = ("claim_on_submit", "claim/on_submit")
    COMMUNICATION_REQUEST = ("communication_request", "communication/request")
    PAYMENT_NOTICE_REQUEST = ("paymentnotice_request", "paymentnotice/request")
    INSURANCE_PLAN_ON_REQUEST = (
        "insuranceplan_on_request",
        "insuranceplan/on_request",
    )
    TASK_ON_SUBMIT = ("task_on_submit", "task/on_submit")
    # NHCX gateway pushes failures from any flow back via /error/response.
    # We persist these with status=COMPLETED (nothing to process, just track).
    ERROR_RESPONSE = ("error_response", "error/response")


class EnvelopeStatusChoices(models.TextChoices):
    PENDING = "pending", "Pending"
    PROCESSING = "processing", "Processing"
    COMPLETED = "completed", "Completed"
    FAILED = "failed", "Failed"


class NHCXInboundEnvelope(EMRBaseModel):
    """
    Persists every inbound NHCX callback envelope (still JWE-encrypted) before
    any work is done. The webhook view returns 202 immediately after creating
    a row here, and a Celery worker handles decrypt + Fhir().process_* off the
    hot path. Gives us:

      * gateway never times out, even on 100MB InsurancePlan ingests
      * idempotency: the gateway re-delivering the same correlation_id
        short-circuits at the view layer
      * replayable audit trail for failed callbacks
      * a single dispatch point with retry / backoff semantics
    """

    correlation_id = models.CharField(
        max_length=128, null=True, blank=True, db_index=True
    )
    api_call_id = models.CharField(
        max_length=128, null=True, blank=True, db_index=True
    )
    callback_type = models.CharField(
        max_length=64,
        choices=CallbackTypeChoices.choices,
        db_index=True,
    )
    recipient_code = models.CharField(max_length=128, null=True, blank=True)

    # Verbatim NHCX body. Usually a JWE string (regular callbacks), sometimes
    # a plain JSON dump (error/response). Kept lossless so failed envelopes
    # can be inspected or replayed.
    raw_payload = models.TextField()
    headers = models.JSONField(default=dict, blank=True)

    status = models.CharField(
        max_length=16,
        choices=EnvelopeStatusChoices.choices,
        default=EnvelopeStatusChoices.PENDING,
        db_index=True,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    error_message = models.TextField(blank=True, default="")
    processed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [
            models.Index(fields=["callback_type", "correlation_id"]),
            models.Index(fields=["status", "callback_type"]),
        ]

    def __str__(self):
        return f"{self.callback_type}:{self.correlation_id or self.pk}:{self.status}"

    def mark_processing(self):
        self.status = EnvelopeStatusChoices.PROCESSING
        self.attempts = (self.attempts or 0) + 1
        self.save(
            update_fields=["status", "attempts", "modified_date"]
        )

    def mark_completed(self):
        self.status = EnvelopeStatusChoices.COMPLETED
        self.processed_at = timezone.now()
        self.error_message = ""
        self.save(
            update_fields=[
                "status",
                "processed_at",
                "error_message",
                "modified_date",
            ]
        )

    def mark_failed(self, error_message: str):
        self.status = EnvelopeStatusChoices.FAILED
        self.error_message = (error_message or "")[:8000]
        self.save(update_fields=["status", "error_message", "modified_date"])
