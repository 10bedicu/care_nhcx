from django.db import models

from care.emr.models.base import EMRBaseModel


class PaymentNotice(EMRBaseModel):
    identifier = models.CharField(max_length=100, null=False, blank=False)
    status = models.CharField(max_length=100, null=False, blank=False)
    period = models.JSONField(default=dict, null=True, blank=True)
    outcome = models.CharField(max_length=100, null=True, blank=True)
    disposition = models.TextField(null=True, blank=True)
    payment_date = models.DateTimeField(null=False, blank=False)
    payment_amount = models.JSONField(default=dict, null=False, blank=False)
    payment_identifier = models.JSONField(null=True, blank=True)
    detail = models.JSONField(default=list, null=True, blank=True)
    process_note = models.JSONField(default=list, null=True, blank=True)
    request = models.ForeignKey(
        "nhcx.Task", on_delete=models.CASCADE, null=False, blank=False
    )
    claim = models.ForeignKey(
        "nhcx.Claim", on_delete=models.CASCADE, null=False, blank=False
    )
    payment_reconciliation = models.ForeignKey(
        "emr.PaymentReconciliation",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        default=None,
    )
