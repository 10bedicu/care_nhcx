from django.db import models

from care.emr.models.base import EMRBaseModel


class Claim(EMRBaseModel):
    use = models.CharField(max_length=100, null=False, blank=False)
    status = models.CharField(max_length=100, null=False, blank=False)
    priority = models.CharField(max_length=100, null=False, blank=False)
    type = models.JSONField(null=False, blank=False)
    provider = models.ForeignKey(
        "nhcx.Provider", on_delete=models.CASCADE, null=False, blank=False
    )
    patient = models.ForeignKey(
        "emr.Patient", on_delete=models.CASCADE, null=False, blank=False
    )
    encounter = models.ForeignKey(
        "emr.Encounter", on_delete=models.CASCADE, null=True, blank=True
    )
    insurer = models.JSONField(default=dict, null=False, blank=False)
    billable_period = models.JSONField(null=True, blank=True)
    related = models.JSONField(default=list, null=True, blank=True)
    care_team = models.JSONField(default=list, null=True, blank=True)
    supporting_info = models.JSONField(default=list, null=True, blank=True)
    procedure = models.JSONField(default=list, null=True, blank=True)
    diagnosis = models.JSONField(default=list, null=False, blank=False)
    insurance = models.JSONField(default=list, null=False, blank=False)
    item = models.JSONField(default=list, null=False, blank=False)
    accident = models.JSONField(null=True, blank=True)
    payee = models.JSONField(null=True, blank=True)
    questionnaire_responses = models.JSONField(default=list, null=True, blank=True)


class ClaimResponse(EMRBaseModel):
    request = models.ForeignKey("nhcx.Claim", on_delete=models.CASCADE)
    outcome = models.CharField(max_length=100, null=False, blank=False)
    disposition = models.TextField(null=True, blank=True)
    item = models.JSONField(null=True, blank=True)
    add_item = models.JSONField(null=True, blank=True)
    total = models.JSONField(null=True, blank=True)
    error = models.JSONField(null=True, blank=True)
