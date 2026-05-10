from django.db import models

from care.emr.models.base import EMRBaseModel


class MemberBiometricAuth(EMRBaseModel):
    payer_id = models.CharField(max_length=100, null=False, blank=False)
    encounter = models.OneToOneField(
        "emr.Encounter",
        on_delete=models.CASCADE,
        related_name="member_biometric_auth",
    )
    patient = models.ForeignKey(
        "emr.Patient",
        on_delete=models.CASCADE,
        related_name="member_biometric_auths",
    )
    token = models.TextField()
    expires_in = models.PositiveIntegerField()
    refresh_token = models.TextField()
    refresh_expires_in = models.PositiveIntegerField()
    accounts = models.JSONField(default=list)
