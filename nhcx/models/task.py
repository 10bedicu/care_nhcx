from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from care.emr.models.base import EMRBaseModel


class TaskUseCaseChoices(models.TextChoices):
    COMMUNICATION_REQUEST = "communication_request", "Communication Request"
    COMMUNICATION_RESPONSE = "communication_response", "Communication Response"
    PAYMENT_NOTICE_REQUEST = "payment_notice_request", "Payment Notice Request"
    PAYMENT_NOTICE_RESPONSE = "payment_notice_response", "Payment Notice Response"
    REPROCESS_REQUEST = "reprocess_request", "Reprocess Request"
    REPROCESS_RESPONSE = "reprocess_response", "Reprocess Response"
    SEARCH_REQUEST = "search_request", "Search Request"
    SEARCH_RESPONSE = "search_response", "Search Response"
    INSURANCE_PLAN_REQUEST = "insurance_plan_request", "Insurance Plan Request"


class Task(EMRBaseModel):
    identifier = models.CharField(max_length=100, null=True, blank=True)
    status = models.CharField(max_length=100, null=False, blank=False)
    intent = models.CharField(max_length=100, null=False, blank=False)
    priority = models.CharField(max_length=100, null=True, blank=True)
    code = models.JSONField(null=True, blank=True)
    authored_on = models.DateTimeField(null=True, blank=True)
    description = models.TextField(null=True, blank=True)
    reason_code = models.JSONField(null=True, blank=True)
    input = models.JSONField(default=list, null=True, blank=True)
    output = models.JSONField(default=list, null=True, blank=True)
    part_of = models.ForeignKey(
        "nhcx.Task", on_delete=models.CASCADE, null=True, blank=True
    )
    claim = models.ForeignKey(
        "nhcx.Claim", on_delete=models.CASCADE, null=True, blank=True
    )
    use_case = models.CharField(
        max_length=32, choices=TaskUseCaseChoices.choices, null=False, blank=False
    )
    focus_type = models.ForeignKey(
        ContentType, on_delete=models.CASCADE, null=True, blank=True
    )
    focus_id = models.PositiveIntegerField(null=True, blank=True)
    focus = GenericForeignKey("focus_type", "focus_id")
