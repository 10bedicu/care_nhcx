# Generated for ClaimConsent rename + stage field

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emr', '0073_product_purchase_price_and_more'),
        ('nhcx', '0019_dispatch_status'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='MemberBiometricAuth',
            new_name='ClaimConsent',
        ),
        migrations.AlterField(
            model_name='claimconsent',
            name='encounter',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='claim_consents',
                to='emr.encounter',
            ),
        ),
        migrations.AlterField(
            model_name='claimconsent',
            name='patient',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.CASCADE,
                related_name='claim_consents',
                to='emr.patient',
            ),
        ),
        migrations.AddField(
            model_name='claimconsent',
            name='stage',
            field=models.CharField(
                choices=[
                    ('preauthorization', 'Pre-Authorization'),
                    ('claim', 'Claim'),
                ],
                default='preauthorization',
                max_length=20,
            ),
        ),
        migrations.AddConstraint(
            model_name='claimconsent',
            constraint=models.UniqueConstraint(
                fields=('encounter', 'payer_id', 'stage'),
                name='uniq_claim_consent_encounter_payer_stage',
            ),
        ),
    ]
