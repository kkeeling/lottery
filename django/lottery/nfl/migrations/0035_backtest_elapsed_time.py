# Generated by Django 2.2 on 2021-07-19 12:21

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('nfl', '0034_auto_20210716_1145'),
    ]

    operations = [
        migrations.AddField(
            model_name='backtest',
            name='elapsed_time',
            field=models.DurationField(default=datetime.timedelta(0)),
        ),
    ]
