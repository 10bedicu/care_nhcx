"""
Drops the legacy single-table ``InsurancePlan`` so the next
``makemigrations`` run can emit a clean ``CreateModel`` series for the new
relational tree (InsurancePlan + Coverage/Plan/SpecificCost/... + the
polymorphic Claim-* extensions + Questionnaire).

Without this intermediate delete, Django's auto-detector tries to convert
the old columns (``identifier``, ``product_identifier``, ``period``,
``coverage``, ``plan``, ``extension``) into the new ones via rename + add,
which forces destructive prompts for NOT NULL defaults.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("nhcx", "0010_alter_task_use_case"),
    ]

    operations = [
        migrations.DeleteModel(name="InsurancePlan"),
    ]
