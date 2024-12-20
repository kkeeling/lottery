# Generated by Django 2.2 on 2022-03-03 15:40

import django.contrib.postgres.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nascar', '0051_auto_20220303_1410'),
    ]

    operations = [
        migrations.AlterField(
            model_name='buildplayerprojection',
            name='ceiling',
            field=models.FloatField(db_index=True, default=0.0, verbose_name='Ceil'),
        ),
        migrations.AlterField(
            model_name='buildplayerprojection',
            name='max_exposure',
            field=models.FloatField(default=1.0, verbose_name='max'),
        ),
        migrations.AlterField(
            model_name='buildplayerprojection',
            name='min_exposure',
            field=models.FloatField(default=0.0, verbose_name='min'),
        ),
        migrations.AlterField(
            model_name='buildplayerprojection',
            name='projection',
            field=models.FloatField(db_index=True, default=0.0, verbose_name='Proj'),
        ),
        migrations.AlterField(
            model_name='buildplayerprojection',
            name='s75',
            field=models.FloatField(db_index=True, default=0.0, verbose_name='s75'),
        ),
        migrations.AlterField(
            model_name='buildplayerprojection',
            name='sim_scores',
            field=django.contrib.postgres.fields.ArrayField(base_field=models.FloatField(), blank=True, null=True, size=None),
        ),
    ]
