from django.db import models

from care.emr.models.base import EMRBaseModel


class ClaimConsentStage(models.TextChoices):
    PREAUTHORIZATION = "preauthorization", "Pre-Authorization"
    CLAIM = "claim", "Claim"


class ClaimConsent(EMRBaseModel):
    stage = models.CharField(
        max_length=20,
        choices=ClaimConsentStage.choices,
        default=ClaimConsentStage.PREAUTHORIZATION,
    )
    payer_id = models.CharField(max_length=100, null=False, blank=False)
    claim = models.ForeignKey(
        "nhcx.Claim",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claim_consents",
    )
    encounter = models.ForeignKey(
        "emr.Encounter",
        on_delete=models.CASCADE,
        related_name="claim_consents",
    )
    patient = models.ForeignKey(
        "emr.Patient",
        on_delete=models.CASCADE,
        related_name="claim_consents",
    )
    account = models.ForeignKey(
        "emr.Account",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="claim_consents",
    )
    cycle = models.PositiveIntegerField(null=True, blank=True)
    token = models.TextField()
    expires_in = models.PositiveIntegerField()
    refresh_token = models.TextField()
    refresh_expires_in = models.PositiveIntegerField()
    accounts = models.JSONField(default=list)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["encounter", "payer_id", "stage"],
                name="uniq_claim_consent_encounter_payer_stage",
            ),
        ]
