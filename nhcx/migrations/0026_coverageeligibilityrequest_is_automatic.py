from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("nhcx", "0025_claim_account_claimconsent_claim"),
    ]

    operations = [
        migrations.AddField(
            model_name="coverageeligibilityrequest",
            name="is_automatic",
            field=models.BooleanField(db_index=True, default=False),
        ),
    ]
