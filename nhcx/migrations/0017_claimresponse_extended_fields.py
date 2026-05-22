# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("nhcx", "0016_claim_questionnaire_responses"),
    ]

    operations = [
        migrations.AddField(
            model_name="claimresponse",
            name="use",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="claimresponse",
            name="status",
            field=models.CharField(blank=True, max_length=100, null=True),
        ),
        migrations.AddField(
            model_name="claimresponse",
            name="pre_auth_ref",
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
        migrations.AddField(
            model_name="claimresponse",
            name="adjudication",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="claimresponse",
            name="identifier",
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="claimresponse",
            name="type",
            field=models.JSONField(blank=True, null=True),
        ),
    ]
