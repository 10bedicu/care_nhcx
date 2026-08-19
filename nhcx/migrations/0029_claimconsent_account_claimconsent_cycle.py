# Generated for ClaimConsent account + cycle tracking

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emr', '0077_tagconfig_metadata'),
        ('nhcx', '0028_claimcondition_discharge_stages_lama_dama_procedure_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='claimconsent',
            name='account',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='claim_consents', to='emr.account'),
        ),
        migrations.AddField(
            model_name='claimconsent',
            name='cycle',
            field=models.PositiveIntegerField(blank=True, null=True),
        ),
    ]
