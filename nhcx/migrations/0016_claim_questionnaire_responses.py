# Generated migration

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nhcx', '0015_insuranceplanquestionnaire_uniq_ip_questionnaire_fhir_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='claim',
            name='questionnaire_responses',
            field=models.JSONField(blank=True, default=list, null=True),
        ),
    ]
