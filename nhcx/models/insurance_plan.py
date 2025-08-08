from django.db import models

from care.emr.models.base import EMRBaseModel


class InsurancePlan(EMRBaseModel):
    identifier = models.CharField(max_length=100, null=False, blank=False)
    text = models.TextField(null=True, blank=True)
    extension = models.JSONField(default=list, null=True, blank=True)
    product_identifier = models.JSONField(default=dict, null=False, blank=False)
    status = models.CharField(max_length=100, null=False, blank=False)
    type = models.JSONField(default=dict, null=False, blank=False)
    name = models.CharField(max_length=100, null=False, blank=False)
    alias = models.JSONField(default=list, null=True, blank=True)
    period = models.JSONField(default=dict, null=False, blank=False)
    contact = models.JSONField(default=list, null=True, blank=True)
    coverage = models.JSONField(default=list, null=False, blank=False)
    plan = models.JSONField(default=list, null=True, blank=True)
    request = models.ForeignKey(
        "nhcx.Task", on_delete=models.CASCADE, null=False, blank=False
    )  # Task responsible for fetching the insurance plan
