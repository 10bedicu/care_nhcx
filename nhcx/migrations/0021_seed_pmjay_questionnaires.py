import uuid

from django.db import migrations

# Slugs are namespaced with the plug name to avoid collisions with core/other
# plugs, mirroring the convention used for the plug's extensions.
ATTENDANT_DETAILS_SLUG = "care_nhcx__attendant_details"
CHILD_VERIFICATION_SLUG = "care_nhcx__child_verification"

# Instance-level role organizations the questionnaires are made visible to.
ROLE_NAMES = [
    "Volunteer",
    "Doctor",
    "Staff",
    "Nurse",
    "Administrator",
    "Facility Admin",
]
ROLE_ORG_TYPE = "role"

ATTENDANT_RELATIONSHIP_OPTIONS = [
    "Father",
    "Mother",
    "Son",
    "Daughter",
    "Spouse",
    "Sibling",
    "Guardian",
    "Other",
]

QUESTIONNAIRE_VERSION = "1.0"
QUESTIONNAIRE_STATUS = "active"


def _attendant_details_questions():
    return [
        {
            "link_id": "1.1",
            "id": str(uuid.uuid4()),
            "text": "Attendant Name",
            "type": "string",
            "required": True,
        },
        {
            "link_id": "1.2",
            "id": str(uuid.uuid4()),
            "text": "Relationship",
            "type": "choice",
            "required": True,
            "answer_option": [
                {"value": option} for option in ATTENDANT_RELATIONSHIP_OPTIONS
            ],
        },
        {
            "link_id": "1.3",
            "id": str(uuid.uuid4()),
            "text": "Phone Number",
            "type": "string",
            "required": True,
        },
    ]


def _child_verification_questions():
    return [
        {
            "link_id": "1.1",
            "id": str(uuid.uuid4()),
            "text": "Birth Certificate",
            "type": "structured",
            "structured_type": "files",
            "required": True,
        },
    ]


def _sync_organization_cache(questionnaire, role_orgs):
    cache = []
    for org in role_orgs:
        cache.extend(org.parent_cache)
        cache.append(org.id)
    questionnaire.organization_cache = sorted(set(cache))
    questionnaire.save(update_fields=["organization_cache"])


def _create_questionnaire(
    apps, slug, title, description, subject_type, questions, role_orgs
):
    Questionnaire = apps.get_model("emr", "Questionnaire")
    QuestionnaireOrganization = apps.get_model("emr", "QuestionnaireOrganization")

    if Questionnaire.objects.filter(slug=slug).exists():
        return

    questionnaire = Questionnaire.objects.create(
        version=QUESTIONNAIRE_VERSION,
        slug=slug,
        title=title,
        description=description,
        subject_type=subject_type,
        status=QUESTIONNAIRE_STATUS,
        questions=questions,
    )

    for org in role_orgs:
        QuestionnaireOrganization.objects.create(
            questionnaire=questionnaire,
            organization=org,
        )

    _sync_organization_cache(questionnaire, role_orgs)


def seed_questionnaires(apps, schema_editor):
    Organization = apps.get_model("emr", "Organization")
    role_orgs = list(
        Organization.objects.filter(name__in=ROLE_NAMES, org_type=ROLE_ORG_TYPE)
    )

    _create_questionnaire(
        apps,
        slug=ATTENDANT_DETAILS_SLUG,
        title="Attendant Details",
        description="Details of the patient's attendant.",
        subject_type="encounter",
        questions=_attendant_details_questions(),
        role_orgs=role_orgs,
    )
    _create_questionnaire(
        apps,
        slug=CHILD_VERIFICATION_SLUG,
        title="Child Verification",
        description="Verification documents for a child patient.",
        subject_type="patient",
        questions=_child_verification_questions(),
        role_orgs=role_orgs,
    )


def remove_questionnaires(apps, schema_editor):
    Questionnaire = apps.get_model("emr", "Questionnaire")
    Questionnaire.objects.filter(
        slug__in=[ATTENDANT_DETAILS_SLUG, CHILD_VERIFICATION_SLUG]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("nhcx", "0020_claimconsent"),
        ("emr", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(seed_questionnaires, remove_questionnaires),
    ]
