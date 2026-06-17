import django.db.models.deletion
import uuid
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('emr', '0030_encounter_tags_medicationrequest_dispense_status_and_more'),
        ('nhcx', '0021_seed_pmjay_questionnaires'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.DeleteModel(
            name='PaymentReconciliation',
        ),
        migrations.CreateModel(
            name='PaymentNotice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('external_id', models.UUIDField(db_index=True, default=uuid.uuid4, unique=True)),
                ('created_date', models.DateTimeField(auto_now_add=True, db_index=True, null=True)),
                ('modified_date', models.DateTimeField(auto_now=True, db_index=True, null=True)),
                ('deleted', models.BooleanField(db_index=True, default=False)),
                ('history', models.JSONField(default=dict)),
                ('meta', models.JSONField(default=dict)),
                ('identifier', models.CharField(max_length=100)),
                ('status', models.CharField(max_length=100)),
                ('period', models.JSONField(blank=True, default=dict, null=True)),
                ('outcome', models.CharField(blank=True, max_length=100, null=True)),
                ('disposition', models.TextField(blank=True, null=True)),
                ('payment_date', models.DateTimeField()),
                ('payment_amount', models.JSONField(default=dict)),
                ('payment_identifier', models.JSONField(blank=True, null=True)),
                ('detail', models.JSONField(blank=True, default=list, null=True)),
                ('process_note', models.JSONField(blank=True, default=list, null=True)),
                ('claim', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='nhcx.claim')),
                ('request', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='nhcx.task')),
                ('payment_reconciliation', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, to='emr.paymentreconciliation')),
                ('created_by', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_created_by', to=settings.AUTH_USER_MODEL)),
                ('updated_by', models.ForeignKey(blank=True, default=None, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='%(app_label)s_%(class)s_updated_by', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'abstract': False,
            },
        ),
    ]
