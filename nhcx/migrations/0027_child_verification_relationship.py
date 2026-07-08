import uuid

from django.db import migrations

CHILD_VERIFICATION_SLUG = "care_nhcx__child_verification"

RELATIONSHIP_LINK_ID = "1.0"
RELATIONSHIP_OPTIONS = [
    "Son",
    "Daughter",
    "Other",
]


def add_relationship_question(apps, schema_editor):
    Questionnaire = apps.get_model("emr", "Questionnaire")
    questionnaire = Questionnaire.objects.filter(slug=CHILD_VERIFICATION_SLUG).first()
    if not questionnaire:
        return

    questions = questionnaire.questions or []
    if any(q.get("link_id") == RELATIONSHIP_LINK_ID for q in questions):
        return

    relationship_question = {
        "link_id": RELATIONSHIP_LINK_ID,
        "id": str(uuid.uuid4()),
        "text": "Relationship to Beneficiary",
        "type": "choice",
        "required": True,
        "answer_option": [{"value": option} for option in RELATIONSHIP_OPTIONS],
    }
    questionnaire.questions = [relationship_question, *questions]
    questionnaire.save(update_fields=["questions"])


def remove_relationship_question(apps, schema_editor):
    Questionnaire = apps.get_model("emr", "Questionnaire")
    questionnaire = Questionnaire.objects.filter(slug=CHILD_VERIFICATION_SLUG).first()
    if not questionnaire:
        return

    questionnaire.questions = [
        q
        for q in (questionnaire.questions or [])
        if q.get("link_id") != RELATIONSHIP_LINK_ID
    ]
    questionnaire.save(update_fields=["questions"])


class Migration(migrations.Migration):
    dependencies = [
        ("nhcx", "0026_coverageeligibilityrequest_is_automatic"),
        ("emr", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            add_relationship_question,
            remove_relationship_question,
        ),
    ]
