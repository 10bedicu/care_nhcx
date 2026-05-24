from django.db import models


class DispatchStatusChoices(models.TextChoices):
    """
    Lifecycle state of every outbound NHCX gateway request
    (Claim, CoverageEligibilityRequest, Task dispatched by us).

    pending   -- created, never sent to the gateway
    awaiting  -- gateway returned 202, waiting for payer's async callback
    partial   -- payer gave a partial response (FHIR outcome "partial");
                 a further full response is still expected
    complete  -- payer callback received with a terminal answer
                 (approved / rejected / any non-queued outcome)
    error     -- failed at any stage:
                   * immediate NHCXAPIException on the gateway POST
                   * ProtocolResponse with x-hcx-status="response.error"
                   * /error/response callback from the gateway
    """

    PENDING = "pending", "Pending"
    AWAITING = "awaiting", "Awaiting"
    PARTIAL = "partial", "Partial"
    COMPLETE = "complete", "Complete"
    ERROR = "error", "Error"
