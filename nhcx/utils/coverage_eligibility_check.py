import json

from nhcx.models.coverage_eligibility import CoverageEligibilityRequest
from nhcx.services.gateway import GatewayService
from nhcx.utils.dispatch import dispatch
from nhcx.utils.fhir import Fhir
from nhcx.utils.nhcx import NHCX
from nhcx.utils.user import get_or_create_nhcx_user


def dispatch_coverage_eligibility_check(
    coverage_eligibility_request: CoverageEligibilityRequest,
):
    fhir_data = Fhir().create_coverage_eligibility_request_bundle(
        coverage_eligibility_request
    )

    fhir_payload = json.loads(fhir_data.json())

    coverage_eligibility_request.workflow_code = "1"
    coverage_eligibility_request.save(update_fields=["workflow_code", "modified_date"])

    encrypted_payload = NHCX.encrypt(
        data=fhir_payload,
        sender_code=coverage_eligibility_request.provider.participant_code,
        recipient_code=coverage_eligibility_request.insurer.get("participant_code"),
        patient_abha_number=coverage_eligibility_request.insurance[0]
        .get("policy", {})
        .get("abhanumber"),
        correlation_id=str(coverage_eligibility_request.external_id),
        status="request.initiated",
        workflow_id="1",
        log_type="coverage_eligibility_request_check",
    )

    dispatch(
        coverage_eligibility_request,
        GatewayService.coverage_eligibility__check,
        encrypted_payload,
    )

    return coverage_eligibility_request


def _find_source_validation_request(claim) -> CoverageEligibilityRequest | None:
    base = (
        CoverageEligibilityRequest.objects.filter(purpose__contains=["validation"])
        .exclude(insurance=[])
        .exclude(insurer={})
    )

    if claim.encounter_id:
        source = (
            base.filter(encounter_id=claim.encounter_id)
            .order_by("-created_date")
            .first()
        )
        if source:
            return source

    return (
        base.filter(patient_id=claim.patient_id, provider_id=claim.provider_id)
        .order_by("-created_date")
        .first()
    )


def create_automatic_wallet_check(claim) -> CoverageEligibilityRequest | None:
    source = _find_source_validation_request(claim)
    if source is None:
        return None

    nhcx_user = get_or_create_nhcx_user()

    request = CoverageEligibilityRequest.objects.create(
        status="active",
        priority="normal",
        purpose=["validation"],
        provider=claim.provider,
        patient=claim.patient,
        encounter=claim.encounter,
        insurer=source.insurer,
        insurance=source.insurance,
        supporting_info=[],
        item=[],
        is_automatic=True,
        created_by=nhcx_user,
        updated_by=nhcx_user,
    )

    dispatch_coverage_eligibility_check(request)

    return request


def create_wallet_check_from_request(
    source: CoverageEligibilityRequest,
) -> CoverageEligibilityRequest:
    """Clone a validation request's policy into a fresh automatic wallet check
    and submit it to the payer.

    Marked ``is_automatic=True`` so it only feeds the wallet balance card and
    never appears as a timeline entry, matching system-initiated refreshes.
    """

    request = CoverageEligibilityRequest.objects.create(
        status="active",
        priority="normal",
        purpose=["validation"],
        provider=source.provider,
        patient=source.patient,
        encounter=source.encounter,
        insurer=source.insurer,
        insurance=source.insurance,
        supporting_info=[],
        item=[],
        is_automatic=True,
        created_by=source.created_by,
        updated_by=source.updated_by,
    )

    dispatch_coverage_eligibility_check(request)

    return request
