# Generated by Django 2.2 on 2021-09-15 21:37

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0086_auto_20210913_0818'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuildstack',
            name='sim_scores',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.DecimalField(decimal_places=2, max_digits=5), blank=True, null=True, size=None),
        ),
    ]
