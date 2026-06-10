from datetime import date, datetime

from django.db.models.fields.json import KeyTextTransform
from django.db.models.signals import pre_save
from django.dispatch import receiver
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from care.emr.extensions.base import ExtensionResource, PlugExtension
from care.emr.models.patient import Patient
from care.emr.registries.extensions.registry import ExtensionRegistry

EXTENSION_NAME = "care_nhcx__pmjay_member"

# Children of this age and below use a parent's member id instead of their own.
PARENT_AGE_THRESHOLD = 6

PMJAY_MEMBER_ID_PROPERTY = {
    "type": "string",
    "title": "PMJAY Member ID",
    "description": "PMJAY member ID of the patient (ages 6 and above).",
}
PARENT_PMJAY_MEMBER_ID_PROPERTY = {
    "type": "string",
    "title": "Parent's PMJAY Member ID",
    "description": "Parent's PMJAY member ID, for children below 6 years.",
}


class PMJAYMemberExtension(PlugExtension):
    extension_name = EXTENSION_NAME
    extension_version = "1.0.0"
    resource_type = ExtensionResource.patient
    write_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "PMJAY Member Details",
        "type": "object",
        "properties": {
            "member_id": PMJAY_MEMBER_ID_PROPERTY,
            "parent_member_id": PARENT_PMJAY_MEMBER_ID_PROPERTY,
        },
        "additionalProperties": False,
    }
    retrieve_schema = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "PMJAY Member Details",
        "type": "object",
        "x-ui": {"control": "grid"},
        "properties": {
            "member_id": PMJAY_MEMBER_ID_PROPERTY,
            "parent_member_id": PARENT_PMJAY_MEMBER_ID_PROPERTY,
        },
        "additionalProperties": False,
    }


ExtensionRegistry.register(PMJAYMemberExtension())


def _resolve_age(instance):
    dob = instance.date_of_birth
    if isinstance(dob, str):
        try:
            dob = date.fromisoformat(dob)
        except ValueError:
            dob = None
    if isinstance(dob, datetime):
        dob = dob.date()
    if isinstance(dob, date):
        today = timezone.now().date()
        return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))

    yob = instance.year_of_birth
    if isinstance(yob, str):
        try:
            yob = int(yob)
        except ValueError:
            yob = None
    if yob:
        return timezone.now().year - yob

    return None


@receiver(pre_save, sender=Patient)
def validate_member(sender, instance, **kwargs):
    data = (instance.extensions or {}).get(EXTENSION_NAME)
    if not data:
        return

    member_id = data.get("member_id")
    parent_member_id = data.get("parent_member_id")

    age = _resolve_age(instance)

    if parent_member_id and age is None:
        raise ValidationError(
            "Date of birth is required when Parent's PMJAY Member ID is set"
        )

    if age is not None:
        if age > PARENT_AGE_THRESHOLD and parent_member_id:
            raise ValidationError(
                "Parent's PMJAY Member ID not allowed for ages 6 and above"
            )
        if age <= PARENT_AGE_THRESHOLD and member_id:
            raise ValidationError(
                "PMJAY Member ID not allowed for children below 6 years"
            )

    if member_id:
        # The extension name contains "__", which Django would treat as a JSON path separator, so access the key explicitly via KeyTextTransform.
        queryset = Patient.objects.annotate(
            _pmjay_member_id=KeyTextTransform(
                "member_id", KeyTextTransform(EXTENSION_NAME, "extensions")
            )
        ).filter(_pmjay_member_id=member_id)
        if instance.pk:
            queryset = queryset.exclude(pk=instance.pk)
        if queryset.exists():
            raise ValidationError("PMJAY Member ID is already in use")
