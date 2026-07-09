from datetime import timedelta

from django.utils import timezone

from nhcx.models.claim_consent import ClaimConsent
from nhcx.services.abha_biometric import AbhaBiometricService
from nhcx.utils.exceptions import NHCXAPIException

TOKEN_EXPIRY_BUFFER_SECONDS = 60


def _is_expired(issued_at, lifetime_seconds: int, buffer_seconds: int = 0) -> bool:
    expiry = issued_at + timedelta(seconds=lifetime_seconds)
    return timezone.now() >= expiry - timedelta(seconds=buffer_seconds)


def is_biometric_token_expired(
    claim_consent: ClaimConsent,
    buffer_seconds: int = TOKEN_EXPIRY_BUFFER_SECONDS,
) -> bool:
    return _is_expired(
        claim_consent.modified_date, claim_consent.expires_in, buffer_seconds
    )


def is_refresh_token_expired(claim_consent: ClaimConsent) -> bool:
    return _is_expired(claim_consent.modified_date, claim_consent.refresh_expires_in)


def ensure_valid_biometric_token(
    claim_consent: ClaimConsent | None,
    *,
    force: bool = False,
) -> ClaimConsent | None:
    if claim_consent is None:
        return None

    if not force and not is_biometric_token_expired(claim_consent):
        return claim_consent

    if is_refresh_token_expired(claim_consent):
        raise NHCXAPIException(
            detail=(
                "Biometric consent has expired. Please re-authenticate the beneficiary before submitting."
            )
        )

    return AbhaBiometricService.auth__refresh_member_token(claim_consent)
