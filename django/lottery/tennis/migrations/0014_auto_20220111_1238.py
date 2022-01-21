# Generated by Django 2.2 on 2022-01-11 12:38

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0013_slatebuildconfig_lineup_multiplier'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuildlineup',
            name='actual',
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True),
        ),
        migrations.AddField(
            model_name='slatebuildlineup',
            name='median',
            field=models.DecimalField(db_index=True, decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AddField(
            model_name='slatebuildlineup',
            name='roi',
            field=models.DecimalField(db_index=True, decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AddField(
            model_name='slatebuildlineup',
            name='s75',
            field=models.DecimalField(db_index=True, decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AddField(
            model_name='slatebuildlineup',
            name='s90',
            field=models.DecimalField(db_index=True, decimal_places=2, default=0.0, max_digits=10),
        ),
        migrations.AddField(
            model_name='slatebuildlineup',
            name='sim_scores',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.DecimalField(decimal_places=2, max_digits=5), blank=True, null=True, size=None),
        ),
    ]
