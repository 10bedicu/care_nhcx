# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("nhcx", "0017_claimresponse_extended_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="claim",
            name="dispatched_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="claim",
            name="dispatch_error",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="coverageeligibilityrequest",
            name="dispatched_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="coverageeligibilityrequest",
            name="dispatch_error",
            field=models.TextField(blank=True, default=""),
        ),
        migrations.AddField(
            model_name="task",
            name="dispatched_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="task",
            name="dispatch_error",
            field=models.TextField(blank=True, default=""),
        ),
    ]
