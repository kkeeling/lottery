# Generated by Django 2.2 on 2021-06-11 09:22

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0008_auto_20210610_2308'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='PositionThresholdCondition',
            new_name='PositionThreshold',
        ),
    ]
