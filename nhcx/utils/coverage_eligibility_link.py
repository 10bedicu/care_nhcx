from datetime import timedelta

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from nhcx.constants import VALIDATION_REUSE_WINDOW_HOURS


def validate_link_encounter(coverage_eligibility_request, encounter) -> None:
    if "validation" not in coverage_eligibility_request.purpose:
        raise ValidationError(
            "Only coverage eligibility requests with validation purpose can be linked"
        )

    if coverage_eligibility_request.encounter_id:
        if coverage_eligibility_request.encounter_id == encounter.id:
            return
        raise ValidationError(
            "This coverage eligibility request is already linked to a different encounter"
        )

    if coverage_eligibility_request.patient_id != encounter.patient_id:
        raise ValidationError(
            "The coverage eligibility request patient does not match the encounter patient"
        )

    # Provider.facility FK uses to_field="external_id", so provider.facility_id
    # stores the facility UUID — not the internal PK on encounter.facility_id.
    if coverage_eligibility_request.provider.facility_id != encounter.facility.external_id:
        raise ValidationError(
            "The coverage eligibility request facility does not match the encounter facility"
        )

    cutoff = timezone.now() - timedelta(hours=VALIDATION_REUSE_WINDOW_HOURS)
    if coverage_eligibility_request.created_date < cutoff:
        raise ValidationError(
            f"Coverage eligibility validation is older than {VALIDATION_REUSE_WINDOW_HOURS} hours "
            "and can no longer be linked to an encounter"
        )


def link_encounter_to_request(coverage_eligibility_request, encounter) -> None:
    validate_link_encounter(coverage_eligibility_request, encounter)
    if coverage_eligibility_request.encounter_id:
        return
    coverage_eligibility_request.encounter = encounter
    coverage_eligibility_request.save(update_fields=["encounter", "modified_date"])
