from django.db import models

from care.emr.models.base import EMRBaseModel


class CommunicationRequest(EMRBaseModel):
    identifier = models.CharField(max_length=100, null=False, blank=False)
    status = models.CharField(max_length=100, null=False, blank=False)
    priority = models.CharField(max_length=100, null=True, blank=True)
    category = models.JSONField(default=list, null=True, blank=True)
    authored_on = models.DateTimeField(null=True, blank=True)
    payload = models.JSONField(default=list, null=True, blank=True)
    replaces = models.ForeignKey(
        "nhcx.CommunicationRequest", on_delete=models.CASCADE, null=True, blank=True
    )
    based_on = models.ForeignKey(
        "nhcx.Task", on_delete=models.CASCADE, null=False, blank=False
    )
    about = models.ForeignKey(
        "nhcx.Claim", on_delete=models.CASCADE, null=False, blank=False
    )


class Communication(EMRBaseModel):
    status = models.CharField(max_length=100, null=False, blank=False)
    priority = models.CharField(max_length=100, null=True, blank=True)
    category = models.JSONField(default=list, null=True, blank=True)
    sent = models.DateTimeField(null=True, blank=True)
    payload = models.JSONField(default=list, null=True, blank=True)
    based_on = models.ForeignKey(
        "nhcx.CommunicationRequest", on_delete=models.CASCADE, null=False, blank=False
    )
    part_of = models.ForeignKey(
        "nhcx.Task", on_delete=models.CASCADE, null=True, blank=True
    )
    about = models.ForeignKey(
        "nhcx.Claim", on_delete=models.CASCADE, null=False, blank=False
    )
