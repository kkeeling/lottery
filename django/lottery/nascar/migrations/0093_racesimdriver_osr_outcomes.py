# Generated by Django 2.2 on 2022-07-14 12:56

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0092_delete_contestbacktestentryresult'),
    ]

    operations = [
        migrations.AddField(
            model_name='racesimdriver',
            name='osr_outcomes',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.IntegerField(default=0), blank=True, null=True, size=None),
        ),
    ]