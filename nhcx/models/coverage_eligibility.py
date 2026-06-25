from django.db import models

from care.emr.models.base import EMRBaseModel
from nhcx.models import DispatchStatusChoices


class CoverageEligibilityRequest(EMRBaseModel):
    status = models.CharField(max_length=100, null=False, blank=False)
    priority = models.CharField(max_length=100, null=False, blank=False)
    purpose = models.JSONField(default=list, null=False, blank=False)
    provider = models.ForeignKey(
        "nhcx.Provider", on_delete=models.CASCADE, null=False, blank=False
    )
    patient = models.ForeignKey(
        "emr.Patient", on_delete=models.CASCADE, null=False, blank=False
    )
    encounter = models.ForeignKey(
        "emr.Encounter", on_delete=models.CASCADE, null=True, blank=True
    )
    appointment = models.ForeignKey(
        "emr.TokenBooking", on_delete=models.SET_NULL, null=True, blank=True
    )
    insurer = models.JSONField(default=dict, null=False, blank=False)
    supporting_info = models.JSONField(default=list, null=True, blank=True)
    insurance = models.JSONField(default=list, null=False, blank=False)
    item = models.JSONField(default=list, null=True, blank=True)
    workflow_code = models.CharField(max_length=8, null=True, blank=True, db_index=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)
    dispatch_error = models.TextField(blank=True, default="")
    dispatch_status = models.CharField(
        max_length=16,
        choices=DispatchStatusChoices.choices,
        default=DispatchStatusChoices.PENDING,
        db_index=True,
    )


class CoverageEligibilityResponse(EMRBaseModel):
    request = models.ForeignKey(
        "nhcx.CoverageEligibilityRequest", on_delete=models.CASCADE
    )
    outcome = models.CharField(max_length=100, null=False, blank=False)
    disposition = models.TextField(null=True, blank=True)
    insurance = models.JSONField(null=True, blank=True)
    error = models.JSONField(null=True, blank=True)
    workflow_code = models.CharField(max_length=8, null=True, blank=True, db_index=True)
