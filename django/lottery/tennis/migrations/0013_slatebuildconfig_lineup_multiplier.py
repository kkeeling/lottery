# Generated by Django 2.2 on 2022-01-11 12:30

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('tennis', '0012_slatebuildconfig_optimize_by'),
    ]

    operations = [
        migrations.AddField(
            model_name='slatebuildconfig',
            name='lineup_multiplier',
            field=models.IntegerField(default=1),
        ),
    ]
