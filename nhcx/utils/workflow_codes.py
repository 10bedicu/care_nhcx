"""
NHCX workflow IDs for claim/task submissions.

These IDs are sent on the ``x-hcx-workflow_id`` header (see
``nhcx.utils.nhcx.NHCX.prepare_headers``) and are how NHCX classifies the
financial transaction type at the gateway level.

The catalogue (per the NHCX spec):

    12   PREAUTH_REQUEST_INITIATED              New preauth submission
    121  PREAUTH_REQUEST_RESUBMITTED            Resubmit after rejection
    122  PREAUTH_CANCEL_INITIATED               Cancel an approved preauth
    19   PREAUTH_QUERY_RESPONSE_SUBMITTED       Reply to a payer preauth query
    13   ENHANCEMENT_REQUEST_INITIATED          Enhancement on an approved preauth
    131  ENHANCEMENT_QUERY_RESPONSE_SUBMITTED   Reply to a payer enhancement query
    15   CLAIM_REQUEST_INITIATED                Final claim submission
    16   CLAIM_REQUEST_RESUBMITTED              Resubmit a rejected claim
    151  CLAIM_QUERY_RESPONSE_SUBMITTED         Reply to a payer claim query
    17   PAYMENT_RECEIVED                       Acknowledge payment notice
    18   REPROCESS_REQUEST_SUBMITTED            Raise reprocess request

Why this lives here:

We don't carry an explicit ``transaction_type`` on the ``Claim`` model, so
the workflow code has to be derived from:

  * ``claim.use``                          (preauth / claim)
  * the related claim (``claim.related[0]``)
  * the latest ``ClaimResponse.adjudication`` status of that related claim
  * whether the related claim is itself part of an *enhancement* chain — i.e.
    whether any ancestor pre-auth in its ``related`` lineage was approved or
    partially approved. That walk-back is needed because an enhancement claim
    can itself be queried (immediate parent status ``queried``), but the chain
    is still in enhancement mode because of an earlier approval.
"""

from enum import StrEnum

from rest_framework.exceptions import ValidationError

from nhcx.models.claim import Claim, ClaimResponse
from nhcx.specs.claim import ClaimUseChoices

APPROVED_RESPONSE_STATUSES: frozenset[str] = frozenset(
    {"approved", "partially_approved"}
)
QUERIED_RESPONSE_STATUS = "queried"
REJECTED_RESPONSE_STATUS = "rejected"

CHAIN_WALK_LIMIT = 32


class WorkflowCode(StrEnum):
    PREAUTH_REQUEST_INITIATED = "12"
    PREAUTH_REQUEST_RESUBMITTED = "121"
    PREAUTH_CANCEL_INITIATED = "122"
    PREAUTH_QUERY_RESPONSE_SUBMITTED = "19"
    ENHANCEMENT_REQUEST_INITIATED = "13"
    ENHANCEMENT_QUERY_RESPONSE_SUBMITTED = "131"
    CLAIM_REQUEST_INITIATED = "15"
    CLAIM_REQUEST_RESUBMITTED = "16"
    CLAIM_QUERY_RESPONSE_SUBMITTED = "151"
    PAYMENT_RECEIVED = "17"
    REPROCESS_REQUEST_SUBMITTED = "18"


def _adjudication_status(claim_response: ClaimResponse | None) -> str | None:
    """
    Pull the machine-readable status code (approved / queried / rejected /
    partially_approved / ...) from a ``ClaimResponse.adjudication`` payload.

    Adjudication entries look like::

        {
            "category": {"coding": [{"code": "status", ...}]},
            "reason":   {"coding": [{"code": "approved", ...}]},
        }

    We pick the entry whose category has ``code == "status"`` and return the
    normalised reason code (lowercased, hyphens converted to underscores so
    ``partially-approved`` collapses onto ``partially_approved``).
    """
    if claim_response is None or not claim_response.adjudication:
        return None

    for entry in claim_response.adjudication:
        category_codes = {
            (c or {}).get("code")
            for c in (entry.get("category") or {}).get("coding") or []
        }
        if "status" not in category_codes:
            continue
        for coding in (entry.get("reason") or {}).get("coding") or []:
            code = (coding or {}).get("code")
            if code:
                return code.strip().lower().replace("-", "_")

    return None


def _latest_response_status(claim: Claim) -> str | None:
    latest = (
        ClaimResponse.objects.filter(request=claim).order_by("-created_date").first()
    )
    return _adjudication_status(latest)


def _related_claim(claim: Claim) -> Claim | None:
    """Return the claim referenced by ``claim.related[0].claim`` (if any)."""
    if not claim.related:
        return None
    first = claim.related[0]
    parent_uuid = first.get("claim") if isinstance(first, dict) else first
    if not parent_uuid:
        return None
    return Claim.objects.filter(external_id=parent_uuid).first()


