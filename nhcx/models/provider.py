from django.db import models

from care.utils.models.base import BaseModel


class Provider(BaseModel):
    participant_code = models.CharField(
        max_length=50, unique=True, null=True, blank=True
    )
    encryption_private_key = models.TextField(null=True, blank=True)
    facility = models.OneToOneField(
        "facility.Facility", on_delete=models.PROTECT, to_field="external_id"
    )

    def __str__(self):
        return f"{self.participant_code} {self.facility}"
