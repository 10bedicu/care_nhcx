import enum

from care.security.permissions.base import PermissionController
from care.security.permissions.constants import Permission, PermissionContext
from care.security.roles.role import (
    ADMINISTRATOR,
    ADMIN_ROLE,
    FACILITY_ADMIN_ROLE,
)


class ClaimConsentPermissions(enum.Enum):
    can_skip_claim_consent = Permission(
        "Can Skip Claim Consent",
        "Allows skipping the biometric claim-consent verification before submitting a pre-authorization or claim.",
        PermissionContext.FACILITY,
        [ADMIN_ROLE, FACILITY_ADMIN_ROLE, ADMINISTRATOR],
    )


PermissionController.override_permission_handlers.append(ClaimConsentPermissions)