def _is_enhancement_claim(claim: Claim) -> bool:
    """
    A pre-auth claim is treated as part of an *enhancement* chain if any of
    its ancestors (via ``related[0].claim``) has a pre-auth response that was
    approved or partially approved.

    This is what disambiguates ``PREAUTH_QUERY_RESPONSE_SUBMITTED`` (19) from
    ``ENHANCEMENT_QUERY_RESPONSE_SUBMITTED`` (131): the immediate parent of a
    queried enhancement is itself ``queried``, so we must walk further back
    until we either find an approved ancestor or run out of related claims.
    """
    if claim.use != ClaimUseChoices.PRE_AUTHORIZATION.value:
        return False

    visited: set[int] = set()
    current = claim
    for _ in range(CHAIN_WALK_LIMIT):
        if current.pk in visited:
            return False
        visited.add(current.pk)

        parent = _related_claim(current)
        if parent is None:
            return False
        if parent.use != ClaimUseChoices.PRE_AUTHORIZATION.value:
            return False
        if _latest_response_status(parent) in APPROVED_RESPONSE_STATUSES:
            return True
        current = parent

    return False


def _resolve_preauth_workflow(claim: Claim) -> WorkflowCode:
    related = _related_claim(claim)
    if related is None:
        return WorkflowCode.PREAUTH_REQUEST_INITIATED

    related_status = _latest_response_status(related)

    if related_status == QUERIED_RESPONSE_STATUS:
        if _is_enhancement_claim(related):
            return WorkflowCode.ENHANCEMENT_QUERY_RESPONSE_SUBMITTED
        return WorkflowCode.PREAUTH_QUERY_RESPONSE_SUBMITTED

    if related_status in APPROVED_RESPONSE_STATUSES:
        return WorkflowCode.ENHANCEMENT_REQUEST_INITIATED

    if related_status == REJECTED_RESPONSE_STATUS:
        return WorkflowCode.PREAUTH_REQUEST_RESUBMITTED

    msg = (
        "Cannot submit pre-auth: related claim is in "
        f"'{related_status or 'pending'}' state."
    )
    raise ValidationError(msg)


def _resolve_claim_workflow(claim: Claim) -> WorkflowCode:
    related = _related_claim(claim)
    if related is None:
        raise ValidationError(
            "A final claim must be linked to a pre-auth via the related field."
        )

    if related.use == ClaimUseChoices.PRE_AUTHORIZATION.value:
        return WorkflowCode.CLAIM_REQUEST_INITIATED

    related_status = _latest_response_status(related)

    if related_status == QUERIED_RESPONSE_STATUS:
        return WorkflowCode.CLAIM_QUERY_RESPONSE_SUBMITTED

    if related_status == REJECTED_RESPONSE_STATUS:
        return WorkflowCode.CLAIM_REQUEST_RESUBMITTED

    if related_status in APPROVED_RESPONSE_STATUSES:
        # An approved/partially-approved claim cannot be re-submitted via
        # this endpoint — the provider has to raise a reprocess Task,
        # which uses ``resolve_reprocess_workflow``.
        raise ValidationError(
            "Claim has already been approved — raise a reprocess request instead."
        )

    msg = (
        "Cannot submit claim: related claim is in "
        f"'{related_status or 'pending'}' state."
    )
    raise ValidationError(msg)


# Dispatch table keyed by ``claim.use``. Pre-determination has no dedicated
# NHCX code; fall back to ``PREAUTH_REQUEST_INITIATED`` to preserve existing
# behaviour (which sent ``"12"`` for any non-claim use).
_WORKFLOW_RESOLVERS = {
    ClaimUseChoices.PRE_AUTHORIZATION.value: _resolve_preauth_workflow,
    ClaimUseChoices.CLAIM.value: _resolve_claim_workflow,
    ClaimUseChoices.PRE_DETERMINATION.value: lambda _claim: WorkflowCode.PREAUTH_REQUEST_INITIATED,
}


def resolve_claim_submission_workflow(claim: Claim) -> WorkflowCode:
    """
    Resolve the NHCX workflow code for a pre-auth or final-claim submission.

    Raises ``ValidationError`` when the related-claim chain is in a state that
    blocks submission (no response yet, in-process, already approved with no
    reprocess intent, etc.).
    """
    resolver = _WORKFLOW_RESOLVERS.get(claim.use)
    if resolver is None:
        msg = f"Unsupported claim.use '{claim.use}' for workflow resolution."
        raise ValidationError(msg)
    return resolver(claim)


def resolve_cancel_workflow(claim: Claim) -> WorkflowCode:
    """Workflow code for the cancel-claim Task action."""
    if claim.use == ClaimUseChoices.PRE_AUTHORIZATION.value:
        return WorkflowCode.PREAUTH_CANCEL_INITIATED
    raise ValidationError("Cancel is only supported for pre-auth claims.")


def resolve_reprocess_workflow(claim: Claim) -> WorkflowCode:
    """Workflow code for the reprocess Task action."""
    if claim.use == ClaimUseChoices.CLAIM.value:
        return WorkflowCode.REPROCESS_REQUEST_SUBMITTED
    raise ValidationError("Reprocess is only supported for final claims.")


def resolve_payment_acknowledge_workflow() -> WorkflowCode:
    """Workflow code for acknowledging a payment notice."""
    return WorkflowCode.PAYMENT_RECEIVED
