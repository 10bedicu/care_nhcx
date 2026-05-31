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
  * whether the submission is an *enhancement* — always determined by a change
    in line-item codes (``item[].product_or_service``); pure amount /
    stratification (``program_code``) / implant (``modifier``) changes are not
    enhancements. There are two flavours of the check:
      - For an *approved* related claim we diff the line-item codes against the
        immediate related claim (``_is_item_enhancement``).
      - For a *queried* related claim we walk the related chain back to the
        first approved/partially-approved ancestor and diff the items there
        (``_is_enhancement_claim``). This handles ``enhancement -> query ->
        query`` chains, where the query responses share items with the
        enhancement and so can't be detected by diffing the immediate parent.
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


def _item_code_key(item: dict) -> tuple[str | None, str | None]:
    """
    Identity of a claim line item for enhancement detection: the
    ``product_or_service`` coding ``(system, code)``.

    Amount (``quantity`` / ``unit_price`` / ``factor``), stratification
    (``program_code``) and implant (``modifier``) are intentionally NOT part
    of the identity — changing only those is not an enhancement.
    """
    product_or_service = item.get("product_or_service") or {}
    return product_or_service.get("system"), product_or_service.get("code")


def _item_code_set(claim: Claim) -> set[tuple[str | None, str | None]]:
    return {_item_code_key(item) for item in claim.item or []}


def _is_item_enhancement(claim: Claim) -> bool:
    """
    Whether *this* submission is an enhancement of its immediate related claim:
    the set of line-item codes (``item[].product_or_service``) differs — i.e. a
    code was added, removed or changed compared to ``related[0].claim``.

    Pure amount / stratification (``program_code``) / implant (``modifier``)
    changes are NOT enhancements, so only ``product_or_service`` is compared.
    (Duplicate item codes within a claim are not allowed, so set comparison is
    sufficient.)

    Returns ``False`` when there is no related claim to compare against.
    """
    related = _related_claim(claim)
    if related is None:
        return False
    return _item_code_set(claim) != _item_code_set(related)


def _is_enhancement_claim(claim: Claim) -> bool:
    """
    A pre-auth claim is treated as part of an *enhancement* chain if it (or one
    of its ancestors via ``related[0].claim``) was submitted against an
    approved/partially-approved pre-auth *with changed line items*.

    Two conditions must both hold at the branch point:

      * the parent pre-auth response was approved/partially approved, and
      * the child's line-item codes differ from that parent
        (``_is_item_enhancement``) — because an approved pre-auth can also be
        *resubmitted* with the same items, which is not an enhancement.

    This is what disambiguates ``PREAUTH_QUERY_RESPONSE_SUBMITTED`` (19) from
    ``ENHANCEMENT_QUERY_RESPONSE_SUBMITTED`` (131): a queried enhancement can be
    queried again (``enhancement -> query -> query``), so the immediate parent
    of a queried enhancement is itself ``queried``. We must walk further back
    until we either reach an approved ancestor or run out of related claims.
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
            # Approved ancestor reached: it's an enhancement chain only if the
            # items actually changed against it (otherwise it's a resubmission).
            return _is_item_enhancement(current)
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
        if _is_item_enhancement(claim):
            return WorkflowCode.ENHANCEMENT_REQUEST_INITIATED
        return WorkflowCode.PREAUTH_REQUEST_RESUBMITTED

    if related_status == REJECTED_RESPONSE_STATUS:
        return WorkflowCode.PREAUTH_REQUEST_RESUBMITTED

    msg = f"Cannot submit pre-auth: related claim is in '{related_status or 'pending'}' state."
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
        # An approved/partially-approved claim whose items changed is an
        # enhancement, which cannot be re-submitted via this endpoint — the
        # provider has to raise a reprocess Task (resolve_reprocess_workflow).
        # When only amounts/stratification/implant changed it's a resubmission.
        if _is_item_enhancement(claim):
            raise ValidationError(
                "Claim has already been approved and its items were changed — "
                "raise a reprocess request instead."
            )
        return WorkflowCode.CLAIM_REQUEST_RESUBMITTED

    msg = f"Cannot submit claim: related claim is in '{related_status or 'pending'}' state."
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
