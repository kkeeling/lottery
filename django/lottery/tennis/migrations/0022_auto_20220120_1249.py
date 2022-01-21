# Generated by Django 2.2 on 2022-01-20 12:49

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0021_slateplayerprojection_s75'),
    ]

    operations = [
        migrations.AddField(
            model_name='slate',
            name='target_scores',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.DecimalField(decimal_places=2, max_digits=5), blank=True, null=True, size=None),
        ),
        migrations.AddField(
            model_name='slate',
            name='top_scores',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.DecimalField(decimal_places=2, max_digits=5), blank=True, null=True, size=None),
        ),
    ]
