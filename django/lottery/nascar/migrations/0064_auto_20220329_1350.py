# Generated by Django 2.2 on 2022-03-29 13:50

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0063_racesimlineup'),
    ]

    operations = [
        migrations.AddField(
            model_name='racesimdriver',
            name='dk_scores',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(), blank=True, null=True, size=None),
        ),
        migrations.AddField(
            model_name='racesimdriver',
            name='fd_scores',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(), blank=True, null=True, size=None),
        ),
    ]
