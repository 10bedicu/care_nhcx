# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nhcx", "0018_dispatch_tracking"),
    ]

    operations = [
        migrations.AddField(
            model_name="claim",
            name="dispatch_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("awaiting", "Awaiting"),
                    ("partial", "Partial"),
                    ("complete", "Complete"),
                    ("error", "Error"),
                ],
                db_index=True,
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="coverageeligibilityrequest",
            name="dispatch_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("awaiting", "Awaiting"),
                    ("partial", "Partial"),
                    ("complete", "Complete"),
                    ("error", "Error"),
                ],
                db_index=True,
                default="pending",
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="task",
            name="dispatch_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("awaiting", "Awaiting"),
                    ("partial", "Partial"),
                    ("complete", "Complete"),
                    ("error", "Error"),
                ],
                db_index=True,
                default="pending",
                max_length=16,
            ),
        ),
    ]
